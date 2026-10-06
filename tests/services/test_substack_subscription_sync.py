"""Substack subscription sync into database source overrides (ri-19).

Each test builds a YAML baseline and a set of override rows, runs the sync
against a fake listing, and checks both the plan and what reached
``source_overrides``. No network, no Postgres.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.sources import SourcesConfig, source_key
from src.ingestion.credential_failures import (
    CredentialsMissingError,
    SessionExpiredError,
)
from src.ingestion.substack import SubscriptionListingError, SubstackSubscription
from src.models.base import Base
from src.models.source_override import SourceOverride
from src.services.source_override_service import SourceOverrideService
from src.services.substack_subscription_sync import (
    MANAGED_BY,
    SubstackSubscriptionSync,
    SubstackSyncRefusedError,
    publication_locator,
    target_url,
)


@pytest.fixture
def db() -> Session:
    """A fresh in-memory database per test.

    The sync commits and rolls back its own transaction, which a shared
    connection with an outer rollback cannot contain on pysqlite.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[SourceOverride.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


PAID = SubstackSubscription(name="Paid Pub", url="https://paid.substack.com/", is_paid=True)
FREE = SubstackSubscription(name="Free Pub", url="https://free.substack.com", is_paid=False)


class FakeClient:
    """Stands in for SubstackClient: returns a listing or raises."""

    def __init__(self, listing: list[SubstackSubscription] | Exception) -> None:
        self.listing = listing
        self.strict_calls: list[bool] = []
        self.closed = False

    def fetch_subscriptions(self, *, strict: bool = False) -> list[SubstackSubscription]:
        self.strict_calls.append(strict)
        if isinstance(self.listing, Exception):
            raise self.listing
        return list(self.listing)

    def close(self) -> None:
        self.closed = True


def _sync(
    db: Session,
    listing: list[SubstackSubscription] | Exception,
    yaml_sources: list[dict[str, Any]] | None = None,
) -> tuple[SubstackSubscriptionSync, FakeClient]:
    client = FakeClient(listing)
    sync = SubstackSubscriptionSync(
        db,
        client_factory=lambda: client,  # type: ignore[arg-type,return-value]
        yaml_loader=lambda: SourcesConfig(sources=yaml_sources or []),
    )
    return sync, client


def _rows(db: Session) -> dict[str, SourceOverride]:
    return {row.source_key: row for row in db.query(SourceOverride).all()}


def _actions(plan) -> list[tuple[str, str, str]]:
    return [(a.action, a.source_type, a.source_key) for a in plan.actions]


# -- matching ----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://x.substack.com",
        "https://x.substack.com/",
        "https://www.X.substack.com/feed",
        "https://x.substack.com/feed/",
    ],
)
def test_publication_locator_ignores_spelling(url: str) -> None:
    assert publication_locator(url) == "x.substack.com"


def test_target_url_by_type() -> None:
    assert target_url(PAID) == "https://paid.substack.com"
    assert target_url(FREE) == "https://free.substack.com/feed"


# -- dry run and apply ---------------------------------------------------------


def test_dry_run_lists_adds_and_writes_nothing(db: Session) -> None:
    sync, client = _sync(db, [PAID, FREE])

    plan = sync.run()

    assert client.strict_calls == [True] and client.closed
    assert _actions(plan) == [
        ("add", "rss", "rss:https://free.substack.com/feed"),
        ("add", "substack", "substack:https://paid.substack.com"),
    ]
    assert (plan.applied, plan.changes) == (False, 2)
    assert _rows(db) == {}


def test_apply_adds_managed_rows_once(db: Session) -> None:
    sync, _ = _sync(db, [PAID, FREE])

    first = sync.run(apply=True)

    rows = _rows(db)
    assert first.applied and set(rows) == {
        "rss:https://free.substack.com/feed",
        "substack:https://paid.substack.com",
    }
    assert {row.managed_by for row in rows.values()} == {MANAGED_BY}
    assert all(row.enabled for row in rows.values())
    assert rows["substack:https://paid.substack.com"].config["name"] == "Paid Pub"

    second = sync.run(apply=True)
    assert second.changes == 0
    assert [a.action for a in second.actions] == ["existing", "existing"]
    assert {key: row.version for key, row in _rows(db).items()} == dict.fromkeys(rows, 1)


# -- operator-configured sources are never modified ---------------------------


def test_yaml_source_with_other_spelling_counts_as_existing(db: Session) -> None:
    yaml = [{"type": "rss", "url": "https://www.free.substack.com/feed/", "name": "Free"}]
    sync, _ = _sync(db, [FREE], yaml)

    plan = sync.run(apply=True)

    assert _actions(plan) == [("existing", "rss", "rss:https://www.free.substack.com/feed/")]
    assert _rows(db) == {}


def test_disabled_source_stays_disabled(db: Session) -> None:
    yaml = [{"type": "substack", "url": "https://paid.substack.com", "enabled": False}]
    sync, _ = _sync(db, [PAID], yaml)

    plan = sync.run(apply=True)

    assert [a.action for a in plan.actions] == ["kept_disabled"]
    assert _rows(db) == {}


def test_disabled_database_override_is_not_re_enabled(db: Session) -> None:
    service = SourceOverrideService(db)
    service.upsert({"type": "substack", "url": "https://paid.substack.com"}, enabled=False)
    sync, _ = _sync(db, [PAID])

    plan = sync.run(apply=True)

    assert [a.action for a in plan.actions] == ["kept_disabled"]
    assert _rows(db)["substack:https://paid.substack.com"].enabled is False


def test_operator_type_mismatch_is_a_conflict(db: Session) -> None:
    yaml = [{"type": "rss", "url": "https://paid.substack.com/feed", "name": "Paid feed"}]
    sync, _ = _sync(db, [PAID], yaml)

    plan = sync.run(apply=True)

    (action,) = plan.actions
    assert action.action == "conflict"
    assert "rss:https://paid.substack.com/feed (yaml)" in (action.detail or "")
    assert plan.changes == 0 and _rows(db) == {}


# -- managed type switch -------------------------------------------------------


def test_free_to_paid_switch_disables_the_managed_feed(db: Session) -> None:
    sync, _ = _sync(db, [SubstackSubscription("Pub", "https://pub.substack.com", False)])
    sync.run(apply=True)

    became_paid = [SubstackSubscription("Pub", "https://pub.substack.com", True)]
    sync, _ = _sync(db, became_paid)
    plan = sync.run(apply=True)

    assert _actions(plan) == [
        ("switch", "rss", "rss:https://pub.substack.com/feed"),
        ("add", "substack", "substack:https://pub.substack.com"),
    ]
    rows = _rows(db)
    assert rows["rss:https://pub.substack.com/feed"].enabled is False
    assert rows["substack:https://pub.substack.com"].enabled is True


# -- prune ---------------------------------------------------------------------


def test_prune_disables_only_managed_rows_no_longer_subscribed(db: Session) -> None:
    sync, _ = _sync(db, [PAID, FREE])
    sync.run(apply=True)
    SourceOverrideService(db).upsert({"type": "rss", "url": "https://handmade.example/feed"})

    sync, _ = _sync(db, [PAID])
    dry = sync.run(prune=True)
    assert [(a.action, a.source_key) for a in dry.actions] == [
        ("existing", "substack:https://paid.substack.com"),
        ("prune", "rss:https://free.substack.com/feed"),
    ]
    assert _rows(db)["rss:https://free.substack.com/feed"].enabled is True

    sync.run(apply=True, prune=True)
    rows = _rows(db)
    assert rows["rss:https://free.substack.com/feed"].enabled is False
    assert rows["rss:https://handmade.example/feed"].enabled is True
    assert len(rows) == 3  # disabled, never deleted


def test_without_prune_unsubscribed_rows_stay_enabled(db: Session) -> None:
    sync, _ = _sync(db, [PAID, FREE])
    sync.run(apply=True)

    sync, _ = _sync(db, [PAID])
    plan = sync.run(apply=True)

    assert "prune" not in {a.action for a in plan.actions}
    assert _rows(db)["rss:https://free.substack.com/feed"].enabled is True


def test_prune_refuses_an_empty_listing(db: Session) -> None:
    sync, _ = _sync(db, [PAID])
    sync.run(apply=True)

    sync, _ = _sync(db, [])
    with pytest.raises(SubstackSyncRefusedError):
        sync.run(apply=True, prune=True)
    assert _rows(db)["substack:https://paid.substack.com"].enabled is True


# -- fail closed ---------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        CredentialsMissingError(
            source="substack",
            credential_label="substack.sid",
            refresh_command="aca auth session substack",
        ),
        SessionExpiredError(
            source="substack",
            credential_label="substack.sid",
            refresh_command="aca auth session substack",
        ),
        SubscriptionListingError("listing failed"),
    ],
)
def test_listing_failures_write_nothing(db: Session, failure: Exception) -> None:
    sync, client = _sync(db, failure)

    with pytest.raises(type(failure)):
        sync.run(apply=True, prune=True)

    assert client.closed and _rows(db) == {}


def test_a_failed_write_rolls_back_the_whole_apply(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real_upsert = SourceOverrideService.upsert

    def upsert_then_fail(self, config, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk full")
        return real_upsert(self, config, **kwargs)

    monkeypatch.setattr(SourceOverrideService, "upsert", upsert_then_fail)
    sync, _ = _sync(db, [PAID, FREE])

    with pytest.raises(RuntimeError):
        sync.run(apply=True)

    assert _rows(db) == {}


def test_paid_listing_wins_over_a_duplicate_free_one(db: Session) -> None:
    duplicate = SubstackSubscription("Paid Pub", "https://www.paid.substack.com", False)
    sync, _ = _sync(db, [duplicate, PAID])

    plan = sync.run()

    assert _actions(plan) == [("add", "substack", "substack:https://paid.substack.com")]


def test_sync_rows_match_their_source_key() -> None:
    assert source_key({"type": "rss", "url": target_url(FREE)}) == (
        "rss:https://free.substack.com/feed"
    )
