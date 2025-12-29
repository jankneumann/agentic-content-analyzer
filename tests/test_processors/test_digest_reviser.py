"""Tests for DigestReviser processor."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.newsletter import Newsletter, NewsletterSource
from src.models.revision import RevisionContext, RevisionResult
from src.models.summary import NewsletterSummary
from src.processors.digest_reviser import DigestReviser


@pytest.fixture
def mock_model_config():
    """Create mock model configuration."""
    config = ModelConfig(
        digest_revision="claude-sonnet-4-5",
        providers=[
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")
        ],
    )
    return config


@pytest.fixture
def sample_digest():
    """Create sample digest for testing."""
    digest = Digest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 15, 0, 0, 0),
        period_end=datetime(2025, 1, 15, 23, 59, 59),
        title="AI Advances - January 15, 2025",
        executive_overview="Key AI developments this week...",
        strategic_insights=[
            {"title": "RAG Architecture", "summary": "Hybrid search...", "details": []}
        ],
        technical_developments=[
            {"title": "Vector DB Performance", "summary": "10x gains...", "details": []}
        ],
        emerging_trends=[
            {"title": "Agentic Workflows", "summary": "Moving to production...", "continuity": ""}
        ],
        actionable_recommendations={
            "For Leadership": ["Action 1"],
            "For Teams": ["Action 2"],
        },
        sources=[],
        newsletter_count=5,
        status=DigestStatus.PENDING_REVIEW,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )
    digest.id = 1
    return digest


@pytest.fixture
def sample_newsletters():
    """Create sample newsletters."""
    newsletters = []
    for i in range(3):
        newsletter = Newsletter(
            source=NewsletterSource.GMAIL,
            source_id=f"test-{i}",
            title=f"Newsletter {i+1}",
            publication="Tech Weekly",
            published_date=datetime(2025, 1, 15, 10 + i, 0, 0),
            raw_text=f"Content for newsletter {i+1} about AI and RAG systems.",
        )
        newsletter.id = i + 1
        newsletters.append(newsletter)
    return newsletters


@pytest.fixture
def sample_summaries(sample_newsletters):
    """Create sample summaries."""
    summaries = []
    for newsletter in sample_newsletters:
        summary = NewsletterSummary(
            newsletter_id=newsletter.id,
            executive_summary=f"Summary for {newsletter.title}",
            key_themes=["AI", "RAG"],
            strategic_insights=["Insight 1"],
            technical_details=["Detail 1"],
            actionable_items=["Action 1"],
            notable_quotes=[],
            relevance_scores={},
            agent_framework="claude",
            model_used="claude-haiku-4-5",
        )
        summary.newsletter = newsletter
        summaries.append(summary)
    return summaries


class TestDigestReviserInitialization:
    """Tests for DigestReviser initialization."""

    def test_initialization_with_config(self, mock_model_config):
        """Test initialization with ModelConfig."""
        reviser = DigestReviser(model_config=mock_model_config)

        assert reviser.model_config == mock_model_config
        assert reviser.model == "claude-sonnet-4-5"
        assert reviser.provider_used is None
        assert reviser.input_tokens == 0
        assert reviser.output_tokens == 0

    def test_initialization_with_model_override(self, mock_model_config):
        """Test initialization with model override."""
        reviser = DigestReviser(
            model_config=mock_model_config,
            model="claude-opus-4-5"
        )

        assert reviser.model == "claude-opus-4-5"

    @patch('src.processors.digest_reviser.settings')
    def test_initialization_without_config(self, mock_settings):
        """Test initialization without config (uses settings)."""
        mock_settings.get_model_config.return_value = mock_model_config

        reviser = DigestReviser()

        assert reviser.model_config is not None
        mock_settings.get_model_config.assert_called_once()


class TestDigestReviserLoadContext:
    """Tests for load_context method."""

    @pytest.mark.asyncio
    async def test_load_context_success(
        self, sample_digest, sample_summaries, sample_newsletters
    ):
        """Test successful context loading."""
        with patch('src.processors.digest_reviser.get_db') as mock_get_db:
            # Setup mock database session
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Mock digest query
            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            # Mock summaries query
            mock_summaries_query = MagicMock()
            mock_summaries_query.join.return_value = mock_summaries_query
            mock_summaries_query.filter.return_value = mock_summaries_query
            mock_summaries_query.order_by.return_value = mock_summaries_query
            mock_summaries_query.all.return_value = sample_summaries

            # Chain query calls
            mock_db.query.side_effect = [
                mock_db.query.return_value,  # First call for Digest
                mock_summaries_query,  # Second call for NewsletterSummary
            ]

            reviser = DigestReviser()
            context = await reviser.load_context(digest_id=1)

            assert isinstance(context, RevisionContext)
            assert context.digest == sample_digest
            assert len(context.summaries) == 3
            assert context.newsletter_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_load_context_digest_not_found(self):
        """Test context loading when digest doesn't exist."""
        with patch('src.processors.digest_reviser.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Mock digest query returning None
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            reviser = DigestReviser()

            with pytest.raises(ValueError, match="Digest .* not found"):
                await reviser.load_context(digest_id=999)


class TestDigestReviserToolDefinitions:
    """Tests for tool definitions."""

    def test_get_tool_definitions(self):
        """Test that tool definitions are properly formatted."""
        reviser = DigestReviser()
        tools = reviser._get_tool_definitions()

        assert len(tools) == 2

        # Check fetch_newsletter_content tool
        fetch_tool = tools[0]
        assert fetch_tool["name"] == "fetch_newsletter_content"
        assert "input_schema" in fetch_tool
        assert fetch_tool["input_schema"]["properties"]["newsletter_id"]["type"] == "integer"

        # Check search_newsletters tool
        search_tool = tools[1]
        assert search_tool["name"] == "search_newsletters"
        assert "input_schema" in search_tool
        assert search_tool["input_schema"]["properties"]["query"]["type"] == "string"


class TestDigestReviserToolHandlers:
    """Tests for tool call handlers."""

    @pytest.mark.asyncio
    async def test_handle_fetch_newsletter_content(
        self, sample_newsletters, sample_summaries
    ):
        """Test fetching newsletter content."""
        with patch('src.processors.digest_reviser.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Mock newsletter query
            newsletter = sample_newsletters[0]
            mock_db.query.return_value.filter_by.return_value.first.return_value = newsletter

            reviser = DigestReviser()
            context = RevisionContext(
                digest=MagicMock(),
                summaries=sample_summaries,
                newsletter_ids=[1, 2, 3],
            )

            result = await reviser._handle_tool_call(
                tool_name="fetch_newsletter_content",
                tool_input={"newsletter_id": 1},
                context=context,
            )

            assert "Newsletter 1" in result
            assert "Tech Weekly" in result
            assert "Content for newsletter 1" in result

    @pytest.mark.asyncio
    async def test_handle_fetch_newsletter_not_in_context(self, sample_summaries):
        """Test fetching newsletter not in current digest period."""
        reviser = DigestReviser()
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
            newsletter_ids=[1, 2, 3],
        )

        result = await reviser._handle_tool_call(
            tool_name="fetch_newsletter_content",
            tool_input={"newsletter_id": 999},
            context=context,
        )

        assert "Error" in result
        assert "not in current digest period" in result

    @pytest.mark.asyncio
    async def test_handle_search_newsletters(self, sample_summaries):
        """Test searching newsletters."""
        reviser = DigestReviser()
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
        )

        result = await reviser._handle_tool_call(
            tool_name="search_newsletters",
            tool_input={"query": "RAG"},
            context=context,
        )

        assert "Found" in result or "No newsletters found" in result

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, sample_summaries):
        """Test handling unknown tool name."""
        reviser = DigestReviser()
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
        )

        result = await reviser._handle_tool_call(
            tool_name="unknown_tool",
            tool_input={},
            context=context,
        )

        assert "Error" in result
        assert "Unknown tool" in result


class TestDigestReviserApplyRevision:
    """Tests for apply_revision method."""

    @pytest.mark.asyncio
    async def test_apply_revision_executive_overview(self, sample_digest):
        """Test applying revision to executive overview."""
        reviser = DigestReviser()

        new_content = "New concise executive summary..."
        updated_digest = await reviser.apply_revision(
            digest=sample_digest,
            section="executive_overview",
            new_content=new_content,
            increment_count=True,
        )

        assert updated_digest.executive_overview == new_content
        assert updated_digest.revision_count == 1

    @pytest.mark.asyncio
    async def test_apply_revision_strategic_insights(self, sample_digest):
        """Test applying revision to strategic insights."""
        reviser = DigestReviser()

        new_insights = [
            {"title": "New Insight", "summary": "Summary", "details": []}
        ]
        updated_digest = await reviser.apply_revision(
            digest=sample_digest,
            section="strategic_insights",
            new_content=new_insights,
        )

        assert updated_digest.strategic_insights == new_insights
        assert updated_digest.revision_count == 1

    @pytest.mark.asyncio
    async def test_apply_revision_without_increment(self, sample_digest):
        """Test applying revision without incrementing count."""
        reviser = DigestReviser()

        updated_digest = await reviser.apply_revision(
            digest=sample_digest,
            section="title",
            new_content="New Title",
            increment_count=False,
        )

        assert updated_digest.title == "New Title"
        assert updated_digest.revision_count == 0

    @pytest.mark.asyncio
    async def test_apply_revision_invalid_section(self, sample_digest):
        """Test applying revision to invalid section."""
        reviser = DigestReviser()

        with pytest.raises(ValueError, match="Invalid section"):
            await reviser.apply_revision(
                digest=sample_digest,
                section="invalid_section",
                new_content="Test",
            )


class TestDigestReviserCostCalculation:
    """Tests for cost calculation."""

    def test_calculate_cost_no_usage(self, mock_model_config):
        """Test cost calculation with no token usage."""
        reviser = DigestReviser(model_config=mock_model_config)

        cost = reviser.calculate_cost()

        assert cost == 0.0

    def test_calculate_cost_with_usage(self, mock_model_config):
        """Test cost calculation with token usage."""
        reviser = DigestReviser(model_config=mock_model_config)

        # Simulate token usage
        reviser.provider_used = Provider.ANTHROPIC
        reviser.input_tokens = 1000
        reviser.output_tokens = 500

        cost = reviser.calculate_cost()

        # Should calculate based on model pricing
        assert cost > 0.0


class TestDigestReviserExtractJSON:
    """Tests for JSON extraction from responses."""

    def test_extract_json_direct_parse(self):
        """Test extracting JSON from direct JSON string."""
        reviser = DigestReviser()

        response_text = '{"section_modified": "executive_overview", "revised_content": "New text", "explanation": "Test"}'

        result = reviser._extract_json_from_response(response_text)

        assert result["section_modified"] == "executive_overview"
        assert result["revised_content"] == "New text"

    def test_extract_json_from_markdown_block(self):
        """Test extracting JSON from markdown code block."""
        reviser = DigestReviser()

        response_text = """Here's the revision:

```json
{
  "section_modified": "strategic_insights",
  "revised_content": ["Item 1", "Item 2"],
  "explanation": "Updated insights"
}
```

Hope that helps!"""

        result = reviser._extract_json_from_response(response_text)

        assert result["section_modified"] == "strategic_insights"
        assert len(result["revised_content"]) == 2

    def test_extract_json_invalid_format(self):
        """Test extracting JSON from invalid format."""
        reviser = DigestReviser()

        response_text = "This is not JSON at all"

        with pytest.raises(json.JSONDecodeError):
            reviser._extract_json_from_response(response_text)
