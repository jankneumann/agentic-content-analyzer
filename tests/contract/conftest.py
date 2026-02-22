"""Shared fixtures for API contract and fuzz tests.

Provides:
- Schemathesis schema loaded directly from the FastAPI ASGI app
- Seeded test database with representative data across content types
- Auth headers injected into all generated requests

Contract tests run against the live app with a test database, validating
that responses conform to the OpenAPI schema and that fuzz inputs don't
cause 500 errors.

Uses Alembic migrations (not ORM metadata) for schema creation to ensure
the test database matches production exactly — including raw SQL columns
(search_vector, embedding), migration-only tables (pgqueuer_jobs), and
triggers that the ORM doesn't define.

Run:
    pytest tests/contract/ -m contract -v
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import schemathesis
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

# Ensure contract tests never boot embedded worker during app import/lifespan.
os.environ.setdefault("WORKER_ENABLED", "false")

from src.api.app import app
from src.models.audio_digest import AudioDigest  # noqa: F401
from src.models.content import ContentStatus
from src.models.settings import PromptOverride  # noqa: F401
from src.models.settings_override import SettingsOverride  # noqa: F401
from src.models.theme import ThemeAnalysis  # noqa: F401
from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.summary import SummaryFactory
from tests.helpers.test_db import create_test_engine, get_test_database_url

TEST_DATABASE_URL = get_test_database_url()

# Locate the alembic config relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"

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


def _reset_schema(engine) -> None:
    """Drop and recreate the public schema for a completely clean slate.

    More thorough than Base.metadata.drop_all() — also removes
    migration-only tables, triggers, functions, and extensions.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        conn.commit()


@pytest.fixture(scope="session")
def contract_db_engine():
    """Create test database via Alembic migrations (session-scoped).

    Uses Alembic instead of ORM metadata to ensure the test database
    matches production exactly — including raw SQL columns (search_vector,
    embedding), migration-only tables (pgqueuer_jobs), triggers, and
    indexes that the ORM doesn't define.
    """
    engine = create_test_engine(TEST_DATABASE_URL)

    # Clean slate: drop and recreate public schema
    _reset_schema(engine)

    # Run Alembic migrations against the test database.
    # Must use subprocess because alembic/env.py imports src.config.settings
    # at module level, caching the main DATABASE_URL. A fresh process with
    # DATABASE_URL pointing to the test DB avoids this.
    import subprocess

    # Override all provider-specific URL vars so settings.get_effective_database_url()
    # returns TEST_DATABASE_URL regardless of .env or profile configuration.
    env = {
        **os.environ,
        "DATABASE_URL": TEST_DATABASE_URL,
        "LOCAL_DATABASE_URL": TEST_DATABASE_URL,
        "NEON_DATABASE_URL": "",
        "SUPABASE_DIRECT_URL": "",
    }
    result = subprocess.run(
        ["alembic", "upgrade", "head"],  # noqa: S607
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stderr}\n{result.stdout}")

    yield engine

    _reset_schema(engine)
    engine.dispose()


@pytest.fixture
def contract_db_session(contract_db_engine) -> Session:
    """Create a database session with auto-savepoint isolation.

    Uses SQLAlchemy's ``after_transaction_end`` event to automatically
    restart savepoints whenever a route handler calls ``session.commit()``
    or ``session.rollback()``.  This keeps the session perpetually inside
    a savepoint so the outer transaction is never committed — allowing
    full rollback at the end of the test.
    """
    connection = contract_db_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    # Start the first savepoint — all subsequent ones are auto-created
    # by the event listener below.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # type: ignore[no-untyped-def]
        """Auto-restart a savepoint when one is committed or rolled back.

        This keeps the session always inside a SAVEPOINT, so route handlers
        that call session.commit() only release the current savepoint (not
        the outer test transaction).
        """
        if trans.nested and not trans._parent.nested:  # type: ignore[union-attr]
            sess.begin_nested()

    # Configure factories to use this session
    ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]

    yield session

    ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    event.remove(session, "after_transaction_end", _restart_savepoint)
    session.close()
    if transaction.is_active:
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
    """Create mock get_db context manager bound to the test session.

    Savepoint isolation is handled by the ``contract_db_session`` fixture's
    ``after_transaction_end`` event listener — the session is always inside
    a SAVEPOINT that is auto-restarted after each commit or rollback.

    If a route handler triggers a database error, we rollback the session
    (releasing the current savepoint) so the event listener can create a
    fresh one for the next request.
    """

    @contextmanager
    def mock_get_db():
        try:
            yield session
        except Exception:
            session.rollback()
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
