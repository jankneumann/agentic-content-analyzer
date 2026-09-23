"""Scheduled trace deletion for self-hosted (open-source) Langfuse.

Automated data retention is an enterprise feature: the open-source build
accepts no retention setting and deletes nothing on a schedule, so a
self-hosted stack grows for as long as it runs. See
https://github.com/orgs/langfuse/discussions/7460.

A ClickHouse ``TTL`` is not a substitute. One trace is three coupled stores --
rows in ClickHouse, and the raw ingestion events as blobs in object storage.
Expiring the rows underneath Langfuse orphans the blobs permanently: the UI
stops showing the trace while its bytes stay in the bucket forever. The public
delete endpoint enqueues a job that clears all of them, so going through the
API is the only way to actually reclaim the space.

Deletion is irreversible and asynchronous. Everything here is therefore off
unless explicitly enabled, bounded per run, and conservative about what it
counts as done.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# The public API answers a page request quickly, but a delete enqueues work in
# ClickHouse and object storage. Deletes get the longer budget.
_LIST_TIMEOUT_SECONDS = 30.0
_DELETE_TIMEOUT_SECONDS = 60.0


class LangfuseRetentionError(RuntimeError):
    """The Langfuse API rejected or failed a retention request."""


@dataclass(frozen=True)
class LangfuseRetentionResult:
    """What one pruning run actually did."""

    deleted_count: int
    batch_count: int
    cutoff: datetime
    capped: bool
    """True when the per-run cap stopped the run with work still outstanding."""
    dry_run: bool = False

    def as_log_fields(self) -> dict[str, Any]:
        return {
            "langfuse_retention_deleted_count": self.deleted_count,
            "langfuse_retention_batch_count": self.batch_count,
            "langfuse_retention_cutoff": self.cutoff.isoformat(),
            "langfuse_retention_capped": self.capped,
            "langfuse_retention_dry_run": self.dry_run,
        }


class LangfuseRetentionClient:
    """Minimal async client for the two public endpoints retention needs.

    The Langfuse Python SDK is an ingestion client -- it has no delete call --
    so the retention path talks to the REST API directly with the same
    project-scoped key pair the SDK uses for writes.
    """

    def __init__(
        self,
        *,
        base_url: str,
        public_key: str,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not public_key or not secret_key:
            raise ValueError("both a public key and a secret key are required")
        self._traces_url = f"{base_url.rstrip('/')}/api/public/traces"
        self._auth = httpx.BasicAuth(public_key, secret_key)
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> LangfuseRetentionClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise LangfuseRetentionError("client used outside its async context")
        return self._client

    async def list_trace_ids_before(
        self,
        *,
        cutoff: datetime,
        limit: int,
        page: int,
    ) -> list[str]:
        """Return trace IDs older than ``cutoff``, one page at a time.

        ``fields=core`` matters: the default response embeds each trace's
        input, output, observations and scores, which is megabytes per page
        for exactly the payload we are about to throw away.
        """

        response = await self._request(
            "GET",
            params={
                "toTimestamp": cutoff.astimezone(UTC).isoformat(),
                "limit": limit,
                "page": page,
                "fields": "core",
            },
            timeout=_LIST_TIMEOUT_SECONDS,
        )
        payload = response.json()
        rows = payload.get("data") or []
        return [str(row["id"]) for row in rows if row.get("id")]

    async def delete_traces(self, trace_ids: Sequence[str]) -> None:
        """Enqueue deletion of a batch of traces."""

        if not trace_ids:
            return
        await self._request(
            "DELETE",
            json={"traceIds": list(trace_ids)},
            timeout=_DELETE_TIMEOUT_SECONDS,
        )

    async def _request(
        self,
        method: str,
        *,
        timeout: float,  # noqa: ASYNC109 - httpx transport timeout, not a cancel scope
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        client = self._require_client()
        try:
            response = await client.request(
                method,
                self._traces_url,
                auth=self._auth,
                params=params,
                json=json,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise LangfuseRetentionError(
                f"langfuse retention request failed: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise LangfuseRetentionError(
                f"langfuse retention request returned HTTP {response.status_code}"
            )
        return response


async def prune_expired_traces(
    client: LangfuseRetentionClient,
    *,
    retention_days: int,
    batch_size: int,
    max_deletes: int,
    now: datetime | None = None,
    dry_run: bool = False,
) -> LangfuseRetentionResult:
    """Delete every trace older than ``retention_days``, up to ``max_deletes``.

    Deletion is asynchronous: the endpoint enqueues work, and a deleted trace
    keeps appearing in listings until the Langfuse worker gets to it. A loop
    that re-reads page 1 expecting it to shrink therefore re-deletes the same
    IDs forever, so this pages forward instead and never revisits a page.

    Paging forward while rows disappear underneath can skip a trace. That
    costs nothing: each run re-lists from the first page against a fresh
    cutoff, so anything skipped is picked up next time. Runs converge rather
    than each one being exhaustive -- the safe direction for a delete loop,
    which should under-reach and retry rather than spin.

    ``dry_run`` counts what would go without sending a delete. Nothing is
    removed, so paging forward is exact rather than convergent, and the count
    is the real number of expired traces up to ``max_deletes``.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_deletes < 1:
        raise ValueError("max_deletes must be at least 1")

    moment = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = moment - timedelta(days=retention_days)

    requested: set[str] = set()
    deleted_count = 0
    batch_count = 0
    page = 1
    capped = False

    while deleted_count < max_deletes:
        trace_ids = await client.list_trace_ids_before(
            cutoff=cutoff,
            limit=batch_size,
            page=page,
        )
        if not trace_ids:
            break
        page += 1

        fresh = [trace_id for trace_id in trace_ids if trace_id not in requested]
        if not fresh:
            continue

        remaining = max_deletes - deleted_count
        if len(fresh) > remaining:
            fresh = fresh[:remaining]
            capped = True

        if not dry_run:
            await client.delete_traces(fresh)
        requested.update(fresh)
        deleted_count += len(fresh)
        batch_count += 1

    return LangfuseRetentionResult(
        deleted_count=deleted_count,
        batch_count=batch_count,
        cutoff=cutoff,
        capped=capped or deleted_count >= max_deletes,
        dry_run=dry_run,
    )


def build_retention_client(settings: Any) -> LangfuseRetentionClient | None:
    """Build a client from settings, or None when retention cannot run.

    Returning None rather than raising keeps a misconfigured pruner from
    crash-looping a worker whose real job is running the queue.
    """

    if not getattr(settings, "langfuse_trace_retention_enabled", False):
        return None
    public_key = getattr(settings, "langfuse_public_key", None)
    secret_key = getattr(settings, "langfuse_secret_key", None)
    base_url = getattr(settings, "langfuse_base_url", None)
    if not (public_key and secret_key and base_url):
        logger.warning("langfuse trace retention enabled but credentials are incomplete; skipping")
        return None
    return LangfuseRetentionClient(
        base_url=base_url,
        public_key=public_key,
        secret_key=secret_key,
    )
