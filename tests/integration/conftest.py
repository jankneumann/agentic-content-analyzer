"""Shared fixtures for integration tests.

Test Database Isolation:
- PostgreSQL: Uses separate test database (newsletters_test)
  - Environment variable: TEST_DATABASE_URL
  - Transaction rollback after each test
  - No impact on development database
- Neo4j: Uses dedicated test instance on different port
  - Dev/prod instance: port 7687 (bolt://localhost:7687)
  - Test instance: port 7688 (bolt://localhost:7688)
  - Environment variables: TEST_NEO4J_URI, TEST_NEO4J_USER, TEST_NEO4J_PASSWORD
  - Automatic cleanup (DETACH DELETE all nodes) after each test
  - Safety check: prevents connecting to port 7687
  - Completely separate Docker container with own data volume
- Neon: Creates ephemeral database branches for testing
  - Environment variables: NEON_API_KEY, NEON_PROJECT_ID
  - Automatic branch cleanup after tests
  - Uses copy-on-write branching for fast, isolated test environments
  - See tests/integration/fixtures/neon.py for fixtures
- Supabase: Tests cloud database connection and pooling
  - Environment variables: SUPABASE_PROJECT_REF, SUPABASE_DB_PASSWORD
  - Tests skipped if credentials not configured
  - See tests/integration/fixtures/supabase.py for fixtures

Setup:
1. Create PostgreSQL test database: createdb newsletters_test
2. Start dev dependencies: docker compose up -d postgres redis neo4j
3. Start test Neo4j instance: docker compose up -d neo4j-test
4. Run integration tests: pytest tests/integration/ -v

Note: The test Neo4j instance uses the 'test' profile and runs on port 7688 to
ensure test cleanup never affects production knowledge graph data.
"""

import os
from collections.abc import Generator
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from neo4j import GraphDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.models import MODEL_REGISTRY
from src.models.digest import Digest  # noqa: F401 - registers with Base.metadata

# Import Base and all models that use it to ensure they're registered with metadata
# All models share the same Base from newsletter.py
from src.models.newsletter import (
    Base,
    Newsletter,
    NewsletterSource,
    ProcessingStatus,
)
from src.models.podcast import (  # noqa: F401 - registers with Base.metadata
    Podcast,
    PodcastScriptRecord,
)
from src.models.summary import NewsletterSummary
from src.models.theme import ThemeAnalysis  # noqa: F401 - registers with Base.metadata

# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://newsletter_user:newsletter_password@localhost/newsletters_test",
)

# Test Neo4j configuration (dedicated test instance on different port)
TEST_NEO4J_URI = os.getenv("TEST_NEO4J_URI", "bolt://localhost:7688")
TEST_NEO4J_USER = os.getenv("TEST_NEO4J_USER", "neo4j")
TEST_NEO4J_PASSWORD = os.getenv("TEST_NEO4J_PASSWORD", "newsletter_password")


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
    # All models share the same Base.metadata
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


@pytest.fixture(scope="session")
def neo4j_driver():
    """Create Neo4j driver for test session.

    Connects to dedicated test Neo4j instance on port 7688.
    Driver is shared across all tests in the session.

    The test instance is separate from dev/prod (port 7687) to prevent
    accidentally deleting production data during test cleanup.
    """
    # Safety check: Verify we're not connecting to production port
    if "7687" in TEST_NEO4J_URI:
        raise ValueError(
            "Safety check failed: TEST_NEO4J_URI is using production port 7687. "
            "Tests must use dedicated test instance on port 7688. "
            "Set TEST_NEO4J_URI=bolt://localhost:7688"
        )

    driver = GraphDatabase.driver(TEST_NEO4J_URI, auth=(TEST_NEO4J_USER, TEST_NEO4J_PASSWORD))

    # Verify connection
    try:
        driver.verify_connectivity()
    except Exception as e:
        driver.close()
        raise RuntimeError(
            f"Failed to connect to test Neo4j instance at {TEST_NEO4J_URI}. "
            f"Make sure the test instance is running: docker compose up -d neo4j-test"
        ) from e

    yield driver

    # Cleanup: Close driver at end of session
    driver.close()


@pytest.fixture(autouse=True)
def clean_neo4j(neo4j_driver):
    """Clean Neo4j test instance after each test for isolation.

    This fixture runs automatically for all integration tests.
    Deletes all nodes and relationships from the test Neo4j instance to ensure
    tests don't interfere with each other.

    Safe to use because this connects to a dedicated test instance (port 7688)
    that is completely separate from dev/prod (port 7687).

    Similar to PostgreSQL transaction rollback, but Neo4j doesn't support
    transactions across connections, so we manually delete all data.
    """
    # Run test first
    yield

    # Cleanup: Delete all nodes and relationships after test
    with neo4j_driver.session() as session:
        # Delete all relationships first, then all nodes
        session.run("MATCH (n) DETACH DELETE n")


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
            source=NewsletterSource.RSS,
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
    # Use any valid model from the registry for test data
    test_model = list(MODEL_REGISTRY.keys())[0]

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
            model_used=test_model,
            model_version="20250929",  # Test version
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
            model_used=test_model,
            model_version="20250929",  # Test version
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
            model_used=test_model,
            model_version="20250929",  # Test version
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

    Includes proper token usage for cost calculation.
    """
    mock_client = MagicMock()

    # Default mock response for summarization
    mock_summary_response = MagicMock()
    mock_summary_response.content = [
        MagicMock(
            text="""{
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
    }"""
        )
    ]

    # Mock token usage for cost calculation
    mock_usage = MagicMock()
    mock_usage.input_tokens = 1000
    mock_usage.output_tokens = 500
    mock_summary_response.usage = mock_usage

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
    mock_client.search_related_concepts = AsyncMock(
        return_value=[
            {"name": "LLM", "relevance": 0.9},
            {"name": "Vector DB", "relevance": 0.7},
        ]
    )
    mock_client.get_temporal_context = AsyncMock(return_value=[])
    mock_client.extract_themes_from_range = AsyncMock(
        return_value=[
            {"name": "RAG", "fact": "Retrieval Augmented Generation improving"},
        ]
    )
    mock_client.get_historical_theme_mentions = AsyncMock(return_value=[])
    mock_client.get_theme_evolution_timeline = AsyncMock(return_value=[])
    mock_client.close = AsyncMock(return_value=None)

    return mock_client


# Import Neon fixtures to make them available to all integration tests
# These fixtures are defined in tests/integration/fixtures/neon.py
from tests.integration.fixtures.neon import (  # noqa: E402, F401
    _detect_default_branch,
    neon_available,
    neon_default_branch,
    neon_isolated_branch,
    neon_manager,
    neon_test_branch,
    requires_neon,
)

# Import Supabase fixtures to make them available to all integration tests
# These fixtures are defined in tests/integration/fixtures/supabase.py
from tests.integration.fixtures.supabase import (  # noqa: E402, F401
    requires_supabase,
    supabase_available,
    supabase_direct_engine,
    supabase_engine,
    supabase_provider,
)
