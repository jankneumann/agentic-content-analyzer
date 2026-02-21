"""Shared fixtures for API contract and fuzz tests.

Provides:
- Schemathesis schema loaded directly from the FastAPI ASGI app
- Seeded test database with representative data across content types
- Auth headers injected into all generated requests

Contract tests run against the live app with a test database, validating
that responses conform to the OpenAPI schema and that fuzz inputs don't
cause 500 errors.

Run:
    pytest tests/contract/ -m contract -v
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import schemathesis
from sqlalchemy.orm import Session, sessionmaker

# Ensure contract tests never boot embedded worker during app import/lifespan.
os.environ.setdefault("WORKER_ENABLED", "false")

from src.api.app import app
from src.models.audio_digest import AudioDigest  # noqa: F401
from src.models.base import Base
from src.models.content import ContentStatus
from src.models.settings import PromptOverride  # noqa: F401
from src.models.settings_override import SettingsOverride  # noqa: F401
from src.models.theme import ThemeAnalysis  # noqa: F401
from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.summary import SummaryFactory
from tests.helpers.test_db import create_test_engine, get_test_database_url

TEST_DATABASE_URL = get_test_database_url()

# ---------------------------------------------------------------------------
# Shared endpoint exclusion patterns used by both conformance and fuzz tests.
# SSE streaming endpoints return text/event-stream, binary endpoints serve
# files, and the OTEL proxy forwards raw OTLP payloads — none of these can
# be validated against JSON response schemas.
# ---------------------------------------------------------------------------
EXCLUDED_COMMON_PATHS: list[str] = [
    # SSE streaming endpoints (return text/event-stream, not JSON)
    r"/api/v1/contents/ingest/status/",
    r"/api/v1/contents/summarize/status/",
    r"/api/v1/content/\{content_id\}/status",
    r"/api/v1/chat/conversations/\{conversation_id\}/messages",
    r"/api/v1/chat/conversations/\{conversation_id\}/regenerate",
    r"/api/v1/summaries/preview",
    # Binary file serving / audio streaming
    r"/api/v1/files/",
    r"/api/v1/podcasts/\{podcast_id\}/audio",
    r"/api/v1/audio-digests/\{audio_digest_id\}/stream",
    # OTEL proxy
    r"/api/v1/otel/",
    # Requires Neo4j
    r"/api/v1/settings/connections",
]


@pytest.fixture(autouse=True)
def contract_test_env(monkeypatch):
    """Set up environment variables required for contract tests."""
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")

    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def contract_db_engine():
    """Create test database engine for contract tests (session-scoped)."""
    engine = create_test_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def contract_db_session(contract_db_engine) -> Session:
    """Create a database session with transaction rollback for contract tests."""
    connection = contract_db_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    # Configure factories to use this session
    ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]

    yield session

    ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def seeded_db(contract_db_session):
    """Seed the database with representative content for contract testing.

    Creates content records across different source types (gmail, rss, youtube)
    with associated summaries and a digest, so GET endpoints return real data
    and Schemathesis can validate response shapes against the schema.
    """
    session = contract_db_session

    # Create content from different sources
    c1 = ContentFactory(
        gmail=True,
        parsed=True,
        source_id="contract-test-001",
        source_url="https://example.com/newsletter-1",
        title="AI Weekly: Contract Test Edition",
        author="AI Weekly Team",
        publication="AI Weekly",
        published_date=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        markdown_content="# AI Weekly\n\nTransformers continue to evolve.",
        content_hash="contract_hash_001",
    )
    c2 = ContentFactory(
        rss=True,
        source_id="contract-test-002",
        source_url="https://example.com/rss-article-2",
        title="Vector Search Performance Guide",
        author="Data Engineering",
        publication="Data Weekly",
        published_date=datetime(2025, 5, 15, 10, 0, 0, tzinfo=UTC),
        markdown_content="# Vector Search\n\nPgvector vs Pinecone benchmarks.",
        content_hash="contract_hash_002",
        status=ContentStatus.COMPLETED,
    )
    c3 = ContentFactory(
        youtube=True,
        parsed=True,
        source_id="contract-test-003",
        source_url="https://youtube.com/watch?v=contract123",
        title="AI Agents Deep Dive",
        author="Tech Channel",
        publication="Tech Channel",
        published_date=datetime(2025, 7, 1, 10, 0, 0, tzinfo=UTC),
        markdown_content="# AI Agents\n\nAutonomous agents overview.",
        content_hash="contract_hash_003",
    )
    session.flush()

    # Create summaries for completed content
    SummaryFactory(
        content=c1,
        executive_summary="AI advances in transformer architectures.",
        key_themes=["Transformers", "NLP"],
        strategic_insights=["Transformer efficiency improving"],
        technical_details=["Context windows expanding"],
        actionable_items=["Evaluate new models"],
        notable_quotes=["Transformers changed everything"],
        relevance_scores={"cto_leadership": 0.9, "technical_teams": 0.85},
        agent_framework="claude",
        token_usage=2500,
        processing_time_seconds=3.5,
    )

    # Update content status
    c1.status = ContentStatus.COMPLETED

    # Create a digest
    DigestFactory(
        daily=True,
        pending_review=True,
        period_start=datetime(2025, 6, 1, 0, 0, 0, tzinfo=UTC),
        period_end=datetime(2025, 6, 1, 23, 59, 59, tzinfo=UTC),
        title="Contract Test Daily Digest",
        executive_overview="Test digest for contract validation.",
        strategic_insights=[],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        sources=[{"content_id": c1.id, "title": c1.title}],
        newsletter_count=3,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )

    session.commit()
    return session


def _make_db_patcher(session):
    """Create mock get_db context manager with savepoint isolation.

    Uses PostgreSQL SAVEPOINTs so that if one Schemathesis-generated request
    triggers a database error (e.g., invalid enum value), subsequent requests
    in the same Hypothesis test case still get a clean transaction state.
    """

    @contextmanager
    def mock_get_db():
        nested = session.begin_nested()
        try:
            yield session
        except Exception:
            nested.rollback()
            raise
        else:
            try:
                nested.commit()
            except Exception:
                nested.rollback()
                raise

    return mock_get_db


@pytest.fixture
def contract_schema(seeded_db):
    """Load Schemathesis schema from the FastAPI ASGI app with DB patching.

    Patches get_db across all route modules so Schemathesis-generated
    requests hit the test database with seeded data.
    """
    mock_get_db = _make_db_patcher(seeded_db)

    with (
        # Source-level patch — catches lazy imports inside service methods
        # (e.g., PromptService._get_override_from_db, SettingsService._get_override_from_db)
        # that do `from src.storage.database import get_db` at call time.
        patch("src.storage.database.get_db", mock_get_db),
        # Route-level patches — each route module has already imported get_db
        # at module load time, so the source patch alone doesn't cover them.
        patch("src.api.audio_digest_routes.get_db", mock_get_db),
        patch("src.api.summary_routes.get_db", mock_get_db),
        patch("src.api.digest_routes.get_db", mock_get_db),
        patch("src.api.podcast_routes.get_db", mock_get_db),
        patch("src.api.script_routes.get_db", mock_get_db),
        patch("src.api.chat_routes.get_db", mock_get_db),
        patch("src.api.settings_routes.get_db", mock_get_db),
        patch("src.api.settings_override_routes.get_db", mock_get_db),
        patch("src.api.model_settings_routes.get_db", mock_get_db),
        patch("src.api.voice_settings_routes.get_db", mock_get_db),
        patch("src.api.content_routes.get_db", mock_get_db),
        patch("src.api.source_routes.get_db", mock_get_db),
        patch("src.api.upload_routes.get_db", mock_get_db),
        patch("src.api.save_routes.get_db", mock_get_db),
        patch("src.api.search_routes.get_db", mock_get_db),
        patch("src.services.script_review_service.get_db", mock_get_db),
        patch("src.processors.theme_analyzer.get_db", mock_get_db),
    ):
        schema = schemathesis.openapi.from_asgi("/openapi.json", app)
        yield schema
