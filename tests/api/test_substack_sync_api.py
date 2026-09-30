"""POST /api/v1/sources/sync/substack (ri-19).

SQLite via a patched get_db and a fake Substack client, so no Postgres and no
network. The planner itself is covered in
tests/services/test_substack_subscription_sync.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.config.sources import SourcesConfig
from src.ingestion.credential_failures import CredentialsMissingError
from src.ingestion.substack import SubscriptionListingError, SubstackSubscription
from src.models.base import Base
from src.models.source_override import SourceOverride

ADMIN_KEY = "test-admin-key"
PAID = SubstackSubscription(name="Paid Pub", url="https://paid.substack.com", is_paid=True)


class FakeClient:
    listing: ClassVar[list[SubstackSubscription] | Exception] = [PAID]

    def fetch_subscriptions(self, *, strict: bool = False) -> list[SubstackSubscription]:
        assert strict
        if isinstance(self.listing, Exception):
            raise self.listing
        return list(self.listing)

    def close(self) -> None:
        pass


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[SourceOverride.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    from src.config.settings import get_settings

    get_settings.cache_clear()
    FakeClient.listing = [PAID]

    @contextmanager
    def mock_get_db():
        yield db_session

    with (
        patch("src.api.source_write_routes.get_db", mock_get_db),
        patch("src.services.substack_subscription_sync.SubstackClient", FakeClient),
        patch(
            "src.services.substack_subscription_sync.load_yaml_sources_config",
            lambda: SourcesConfig(),
        ),
        TestClient(app, headers={"X-Admin-Key": ADMIN_KEY}) as c,
    ):
        yield c
    get_settings.cache_clear()


URL = "/api/v1/sources/sync/substack"


def test_dry_run_is_the_default(client, db_session) -> None:
    response = client.post(URL, json={})

    assert response.status_code == 200
    body = response.json()
    assert (body["applied"], body["changes"], body["counts"]["add"]) == (False, 1, 1)
    assert body["actions"][0]["source_key"] == "substack:https://paid.substack.com"
    assert db_session.query(SourceOverride).count() == 0


def test_apply_writes_a_managed_row(client, db_session) -> None:
    response = client.post(URL, json={"apply": True})

    assert response.status_code == 200 and response.json()["applied"] is True
    (row,) = db_session.query(SourceOverride).all()
    assert (row.source_key, row.managed_by) == (
        "substack:https://paid.substack.com",
        "substack-sync",
    )


def test_missing_session_is_412_with_the_refresh_command(client, db_session) -> None:
    FakeClient.listing = CredentialsMissingError(
        source="substack",
        credential_label="substack.sid",
        refresh_command="aca auth session substack",
    )

    response = client.post(URL, json={"apply": True})

    assert response.status_code == 412
    detail = response.json()["detail"]
    assert detail["code"] == "credentials_missing"
    assert detail["refresh_command"] == "aca auth session substack"
    assert db_session.query(SourceOverride).count() == 0


def test_listing_failure_is_502(client) -> None:
    FakeClient.listing = SubscriptionListingError("Substack returned no subscription listing")

    response = client.post(URL, json={})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "subscription_listing_failed"


def test_prune_with_an_empty_listing_is_409(client) -> None:
    FakeClient.listing = []

    response = client.post(URL, json={"apply": True, "prune": True})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "prune_refused"


def test_requires_the_admin_key(client) -> None:
    response = client.post(URL, json={}, headers={"X-Admin-Key": "wrong"})

    assert response.status_code in (401, 403)
