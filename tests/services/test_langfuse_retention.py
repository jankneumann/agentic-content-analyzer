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
    LangfuseRetentionClient,
    LangfuseRetentionError,
    build_retention_client,
    prune_expired_traces,
)


class _FakeClient:
    """Stands in for the API: serves pages, records deletes."""

    def __init__(self, pages: list[list[str]]) -> None:
        self._pages = pages
        self.deleted: list[list[str]] = []
        self.listed_cutoffs: list[datetime] = []
        self.listed_pages: list[int] = []

    async def list_trace_ids_before(
        self,
        *,
        cutoff: datetime,
        limit: int,
        page: int,
    ) -> list[str]:
        self.listed_cutoffs.append(cutoff)
        self.listed_pages.append(page)
        if page > len(self._pages):
            return []
        return list(self._pages[page - 1])[:limit]

    async def delete_traces(self, trace_ids: list[str]) -> None:
        self.deleted.append(list(trace_ids))


@pytest.mark.asyncio
async def test_it_deletes_every_trace_older_than_the_window() -> None:
    client = _FakeClient([["a", "b"], ["c"]])

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=2,
        max_deletes=100,
    )

    assert result.deleted_count == 3
    assert client.deleted == [["a", "b"], ["c"]]
    assert result.capped is False


@pytest.mark.asyncio
async def test_the_cutoff_is_the_retention_window_back_from_now() -> None:
    client = _FakeClient([[]])
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=50,
        max_deletes=100,
        now=now,
    )

    assert result.cutoff == now - timedelta(days=30)
    assert client.listed_cutoffs == [now - timedelta(days=30)]


@pytest.mark.asyncio
async def test_a_trace_that_is_still_listed_after_deletion_is_not_deleted_twice() -> None:
    """Deletion is asynchronous, so a deleted trace keeps being listed.

    This is the loop's real hazard: re-reading a page expecting it to shrink
    re-deletes the same IDs forever. Paging forward plus a per-run seen set
    means a repeat costs one wasted listing, not an unbounded request storm.
    """
    client = _FakeClient([["a", "b"], ["a", "b"], ["c"]])

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=2,
        max_deletes=100,
    )

    assert client.deleted == [["a", "b"], ["c"]]
    assert result.deleted_count == 3
    assert result.batch_count == 2


@pytest.mark.asyncio
async def test_an_empty_page_ends_the_run() -> None:
    client = _FakeClient([["a"], [], ["never-reached"]])

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=10,
        max_deletes=100,
    )

    assert result.deleted_count == 1
    assert client.deleted == [["a"]]


@pytest.mark.asyncio
async def test_the_per_run_cap_bounds_a_first_run_against_a_huge_backlog() -> None:
    """Without this a first prune could delete for hours on one tick."""
    client = _FakeClient([["a", "b", "c"], ["d", "e", "f"]])

    result = await prune_expired_traces(
        client,
        retention_days=7,
        batch_size=3,
        max_deletes=4,
    )

    assert result.deleted_count == 4
    assert client.deleted == [["a", "b", "c"], ["d"]]
    assert result.capped is True


@pytest.mark.asyncio
async def test_a_dry_run_counts_without_deleting_anything() -> None:
    """Nobody should have to delete 200k traces to find out how many there are."""
    client = _FakeClient([["a", "b"], ["c"]])

    result = await prune_expired_traces(
        client,
        retention_days=30,
        batch_size=2,
        max_deletes=100,
        dry_run=True,
    )

    assert result.deleted_count == 3
    assert result.dry_run is True
    assert client.deleted == [], "a dry run must not issue a delete"


@pytest.mark.asyncio
async def test_it_refuses_a_zero_day_window() -> None:
    """A zero-day window would delete traces as fast as they are written."""
    client = _FakeClient([["a"]])

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
        ids = await client.list_trace_ids_before(
            cutoff=datetime(2026, 8, 1, tzinfo=UTC),
            limit=50,
            page=1,
        )

    assert ids == ["t1"]
    assert seen["fields"] == "core"
    assert seen["limit"] == "50"
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
            await client.list_trace_ids_before(
                cutoff=datetime(2026, 8, 1, tzinfo=UTC),
                limit=10,
                page=1,
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
