"""Shared fixtures for integration tests.

Test Database Isolation:
- Uses separate test database (newsletters_test)
- Environment variable: TEST_DATABASE_URL
- Transaction rollback after each test
- No impact on development database

Setup:
1. Create test database: createdb newsletters_test
2. Run integration tests: pytest tests/integration/ -v
"""

import os
from datetime import datetime
from typing import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.digest import Base as DigestBase
from src.models.newsletter import Base as NewsletterBase
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.summary import NewsletterSummary


# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://newsletter_user:newsletter_password@localhost/newsletters_test"
)


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine.

    Uses newsletters_test database (separate from development).
    Creates all tables at session start, drops them at session end.
    """
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Verify we're using test database
    db_name = engine.url.database
    if not db_name or "test" not in db_name.lower():
        raise ValueError(
            f"Safety check failed: Database '{db_name}' does not contain 'test'. "
            f"Set TEST_DATABASE_URL to a test database to proceed."
        )

    # Create all tables
    NewsletterBase.metadata.create_all(engine)
    DigestBase.metadata.create_all(engine)

    yield engine

    # Cleanup: Drop all tables after all tests complete
    NewsletterBase.metadata.drop_all(engine)
    DigestBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test with transaction rollback.

    Each test gets a fresh session. Changes are rolled back after test completes.
    This ensures tests don't interfere with each other.
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


@pytest.fixture
def mock_get_db(db_session):
    """Mock get_db() to return the test's database session.

    This ensures all database operations happen in the same transaction,
    making changes visible across the code being tested.
    """
    from contextlib import contextmanager

    @contextmanager
    def _mock_get_db():
        """Return the test's db_session."""
        yield db_session

    return _mock_get_db


@pytest.fixture
def sample_newsletters(db_session) -> list[Newsletter]:
    """Create sample newsletters in the test database."""
    newsletters = [
        Newsletter(
            source=NewsletterSource.GMAIL,
            source_id="msg-001",
            sender="ai-weekly@example.com",
            publication="AI Weekly",
            title="Latest LLM Advances",
            raw_html="<html><body>Newsletter about LLM advances...</body></html>",
            raw_text="Newsletter content about LLM advances and new models. Context windows are expanding to 1M tokens. Costs are decreasing by 40%. Multimodal capabilities are becoming standard.",
            published_date=datetime(2025, 1, 15, 10, 0, 0),
            url="https://example.com/newsletter1",
            status=ProcessingStatus.PENDING,
        ),
        Newsletter(
            source=NewsletterSource.GMAIL,
            source_id="msg-002",
            sender="data-eng@example.com",
            publication="Data Engineering Weekly",
            title="Vector Database Performance",
            raw_html="<html><body>Newsletter about vector databases...</body></html>",
            raw_text="Newsletter about vector database optimizations and benchmarks. Hybrid search combining vector and keyword search is critical. Performance matters at scale.",
            published_date=datetime(2025, 1, 14, 10, 0, 0),
            url="https://example.com/newsletter2",
            status=ProcessingStatus.PENDING,
        ),
        Newsletter(
            source=NewsletterSource.SUBSTACK_RSS,
            source_id="rss-003",
            sender="tech-trends@substack.com",
            publication="Tech Trends",
            title="AI Agent Frameworks",
            raw_html="<html><body>Newsletter about AI agent frameworks...</body></html>",
            raw_text="Comparison of AI agent frameworks including Claude SDK and OpenAI. Framework choice impacts development velocity. Tool use patterns vary significantly.",
            published_date=datetime(2025, 1, 13, 10, 0, 0),
            url="https://example.com/newsletter3",
            status=ProcessingStatus.PENDING,
        ),
    ]

    for newsletter in newsletters:
        db_session.add(newsletter)

    db_session.commit()

    # Refresh to get IDs
    for newsletter in newsletters:
        db_session.refresh(newsletter)

    return newsletters


@pytest.fixture
def sample_summaries(db_session, sample_newsletters) -> list[NewsletterSummary]:
    """Create sample summaries for the newsletters."""
    summaries = [
        NewsletterSummary(
            newsletter_id=sample_newsletters[0].id,
            executive_summary="Major LLM advances including cost reduction and performance improvements.",
            key_themes=["LLM Performance", "Cost Optimization", "Multimodal AI"],
            strategic_insights=["LLM costs decreasing enables broader adoption"],
            technical_details=["Context windows expanded to 1M tokens"],
            actionable_items=["Evaluate new pricing for optimization"],
            notable_quotes=["Context is king in AI"],
            relevance_scores={
                "cto_leadership": 0.9,
                "technical_teams": 0.85,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5-20251001",
            token_usage=2500,
            processing_time_seconds=3.5,
        ),
        NewsletterSummary(
            newsletter_id=sample_newsletters[1].id,
            executive_summary="Vector database performance benchmarks and optimization techniques.",
            key_themes=["Vector Search", "Performance", "Hybrid Search"],
            strategic_insights=["Database selection critical for production"],
            technical_details=["Hybrid search combining vector and keyword"],
            actionable_items=["Benchmark vector databases for use case"],
            notable_quotes=["Performance matters at scale"],
            relevance_scores={
                "cto_leadership": 0.6,
                "technical_teams": 0.95,
                "individual_developers": 0.85,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5-20251001",
            token_usage=2200,
            processing_time_seconds=3.2,
        ),
        NewsletterSummary(
            newsletter_id=sample_newsletters[2].id,
            executive_summary="Comparison of major AI agent frameworks and their capabilities.",
            key_themes=["AI Agents", "Framework Comparison", "Tool Use"],
            strategic_insights=["Framework choice impacts development velocity"],
            technical_details=["Claude SDK offers best tool integration"],
            actionable_items=["Prototype with multiple frameworks"],
            notable_quotes=["Choose frameworks based on use case"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.95,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5-20251001",
            token_usage=2400,
            processing_time_seconds=3.4,
        ),
    ]

    for summary in summaries:
        db_session.add(summary)

    db_session.commit()

    # Refresh to get IDs
    for summary in summaries:
        db_session.refresh(summary)

    return summaries


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for LLM API calls.

    Returns different responses based on prompt content to simulate
    summarization, theme analysis, and digest creation.
    """
    mock_client = MagicMock()

    # Default mock response for summarization
    mock_summary_response = MagicMock()
    mock_summary_response.content = [MagicMock(text='''{
        "executive_summary": "Test summary of newsletter content.",
        "key_themes": ["Theme 1", "Theme 2", "Theme 3"],
        "strategic_insights": ["Strategic insight 1", "Strategic insight 2"],
        "technical_details": ["Technical detail 1", "Technical detail 2"],
        "actionable_items": ["Action 1", "Action 2"],
        "notable_quotes": ["Quote 1", "Quote 2"],
        "relevance_scores": {
            "cto_leadership": 0.8,
            "technical_teams": 0.85,
            "individual_developers": 0.75
        }
    }''')]
    mock_summary_response.usage.input_tokens = 1000
    mock_summary_response.usage.output_tokens = 500

    mock_client.messages.create.return_value = mock_summary_response

    return mock_client


@pytest.fixture
def mock_graphiti_client():
    """Mock Graphiti client for knowledge graph operations.

    Provides mock responses for entity extraction, theme queries,
    and historical context retrieval.
    """
    from unittest.mock import AsyncMock

    mock_client = MagicMock()

    # Mock async methods using AsyncMock
    mock_client.add_newsletter_summary = AsyncMock(return_value=None)
    mock_client.search_related_concepts = AsyncMock(return_value=[
        {"name": "LLM", "relevance": 0.9},
        {"name": "Vector DB", "relevance": 0.7},
    ])
    mock_client.get_temporal_context = AsyncMock(return_value=[])
    mock_client.extract_themes_from_range = AsyncMock(return_value=[
        {"name": "RAG", "fact": "Retrieval Augmented Generation improving"},
    ])
    mock_client.get_historical_theme_mentions = AsyncMock(return_value=[])
    mock_client.get_theme_evolution_timeline = AsyncMock(return_value=[])
    mock_client.close = AsyncMock(return_value=None)

    return mock_client
