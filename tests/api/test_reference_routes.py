"""Tests for Content Reference API endpoints.

Tests the reference tracking endpoints:
- GET /api/v1/contents/{content_id}/references — outgoing references
- GET /api/v1/contents/{content_id}/cited-by — incoming resolved references
"""

from datetime import UTC, datetime

import pytest

from src.models.content_reference import ContentReference, ResolutionStatus
from tests.factories.content import ContentFactory


@pytest.fixture
def source_content(db_session):
    """Create a source content item that has outgoing references."""
    return ContentFactory(
        rss=True,
        parsed=True,
        source_id="ref-source-001",
        title="Survey of LLM Techniques",
        content_hash="ref_hash_001",
    )


@pytest.fixture
def target_content(db_session):
    """Create a target content item that is referenced by others."""
    return ContentFactory(
        rss=True,
        source_id="ref-target-001",
        title="Original LLM Paper",
        content_hash="ref_hash_002",
    )


@pytest.fixture
def unresolved_ref(db_session, source_content):
    """Create an unresolved external reference."""
    ref = ContentReference(
        source_content_id=source_content.id,
        reference_type="cites",
        external_url="https://arxiv.org/abs/2301.00001",
        external_id="2301.00001",
        external_id_type="arxiv",
        resolution_status=ResolutionStatus.UNRESOLVED,
        confidence=0.95,
        context_snippet="As shown in [1], LLMs can...",
    )
    db_session.add(ref)
    db_session.commit()
    db_session.refresh(ref)
    return ref


@pytest.fixture
def resolved_ref(db_session, source_content, target_content):
    """Create a resolved reference linking source to target content."""
    ref = ContentReference(
        source_content_id=source_content.id,
        reference_type="cites",
        target_content_id=target_content.id,
        external_url="https://example.com/paper",
        external_id="10.1234/test",
        external_id_type="doi",
        resolution_status=ResolutionStatus.RESOLVED,
        resolved_at=datetime.now(UTC),
        confidence=0.99,
        context_snippet="Building on the work of [2]...",
    )
    db_session.add(ref)
    db_session.commit()
    db_session.refresh(ref)
    return ref


class TestGetReferences:
    """Tests for GET /api/v1/contents/{content_id}/references endpoint."""

    def test_empty_references(self, client, source_content):
        """Content with no references returns empty list."""
        response = client.get(f"/api/v1/contents/{source_content.id}/references")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_returns_outgoing_refs(self, client, source_content, unresolved_ref, resolved_ref):
        """Returns all outgoing references from a content item."""
        response = client.get(f"/api/v1/contents/{source_content.id}/references")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_reference_fields(self, client, source_content, unresolved_ref):
        """Response includes all expected reference fields."""
        response = client.get(f"/api/v1/contents/{source_content.id}/references")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_content_id"] == source_content.id
        assert item["reference_type"] == "cites"
        assert item["external_url"] == "https://arxiv.org/abs/2301.00001"
        assert item["external_id"] == "2301.00001"
        assert item["external_id_type"] == "arxiv"
        assert item["resolution_status"] == "unresolved"
        assert item["confidence"] == 0.95
        assert item["context_snippet"] == "As shown in [1], LLMs can..."
        # Unresolved ref has no target
        assert item["target_content_id"] is None
        assert item["target_title"] is None
        assert item["target_source_type"] is None

    def test_resolved_ref_includes_target_info(
        self, client, source_content, resolved_ref, target_content
    ):
        """Resolved references include target_title and target_source_type."""
        response = client.get(f"/api/v1/contents/{source_content.id}/references")
        assert response.status_code == 200
        items = response.json()["items"]
        # Find the resolved ref
        resolved_items = [i for i in items if i["resolution_status"] == "resolved"]
        assert len(resolved_items) == 1
        item = resolved_items[0]
        assert item["target_content_id"] == target_content.id
        assert item["target_title"] == "Original LLM Paper"
        assert item["target_source_type"] == "rss"

    def test_pagination(self, client, db_session, source_content):
        """Pagination works correctly for references."""
        # Create 5 references
        for i in range(5):
            ref = ContentReference(
                source_content_id=source_content.id,
                reference_type="cites",
                external_url=f"https://example.com/paper-{i}",
                external_id=f"10.1234/paper-{i}",
                external_id_type="doi",
                resolution_status=ResolutionStatus.EXTERNAL,
                confidence=0.8,
            )
            db_session.add(ref)
        db_session.commit()

        # Page 1 with page_size=2
        response = client.get(f"/api/v1/contents/{source_content.id}/references?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

        # Page 3 with page_size=2 (last page, 1 item)
        response = client.get(f"/api/v1/contents/{source_content.id}/references?page=3&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 5

    def test_nonexistent_content_returns_empty(self, client):
        """Requesting references for a non-existent content_id returns empty list."""
        response = client.get("/api/v1/contents/99999/references")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestGetCitedBy:
    """Tests for GET /api/v1/contents/{content_id}/cited-by endpoint."""

    def test_empty_cited_by(self, client, target_content):
        """Content with no incoming citations returns empty list."""
        response = client.get(f"/api/v1/contents/{target_content.id}/cited-by")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_returns_resolved_incoming_refs(
        self, client, source_content, target_content, resolved_ref
    ):
        """Returns resolved references pointing TO this content."""
        response = client.get(f"/api/v1/contents/{target_content.id}/cited-by")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["source_content_id"] == source_content.id
        assert item["target_content_id"] == target_content.id
        assert item["resolution_status"] == "resolved"

    def test_excludes_unresolved_refs(self, client, db_session, source_content, target_content):
        """Only resolved references appear in cited-by results."""
        # Create an unresolved ref pointing to target
        unresolved = ContentReference(
            source_content_id=source_content.id,
            reference_type="discusses",
            target_content_id=target_content.id,
            external_url="https://example.com/unresolved",
            resolution_status=ResolutionStatus.UNRESOLVED,
            confidence=0.5,
        )
        db_session.add(unresolved)
        db_session.commit()

        response = client.get(f"/api/v1/contents/{target_content.id}/cited-by")
        assert response.status_code == 200
        data = response.json()
        # Unresolved refs should NOT appear in cited-by
        assert data["total"] == 0

    def test_cited_by_pagination(self, client, db_session, target_content):
        """Pagination works correctly for cited-by endpoint."""
        # Create 4 resolved refs from different sources
        for i in range(4):
            src = ContentFactory(
                rss=True,
                source_id=f"citing-src-{i}",
                title=f"Citing Paper {i}",
                content_hash=f"citing_hash_{i}",
            )
            ref = ContentReference(
                source_content_id=src.id,
                reference_type="cites",
                target_content_id=target_content.id,
                external_url=f"https://example.com/citing-{i}",
                external_id=f"10.5678/citing-{i}",
                external_id_type="doi",
                resolution_status=ResolutionStatus.RESOLVED,
                resolved_at=datetime.now(UTC),
                confidence=0.9,
            )
            db_session.add(ref)
        db_session.commit()

        # Page 1 with page_size=2
        response = client.get(f"/api/v1/contents/{target_content.id}/cited-by?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 4

        # Page 2
        response = client.get(f"/api/v1/contents/{target_content.id}/cited-by?page=2&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 4

    def test_nonexistent_content_returns_empty(self, client):
        """Requesting cited-by for a non-existent content_id returns empty list."""
        response = client.get("/api/v1/contents/99999/cited-by")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


# =============================================================================
# POST /api/v1/references/extract and /api/v1/references/resolve
# (added by cloud-db-source-of-truth — separate from the /contents/*/references
# endpoints above)
# =============================================================================

from contextlib import contextmanager  # noqa: E402
from unittest.mock import patch  # noqa: E402

from src.models.content import Content, ContentSource, ContentStatus  # noqa: E402


@pytest.fixture
def references_v2_db(monkeypatch, db_session):
    """Patch the new ``src.api.routes.reference_routes`` module's ``get_db``."""

    @contextmanager
    def _fake_get_db():
        yield db_session

    monkeypatch.setattr("src.api.routes.reference_routes.get_db", _fake_get_db)
    return _fake_get_db


def _make_extract_content(db_session, *, ingested_at: datetime | None = None) -> Content:
    stamp = ingested_at or datetime.now(UTC)
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id=f"ref-extract-{stamp.timestamp()}",
        title="Seed content",
        markdown_content="# Title\nhttps://arxiv.org/abs/2401.00001 body",
        content_hash=f"hash-{stamp.timestamp()}",
        status=ContentStatus.COMPLETED,
        ingested_at=stamp,
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


class TestExtractReferencesEndpoint:
    def test_by_content_ids_returns_counts(self, client, db_session, references_v2_db):
        c1 = _make_extract_content(db_session)
        c2 = _make_extract_content(db_session)

        fake_result = {
            "references_extracted": 3,
            "content_processed": 2,
            "has_more": False,
            "next_cursor": None,
            "per_content": [],
        }
        with patch(
            "src.api.routes.reference_routes._run_extraction",
            return_value=fake_result,
        ):
            resp = client.post(
                "/api/v1/references/extract",
                json={"content_ids": [c1.id, c2.id]},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["references_extracted"] == 3
        assert body["content_processed"] == 2
        assert body["has_more"] is False
        assert body["next_cursor"] is None

    def test_date_range_has_more_and_cursor(self, client, references_v2_db):
        cursor = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
        fake_result = {
            "references_extracted": 5,
            "content_processed": 50,
            "has_more": True,
            "next_cursor": cursor,
            "per_content": [{"content_id": i, "references_found": 0} for i in range(50)],
        }
        with patch(
            "src.api.routes.reference_routes._run_extraction",
            return_value=fake_result,
        ):
            resp = client.post(
                "/api/v1/references/extract",
                json={
                    "since": "2026-04-01T00:00:00+00:00",
                    "until": "2026-04-21T00:00:00+00:00",
                    "batch_size": 50,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_more"] is True
        assert body["next_cursor"] is not None
        assert body["per_content"] is not None
        assert len(body["per_content"]) == 50

    def test_per_content_omitted_on_large_batches(self, client, references_v2_db):
        fake_result = {
            "references_extracted": 0,
            "content_processed": 150,
            "has_more": False,
            "next_cursor": None,
            "per_content": [{"content_id": i, "references_found": 0} for i in range(150)],
        }
        with patch(
            "src.api.routes.reference_routes._run_extraction",
            return_value=fake_result,
        ):
            resp = client.post(
                "/api/v1/references/extract",
                json={"since": "2026-04-01T00:00:00+00:00", "batch_size": 500},
            )
        body = resp.json()
        assert body["per_content"] is None

    def test_conflicting_filters_returns_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/extract",
            json={
                "content_ids": [1, 2],
                "since": "2026-04-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 422

    def test_oversized_content_ids_returns_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/extract",
            json={"content_ids": list(range(1, 502))},
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client, references_v2_db):
        resp = client.post("/api/v1/references/extract", json={})
        assert resp.status_code == 422

    def test_extra_field_rejected_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/extract",
            json={"content_ids": [1], "unexpected": True},
        )
        assert resp.status_code == 422

    def test_timeout_returns_504(self, client, references_v2_db):
        async def raising_wait_for(coro, *args, **kwargs):
            del args, kwargs  # asyncio.wait_for signature passes timeout
            coro.close()
            raise TimeoutError

        with patch(
            "src.api.routes.reference_routes.asyncio.wait_for",
            side_effect=raising_wait_for,
        ):
            resp = client.post(
                "/api/v1/references/extract",
                json={"content_ids": [1]},
            )
        assert resp.status_code == 504
        assert "application/problem+json" in resp.headers.get("content-type", "")
        body = resp.json()
        assert body["status"] == 504

    def test_audit_records_extract_operation(self, client, db_session, references_v2_db):
        c = _make_extract_content(db_session)
        fake_result = {
            "references_extracted": 0,
            "content_processed": 1,
            "has_more": False,
            "next_cursor": None,
            "per_content": [{"content_id": c.id, "references_found": 0}],
        }
        captured: list[dict] = []

        def capture(**kwargs):
            captured.append(kwargs)

        with (
            patch(
                "src.api.routes.reference_routes._run_extraction",
                return_value=fake_result,
            ),
            patch(
                "src.api.middleware.audit._default_writer",
                side_effect=capture,
            ),
        ):
            resp = client.post(
                "/api/v1/references/extract",
                json={"content_ids": [c.id]},
            )
        assert resp.status_code == 200
        rows = [r for r in captured if r.get("path") == "/api/v1/references/extract"]
        assert rows and rows[0]["operation"] == "references.extract"


class TestResolveReferencesEndpoint:
    def test_default_batch_empty_body(self, client, references_v2_db):
        fake_result = {
            "resolved_count": 7,
            "still_unresolved_count": 0,
            "has_more": False,
        }
        with patch(
            "src.api.routes.reference_routes._run_resolution",
            return_value=fake_result,
        ) as m:
            resp = client.post("/api/v1/references/resolve", json={})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == fake_result
        m.assert_called_once()
        assert m.call_args.kwargs.get("batch_size") == 100

    def test_explicit_batch_size_passed_through(self, client, references_v2_db):
        fake_result = {
            "resolved_count": 3,
            "still_unresolved_count": 2,
            "has_more": True,
        }
        with patch(
            "src.api.routes.reference_routes._run_resolution",
            return_value=fake_result,
        ) as m:
            resp = client.post(
                "/api/v1/references/resolve",
                json={"batch_size": 500},
            )
        assert resp.status_code == 200
        assert m.call_args.kwargs.get("batch_size") == 500
        assert resp.json()["has_more"] is True

    def test_oversized_batch_size_returns_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/resolve",
            json={"batch_size": 5000},
        )
        assert resp.status_code == 422

    def test_under_minimum_batch_size_returns_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/resolve",
            json={"batch_size": 0},
        )
        assert resp.status_code == 422

    def test_extra_field_rejected_422(self, client, references_v2_db):
        resp = client.post(
            "/api/v1/references/resolve",
            json={"batch_size": 100, "unknown": True},
        )
        assert resp.status_code == 422

    def test_no_body_uses_default_batch(self, client, references_v2_db):
        fake_result = {
            "resolved_count": 0,
            "still_unresolved_count": 0,
            "has_more": False,
        }
        with patch(
            "src.api.routes.reference_routes._run_resolution",
            return_value=fake_result,
        ) as m:
            resp = client.post("/api/v1/references/resolve")
        assert resp.status_code == 200
        assert m.call_args.kwargs.get("batch_size") == 100

    def test_timeout_returns_504(self, client, references_v2_db):
        async def raising_wait_for(coro, *args, **kwargs):
            del args, kwargs
            coro.close()
            raise TimeoutError

        with patch(
            "src.api.routes.reference_routes.asyncio.wait_for",
            side_effect=raising_wait_for,
        ):
            resp = client.post("/api/v1/references/resolve", json={})
        assert resp.status_code == 504
        body = resp.json()
        assert body["status"] == 504

    def test_audit_records_resolve_operation(self, client, references_v2_db):
        fake_result = {
            "resolved_count": 0,
            "still_unresolved_count": 0,
            "has_more": False,
        }
        captured: list[dict] = []

        def capture(**kwargs):
            captured.append(kwargs)

        with (
            patch(
                "src.api.routes.reference_routes._run_resolution",
                return_value=fake_result,
            ),
            patch(
                "src.api.middleware.audit._default_writer",
                side_effect=capture,
            ),
        ):
            resp = client.post("/api/v1/references/resolve", json={})
        assert resp.status_code == 200
        rows = [r for r in captured if r.get("path") == "/api/v1/references/resolve"]
        assert rows and rows[0]["operation"] == "references.resolve"
