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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.app import app
from src.config.models import MODEL_REGISTRY
from src.models.audio_digest import AudioDigest  # noqa: F401 - registers with Base.metadata
from src.models.base import Base
from src.models.content import Content, ContentSource, ContentStatus
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.podcast import (
    Podcast,
    PodcastScriptRecord,
    PodcastStatus,
)
from src.models.settings import PromptOverride  # noqa: F401 - registers with Base.metadata
from src.models.summary import Summary
from src.models.theme import ThemeAnalysis  # noqa: F401 - registers with Base.metadata

# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://newsletter_user:newsletter_password@localhost/newsletters_test",
)


@pytest.fixture(autouse=True)
def api_test_env(monkeypatch):
    """Set up environment variables required for API tests.

    This sets ADMIN_API_KEY which is required by the settings routes
    to allow authenticated access.
    """
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

    # Clear settings cache to pick up the new env var
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine.

    Uses newsletters_test database (separate from development).
    Drops and recreates all tables at session start for clean state.
    This handles interrupted previous runs that left stale data.
    """
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Verify we're using test database (safety check)
    db_name = engine.url.database
    if not db_name or "test" not in db_name.lower():
        raise ValueError(
            f"Safety check failed: Database '{db_name}' does not contain 'test'. "
            f"Set TEST_DATABASE_URL to a test database to proceed."
        )

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
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    # Cleanup: Rollback transaction and close connection
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
    from unittest.mock import patch

    @contextmanager
    def mock_get_db():
        """Return the test's db_session."""
        yield db_session

    # Patch get_db in all route modules and services that use it directly
    with (
        patch("src.api.audio_digest_routes.get_db", mock_get_db),
        patch("src.api.summary_routes.get_db", mock_get_db),
        patch("src.api.digest_routes.get_db", mock_get_db),
        patch("src.api.podcast_routes.get_db", mock_get_db),
        patch("src.api.script_routes.get_db", mock_get_db),
        patch("src.api.chat_routes.get_db", mock_get_db),
        patch("src.api.settings_routes.get_db", mock_get_db),
        patch("src.api.content_routes.get_db", mock_get_db),
        patch("src.api.source_routes.get_db", mock_get_db),
        patch("src.api.upload_routes.get_db", mock_get_db),
        patch("src.api.save_routes.get_db", mock_get_db),
        patch("src.services.script_review_service.get_db", mock_get_db),
        patch("src.processors.theme_analyzer.get_db", mock_get_db),
    ):
        with TestClient(app) as test_client:
            yield AuthenticatedTestClient(test_client, "test-admin-key")


# ==============================================================================
# Sample Data Fixtures
# ==============================================================================


@pytest.fixture
def sample_summary(db_session, sample_content) -> Summary:
    """Create a single sample summary linked to content."""
    test_model = list(MODEL_REGISTRY.keys())[0]

    summary = Summary(
        content_id=sample_content.id,
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
        model_used=test_model,
        model_version="20250929",
        token_usage=2500,
        processing_time_seconds=3.5,
    )

    # Update content status to reflect it has been summarized
    sample_content.status = ContentStatus.COMPLETED
    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)
    return summary


@pytest.fixture
def sample_summaries(db_session, sample_contents) -> list[Summary]:
    """Create multiple sample summaries linked to contents."""
    test_model = list(MODEL_REGISTRY.keys())[0]

    summaries = [
        Summary(
            content_id=sample_contents[0].id,
            executive_summary="Major LLM advances summary.",
            key_themes=["LLM Performance", "Cost Optimization"],
            strategic_insights=["LLM costs decreasing"],
            technical_details=["Context windows expanded"],
            actionable_items=["Evaluate new pricing"],
            notable_quotes=["Context is king"],
            relevance_scores={"cto_leadership": 0.9, "technical_teams": 0.85},
            agent_framework="claude",
            model_used=test_model,
            token_usage=2500,
            processing_time_seconds=3.5,
        ),
        Summary(
            content_id=sample_contents[1].id,
            executive_summary="Vector database performance summary.",
            key_themes=["Vector Search", "Performance"],
            strategic_insights=["Database selection critical"],
            technical_details=["Hybrid search combining vector and keyword"],
            actionable_items=["Benchmark databases"],
            notable_quotes=["Performance matters"],
            relevance_scores={"cto_leadership": 0.6, "technical_teams": 0.95},
            agent_framework="claude",
            model_used=test_model,
            token_usage=2200,
            processing_time_seconds=3.2,
        ),
    ]

    for summary in summaries:
        db_session.add(summary)

    db_session.commit()

    for summary in summaries:
        db_session.refresh(summary)

    return summaries


@pytest.fixture
def sample_digest(db_session) -> Digest:
    """Create a single sample digest in the test database."""
    digest = Digest(
        digest_type=DigestType.DAILY,
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
        status=DigestStatus.PENDING_REVIEW,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )
    db_session.add(digest)
    db_session.commit()
    db_session.refresh(digest)
    return digest


@pytest.fixture
def sample_digests(db_session) -> list[Digest]:
    """Create multiple sample digests in the test database."""
    digests = [
        Digest(
            digest_type=DigestType.DAILY,
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
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        ),
        Digest(
            digest_type=DigestType.WEEKLY,
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
            status=DigestStatus.APPROVED,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        ),
    ]

    for digest in digests:
        db_session.add(digest)

    db_session.commit()

    for digest in digests:
        db_session.refresh(digest)

    return digests


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
# Content Model Fixtures (Unified Content Model)
# ==============================================================================


@pytest.fixture
def sample_content(db_session) -> Content:
    """Create a single sample content in the test database."""
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="test-content-001",
        source_url="https://example.com/content1",
        title="LLM Advances Newsletter",
        author="AI Weekly Team",
        publication="AI Weekly",
        published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        markdown_content="# LLM Advances\n\nContent about LLM advances and new models.",
        raw_content="<html><body>Newsletter about LLM advances...</body></html>",
        raw_format="html",
        content_hash="abc123hash",
        status=ContentStatus.PARSED,
        ingested_at=datetime.now(UTC),
        parsed_at=datetime.now(UTC),
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


@pytest.fixture
def sample_contents(db_session) -> list[Content]:
    """Create multiple sample contents in the test database."""
    contents = [
        Content(
            source_type=ContentSource.GMAIL,
            source_id="test-content-001",
            source_url="https://example.com/content1",
            title="LLM Advances Newsletter",
            author="AI Weekly Team",
            publication="AI Weekly",
            published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
            markdown_content="# LLM Advances\n\nContent about LLM advances.",
            content_hash="hash001",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        ),
        Content(
            source_type=ContentSource.RSS,
            source_id="test-content-002",
            source_url="https://example.com/content2",
            title="Vector Database Guide",
            author="Data Engineering",
            publication="Data Weekly",
            published_date=datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC),
            markdown_content="# Vector Databases\n\nGuide to vector databases.",
            content_hash="hash002",
            status=ContentStatus.COMPLETED,
            ingested_at=datetime.now(UTC),
            processed_at=datetime.now(UTC),
        ),
        Content(
            source_type=ContentSource.YOUTUBE,
            source_id="test-video-003",
            source_url="https://youtube.com/watch?v=test123",
            title="AI Agents Tutorial",
            author="Tech Channel",
            publication="Tech Channel",
            published_date=datetime(2025, 1, 13, 10, 0, 0, tzinfo=UTC),
            markdown_content="# AI Agents Tutorial\n\n[00:00](https://youtube.com/watch?v=test123&t=0) Introduction",
            metadata_json={"video_id": "test123", "channel": "Tech Channel"},
            content_hash="hash003",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        ),
    ]

    for content in contents:
        db_session.add(content)

    db_session.commit()

    for content in contents:
        db_session.refresh(content)

    return contents


@pytest.fixture
def sample_content_with_summary(db_session, sample_content) -> tuple[Content, Summary]:
    """Create a content with an associated summary."""
    test_model = list(MODEL_REGISTRY.keys())[0]

    summary = Summary(
        content_id=sample_content.id,
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
        model_used=test_model,
        model_version="20250929",
        token_usage=2500,
        processing_time_seconds=3.5,
    )

    sample_content.status = ContentStatus.COMPLETED
    sample_content.processed_at = datetime.now(UTC)

    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)
    db_session.refresh(sample_content)

    return sample_content, summary
