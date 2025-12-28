"""Tests for GraphitiClient."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.graphiti_client import GraphitiClient


@pytest.fixture
def mock_neo4j_driver():
    """Create mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver


@pytest.fixture
def mock_graphiti():
    """Create mock Graphiti client."""
    graphiti = AsyncMock()
    graphiti.add_episode = AsyncMock(return_value="episode-123")
    graphiti.search = AsyncMock(return_value=[])
    return graphiti


@pytest.fixture
def sample_newsletter() -> Newsletter:
    """Create sample newsletter for testing."""
    newsletter = Newsletter(
        source=NewsletterSource.GMAIL,
        source_id="msg-123",
        sender="test@example.com",
        publication="Tech Weekly",
        title="AI Advances in 2025",
        raw_html="<html>Newsletter content about AI...</html>",
        raw_text="Newsletter content about AI...",
        published_date=datetime(2025, 1, 15, 10, 0, 0),
        url="https://example.com/newsletter",
        status=ProcessingStatus.PENDING,
    )
    newsletter.id = 1  # Set ID manually after creation
    return newsletter


@pytest.fixture
def sample_summary() -> NewsletterSummary:
    """Create sample newsletter summary for testing."""
    return NewsletterSummary(
        newsletter_id=1,
        executive_summary="Major AI breakthroughs announced this week.",
        key_themes=["Large Language Models", "AI Agents", "RAG"],
        strategic_insights=[
            "LLMs becoming more cost-effective",
            "Agent orchestration gaining traction",
        ],
        technical_details=[
            "New context window techniques",
            "Improved embeddings quality",
        ],
        actionable_items=[
            "Evaluate LLM providers",
            "Experiment with agent frameworks",
        ],
        notable_quotes=["Context is king in 2025"],
        relevance_scores={"strategic": 0.9, "tactical": 0.7},
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=5.2,
    )


def test_graphiti_client_initialization(mock_neo4j_driver, mock_graphiti):
    """Test GraphitiClient initialization."""
    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
                anthropic_api_key="test-anthropic-key",
                openai_api_key="test-openai-key",
            )

            # Verify driver was created
            mock_graphdb.driver.assert_called_once_with(
                "bolt://localhost:7687",
                auth=("neo4j", "password")
            )

            # Verify Graphiti was initialized
            mock_graphiti_class.assert_called_once()

            assert client.neo4j_uri == "bolt://localhost:7687"
            assert client.driver == mock_neo4j_driver
            assert client.graphiti == mock_graphiti


def test_close_connection(mock_neo4j_driver, mock_graphiti):
    """Test closing GraphitiClient connection."""
    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti"):
            client = GraphitiClient()
            client.close()

            # Verify driver close was called
            mock_neo4j_driver.close.assert_called_once()


@pytest.mark.asyncio
async def test_add_newsletter_summary(
    mock_neo4j_driver, mock_graphiti, sample_newsletter, sample_summary
):
    """Test adding newsletter summary to knowledge graph."""
    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            episode_id = await client.add_newsletter_summary(
                sample_newsletter, sample_summary
            )

            # Verify episode was added to Graphiti
            mock_graphiti.add_episode.assert_called_once()
            call_args = mock_graphiti.add_episode.call_args

            # Check episode name
            assert "Tech Weekly: AI Advances in 2025" in call_args.kwargs["name"]

            # Check episode content includes summary sections
            episode_body = call_args.kwargs["episode_body"]
            assert "[EXECUTIVE_SUMMARY]" in episode_body
            assert "Major AI breakthroughs" in episode_body
            assert "[KEY_THEMES]" in episode_body
            assert "Large Language Models" in episode_body

            # Check reference time
            assert call_args.kwargs["reference_time"] == sample_newsletter.published_date

            # Verify return value
            assert episode_id == "episode-123"


@pytest.mark.asyncio
async def test_search_related_concepts(mock_neo4j_driver, mock_graphiti):
    """Test searching for related concepts."""
    # Mock search results
    mock_results = [
        {"entity": "RAG", "type": "concept", "score": 0.95},
        {"entity": "Vector Database", "type": "concept", "score": 0.87},
    ]
    mock_graphiti.search = AsyncMock(return_value=mock_results)

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            results = await client.search_related_concepts("RAG", limit=10)

            # Verify search was called
            mock_graphiti.search.assert_called_once_with(
                query="RAG",
                num_results=10,
            )

            # Verify results
            assert len(results) == 2
            assert results[0]["entity"] == "RAG"


@pytest.mark.asyncio
async def test_get_temporal_context(mock_neo4j_driver, mock_graphiti):
    """Test getting temporal context for concepts."""
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 31)

    # Mock search results with timestamps
    mock_results_rag = [
        {"entity": "RAG", "reference_time": datetime(2025, 1, 15), "content": "RAG discussion 1"},
        {"entity": "RAG", "reference_time": datetime(2024, 12, 1), "content": "Old RAG discussion"},
    ]
    mock_results_llm = [
        {"entity": "LLM", "reference_time": datetime(2025, 1, 20), "content": "LLM discussion"},
    ]

    async def mock_search_side_effect(query, num_results):
        if query == "RAG":
            return mock_results_rag
        elif query == "LLM":
            return mock_results_llm
        return []

    mock_graphiti.search = AsyncMock(side_effect=mock_search_side_effect)

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            results = await client.get_temporal_context(
                concepts=["RAG", "LLM"],
                start_date=start_date,
                end_date=end_date,
            )

            # Should filter out results outside date range
            assert len(results) == 2  # One RAG, one LLM (old RAG filtered out)
            assert all(start_date <= r["reference_time"] <= end_date for r in results)


@pytest.mark.asyncio
async def test_get_newsletters_in_range(mock_neo4j_driver, mock_graphiti):
    """Test getting newsletters in date range."""
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 31)

    # Mock Neo4j query results
    mock_records = [
        {
            "episode_id": "ep-1",
            "title": "Newsletter 1",
            "content": "Content 1",
            "timestamp": datetime(2025, 1, 15),
            "source": "Source 1",
        },
        {
            "episode_id": "ep-2",
            "title": "Newsletter 2",
            "content": "Content 2",
            "timestamp": datetime(2025, 1, 20),
            "source": "Source 2",
        },
    ]

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter(mock_records)
    mock_session.run.return_value = mock_result

    mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            episodes = await client.get_newsletters_in_range(start_date, end_date)

            # Verify Neo4j query was called
            mock_session.run.assert_called_once()
            call_args = mock_session.run.call_args
            assert "MATCH (e:Episode)" in call_args[0][0]
            assert call_args.kwargs["start_date"] == start_date
            assert call_args.kwargs["end_date"] == end_date

            # Verify results
            assert len(episodes) == 2
            assert episodes[0]["episode_id"] == "ep-1"
            assert episodes[1]["episode_id"] == "ep-2"


@pytest.mark.asyncio
async def test_extract_themes_from_range(mock_neo4j_driver, mock_graphiti):
    """Test extracting themes from date range."""
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 31)

    mock_results = [
        {"theme": "AI Agents", "mentions": 5},
        {"theme": "Vector Search", "mentions": 3},
    ]
    mock_graphiti.search = AsyncMock(return_value=mock_results)

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            themes = await client.extract_themes_from_range(start_date, end_date)

            # Verify search was called with broad query
            mock_graphiti.search.assert_called_once_with(
                query="AI and technology themes, trends, and topics",
                num_results=100,
            )

            assert len(themes) == 2


@pytest.mark.asyncio
async def test_get_entity_facts(mock_neo4j_driver, mock_graphiti):
    """Test getting facts about entities."""
    mock_facts_rag = [{"fact": "RAG improves accuracy"}]
    mock_facts_llm = [{"fact": "LLMs are getting cheaper"}]

    async def mock_search_side_effect(query, num_results):
        if query == "RAG":
            return mock_facts_rag
        elif query == "LLM":
            return mock_facts_llm
        return []

    mock_graphiti.search = AsyncMock(side_effect=mock_search_side_effect)

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            facts = await client.get_entity_facts(["RAG", "LLM"], limit=50)

            # Should have facts from both entities
            assert len(facts) == 2
            assert mock_graphiti.search.call_count == 2


@pytest.mark.asyncio
async def test_get_historical_theme_mentions(mock_neo4j_driver, mock_graphiti):
    """Test getting historical theme mentions."""
    before_date = datetime(2025, 1, 31)
    theme_name = "AI Agents"

    # Mock Neo4j query results (direct mentions)
    mock_records = [
        {
            "episode_id": "ep-1",
            "title": "Newsletter about AI Agents",
            "content": "Discussion of AI Agents...",
            "timestamp": datetime(2025, 1, 15),
            "source": "Source 1",
        },
    ]

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter(mock_records)
    mock_session.run.return_value = mock_result

    mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session

    # Mock Graphiti search results (semantic matches)
    mock_semantic = [
        {
            "content": "Related to agents",
            "reference_time": datetime(2025, 1, 10),
        },
        {
            "content": "Old mention",
            "reference_time": datetime(2024, 10, 1),  # Outside lookback window
        },
    ]
    mock_graphiti.search = AsyncMock(return_value=mock_semantic)

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            mentions = await client.get_historical_theme_mentions(
                theme_name, before_date, lookback_days=90
            )

            # Verify Neo4j query
            mock_session.run.assert_called_once()
            call_args = mock_session.run.call_args
            assert call_args.kwargs["theme_name"] == theme_name
            assert call_args.kwargs["before_date"] == before_date

            # Should have direct mention + filtered semantic match
            assert len(mentions) >= 2


@pytest.mark.asyncio
async def test_get_theme_evolution_timeline(mock_neo4j_driver, mock_graphiti):
    """Test getting theme evolution timeline."""
    theme_name = "Vector Databases"
    end_date = datetime(2025, 1, 31)

    mock_records = [
        {
            "episode_id": "ep-1",
            "title": "First mention",
            "content": "Vector Databases intro",
            "timestamp": datetime(2025, 1, 5),
            "source": "Source 1",
        },
        {
            "episode_id": "ep-2",
            "title": "Later discussion",
            "content": "Vector Databases performance",
            "timestamp": datetime(2025, 1, 20),
            "source": "Source 2",
        },
    ]

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter(mock_records)
    mock_session.run.return_value = mock_result

    mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            client = GraphitiClient()
            timeline = await client.get_theme_evolution_timeline(theme_name, end_date)

            # Verify query
            mock_session.run.assert_called_once()
            call_args = mock_session.run.call_args
            assert "ORDER BY e.valid_at ASC" in call_args[0][0]  # Chronological

            # Verify results
            assert len(timeline) == 2
            assert timeline[0]["timestamp"] < timeline[1]["timestamp"]  # Chronological


def test_get_previous_analyses(mock_neo4j_driver, mock_graphiti):
    """Test getting previous theme analyses."""
    before_date = datetime(2025, 1, 31)

    # Mock database query
    mock_analysis = MagicMock()
    mock_analysis.id = 1
    mock_analysis.analysis_date = datetime(2025, 1, 15)
    mock_analysis.start_date = datetime(2025, 1, 8)
    mock_analysis.end_date = datetime(2025, 1, 15)
    mock_analysis.themes = [{"name": "AI Agents", "score": 0.9}]
    mock_analysis.total_themes = 1

    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            # Patch get_db where it's imported in the method
            with patch("src.storage.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_query = MagicMock()
                mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                    mock_analysis
                ]
                mock_db.query.return_value = mock_query
                mock_get_db.return_value.__enter__.return_value = mock_db

                client = GraphitiClient()
                analyses = client.get_previous_analyses(before_date, limit=10)

                # Verify query
                assert len(analyses) == 1
                assert analyses[0]["id"] == 1
                assert analyses[0]["total_themes"] == 1


def test_create_episode_content(sample_newsletter, sample_summary):
    """Test episode content creation."""
    with patch("src.storage.graphiti_client.GraphDatabase"):
        with patch("src.storage.graphiti_client.Graphiti"):
            client = GraphitiClient()
            content = client._create_episode_content(sample_newsletter, sample_summary)

            # Verify all sections are included
            assert "[EXECUTIVE_SUMMARY]" in content
            assert "Major AI breakthroughs" in content

            assert "[KEY_THEMES]" in content
            assert "Large Language Models" in content

            assert "[STRATEGIC_INSIGHTS]" in content
            assert "LLMs becoming more cost-effective" in content

            assert "[TECHNICAL_DETAILS]" in content
            assert "New context window techniques" in content

            assert "[ACTIONABLE_ITEMS]" in content
            assert "Evaluate LLM providers" in content

            assert "[NOTABLE_DATA]" in content
            assert "Context is king in 2025" in content


def test_create_episode_content_minimal(sample_newsletter):
    """Test episode content creation with minimal summary."""
    minimal_summary = NewsletterSummary(
        newsletter_id=1,
        executive_summary="Brief summary.",
        key_themes=[],  # Empty
        strategic_insights=[],
        technical_details=[],
        actionable_items=[],
        notable_quotes=[],
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=1.0,
    )

    with patch("src.storage.graphiti_client.GraphDatabase"):
        with patch("src.storage.graphiti_client.Graphiti"):
            client = GraphitiClient()
            content = client._create_episode_content(sample_newsletter, minimal_summary)

            # Should only have executive summary
            assert "[EXECUTIVE_SUMMARY]" in content
            assert "Brief summary." in content

            # Empty sections should not appear
            assert "[KEY_THEMES]" not in content
            assert "[STRATEGIC_INSIGHTS]" not in content


@pytest.mark.asyncio
async def test_async_context_manager(mock_neo4j_driver, mock_graphiti):
    """Test using GraphitiClient as async context manager."""
    with patch("src.storage.graphiti_client.GraphDatabase") as mock_graphdb:
        mock_graphdb.driver.return_value = mock_neo4j_driver

        with patch("src.storage.graphiti_client.Graphiti") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            async with GraphitiClient() as client:
                # Verify client is usable
                assert client.graphiti == mock_graphiti

            # Verify close was called on exit
            mock_neo4j_driver.close.assert_called_once()
