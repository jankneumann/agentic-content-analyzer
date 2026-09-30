"""Open-source Langfuse deletes nothing on a schedule; this is what does.

Automated retention is an enterprise feature (langfuse discussion 7460), so a
self-hosted stack grows until the disk fills. On GX-10 it reached 39GB of
ClickHouse and 4.9GB of object storage after a single ingest. The pruner walks
the public API, which is the only path that clears the ClickHouse rows and the
object-storage blobs together.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from src.services.langfuse_retention import (
    LangfuseResourceLimitError,
    LangfuseRetentionClient,
    LangfuseRetentionError,
    TracePage,
    build_retention_client,
    prune_expired_traces,
)


class _FakeClient:
    """A timestamp-ordered trace store that honours the keyset cursor.

    Deliberately NOT page-number based: the real API turns pages into a
    ClickHouse OFFSET, and modelling pages here is what let an offset-paging
    pruner look correct in tests while failing on the host.
    """

    def __init__(
        self,
        traces: list[tuple[str, datetime]] | None = None,
        *,
        resource_limit_after: int | None = None,
    ) -> None:
        self._traces = sorted(traces or [], key=lambda t: t[1])
        self.deleted: list[list[str]] = []
        self.windows: list[tuple[datetime | None, datetime]] = []
        self._resource_limit_after = resource_limit_after

    async def list_trace_window(
        self,
        *,
        until: datetime,
        since: datetime | None,
        limit: int,
    ) -> TracePage:
        self.windows.append((since, until))
        if (
            self._resource_limit_after is not None
            and len(self.windows) > self._resource_limit_after
        ):
            raise LangfuseResourceLimitError("langfuse aborted the query (HTTP 422)")
        rows = [
            (tid, ts) for tid, ts in self._traces if ts < until and (since is None or ts >= since)
        ][:limit]
        newest = max((ts for _, ts in rows), default=None)
        return TracePage(trace_ids=[tid for tid, _ in rows], newest_timestamp=newest)

    async def delete_traces(self, trace_ids: list[str]) -> None:
        self.deleted.append(list(trace_ids))


def _store(count: int, *, start: datetime | None = None) -> list[tuple[str, datetime]]:
    """A store of distinctly-timestamped traces, oldest first."""
    base = start or datetime(2026, 1, 1, tzinfo=UTC)
    return [(f"t{i}", base + timedelta(seconds=i)) for i in range(count)]


@pytest.mark.asyncio
async def test_it_deletes_every_trace_older_than_the_window() -> None:
    client = _FakeClient(_store(3))

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=2,
        max_deletes=100,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 3
    assert [t for batch in client.deleted for t in batch] == ["t0", "t1", "t2"]
    assert result.capped is False


@pytest.mark.asyncio
async def test_it_never_asks_for_a_deep_page() -> None:
    """The live failure: page=N becomes a ClickHouse OFFSET and 422s.

    Walking 400 pages of a real trace store aborted the query outright. The
    cursor must carry the window forward instead, so every request costs the
    same no matter how far in the run gets.
    """
    client = _FakeClient(_store(500))

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=50,
        max_deletes=1000,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 500
    # Each window starts where the previous one ended, and only moves forward.
    starts = [since for since, _ in client.windows]
    assert starts[0] is None, "the first window is open-ended"
    later = [since for since in starts[1:] if since is not None]
    assert len(later) == len(starts) - 1, "every later window carries a cursor"
    assert later == sorted(later), "the cursor must never go backwards"


@pytest.mark.asyncio
async def test_the_cutoff_is_the_retention_window_back_from_now() -> None:
    client = _FakeClient([])
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=50,
        max_deletes=100,
        now=now,
    )

    assert result.cutoff == now - timedelta(days=30)
    assert client.windows == [(None, now - timedelta(days=30))]


@pytest.mark.asyncio
async def test_a_trace_still_listed_after_deletion_is_not_deleted_twice() -> None:
    """Deletion is async and fromTimestamp is inclusive, so batches overlap.

    The boundary trace comes back on the next window. Without the per-run set
    it would be submitted again on every iteration.
    """
    client = _FakeClient(_store(4))

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=2,
        max_deletes=100,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    submitted = [t for batch in client.deleted for t in batch]
    assert sorted(submitted) == ["t0", "t1", "t2", "t3"]
    assert len(submitted) == len(set(submitted)), "no trace may be submitted twice"
    assert result.deleted_count == 4


@pytest.mark.asyncio
async def test_traces_sharing_one_timestamp_do_not_stall_the_cursor() -> None:
    """An inclusive cursor cannot advance past a cluster on its own."""
    same = datetime(2026, 1, 1, tzinfo=UTC)
    traces = [(f"c{i}", same) for i in range(5)]
    traces += [("later", same + timedelta(seconds=1))]
    client = _FakeClient(traces)

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=2,
        max_deletes=100,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 6
    assert "later" in [t for batch in client.deleted for t in batch]


@pytest.mark.parametrize("batch_size", [1, 2, 3, 7, 50])
@pytest.mark.parametrize("cluster", [1, 2, 5])
@pytest.mark.asyncio
async def test_it_never_skips_a_trace_whatever_the_batch_and_clustering(
    batch_size: int, cluster: int
) -> None:
    """The guarantee that matters: a prune must not leave traces behind.

    Skipping is the silent failure here -- the run reports success, the disk
    never shrinks, and nothing says which traces were missed. Clusters of
    identical timestamps are the case that breaks a naive cursor.
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    traces = [(f"t{i}", base + timedelta(seconds=i // cluster)) for i in range(30)]
    client = _FakeClient(traces)

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=batch_size,
        max_deletes=10_000,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    submitted = [t for batch in client.deleted for t in batch]
    assert sorted(submitted) == sorted(t for t, _ in traces), "a trace was skipped"
    assert len(submitted) == len(set(submitted)), "a trace was submitted twice"
    assert result.deleted_count == 30


@pytest.mark.asyncio
async def test_an_empty_window_ends_the_run() -> None:
    client = _FakeClient([])

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=10,
        max_deletes=100,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 0
    assert client.deleted == []


@pytest.mark.asyncio
async def test_the_per_run_cap_bounds_a_first_run_against_a_huge_backlog() -> None:
    """Without this a first prune could delete for hours on one tick."""
    client = _FakeClient(_store(6))

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=3,
        max_deletes=4,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 4
    assert result.capped is True


@pytest.mark.asyncio
async def test_a_resource_limit_stops_the_run_and_keeps_what_it_did() -> None:
    """422 is load, not a bad request: bank the progress and say why."""
    client = _FakeClient(_store(200), resource_limit_after=2)

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=10,
        max_deletes=1000,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    # 10 from the first window, 9 from the second: the inclusive cursor
    # re-reads the boundary trace, which `requested` filters out.
    assert result.deleted_count == 19, "work done before the limit must be kept"
    assert result.stopped_reason is not None
    assert "422" in result.stopped_reason


@pytest.mark.asyncio
async def test_a_dry_run_counts_without_deleting_anything() -> None:
    """Nobody should have to delete 200k traces to find out how many there are."""
    client = _FakeClient(_store(3))

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=2,
        max_deletes=100,
        dry_run=True,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert result.deleted_count == 3
    assert result.dry_run is True
    assert client.deleted == [], "a dry run must not issue a delete"


@pytest.mark.asyncio
async def test_it_refuses_a_zero_day_window() -> None:
    """A zero-day window would delete traces as fast as they are written."""
    client = _FakeClient(_store(1))

    with pytest.raises(ValueError, match="retention_days"):
        await prune_expired_traces(
            client,
            retention_days=0,
            batch_size=10,
            max_deletes=10,
        )

    assert client.deleted == []


@pytest.mark.asyncio
async def test_it_asks_only_for_core_fields() -> None:
    """The default response embeds the very payload we are about to delete."""
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        assert request.headers.get("authorization", "").startswith("Basic ")
        return httpx.Response(200, json={"data": [{"id": "t1"}], "meta": {"page": 1}})

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000/",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        page = await client.list_trace_window(
            until=datetime(2026, 8, 1, tzinfo=UTC),
            since=None,
            limit=50,
        )
        ids = page.trace_ids

    assert ids == ["t1"]
    assert seen["fields"] == "core"
    assert seen["limit"] == "50"
    assert seen["page"] == "1", "a page number becomes a ClickHouse OFFSET"
    assert seen["orderBy"] == "timestamp.asc"
    assert "2026-08-01" in str(seen["toTimestamp"])


@pytest.mark.asyncio
async def test_the_delete_sends_the_batch_as_trace_ids() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"message": "queued"})

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        await client.delete_traces(["t1", "t2"])

    assert captured["method"] == "DELETE"
    assert captured["url"] == "http://langfuse-web:3000/api/public/traces"
    assert '"traceIds"' in str(captured["body"])
    assert "t1" in str(captured["body"])


@pytest.mark.asyncio
async def test_an_empty_batch_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made for an empty batch")

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        await client.delete_traces([])


@pytest.mark.asyncio
async def test_a_rejected_request_reports_the_servers_own_explanation() -> None:
    """A 422 names the offending field; a bare status turns that into guesswork.

    The first live run of this pruner failed with `HTTP 422` and nothing else,
    which is the same defect the backup executor exists to avoid: a status
    without evidence is not diagnosable.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "message": "Invalid request data",
                "error": [{"path": ["toTimestamp"], "message": "Invalid datetime"}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        with pytest.raises(LangfuseRetentionError) as caught:
            await client.list_trace_window(
                until=datetime(2026, 8, 1, tzinfo=UTC),
                since=None,
                limit=10,
            )

    message = str(caught.value)
    assert "422" in message
    assert "toTimestamp" in message, "the offending field must reach the operator"
    assert "Invalid datetime" in message


@pytest.mark.asyncio
async def test_error_evidence_is_bounded() -> None:
    """An error body can echo the request; it must not become the log."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="x" * 5000)

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        with pytest.raises(LangfuseRetentionError) as caught:
            await client.delete_traces(["t1"])

    assert len(str(caught.value)) < 600


@pytest.mark.asyncio
async def test_an_http_error_is_raised_as_a_retention_error() -> None:
    """A 403 must not read as 'nothing left to delete'."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    transport = httpx.MockTransport(handler)
    async with LangfuseRetentionClient(
        base_url="http://langfuse-web:3000",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        client=httpx.AsyncClient(transport=transport),
    ) as client:
        with pytest.raises(LangfuseRetentionError, match="403"):
            await client.list_trace_window(
                until=datetime(2026, 8, 1, tzinfo=UTC),
                since=None,
                limit=10,
            )


class _Settings:
    def __init__(self, **kwargs: object) -> None:
        self.langfuse_trace_retention_enabled = True
        self.langfuse_public_key = "pk-lf-test"
        self.langfuse_secret_key = "sk-lf-test"
        self.langfuse_base_url = "http://langfuse-web:3000"
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_retention_is_off_unless_explicitly_enabled() -> None:
    """Deletion is irreversible, so it never turns itself on."""
    assert build_retention_client(_Settings(langfuse_trace_retention_enabled=False)) is None


def test_incomplete_credentials_skip_rather_than_crash_the_worker() -> None:
    """The worker's real job is the queue; housekeeping must not kill it."""
    assert build_retention_client(_Settings(langfuse_secret_key=None)) is None
    assert build_retention_client(_Settings(langfuse_base_url="")) is None


def test_a_complete_configuration_builds_a_client() -> None:
    assert isinstance(build_retention_client(_Settings()), LangfuseRetentionClient)
