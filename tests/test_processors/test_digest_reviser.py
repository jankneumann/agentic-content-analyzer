"""Tests for DigestReviser processor.

Updated to mock LLMRouter.generate_with_tools() instead of direct Anthropic SDK.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.config.models import ModelConfig, Provider, ProviderConfig
from src.models.content import Content, ContentSource
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.revision import RevisionContext
from src.models.summary import Summary
from src.processors.digest_reviser import DigestReviser
from src.services.llm_router import LLMResponse, ToolDefinition


@pytest.fixture
def mock_model_config():
    """Create mock model configuration."""
    config = ModelConfig(
        digest_revision="claude-sonnet-4-5",
        providers=[ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")],
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
        revision_count=0,
    )
    digest.id = 1
    return digest


@pytest.fixture
def sample_contents():
    """Create sample content items."""
    contents = []
    for i in range(3):
        content = Content(
            source_type=ContentSource.RSS,
            source_id=f"test-{i}",
            title=f"Content Item {i + 1}",
            publication="Tech Weekly",
            published_date=datetime(2025, 1, 15, 10 + i, 0, 0),
            markdown_content=f"Content for item {i + 1} about AI and RAG systems.",
            content_hash=f"hash-{i}",
        )
        content.id = i + 1
        contents.append(content)
    return contents


@pytest.fixture
def sample_summaries(sample_contents):
    """Create sample summaries."""
    summaries = []
    for content in sample_contents:
        summary = Summary(
            content_id=content.id,
            executive_summary=f"Summary for {content.title}",
            key_themes=["AI", "RAG"],
            strategic_insights=["Insight 1"],
            technical_details=["Detail 1"],
            actionable_items=["Action 1"],
            notable_quotes=[],
            relevance_scores={},
            agent_framework="claude",
            model_used="claude-haiku-4-5",
        )
        summary.content = content
        summaries.append(summary)
    return summaries


class TestDigestReviserInitialization:
    """Tests for DigestReviser initialization."""

    def test_initialization_with_config(self, mock_model_config):
        """Test initialization with ModelConfig."""
        reviser = DigestReviser(model_config=mock_model_config)

        assert reviser.model_config == mock_model_config
        assert reviser.model == "claude-sonnet-4-5"
        assert reviser.router is not None
        assert reviser.provider_used is None
        assert reviser.input_tokens == 0
        assert reviser.output_tokens == 0

    def test_initialization_with_model_override(self, mock_model_config):
        """Test initialization with model override."""
        reviser = DigestReviser(model_config=mock_model_config, model="claude-opus-4-5")

        assert reviser.model == "claude-opus-4-5"

    @patch("src.config.settings")
    def test_initialization_without_config(self, mock_settings, mock_model_config):
        """Test initialization without config (uses settings)."""
        mock_settings.get_model_config.return_value = mock_model_config

        reviser = DigestReviser()

        assert reviser.model_config is not None
        mock_settings.get_model_config.assert_called_once()


class TestDigestReviserLoadContext:
    """Tests for load_context method."""

    @pytest.mark.asyncio
    async def test_load_context_success(self, sample_digest, sample_summaries, sample_contents):
        """Test successful context loading."""
        with patch("src.processors.digest_reviser.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            digest_query_mock = MagicMock()
            digest_query_mock.filter_by.return_value.first.return_value = sample_digest

            summary_query_mock = MagicMock()
            summary_query_mock.options.return_value = summary_query_mock
            summary_query_mock.join.return_value = summary_query_mock
            summary_query_mock.filter.return_value = summary_query_mock
            summary_query_mock.order_by.return_value = summary_query_mock
            summary_query_mock.all.return_value = sample_summaries

            def query_side_effect(model):
                if model.__name__ == "Digest":
                    return digest_query_mock
                elif model.__name__ == "Summary":
                    return summary_query_mock
                return MagicMock()

            mock_db.query.side_effect = query_side_effect

            reviser = DigestReviser()
            context = await reviser.load_context(digest_id=1)

            assert isinstance(context, RevisionContext)
            assert context.digest == sample_digest
            assert len(context.summaries) == 3
            assert context.content_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_load_context_digest_not_found(self):
        """Test context loading when digest doesn't exist."""
        with patch("src.processors.digest_reviser.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            reviser = DigestReviser()

            with pytest.raises(ValueError, match="Digest .* not found"):
                await reviser.load_context(digest_id=999)


class TestDigestReviserToolDefinitions:
    """Tests for tool definitions."""

    def test_get_tool_definitions_returns_tool_definition_objects(self):
        """Tool definitions should be ToolDefinition objects (not Anthropic dicts)."""
        reviser = DigestReviser()
        tools = reviser._get_tool_definitions()

        assert len(tools) == 2
        assert all(isinstance(t, ToolDefinition) for t in tools)

        # Check fetch_content tool
        fetch_tool = tools[0]
        assert fetch_tool.name == "fetch_content"
        assert fetch_tool.parameters["properties"]["content_id"]["type"] == "integer"

        # Check search_content tool
        search_tool = tools[1]
        assert search_tool.name == "search_content"
        assert search_tool.parameters["properties"]["query"]["type"] == "string"


class TestDigestReviserToolHandlers:
    """Tests for tool call handlers."""

    @pytest.mark.asyncio
    async def test_handle_fetch_content(self, sample_contents, sample_summaries):
        """Test fetching content."""
        with patch("src.processors.digest_reviser.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            content = sample_contents[0]
            mock_db.query.return_value.filter_by.return_value.first.return_value = content

            reviser = DigestReviser()
            context = RevisionContext(
                digest=MagicMock(),
                summaries=sample_summaries,
                content_ids=[1, 2, 3],
            )

            result = await reviser._handle_tool_call(
                tool_name="fetch_content",
                tool_input={"content_id": 1},
                context=context,
            )

            assert "Content Item 1" in result
            assert "Tech Weekly" in result
            assert "Content for item 1" in result

    @pytest.mark.asyncio
    async def test_handle_fetch_content_not_in_context(self, sample_summaries):
        """Test fetching content not in current digest period."""
        reviser = DigestReviser()
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
            content_ids=[1, 2, 3],
        )

        result = await reviser._handle_tool_call(
            tool_name="fetch_content",
            tool_input={"content_id": 999},
            context=context,
        )

        assert "Error" in result
        assert "not in current digest period" in result

    @pytest.mark.asyncio
    async def test_handle_search_content(self, sample_summaries):
        """Test searching content."""
        reviser = DigestReviser()
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
        )

        result = await reviser._handle_tool_call(
            tool_name="search_content",
            tool_input={"query": "RAG"},
            context=context,
        )

        assert "Found" in result or "No content found" in result

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


class TestDigestReviserReviseSection:
    """Tests for revise_section method using LLMRouter."""

    @pytest.mark.asyncio
    async def test_revise_section_calls_router(self, mock_model_config, sample_summaries):
        """revise_section should delegate to LLMRouter.generate_with_tools()."""
        revision_json = json.dumps(
            {
                "section_modified": "executive_overview",
                "revised_content": "Improved overview text",
                "explanation": "Made it more concise",
                "confidence_score": 0.95,
            }
        )

        mock_response = LLMResponse(
            text=revision_json,
            input_tokens=1000,
            output_tokens=500,
            provider=Provider.ANTHROPIC,
        )

        reviser = DigestReviser(model_config=mock_model_config)
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
            content_ids=[1, 2, 3],
        )
        context.to_llm_context = MagicMock(return_value="Mock context text")

        with patch.object(
            reviser.router, "generate_with_tools", return_value=mock_response
        ) as mock_gen:
            result = await reviser.revise_section(context, "Make it more concise")

            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args.kwargs
            assert call_kwargs["max_tokens"] == 8000
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["max_iterations"] == 5
            assert len(call_kwargs["tools"]) == 2
            assert result.section_modified == "executive_overview"
            assert result.revised_content == "Improved overview text"

    @pytest.mark.asyncio
    async def test_revise_section_tracks_tokens(self, mock_model_config, sample_summaries):
        """Should accumulate token usage from the router response."""
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "section_modified": "title",
                    "revised_content": "New Title",
                    "explanation": "Shortened",
                }
            ),
            input_tokens=800,
            output_tokens=200,
            provider=Provider.ANTHROPIC,
        )

        reviser = DigestReviser(model_config=mock_model_config)
        context = RevisionContext(
            digest=MagicMock(),
            summaries=sample_summaries,
        )
        context.to_llm_context = MagicMock(return_value="Context")

        with patch.object(reviser.router, "generate_with_tools", return_value=mock_response):
            await reviser.revise_section(context, "Shorten the title")

            assert reviser.input_tokens == 800
            assert reviser.output_tokens == 200
            assert reviser.provider_used == Provider.ANTHROPIC


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

        new_insights = [{"title": "New Insight", "summary": "Summary", "details": []}]
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

        reviser.provider_used = Provider.ANTHROPIC
        reviser.input_tokens = 1000
        reviser.output_tokens = 500

        cost = reviser.calculate_cost()

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
