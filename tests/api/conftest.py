"""Shared fixtures for API endpoint tests.

Provides TestClient with test database integration for testing
FastAPI endpoints without hitting production database.

Test Database Isolation:
- Uses separate test database (newsletters_test)
- Transaction rollback after each test
- No impact on development/production database
"""

import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

# Ensure API tests never boot embedded worker during app import/lifespan.
os.environ.setdefault("WORKER_ENABLED", "false")

from src.api.app import app
from src.models.audio_digest import AudioDigest  # noqa: F401 - registers with Base.metadata
from src.models.base import Base
from src.models.content import ContentStatus
from src.models.podcast import (
    Podcast,
    PodcastScriptRecord,
    PodcastStatus,
)
from src.models.settings import PromptOverride  # noqa: F401 - registers with Base.metadata
from src.models.settings_override import (
    SettingsOverride,  # noqa: F401 - registers with Base.metadata
)
from src.models.theme import ThemeAnalysis  # noqa: F401 - registers with Base.metadata
from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.podcast import PodcastFactory, PodcastScriptRecordFactory
from tests.factories.summary import SummaryFactory
from tests.helpers.test_db import create_test_engine, get_test_database_url

# Worktree-aware test database URL (shared helper handles detection)
TEST_DATABASE_URL = get_test_database_url()


@pytest.fixture(autouse=True)
def api_test_env(monkeypatch):
    """Set up environment variables required for API tests.

    This sets ADMIN_API_KEY which is required by the settings routes
    to allow authenticated access.
    """
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    # API tests validate routes; they do not need embedded worker startup.
    monkeypatch.setenv("WORKER_ENABLED", "false")

    # Clear settings cache to pick up the new env var
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine.

    Uses shared helper for worktree-aware DB naming and auto-creation.
    Drops and recreates all tables at session start for clean state.
    """
    engine = create_test_engine(TEST_DATABASE_URL)

    # Drop all tables first for clean state (handles interrupted previous runs)
    Base.metadata.drop_all(engine)

    # Create all tables fresh
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Drop all tables after all tests complete
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test with transaction rollback.

    Each test gets a fresh session. Changes are rolled back after test completes.
    Also configures Factory Boy to use this session for model creation.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    # Configure factories to use this session
    ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    PodcastScriptRecordFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    PodcastFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]

    yield session

    # Cleanup: Reset factory sessions, rollback transaction, close connection
    ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    PodcastScriptRecordFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    PodcastFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    session.close()
    transaction.rollback()
    connection.close()


class AuthenticatedTestClient:
    """Wrapper around TestClient that adds admin auth headers to mutating requests."""

    def __init__(self, client: TestClient, admin_key: str):
        self._client = client
        self._admin_key = admin_key

    def _add_auth_headers(self, kwargs):
        """Add admin auth header for requests that need it."""
        headers = kwargs.get("headers", {})
        if "X-Admin-Key" not in headers:
            headers["X-Admin-Key"] = self._admin_key
        kwargs["headers"] = headers
        return kwargs

    def get(self, *args, **kwargs):
        kwargs = self._add_auth_headers(kwargs)
        return self._client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        kwargs = self._add_auth_headers(kwargs)
        return self._client.post(*args, **kwargs)

    def put(self, *args, **kwargs):
        kwargs = self._add_auth_headers(kwargs)
        return self._client.put(*args, **kwargs)

    def delete(self, *args, **kwargs):
        kwargs = self._add_auth_headers(kwargs)
        return self._client.delete(*args, **kwargs)

    def patch(self, *args, **kwargs):
        kwargs = self._add_auth_headers(kwargs)
        return self._client.patch(*args, **kwargs)

    def stream(self, *args, **kwargs):
        """Pass through to underlying client's stream method."""
        return self._client.stream(*args, **kwargs)

    def __getattr__(self, name):
        """Delegate unknown attributes to the underlying client."""
        return getattr(self._client, name)


@pytest.fixture
def client(db_session) -> Generator[AuthenticatedTestClient, None, None]:
    """Create FastAPI TestClient with test database override and admin auth.

    Patches get_db in all route modules to use the test database session,
    ensuring all API operations use the test database with transaction rollback.

    PUT, DELETE, and PATCH requests automatically include the X-Admin-Key header.
    """
    from contextlib import ExitStack
    from unittest.mock import patch

    @contextmanager
    def mock_get_db():
        """Return the test's db_session."""
        yield db_session

    # All route/service modules that import get_db and need the test session
    db_patch_targets = [
        "src.api.audio_digest_routes.get_db",
        "src.api.summary_routes.get_db",
        "src.api.digest_routes.get_db",
        "src.api.podcast_routes.get_db",
        "src.api.script_routes.get_db",
        "src.api.chat_routes.get_db",
        "src.api.settings_routes.get_db",
        "src.api.settings_override_routes.get_db",
        "src.api.model_settings_routes.get_db",
        "src.api.voice_settings_routes.get_db",
        "src.api.content_routes.get_db",
        "src.api.source_routes.get_db",
        "src.api.upload_routes.get_db",
        "src.api.save_routes.get_db",
        "src.api.search_routes.get_db",
        "src.api.share_routes.get_db",
        "src.api.shared_routes.get_db",
        "src.api.image_generation_routes.get_db",
        "src.services.script_review_service.get_db",
        "src.processors.theme_analyzer.get_db",
    ]

    # Use ExitStack to avoid exceeding Python's static nesting limit (20)
    with ExitStack() as stack:
        for target in db_patch_targets:
            stack.enter_context(patch(target, mock_get_db))
        with TestClient(app) as test_client:
            yield AuthenticatedTestClient(test_client, "test-admin-key")


# ==============================================================================
# Sample Data Fixtures (using Factory Boy)
# ==============================================================================


@pytest.fixture
def sample_summary(db_session, sample_content):
    """Create a single sample summary linked to content."""
    summary = SummaryFactory(
        content=sample_content,
        executive_summary="Major LLM advances including cost reduction.",
        key_themes=["LLM Performance", "Cost Optimization"],
        strategic_insights=["LLM costs decreasing enables broader adoption"],
        technical_details=["Context windows expanded to 1M tokens"],
        actionable_items=["Evaluate new pricing"],
        notable_quotes=["Context is king in AI"],
        relevance_scores={
            "cto_leadership": 0.9,
            "technical_teams": 0.85,
            "individual_developers": 0.7,
        },
        agent_framework="claude",
        model_version="20250929",
        token_usage=2500,
        processing_time_seconds=3.5,
    )

    # Update content status to reflect it has been summarized
    sample_content.status = ContentStatus.COMPLETED
    db_session.commit()
    db_session.refresh(summary)
    return summary


@pytest.fixture
def sample_summaries(db_session, sample_contents):
    """Create multiple sample summaries linked to contents."""
    summaries = [
        SummaryFactory(
            content=sample_contents[0],
            executive_summary="Major LLM advances summary.",
            key_themes=["LLM Performance", "Cost Optimization"],
            strategic_insights=["LLM costs decreasing"],
            technical_details=["Context windows expanded"],
            actionable_items=["Evaluate new pricing"],
            notable_quotes=["Context is king"],
            relevance_scores={"cto_leadership": 0.9, "technical_teams": 0.85},
            agent_framework="claude",
            token_usage=2500,
            processing_time_seconds=3.5,
        ),
        SummaryFactory(
            content=sample_contents[1],
            executive_summary="Vector database performance summary.",
            key_themes=["Vector Search", "Performance"],
            strategic_insights=["Database selection critical"],
            technical_details=["Hybrid search combining vector and keyword"],
            actionable_items=["Benchmark databases"],
            notable_quotes=["Performance matters"],
            relevance_scores={"cto_leadership": 0.6, "technical_teams": 0.95},
            agent_framework="claude",
            token_usage=2200,
            processing_time_seconds=3.2,
        ),
    ]

    return summaries


@pytest.fixture
def sample_digest(db_session):
    """Create a single sample digest in the test database."""
    return DigestFactory(
        daily=True,
        pending_review=True,
        period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
        period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
        title="Test Daily Digest",
        executive_overview="Test executive overview of AI developments.",
        strategic_insights=[
            {
                "title": "Strategic Insight 1",
                "summary": "LLM costs decreasing",
                "details": ["Detail 1", "Detail 2"],
                "themes": ["Cost", "Efficiency"],
            }
        ],
        technical_developments=[
            {
                "title": "Technical Development 1",
                "summary": "Vector DB performance",
                "details": ["Benchmark 1"],
                "themes": ["Performance"],
            }
        ],
        emerging_trends=[
            {
                "title": "Emerging Trend 1",
                "summary": "AI agents are evolving",
                "details": ["Trend detail"],
                "themes": ["AI Agents"],
            }
        ],
        actionable_recommendations={
            "leadership": ["Review AI strategy"],
            "technical": ["Evaluate new tools"],
        },
        sources=[{"content_id": 1, "title": "AI Weekly"}],
        newsletter_count=3,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )


@pytest.fixture
def sample_digests(db_session):
    """Create multiple sample digests in the test database."""
    return [
        DigestFactory(
            daily=True,
            pending_review=True,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Daily Digest 1",
            executive_overview="Daily overview.",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=3,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        ),
        DigestFactory(
            weekly=True,
            approved=True,
            period_start=datetime(2025, 1, 8, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Weekly Digest 1",
            executive_overview="Weekly overview.",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=10,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        ),
    ]


@pytest.fixture
def sample_script(db_session, sample_digest) -> PodcastScriptRecord:
    """Create a single sample podcast script in the test database."""
    script = PodcastScriptRecord(
        digest_id=sample_digest.id,
        title="Test Podcast Script",
        length="standard",
        word_count=1500,
        estimated_duration_seconds=600,
        status=PodcastStatus.SCRIPT_PENDING_REVIEW.value,
        script_json={
            "title": "Test Podcast Script",
            "length": "standard",
            "sections": [
                {
                    "section_type": "intro",
                    "title": "Introduction",
                    "dialogue": [
                        {"speaker": "Alex", "text": "Welcome to the podcast."},
                        {"speaker": "Sam", "text": "Great to be here!"},
                    ],
                    "sources_cited": [],
                },
                {
                    "section_type": "strategic",
                    "title": "Main Discussion",
                    "dialogue": [
                        {"speaker": "Alex", "text": "Let's discuss AI developments."},
                        {"speaker": "Sam", "text": "Sounds good!"},
                    ],
                    "sources_cited": [],
                },
            ],
            "word_count": 1500,
            "estimated_duration_seconds": 600,
            "sources_summary": [],
        },
        model_used="claude-sonnet-4-5",
    )
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)
    return script


@pytest.fixture
def sample_podcast(db_session, sample_script) -> Podcast:
    """Create a single sample podcast in the test database."""
    # First approve the script
    sample_script.status = PodcastStatus.SCRIPT_APPROVED.value
    sample_script.approved_at = datetime.now(UTC)
    db_session.commit()

    podcast = Podcast(
        script_id=sample_script.id,
        audio_format="mp3",
        voice_provider="openai_tts",
        alex_voice="alex_male",
        sam_voice="sam_female",
        status="completed",
        duration_seconds=600,
        file_size_bytes=1024000,
        audio_url="/tmp/test_podcast.mp3",  # noqa: S108 - test fixture path
    )
    db_session.add(podcast)
    db_session.commit()
    db_session.refresh(podcast)
    return podcast


# ==============================================================================
# Content Model Fixtures (using Factory Boy)
# ==============================================================================


@pytest.fixture
def sample_content(db_session):
    """Create a single sample content in the test database."""
    return ContentFactory(
        gmail=True,
        parsed=True,
        source_id="test-content-001",
        source_url="https://example.com/content1",
        title="LLM Advances Newsletter",
        author="AI Weekly Team",
        publication="AI Weekly",
        published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        markdown_content="# LLM Advances\n\nContent about LLM advances and new models.",
        raw_content="<html><body>Newsletter about LLM advances...</body></html>",
        content_hash="abc123hash",
    )


@pytest.fixture
def sample_contents(db_session):
    """Create multiple sample contents in the test database."""
    return [
        ContentFactory(
            gmail=True,
            parsed=True,
            source_id="test-content-001",
            source_url="https://example.com/content1",
            title="LLM Advances Newsletter",
            author="AI Weekly Team",
            publication="AI Weekly",
            published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
            markdown_content="# LLM Advances\n\nContent about LLM advances.",
            content_hash="hash001",
        ),
        ContentFactory(
            rss=True,
            source_id="test-content-002",
            source_url="https://example.com/content2",
            title="Vector Database Guide",
            author="Data Engineering",
            publication="Data Weekly",
            published_date=datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC),
            markdown_content="# Vector Databases\n\nGuide to vector databases.",
            content_hash="hash002",
            status=ContentStatus.COMPLETED,
        ),
        ContentFactory(
            youtube=True,
            parsed=True,
            source_id="test-video-003",
            source_url="https://youtube.com/watch?v=test123",
            title="AI Agents Tutorial",
            author="Tech Channel",
            publication="Tech Channel",
            published_date=datetime(2025, 1, 13, 10, 0, 0, tzinfo=UTC),
            markdown_content="# AI Agents Tutorial\n\n[00:00](https://youtube.com/watch?v=test123&t=0) Introduction",
            metadata_json={"video_id": "test123", "channel": "Tech Channel"},
            content_hash="hash003",
        ),
    ]


@pytest.fixture
def sample_content_with_summary(db_session, sample_content):
    """Create a content with an associated summary."""
    summary = SummaryFactory(
        content=sample_content,
        executive_summary="Major LLM advances including cost reduction.",
        key_themes=["LLM Performance", "Cost Optimization"],
        strategic_insights=["LLM costs decreasing enables broader adoption"],
        technical_details=["Context windows expanded to 1M tokens"],
        actionable_items=["Evaluate new pricing"],
        notable_quotes=["Context is king in AI"],
        relevance_scores={
            "cto_leadership": 0.9,
            "technical_teams": 0.85,
            "individual_developers": 0.7,
        },
        markdown_content="# Newsletter Summary\n\n## Executive Summary\nMajor LLM advances.",
        theme_tags=["llm", "cost-optimization", "performance"],
        agent_framework="claude",
        model_version="20250929",
        token_usage=2500,
        processing_time_seconds=3.5,
    )

    sample_content.status = ContentStatus.COMPLETED
    sample_content.processed_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(summary)
    db_session.refresh(sample_content)

    return sample_content, summary
