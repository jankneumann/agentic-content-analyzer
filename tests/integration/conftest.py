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
2. Start dev dependencies: docker compose up -d postgres neo4j
3. Start test Neo4j instance: docker compose up -d neo4j-test
4. Run integration tests: pytest tests/integration/ -v

Note: The test Neo4j instance uses the 'test' profile and runs on port 7688 to
ensure test cleanup never affects production knowledge graph data.
"""

import logging
import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from neo4j import GraphDatabase
from sqlalchemy.orm import Session, sessionmaker

# Import Base and all models that use it to ensure they're registered with metadata
# All models share the same Base from base.py
from src.models.base import Base
from src.models.content import Content, ContentSource, ContentStatus  # noqa: F401
from src.models.digest import Digest  # noqa: F401 - registers with Base.metadata
from src.models.podcast import (  # noqa: F401 - registers with Base.metadata
    Podcast,
    PodcastScriptRecord,
)
from src.models.summary import Summary  # noqa: F401
from src.models.theme import ThemeAnalysis  # noqa: F401 - registers with Base.metadata
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory
from tests.helpers.test_db import (
    create_test_engine,
    get_test_database_url,
    get_worktree_name,
)

logger = logging.getLogger(__name__)

# Worktree-aware test database URL (shared helper handles detection)
TEST_DATABASE_URL = get_test_database_url()

# Test Neo4j configuration (dedicated test instance on different port)
TEST_NEO4J_URI = os.getenv("TEST_NEO4J_URI", "bolt://localhost:7688")
TEST_NEO4J_USER = os.getenv("TEST_NEO4J_USER", "neo4j")
TEST_NEO4J_PASSWORD = os.getenv("TEST_NEO4J_PASSWORD", "newsletter_password")


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine.

    Uses shared helper for worktree-aware DB naming and auto-creation.
    Drops and recreates all tables at session start for clean state.
    """
    engine = create_test_engine(TEST_DATABASE_URL)

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
    Also configures Factory Boy to use this session for model creation.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    # Configure factories to use this session
    ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]

    yield session

    # Cleanup: Reset factory sessions, rollback transaction, close connection
    ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
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
    # Warn when running from a worktree without a dedicated Neo4j URI
    worktree = get_worktree_name()
    if worktree and not os.getenv("TEST_NEO4J_URI"):
        logger.warning(
            "Running from worktree '%s' without TEST_NEO4J_URI set. "
            "All worktrees share the same Neo4j test instance on port 7688. "
            "Concurrent integration tests may interfere with each other. "
            "Set TEST_NEO4J_URI to a dedicated instance for parallel safety.",
            worktree,
        )

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
        yield driver
        # Cleanup: Close driver at end of session
        driver.close()
    except Exception:
        # If we can't connect, yield None so tests that don't strictly require it can still run
        # (e.g. tests that mock GraphitiClient)
        driver.close()
        yield None


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
    if neo4j_driver:
        with neo4j_driver.session() as session:
            # Delete all relationships first, then all nodes
            session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def sample_contents(db_session):
    """Create sample contents in the test database."""
    return [
        ContentFactory(
            gmail=True,
            parsed=True,
            source_id="msg-001",
            source_url="https://example.com/newsletter1",
            title="Latest LLM Advances",
            author="ai-weekly@example.com",
            publication="AI Weekly",
            markdown_content="Newsletter content about LLM advances and new models. Context windows are expanding to 1M tokens. Costs are decreasing by 40%. Multimodal capabilities are becoming standard.",
            content_hash="hash001",
        ),
        ContentFactory(
            gmail=True,
            parsed=True,
            source_id="msg-002",
            source_url="https://example.com/newsletter2",
            title="Vector Database Performance",
            author="data-eng@example.com",
            publication="Data Engineering Weekly",
            markdown_content="Newsletter about vector database optimizations and benchmarks. Hybrid search combining vector and keyword search is critical. Performance matters at scale.",
            content_hash="hash002",
        ),
        ContentFactory(
            rss=True,
            parsed=True,
            source_id="rss-003",
            source_url="https://example.com/newsletter3",
            title="AI Agent Frameworks",
            author="tech-trends@substack.com",
            publication="Tech Trends",
            markdown_content="Comparison of AI agent frameworks including Claude SDK and OpenAI. Framework choice impacts development velocity. Tool use patterns vary significantly.",
            content_hash="hash003",
        ),
    ]


@pytest.fixture
def sample_summaries(db_session, sample_contents):
    """Create sample summaries for the contents."""
    return [
        SummaryFactory(
            content=sample_contents[0],
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
            model_version="20250929",
            token_usage=2500,
            processing_time_seconds=3.5,
        ),
        SummaryFactory(
            content=sample_contents[1],
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
            model_version="20250929",
            token_usage=2200,
            processing_time_seconds=3.2,
        ),
        SummaryFactory(
            content=sample_contents[2],
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
            model_version="20250929",
            token_usage=2400,
            processing_time_seconds=3.4,
        ),
    ]


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
    mock_client.add_content_summary = AsyncMock(return_value=None)
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

# Import Opik fixtures to make them available to all integration tests
# These fixtures are defined in tests/integration/fixtures/opik.py
from tests.integration.fixtures.opik import (  # noqa: E402, F401
    opik_available,
    opik_provider,
    opik_test_helpers,
    requires_opik,
    unique_project_name,
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
