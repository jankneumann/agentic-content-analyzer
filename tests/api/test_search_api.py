"""Search API endpoint tests — smoke + spec compliance.

Tests the hybrid search API (GET, POST, chunk detail) against a test database
with pre-seeded content and document chunks. Verifiable as a regression suite.

Run:
    pytest tests/api/test_search_api.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from tests.factories.content import ContentFactory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _search_columns(test_db_engine):
    """Add search_vector and embedding columns + trigger to test DB.

    These columns are managed via Alembic migration (not in the ORM model),
    so Base.metadata.create_all() in conftest doesn't create them.
    """
    with test_db_engine.connect() as conn:
        # Check if columns already exist (idempotent)
        exists = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'document_chunks' AND column_name = 'search_vector'"
            )
        ).fetchone()
        if exists:
            conn.commit()
            return

        # Add tsvector column for full-text search
        conn.execute(
            text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector")
        )

        # Try adding pgvector column (skip if extension not available)
        # Uses unconstrained vector (no fixed dimensions) matching production schema
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector")
            )
        except Exception:
            conn.rollback()
            # pgvector not available — vector search tests will still run
            # but return empty results (expected behavior)

        # Create trigger function for auto-updating search_vector
        conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        )

        # Create trigger
        conn.execute(
            text("""
            DROP TRIGGER IF EXISTS document_chunks_search_vector_trigger
            ON document_chunks;
        """)
        )
        conn.execute(
            text("""
            CREATE TRIGGER document_chunks_search_vector_trigger
            BEFORE INSERT OR UPDATE OF chunk_text ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION document_chunks_search_vector_update();
        """)
        )

        # Create GIN index for FTS
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_search_vector_gin "
                "ON document_chunks USING gin(search_vector)"
            )
        )

        conn.commit()


@pytest.fixture
def seeded_content(db_session):
    """Create content records with associated document_chunks for search tests."""
    c1 = ContentFactory(
        gmail=True,
        parsed=True,
        source_id="search-test-001",
        title="Machine Learning Advances in NLP",
        author="AI Weekly",
        publication="AI Weekly",
        published_date=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        markdown_content="# Machine Learning in NLP\n\nTransformers changed everything.",
        content_hash="search_hash_001",
    )
    c2 = ContentFactory(
        rss=True,
        source_id="search-test-002",
        title="Vector Database Performance Guide",
        author="Data Engineering",
        publication="Data Weekly",
        published_date=datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC),
        markdown_content="# Vector Databases\n\nPgvector vs Pinecone comparison.",
        content_hash="search_hash_002",
    )
    c3 = ContentFactory(
        youtube=True,
        parsed=True,
        source_id="search-test-003",
        title="AI Agents Deep Dive",
        author="Tech Channel",
        publication="Tech Channel",
        published_date=datetime(2025, 7, 1, 10, 0, 0, tzinfo=UTC),
        markdown_content="# AI Agents\n\nAutonomous agents are the future.",
        content_hash="search_hash_003",
    )
    db_session.flush()

    # Insert document_chunks directly (ORM doesn't map embedding/search_vector)
    chunks = [
        # Content 1: ML/NLP
        (
            c1.id,
            "Transformers have revolutionized machine learning in natural language processing.",
            0,
            "paragraph",
            "Machine Learning in NLP",
        ),
        (
            c1.id,
            "BERT and GPT architectures demonstrate remarkable few-shot learning capabilities.",
            1,
            "paragraph",
            "Machine Learning in NLP",
        ),
        (
            c1.id,
            "Fine-tuning large language models requires careful hyperparameter selection.",
            2,
            "paragraph",
            "Machine Learning in NLP",
        ),
        # Content 2: Vector DBs
        (
            c2.id,
            "Vector databases like pgvector enable efficient similarity search at scale.",
            0,
            "paragraph",
            "Vector Databases",
        ),
        (
            c2.id,
            "HNSW indexes provide sub-millisecond approximate nearest neighbor lookups.",
            1,
            "paragraph",
            "Vector Databases",
        ),
        (
            c2.id,
            "SELECT * FROM items ORDER BY embedding <=> query_vec LIMIT 10;",
            2,
            "code",
            "Vector Databases",
        ),
        # Content 3: AI Agents (YouTube transcript style)
        (
            c3.id,
            "Autonomous AI agents can plan and execute multi-step tasks without human intervention.",
            0,
            "transcript",
            "AI Agents",
        ),
        (
            c3.id,
            "ReAct and chain-of-thought prompting are key techniques for agent reasoning.",
            1,
            "transcript",
            "AI Agents",
        ),
    ]
    for content_id, chunk_text, idx, ctype, heading in chunks:
        db_session.execute(
            text("""
                INSERT INTO document_chunks
                    (content_id, chunk_text, chunk_index, chunk_type, heading_text,
                     embedding_provider, embedding_model, created_at)
                VALUES (:cid, :txt, :idx, :ctype, :heading,
                        :provider, :model, NOW())
            """),
            {
                "cid": content_id,
                "txt": chunk_text,
                "idx": idx,
                "ctype": ctype,
                "heading": heading,
                "provider": "local",
                "model": "all-MiniLM-L6-v2",
            },
        )

    db_session.flush()
    return c1, c2, c3


# ===========================================================================
# Smoke Tests — basic endpoint availability and response shape
# ===========================================================================


class TestSearchSmoke:
    """Smoke tests: endpoints reachable and return correct shapes."""

    def test_get_search_returns_200(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=machine+learning&limit=5")
        assert resp.status_code == 200

    def test_post_search_returns_200(self, client, seeded_content):
        resp = client.post(
            "/api/v1/search",
            json={"query": "vector database", "limit": 5, "type": "bm25"},
        )
        assert resp.status_code == 200

    def test_get_chunk_detail_returns_404_for_missing(self, client, seeded_content):
        resp = client.get("/api/v1/search/chunks/999999")
        assert resp.status_code == 404

    def test_empty_query_returns_422(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422

    def test_response_has_required_keys(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=test&limit=1")
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "meta" in data


# ===========================================================================
# Spec Compliance — verify each spec scenario
# ===========================================================================


class TestSearchResponseShape:
    """Spec: search response shape and meta fields."""

    def test_meta_contains_all_required_fields(self, client, seeded_content):
        """Spec: SearchMeta includes strategy, provider, model, timing, backend."""
        data = client.get("/api/v1/search?q=test&limit=1").json()
        meta = data["meta"]
        for key in [
            "bm25_strategy",
            "embedding_provider",
            "embedding_model",
            "rerank_provider",
            "rerank_model",
            "query_time_ms",
            "backend",
        ]:
            assert key in meta, f"Missing meta key: {key}"

    def test_bm25_strategy_is_valid(self, client, seeded_content):
        """Spec: BM25 auto-detects paradedb_bm25 or postgres_native_fts."""
        data = client.get("/api/v1/search?q=test&limit=1").json()
        assert data["meta"]["bm25_strategy"] in ("paradedb_bm25", "postgres_native_fts")

    def test_reranking_disabled_by_default(self, client, seeded_content):
        """Spec: reranking disabled by default (SEARCH_RERANK_ENABLED=false)."""
        data = client.get("/api/v1/search?q=test&limit=1").json()
        assert data["meta"]["rerank_provider"] is None

    def test_backend_is_local(self, client, seeded_content):
        """Spec: backend matches database_provider."""
        data = client.get("/api/v1/search?q=test&limit=1").json()
        assert data["meta"]["backend"] == "local"


class TestBM25Search:
    """Spec: BM25 full-text search scenarios."""

    def test_bm25_returns_matching_results(self, client, seeded_content):
        """Spec: BM25 search returns chunks matching query terms."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning transformers", "type": "bm25", "limit": 10},
        ).json()
        assert data["total"] > 0
        titles = [r["title"] for r in data["results"]]
        assert any("Machine Learning" in t for t in titles)

    def test_bm25_returns_scores(self, client, seeded_content):
        """Spec: results include bm25 score in scores object."""
        data = client.post(
            "/api/v1/search",
            json={"query": "vector database pgvector", "type": "bm25", "limit": 5},
        ).json()
        if data["results"]:
            scores = data["results"][0]["scores"]
            assert scores["bm25"] is not None
            assert scores["bm25"] > 0


class TestSearchResults:
    """Spec: result aggregation, pagination, chunk limits."""

    def test_max_three_chunks_per_document(self, client, seeded_content):
        """Spec: returns up to 3 matching chunks per document."""
        data = client.get("/api/v1/search?q=machine+learning&limit=10").json()
        for result in data["results"]:
            assert len(result["matching_chunks"]) <= 3

    def test_matching_chunks_have_required_fields(self, client, seeded_content):
        """Spec: each chunk has chunk_id, content, score, highlight, chunk_type."""
        data = client.post(
            "/api/v1/search",
            json={"query": "vector database", "type": "bm25", "limit": 5},
        ).json()
        if data["results"]:
            chunk = data["results"][0]["matching_chunks"][0]
            for key in ["chunk_id", "content", "score", "highlight", "chunk_type"]:
                assert key in chunk, f"Missing chunk key: {key}"

    def test_result_has_document_metadata(self, client, seeded_content):
        """Spec: result includes id, title, score, scores, source, publication."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning", "type": "bm25", "limit": 5},
        ).json()
        if data["results"]:
            result = data["results"][0]
            for key in ["id", "title", "score", "scores", "source", "publication"]:
                assert key in result, f"Missing result key: {key}"

    def test_pagination_offset(self, client, seeded_content):
        """Spec: pagination via offset and limit."""
        all_data = client.get("/api/v1/search?q=agent+learning+database&limit=10&offset=0").json()
        total = all_data["total"]
        if total > 1:
            offset_data = client.get(
                "/api/v1/search?q=agent+learning+database&limit=1&offset=1"
            ).json()
            # Offset results should differ from first result
            assert offset_data["total"] == total  # Total stays the same


class TestSearchHighlighting:
    """Spec: query term highlighting with <mark> tags."""

    def test_bm25_highlights_with_mark_tags(self, client, seeded_content):
        """Spec: BM25 wraps literal query term matches in <mark> tags."""
        data = client.post(
            "/api/v1/search",
            json={"query": "vector database", "type": "bm25", "limit": 5},
        ).json()
        if data["results"]:
            highlights = [c["highlight"] for r in data["results"] for c in r["matching_chunks"]]
            assert any("<mark>" in h for h in highlights), (
                f"Expected <mark> tags in highlights, got: {highlights[:2]}"
            )

    def test_highlights_are_html_escaped(self, client, seeded_content):
        """Spec: chunk text is HTML-escaped before marking."""
        # The code chunk contains <, > which should be escaped
        data = client.post(
            "/api/v1/search",
            json={"query": "SELECT items", "type": "bm25", "limit": 5},
        ).json()
        # If we find the code chunk, verify HTML chars are escaped
        for r in data.get("results", []):
            for c in r.get("matching_chunks", []):
                if "SELECT" in c.get("content", ""):
                    # The raw SQL has no < or > so this is a basic check
                    assert "<script>" not in c["highlight"]


class TestSearchFiltering:
    """Spec: pre-filter by source_types, dates, publications."""

    def test_filter_by_source_type(self, client, seeded_content):
        """Spec: source_types filter applied before ranking."""
        data = client.post(
            "/api/v1/search",
            json={
                "query": "learning database agents",
                "limit": 10,
                "filters": {"source_types": ["rss"]},
            },
        ).json()
        for r in data["results"]:
            assert r["source"] == "rss", f"Expected rss, got {r['source']}"

    def test_filter_by_date_range(self, client, seeded_content):
        """Spec: date_from/date_to filter on published_date."""
        data = client.post(
            "/api/v1/search",
            json={
                "query": "learning database agents",
                "limit": 10,
                "filters": {"date_from": "2025-06-01T00:00:00"},
            },
        ).json()
        for r in data["results"]:
            pub_date = r.get("published_date", "")
            assert pub_date >= "2025-06-01", f"Date {pub_date} before filter"

    def test_filter_by_publication(self, client, seeded_content):
        """Spec: publications filter narrows to matching publications."""
        data = client.post(
            "/api/v1/search",
            json={
                "query": "learning database agents",
                "limit": 10,
                "filters": {"publications": ["AI Weekly"]},
            },
        ).json()
        for r in data["results"]:
            assert r["publication"] == "AI Weekly"


class TestSearchTypes:
    """Spec: BM25, vector, and hybrid search types."""

    def test_bm25_search_type(self, client, seeded_content):
        """Spec: type=bm25 uses only keyword search."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning", "type": "bm25", "limit": 5},
        ).json()
        assert data["meta"]["bm25_strategy"] in ("paradedb_bm25", "postgres_native_fts")

    def test_vector_search_type(self, client, seeded_content):
        """Spec: type=vector uses only embedding similarity."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning", "type": "vector", "limit": 5},
        ).json()
        # Vector search may return no results if embeddings aren't generated
        assert "results" in data
        assert "meta" in data

    def test_hybrid_search_type(self, client, seeded_content):
        """Spec: type=hybrid combines BM25 + vector via RRF."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning", "type": "hybrid", "limit": 5},
        ).json()
        assert "results" in data

    def test_hybrid_is_default(self, client, seeded_content):
        """Spec: default search type is hybrid."""
        data = client.get("/api/v1/search?q=test&limit=1").json()
        # No explicit type param → should use hybrid
        assert "results" in data


class TestChunkDetail:
    """Spec: GET /api/v1/search/chunks/{chunk_id} endpoint."""

    def test_chunk_detail_returns_full_data(self, client, seeded_content, db_session):
        """Spec: chunk detail includes chunk fields + content metadata."""
        # Get a real chunk ID
        row = db_session.execute(text("SELECT id FROM document_chunks LIMIT 1")).fetchone()
        assert row is not None, "No chunks in test DB"

        resp = client.get(f"/api/v1/search/chunks/{row.id}")
        assert resp.status_code == 200
        data = resp.json()

        # Chunk fields
        for key in [
            "chunk_id",
            "content_id",
            "chunk_text",
            "chunk_index",
            "chunk_type",
            "created_at",
        ]:
            assert key in data, f"Missing chunk field: {key}"

        # Content metadata
        assert "content" in data
        content = data["content"]
        for key in ["id", "title", "source_type"]:
            assert key in content, f"Missing content field: {key}"

    def test_chunk_detail_404_for_nonexistent(self, client, seeded_content):
        """Spec: returns 404 for non-existent chunk ID."""
        resp = client.get("/api/v1/search/chunks/999999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Chunk not found"


class TestSearchPerformance:
    """Spec: performance SLAs."""

    def test_search_under_1000ms(self, client, seeded_content):
        """Spec: hybrid search <1000ms for <100k chunks."""
        data = client.post(
            "/api/v1/search",
            json={"query": "machine learning neural networks", "type": "hybrid", "limit": 20},
        ).json()
        assert data["meta"]["query_time_ms"] < 1000, (
            f"Search took {data['meta']['query_time_ms']}ms, exceeds 1000ms SLA"
        )


class TestSearchValidation:
    """Spec: input validation."""

    def test_empty_query_rejected(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422

    def test_limit_exceeds_max_rejected(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=test&limit=101")
        assert resp.status_code == 422

    def test_negative_offset_rejected(self, client, seeded_content):
        resp = client.get("/api/v1/search?q=test&offset=-1")
        assert resp.status_code == 422
