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

Two things keep the queries inside what the server will actually do.

Pagination is keyset, never ``page=N``: the API turns a page number into a
ClickHouse ``OFFSET``, which reads and discards every preceding row, so
walking a large store by page degrades until the server aborts the query.

Every query is also bounded at BOTH ends. A cursor alone leaves the window
open up to the cutoff, which is still weeks wide, and the 422 this endpoint
answers with says so in as many words: "narrow your request by adding more
specific filters (e.g., a shorter date range)". The expired period is
therefore swept as a series of narrow slices, and a slice that still trips the
limit is halved and retried, so the run tunes itself to whatever the server
can take rather than to a width guessed here.
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


class LangfuseResourceLimitError(LangfuseRetentionError):
    """Langfuse aborted the query because ClickHouse ran out of budget.

    The public API answers 422 for this, which is a load condition rather than
    a bad request: the same call succeeds against a smaller window. A run that
    hits it stops and keeps what it already did.
    """


# A 422 names the offending field in its body. Reporting the status alone turns
# a precise server answer into a guessing game, so the body travels with the
# error -- bounded, because a Langfuse error body can embed request echoes.
_MAX_EVIDENCE_CHARS = 400

# Slack above the delete ceiling for cursor nudges past same-timestamp clusters.
_CURSOR_NUDGE_ALLOWANCE = 100

# A slice narrow enough that the legacy traces endpoint can answer it, halved
# on a resource limit until the server stops complaining. Five minutes is the
# floor: below that an empty sweep costs more requests than it saves work.
_MIN_SLICE = timedelta(minutes=5)

# The public API caps `limit` at 100 (paginationLimitZod).
_MAX_API_LIMIT = 100


def _response_evidence(response: httpx.Response) -> str:
    """Return the server's own explanation, bounded and single-line."""

    try:
        body = response.text
    except Exception:  # pragma: no cover - body already consumed or undecodable
        return "(no readable body)"
    collapsed = " ".join(body.split())
    if not collapsed:
        return "(empty body)"
    if len(collapsed) > _MAX_EVIDENCE_CHARS:
        collapsed = collapsed[:_MAX_EVIDENCE_CHARS] + "..."
    return collapsed


@dataclass(frozen=True)
class LangfuseRetentionResult:
    """What one pruning run actually did."""

    deleted_count: int
    batch_count: int
    cutoff: datetime
    capped: bool
    """True when the per-run cap stopped the run with work still outstanding."""
    dry_run: bool = False
    stopped_reason: str | None = None
    """Set when the server ended the run early, e.g. a ClickHouse limit."""

    def as_log_fields(self) -> dict[str, Any]:
        return {
            "langfuse_retention_deleted_count": self.deleted_count,
            "langfuse_retention_batch_count": self.batch_count,
            "langfuse_retention_cutoff": self.cutoff.isoformat(),
            "langfuse_retention_capped": self.capped,
            "langfuse_retention_dry_run": self.dry_run,
            "langfuse_retention_stopped_reason": self.stopped_reason,
        }


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a Langfuse ISO timestamp, tolerating a trailing ``Z``."""

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True)
class TracePage:
    """One batch of expired traces and the cursor that follows it."""

    trace_ids: list[str]
    newest_timestamp: datetime | None


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

    async def list_trace_window(
        self,
        *,
        until: datetime,
        since: datetime | None,
        limit: int,
    ) -> TracePage:
        """Return the oldest traces in ``(since, until]``, plus a next cursor.

        Always page 1, ordered oldest first, with ``since`` carried forward
        from the previous batch. Asking for ``page=N`` instead would make
        ClickHouse skip ``N * limit`` rows on every request and eventually
        abort the query.

        ``fields=core`` matters: the default response embeds each trace's
        input, output, observations and scores, which is megabytes per page
        for exactly the payload we are about to throw away.
        """

        params: dict[str, Any] = {
            "toTimestamp": until.astimezone(UTC).isoformat(),
            "limit": limit,
            "page": 1,
            "fields": "core",
            "orderBy": "timestamp.asc",
        }
        if since is not None:
            params["fromTimestamp"] = since.astimezone(UTC).isoformat()

        response = await self._request("GET", params=params, timeout=_LIST_TIMEOUT_SECONDS)
        payload = response.json()
        rows = payload.get("data") or []

        trace_ids: list[str] = []
        newest: datetime | None = None
        for row in rows:
            trace_id = row.get("id")
            if not trace_id:
                continue
            trace_ids.append(str(trace_id))
            stamp = _parse_timestamp(row.get("timestamp"))
            if stamp is not None and (newest is None or stamp > newest):
                newest = stamp
        return TracePage(trace_ids=trace_ids, newest_timestamp=newest)

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
        if response.status_code == 422:
            raise LangfuseResourceLimitError(
                f"langfuse aborted the query (HTTP 422) {_response_evidence(response)}"
            )
        if response.status_code >= 400:
            raise LangfuseRetentionError(
                f"langfuse retention request returned HTTP {response.status_code}"
                f" {_response_evidence(response)}"
            )
        return response


@dataclass
class _SweepState:
    """Mutable totals shared across the slices of one run."""

    requested: set[str]
    deleted_count: int = 0
    batch_count: int = 0
    capped: bool = False


async def _prune_window(
    client: LangfuseRetentionClient,
    *,
    since: datetime,
    until: datetime,
    batch_size: int,
    max_deletes: int,
    state: _SweepState,
    dry_run: bool,
) -> None:
    """Delete every not-yet-submitted trace in one narrow window.

    Walks the window oldest-first with a timestamp cursor. Raises
    ``LangfuseResourceLimitError`` if the window is still too wide for the
    server, which the caller answers by halving it.
    """

    cursor = since
    window_limit = batch_size
    max_iterations = (max_deletes // batch_size) + _CURSOR_NUDGE_ALLOWANCE

    for _ in range(max_iterations):
        if state.deleted_count >= max_deletes:
            state.capped = True
            return

        page = await client.list_trace_window(
            until=until,
            since=cursor,
            limit=window_limit,
        )
        if not page.trace_ids:
            return

        fresh = [tid for tid in page.trace_ids if tid not in state.requested]

        if not fresh:
            # Everything visible here was already submitted. If the window came
            # back full, the rest of a same-timestamp cluster sits just past its
            # edge, and stepping the cursor over it would silently skip those
            # traces -- so widen first and only step once the cluster is whole.
            if len(page.trace_ids) >= window_limit and window_limit < _MAX_API_LIMIT:
                window_limit = min(window_limit * 2, _MAX_API_LIMIT)
                continue
            if page.newest_timestamp is None:
                return
            cursor = page.newest_timestamp + timedelta(microseconds=1)
            window_limit = batch_size
            continue

        remaining = max_deletes - state.deleted_count
        if len(fresh) > remaining:
            fresh = fresh[:remaining]
            state.capped = True

        if not dry_run:
            await client.delete_traces(fresh)

        state.requested.update(fresh)
        state.deleted_count += len(fresh)
        state.batch_count += 1
        window_limit = batch_size

        if page.newest_timestamp is None:
            return
        # Inclusive: a cluster may straddle this edge, so the boundary trace is
        # re-read next time and filtered by `requested`. One duplicated row per
        # batch is the price of never skipping one.
        cursor = page.newest_timestamp


async def prune_expired_traces(
    client: LangfuseRetentionClient,
    *,
    retention_days: int,
    batch_size: int,
    max_deletes: int,
    lookback_days: int = 400,
    slice_hours: int = 168,
    now: datetime | None = None,
    dry_run: bool = False,
) -> LangfuseRetentionResult:
    """Delete every trace older than ``retention_days``, up to ``max_deletes``.

    Sweeps the expired period oldest-first as a series of narrow time slices,
    walking each slice with a timestamp cursor. Both ends of every query are
    bounded: the legacy traces endpoint answers 422 when a query exceeds
    ClickHouse's budget, and its own advice is to shorten the date range. A
    slice that still trips the limit is halved and retried, down to five
    minutes, so the run adapts to the server instead of to a guess.

    ``lookback_days`` bounds how far back the sweep starts, since there is no
    cheap way to ask where history begins -- a trace older than that is left
    alone. Empty slices cost one fast request each.

    Each iteration either records new deletions or advances, and both are
    bounded, so the run terminates. Deletion is asynchronous and the cursor is
    inclusive, so a trace can be listed again after being submitted; the
    per-run set makes that a wasted comparison rather than a duplicate request.

    ``dry_run`` counts what would go without sending a delete.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_deletes < 1:
        raise ValueError("max_deletes must be at least 1")
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    if slice_hours < 1:
        raise ValueError("slice_hours must be at least 1")

    moment = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = moment - timedelta(days=retention_days)

    state = _SweepState(requested=set())
    stopped_reason: str | None = None
    slice_width = timedelta(hours=slice_hours)
    window_start = cutoff - timedelta(days=lookback_days)

    while window_start < cutoff and state.deleted_count < max_deletes:
        window_end = min(window_start + slice_width, cutoff)
        try:
            await _prune_window(
                client,
                since=window_start,
                until=window_end,
                batch_size=batch_size,
                max_deletes=max_deletes,
                state=state,
                dry_run=dry_run,
            )
        except LangfuseResourceLimitError as exc:
            if slice_width > _MIN_SLICE:
                slice_width = max(slice_width // 2, _MIN_SLICE)
                logger.info(
                    "langfuse retention narrowed its window",
                    extra={"langfuse_retention_slice_seconds": slice_width.total_seconds()},
                )
                continue
            # Already at the floor: the server cannot serve even five minutes
            # of this store. Keep the progress and say why.
            stopped_reason = str(exc)
            break
        window_start = window_end

    return LangfuseRetentionResult(
        deleted_count=state.deleted_count,
        batch_count=state.batch_count,
        cutoff=cutoff,
        capped=state.capped or state.deleted_count >= max_deletes,
        dry_run=dry_run,
        stopped_reason=stopped_reason,
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
