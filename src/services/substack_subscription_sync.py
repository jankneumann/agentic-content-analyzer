"""Sync the operator's Substack subscriptions into database source overrides.

``aca sources sync substack`` and ``POST /api/v1/sources/sync/substack`` list
the subscriptions through the live session and plan one action per
publication:

* **add**: not configured anywhere; a paid publication becomes a ``substack``
  override, a free one an ``rss`` override at its ``/feed`` URL, both marked
  ``managed_by = "substack-sync"``.
* **existing** / **kept_disabled**: already configured under the right type (by
  the operator or an earlier sync); never touched, even when disabled.
* **switch**: configured by this sync under the other type (the publication
  moved between free and paid); the old managed row is disabled and the new
  type added.
* **conflict**: configured by the operator under the other type; reported only,
  because the operator decides which type to ingest.
* **prune** (``prune=True`` only): an enabled managed row whose publication is
  no longer subscribed under its type; disabled, never deleted.

Publications are matched by host (without ``www.``) and path (without a trailing
``/`` or ``/feed``), because source keys are raw URL strings and YAML mixes
subdomains, custom domains, and feed URLs.

The listing is strict: a missing or dead session raises the credential failure
and a failed listing raises :class:`SubscriptionListingError`, so a broken
listing can never read as "unsubscribed from everything". Pruning with an empty
listing is refused as well.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from src.config.sources import (
    SourcesConfig,
    load_yaml_sources_config,
    merge_source_overrides,
    source_key,
)
from src.ingestion.substack import SubstackClient, SubstackSubscription
from src.services.source_override_service import SourceOverrideService
from src.utils.logging import get_logger

logger = get_logger(__name__)

MANAGED_BY = "substack-sync"
"""The ``source_overrides.managed_by`` marker this sync writes and prunes."""

SYNC_DESCRIPTION = "Added by aca sources sync substack"

SourceType = Literal["substack", "rss"]
ActionKind = Literal["add", "existing", "kept_disabled", "switch", "conflict", "prune"]
ACTION_KINDS: tuple[ActionKind, ...] = (
    "add",
    "existing",
    "kept_disabled",
    "switch",
    "conflict",
    "prune",
)
_WRITING_ACTIONS = frozenset({"add", "switch", "prune"})


class SubstackSyncRefusedError(ValueError):
    """The sync refused to run as requested (e.g. prune with an empty listing)."""


@dataclass(frozen=True)
class SyncAction:
    """One planned action for one publication."""

    action: ActionKind
    name: str
    source_type: SourceType
    url: str
    source_key: str
    detail: str | None = None
    """Why, for conflict/switch/prune (e.g. the other type's key)."""


@dataclass
class SubstackSyncPlan:
    """What the sync would do (dry run) or did (``applied=True``)."""

    apply: bool
    prune: bool
    subscriptions: int
    actions: list[SyncAction] = field(default_factory=list)
    applied: bool = False

    @property
    def changes(self) -> int:
        """Writes this plan makes (adds, switches, prunes)."""
        return sum(1 for action in self.actions if action.action in _WRITING_ACTIONS)

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = dict.fromkeys(ACTION_KINDS, 0)
        for action in self.actions:
            counts[action.action] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "apply": self.apply,
            "prune": self.prune,
            "applied": self.applied,
            "subscriptions": self.subscriptions,
            "changes": self.changes,
            "counts": self.counts(),
            "actions": [asdict(action) for action in self.actions],
        }


@dataclass(frozen=True)
class _Configured:
    source_type: SourceType
    key: str
    url: str
    enabled: bool
    managed: bool
    origin: str


def publication_locator(url: str) -> str:
    """Identity of a publication across URL spellings: host + path.

    Lowercased, ``www.`` dropped, trailing ``/`` and a trailing ``/feed``
    dropped, so ``https://www.X.substack.com/feed/`` and ``https://x.substack.com``
    match.
    """
    parsed = urlparse(url.strip().lower())
    host = parsed.netloc.removeprefix("www.")
    path = parsed.path.rstrip("/")
    path = path.removesuffix("/feed").rstrip("/")
    return f"{host}{path}"


def target_url(subscription: SubstackSubscription) -> str:
    """The URL the sync writes for this subscription under its type."""
    base = subscription.url.strip().rstrip("/")
    base = base.removesuffix("/feed").rstrip("/")
    return base if subscription.is_paid else f"{base}/feed"


def _source_type(subscription: SubstackSubscription) -> SourceType:
    return "substack" if subscription.is_paid else "rss"


def plan_substack_sync(
    subscriptions: Iterable[SubstackSubscription],
    *,
    config: SourcesConfig,
    overrides: list[dict[str, Any]],
    apply: bool = False,
    prune: bool = False,
) -> SubstackSyncPlan:
    """Plan the sync against the merged configuration. Pure; writes nothing.

    ``config`` is the YAML baseline merged with every override (enabled and
    disabled); ``overrides`` are the override rows with their ``managed_by``.
    """
    unique = _unique_subscriptions(subscriptions)
    if prune and not unique:
        raise SubstackSyncRefusedError(
            "Substack returned no subscriptions; refusing to prune every synced source"
        )

    managed_keys = {row["source_key"] for row in overrides if row.get("managed_by") == MANAGED_BY}
    index: dict[str, list[_Configured]] = {}
    for source in config.sources:
        if source.type not in ("substack", "rss"):
            continue
        url = getattr(source, "url", "")
        key = source_key(source)
        index.setdefault(publication_locator(url), []).append(
            _Configured(
                source_type=source.type,
                key=key,
                url=url,
                enabled=source.enabled,
                managed=key in managed_keys,
                origin=source.origin,
            )
        )

    plan = SubstackSyncPlan(apply=apply, prune=prune, subscriptions=len(unique))
    wanted: set[tuple[SourceType, str]] = set()
    switched: set[str] = set()
    for locator, subscription in unique.items():
        stype = _source_type(subscription)
        url = target_url(subscription)
        key = source_key({"type": stype, "url": url})
        wanted.add((stype, locator))
        entries = index.get(locator, [])
        same = [entry for entry in entries if entry.source_type == stype]
        other = [entry for entry in entries if entry.source_type != stype]

        if same:
            enabled = next((entry for entry in same if entry.enabled), None)
            chosen = enabled or same[0]
            plan.actions.append(
                SyncAction(
                    action="existing" if enabled else "kept_disabled",
                    name=subscription.name,
                    source_type=stype,
                    url=chosen.url,
                    source_key=chosen.key,
                )
            )
        elif other and all(entry.managed for entry in other):
            for entry in other:
                if entry.enabled:
                    switched.add(entry.key)
                    plan.actions.append(
                        SyncAction(
                            action="switch",
                            name=subscription.name,
                            source_type=entry.source_type,
                            url=entry.url,
                            source_key=entry.key,
                            detail=f"replaced by {key}",
                        )
                    )
            plan.actions.append(
                SyncAction(
                    action="add",
                    name=subscription.name,
                    source_type=stype,
                    url=url,
                    source_key=key,
                )
            )
        elif other:
            configured_as = ", ".join(
                f"{entry.key} ({entry.origin}{'' if entry.enabled else ', disabled'})"
                for entry in other
                if not entry.managed
            )
            plan.actions.append(
                SyncAction(
                    action="conflict",
                    name=subscription.name,
                    source_type=stype,
                    url=url,
                    source_key=key,
                    detail=f"subscribed as {'paid' if subscription.is_paid else 'free'} "
                    f"but configured as {configured_as}",
                )
            )
        else:
            plan.actions.append(
                SyncAction(
                    action="add",
                    name=subscription.name,
                    source_type=stype,
                    url=url,
                    source_key=key,
                )
            )

    if prune:
        for locator, entries in sorted(index.items()):
            for entry in entries:
                if (
                    entry.managed
                    and entry.enabled
                    and entry.key not in switched
                    and (entry.source_type, locator) not in wanted
                ):
                    plan.actions.append(
                        SyncAction(
                            action="prune",
                            name=locator,
                            source_type=entry.source_type,
                            url=entry.url,
                            source_key=entry.key,
                            detail="no longer subscribed",
                        )
                    )
    return plan


def _unique_subscriptions(
    subscriptions: Iterable[SubstackSubscription],
) -> dict[str, SubstackSubscription]:
    """One subscription per publication; a paid listing wins over a free one."""
    unique: dict[str, SubstackSubscription] = {}
    for subscription in subscriptions:
        locator = publication_locator(subscription.url)
        if not locator:
            continue
        current = unique.get(locator)
        if current is None or (subscription.is_paid and not current.is_paid):
            unique[locator] = subscription
    return dict(sorted(unique.items()))


class SubstackSubscriptionSync:
    """List subscriptions through the live session, plan, and optionally apply."""

    def __init__(
        self,
        db: Session,
        *,
        client_factory: Callable[[], SubstackClient] | None = None,
        yaml_loader: Callable[[], SourcesConfig] | None = None,
    ) -> None:
        # Defaults resolve at call time so tests can patch this module's names.
        self._db = db
        self._client_factory = client_factory or (lambda: SubstackClient())
        self._yaml_loader = yaml_loader or (lambda: load_yaml_sources_config())

    def run(self, *, apply: bool = False, prune: bool = False) -> SubstackSyncPlan:
        """Plan (and with ``apply`` write) the sync.

        Raises the credential failure for a missing or dead session,
        :class:`~src.ingestion.substack.SubscriptionListingError` for a failed
        listing, and :class:`SubstackSyncRefusedError` for a prune the listing
        cannot justify. Nothing is written in any of those cases.
        """
        client = self._client_factory()
        try:
            subscriptions = client.fetch_subscriptions(strict=True)
        finally:
            client.close()

        service = SourceOverrideService(self._db)
        overrides = service.list_overrides()
        config = merge_source_overrides(
            self._yaml_loader(),
            [
                {
                    "source_key": row["source_key"],
                    "config": row["config"],
                    "enabled": row["enabled"],
                }
                for row in overrides
            ],
        )
        plan = plan_substack_sync(
            subscriptions, config=config, overrides=overrides, apply=apply, prune=prune
        )
        if apply and plan.changes:
            self._apply(service, plan)
        plan.applied = apply
        logger.info(
            "substack.subscription_sync: %s subscriptions, %s changes (%s)",
            plan.subscriptions,
            plan.changes,
            "applied" if apply else "dry run",
        )
        return plan

    def _apply(self, service: SourceOverrideService, plan: SubstackSyncPlan) -> None:
        """Write every change in one transaction; roll back all of it on failure."""
        try:
            for action in plan.actions:
                if action.action == "add":
                    service.upsert(
                        {"type": action.source_type, "name": action.name, "url": action.url},
                        managed_by=MANAGED_BY,
                        description=SYNC_DESCRIPTION,
                        commit=False,
                    )
                elif action.action in ("switch", "prune"):
                    service.set_enabled(action.source_key, False, commit=False)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
