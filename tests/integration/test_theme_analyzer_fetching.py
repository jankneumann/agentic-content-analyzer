"""Integration tests for ThemeAnalyzer fetching logic."""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import NewsletterSummary
from src.processors.theme_analyzer import ThemeAnalyzer


@pytest.fixture
def mock_get_db(db_session):
    """Mock get_db to return the test database session."""

    @contextmanager
    def _mock():
        yield db_session

    return _mock


# Override autouse fixture from conftest.py to avoid Neo4j connection
@pytest.fixture(autouse=True)
def clean_neo4j():
    """Mock clean_neo4j to avoid connecting to real Neo4j."""
    pass


@pytest.fixture(scope="module")
def neo4j_driver():
    """Mock neo4j_driver to avoid connecting to real Neo4j."""
    return MagicMock()


@pytest.fixture
def sample_contents_db(db_session: Session):
    """Create sample contents in the database."""
    contents = [
        Content(
            title="AI Advances",
            publication="Tech Weekly",
            published_date=datetime(2025, 1, 15),
            source_type=ContentSource.RSS,
            source_id="rss-1",
            content_hash="hash1",
            markdown_content="Content 1",
            status=ContentStatus.COMPLETED,
        ),
        Content(
            title="Vector Databases",
            publication="Data News",
            published_date=datetime(2025, 1, 10),
            source_type=ContentSource.GMAIL,
            source_id="gmail-1",
            content_hash="hash2",
            markdown_content="Content 2",
            status=ContentStatus.COMPLETED,
        ),
        Content(
            title="LLM Updates",
            publication="AI Digest",
            published_date=datetime(2025, 1, 5),
            source_type=ContentSource.RSS,
            source_id="rss-2",
            content_hash="hash3",
            markdown_content="Content 3",
            status=ContentStatus.COMPLETED,
        ),
        # Content outside date range
        Content(
            title="Old News",
            publication="Tech Weekly",
            published_date=datetime(2024, 12, 31),
            source_type=ContentSource.RSS,
            source_id="rss-3",
            content_hash="hash4",
            markdown_content="Content 4",
            status=ContentStatus.COMPLETED,
        ),
        # Content with different status
        Content(
            title="Pending News",
            publication="Tech Weekly",
            published_date=datetime(2025, 1, 12),
            source_type=ContentSource.RSS,
            source_id="rss-4",
            content_hash="hash5",
            markdown_content="Content 5",
            status=ContentStatus.PENDING,
        ),
    ]

    for content in contents:
        db_session.add(content)
    db_session.commit()

    for content in contents:
        db_session.refresh(content)

    return contents


@pytest.fixture
def sample_summaries_db(db_session: Session, sample_contents_db):
    """Create sample summaries in the database."""
    summaries = [
        NewsletterSummary(
            content_id=sample_contents_db[0].id,
            executive_summary="Summary 1",
            key_themes=["AI", "ML"],
            strategic_insights=["Insight 1"],
            technical_details=["Detail 1"],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={"score": 0.9},
            agent_framework="claude",
            model_used="claude-3-opus",
            theme_tags=["tag1", "tag2"],
        ),
        NewsletterSummary(
            content_id=sample_contents_db[1].id,
            executive_summary="Summary 2",
            key_themes=["Vector DB"],
            strategic_insights=["Insight 2"],
            technical_details=["Detail 2"],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={"score": 0.8},
            agent_framework="claude",
            model_used="claude-3-opus",
            theme_tags=["tag3"],
        ),
    ]

    for summary in summaries:
        db_session.add(summary)
    db_session.commit()

    return summaries


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_contents_integration(db_session, sample_contents_db, mock_get_db):
    """Test fetching contents from database (INTEGRATION TEST)."""

    # We need to use mock_get_db to ensure the analyzer uses the test session
    # because ThemeAnalyzer._fetch_contents calls get_db() directly
    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.processors.theme_analyzer.get_db", mock_get_db)

        analyzer = ThemeAnalyzer()

        # Test date range filtering
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        contents = await analyzer._fetch_contents(start_date, end_date)

        # Should match 3 contents (excludes Old News and Pending News)
        assert len(contents) == 3

        # Verify content fields
        titles = {c["title"] for c in contents}
        assert "AI Advances" in titles
        assert "Vector Databases" in titles
        assert "LLM Updates" in titles
        assert "Old News" not in titles
        assert "Pending News" not in titles

        # Verify structure
        content = contents[0]
        assert "id" in content
        assert "title" in content
        assert "publication" in content
        assert "published_date" in content
        assert "source_type" in content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_summaries_integration(
    db_session, sample_contents_db, sample_summaries_db, mock_get_db
):
    """Test fetching summaries from database (INTEGRATION TEST)."""

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.processors.theme_analyzer.get_db", mock_get_db)

        analyzer = ThemeAnalyzer()

        # Get IDs for contents that have summaries
        content_ids = [c.id for c in sample_contents_db[:3]]  # Includes one without summary

        summaries = await analyzer._fetch_summaries(content_ids)

        # Should return 2 summaries
        assert len(summaries) == 2

        # Verify summary fields
        summary_contents = {s["content_id"] for s in summaries}
        assert sample_contents_db[0].id in summary_contents
        assert sample_contents_db[1].id in summary_contents
        assert sample_contents_db[2].id not in summary_contents  # No summary for this one

        # Verify structure
        summary = summaries[0]
        assert "content_id" in summary
        assert "executive_summary" in summary
        assert "key_themes" in summary
        assert "theme_tags" in summary
        assert "strategic_insights" in summary
        assert "technical_details" in summary
