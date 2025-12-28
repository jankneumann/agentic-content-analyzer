"""Tests for HistoricalContextAnalyzer."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.theme import (
    HistoricalMention,
    ThemeCategory,
    ThemeData,
    ThemeEvolution,
    ThemeTrend,
)
from src.processors.historical_context import HistoricalContextAnalyzer


@pytest.fixture
def sample_themes() -> list[ThemeData]:
    """Create sample themes for testing."""
    return [
        ThemeData(
            name="Large Language Models",
            description="Advanced LLM capabilities",
            category=ThemeCategory.ML_AI,
            mention_count=3,
            trend=ThemeTrend.GROWING,
            relevance_score=0.9,
            strategic_relevance=0.85,
            tactical_relevance=0.75,
            novelty_score=0.6,
            cross_functional_impact=0.8,
            related_themes=["AI Agents"],
            key_points=["Context windows expanding"],
            newsletter_ids=[1, 2, 3],
            first_seen=datetime(2025, 1, 5),
            last_seen=datetime(2025, 1, 15),
        ),
        ThemeData(
            name="Vector Databases",
            description="Performance optimization",
            category=ThemeCategory.DATA_ENGINEERING,
            mention_count=1,
            trend=ThemeTrend.EMERGING,
            relevance_score=0.7,
            strategic_relevance=0.6,
            tactical_relevance=0.85,
            novelty_score=0.9,
            cross_functional_impact=0.5,
            related_themes=["RAG"],
            key_points=["Hybrid search"],
            newsletter_ids=[2],
            first_seen=datetime(2025, 1, 10),
            last_seen=datetime(2025, 1, 10),
        ),
    ]


@pytest.fixture
def sample_historical_mentions() -> list[dict]:
    """Create sample historical mentions from Graphiti."""
    return [
        {
            "timestamp": datetime(2025, 1, 10),
            "title": "AI Newsletter #1",
            "source": "Tech Weekly",
            "content": "Discussion about Large Language Models and their performance improvements",
        },
        {
            "timestamp": datetime(2025, 1, 5),
            "title": "AI Newsletter #2",
            "source": "AI Digest",
            "content": "Large Language Models are becoming more efficient",
        },
        {
            "timestamp": datetime(2024, 12, 20),
            "title": "AI Newsletter #3",
            "source": "Tech Weekly",
            "content": "Early discussion of LLM capabilities and limitations",
        },
    ]


@pytest.fixture
def sample_timeline() -> list[dict]:
    """Create sample timeline data."""
    return [
        {
            "timestamp": datetime(2024, 12, 20),
            "title": "AI Newsletter #3",
            "content": "Early discussion of LLM capabilities",
        },
        {
            "timestamp": datetime(2025, 1, 5),
            "title": "AI Newsletter #2",
            "content": "LLMs becoming more efficient",
        },
        {
            "timestamp": datetime(2025, 1, 10),
            "title": "AI Newsletter #1",
            "content": "Discussion about LLM performance",
        },
    ]


@pytest.fixture
def mock_llm_evolution_response() -> str:
    """Create mock LLM response for evolution analysis."""
    return """```json
{
  "evolution_summary": "Discussion has shifted from theoretical capabilities to practical performance improvements and cost reduction.",
  "previous_discussions": [
    "Initial focus on model capabilities and limitations",
    "Growing interest in efficiency and cost optimization",
    "Recent emphasis on production deployments"
  ],
  "stance_change": "From cautious exploration to confident adoption"
}
```"""


def test_historical_context_analyzer_initialization():
    """Test HistoricalContextAnalyzer initialization."""
    with patch("src.processors.historical_context.Anthropic") as mock_anthropic:
        analyzer = HistoricalContextAnalyzer()

        assert analyzer.model == "claude-sonnet-4-20250514"
        assert analyzer.graphiti_client is None
        mock_anthropic.assert_called_once()


def test_historical_context_analyzer_custom_model():
    """Test initialization with custom model."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer(model="claude-opus-4-5-20251101")

        assert analyzer.model == "claude-opus-4-5-20251101"


@pytest.mark.asyncio
async def test_enrich_themes_with_history_success(
    sample_themes, sample_historical_mentions, sample_timeline, mock_llm_evolution_response
):
    """Test successful theme enrichment with historical context."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_llm_evolution_response)]
    mock_client.messages.create.return_value = mock_response

    mock_graphiti = AsyncMock()
    mock_graphiti.get_historical_theme_mentions = AsyncMock(
        return_value=sample_historical_mentions
    )
    mock_graphiti.get_theme_evolution_timeline = AsyncMock(return_value=sample_timeline)
    mock_graphiti.close = MagicMock()

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch(
            "src.processors.historical_context.GraphitiClient"
        ) as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            analyzer = HistoricalContextAnalyzer()
            enriched_themes = await analyzer.enrich_themes_with_history(
                themes=sample_themes,
                current_date=datetime(2025, 1, 15),
                lookback_days=90,
            )

    # Verify enrichment
    assert len(enriched_themes) == 2

    # First theme should have historical context
    assert enriched_themes[0].historical_context is not None
    assert enriched_themes[0].continuity_text is not None
    assert "Growing Theme" in enriched_themes[0].continuity_text

    # GraphitiClient should be closed
    mock_graphiti.close.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_themes_with_history_no_history(sample_themes):
    """Test enrichment when no historical data exists."""
    mock_client = MagicMock()

    mock_graphiti = AsyncMock()
    mock_graphiti.get_historical_theme_mentions = AsyncMock(return_value=[])
    mock_graphiti.close = MagicMock()

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch(
            "src.processors.historical_context.GraphitiClient"
        ) as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            analyzer = HistoricalContextAnalyzer()
            enriched_themes = await analyzer.enrich_themes_with_history(
                themes=sample_themes[:1],  # Just one theme
                current_date=datetime(2025, 1, 15),
            )

    # Should still enrich, marking as new theme
    assert len(enriched_themes) == 1
    assert enriched_themes[0].historical_context.total_mentions == 0
    assert enriched_themes[0].historical_context.mention_frequency == "new"
    assert "new theme" in enriched_themes[0].historical_context.evolution_summary


@pytest.mark.asyncio
async def test_analyze_theme_evolution_with_history(
    sample_historical_mentions, sample_timeline, mock_llm_evolution_response
):
    """Test theme evolution analysis with historical data."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_llm_evolution_response)]
    mock_client.messages.create.return_value = mock_response

    mock_graphiti = AsyncMock()
    mock_graphiti.get_historical_theme_mentions = AsyncMock(
        return_value=sample_historical_mentions
    )
    mock_graphiti.get_theme_evolution_timeline = AsyncMock(return_value=sample_timeline)

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch(
            "src.processors.historical_context.GraphitiClient"
        ) as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            analyzer = HistoricalContextAnalyzer()
            analyzer.graphiti_client = mock_graphiti

            evolution = await analyzer._analyze_theme_evolution(
                theme_name="Large Language Models",
                current_date=datetime(2025, 1, 15),
                lookback_days=90,
            )

    # Verify evolution data
    assert evolution.theme_name == "Large Language Models"
    assert evolution.total_mentions == 3
    assert evolution.first_mention == datetime(2024, 12, 20)
    assert evolution.mention_frequency in ["rare", "occasional", "frequent", "constant"]
    assert len(evolution.evolution_summary) > 0
    assert len(evolution.previous_discussions) > 0
    assert len(evolution.recent_mentions) > 0


@pytest.mark.asyncio
async def test_analyze_theme_evolution_no_history():
    """Test theme evolution when no historical data exists."""
    mock_graphiti = AsyncMock()
    mock_graphiti.get_historical_theme_mentions = AsyncMock(return_value=[])

    with patch("src.processors.historical_context.Anthropic"):
        with patch(
            "src.processors.historical_context.GraphitiClient"
        ) as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            analyzer = HistoricalContextAnalyzer()
            analyzer.graphiti_client = mock_graphiti

            evolution = await analyzer._analyze_theme_evolution(
                theme_name="New Theme",
                current_date=datetime(2025, 1, 15),
                lookback_days=90,
            )

    # Should return new theme evolution
    assert evolution.total_mentions == 0
    assert evolution.mention_frequency == "new"
    assert "new theme" in evolution.evolution_summary.lower()
    assert len(evolution.recent_mentions) == 0


def test_extract_recent_mentions(sample_historical_mentions):
    """Test extracting recent mentions from raw data."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        mentions = analyzer._extract_recent_mentions(sample_historical_mentions)

    assert len(mentions) == 3

    # Verify first mention
    assert isinstance(mentions[0], HistoricalMention)
    assert mentions[0].date == datetime(2025, 1, 10)
    assert mentions[0].newsletter_title == "AI Newsletter #1"
    assert mentions[0].publication == "Tech Weekly"
    assert "Large Language Models" in mentions[0].context


def test_extract_recent_mentions_long_content():
    """Test context truncation for long content."""
    long_content = "A" * 300  # Content longer than 200 chars

    mentions = [
        {
            "timestamp": datetime(2025, 1, 10),
            "title": "Test",
            "source": "Source",
            "content": long_content,
        }
    ]

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        result = analyzer._extract_recent_mentions(mentions)

    # Context should be truncated to 200 chars + "..."
    assert len(result[0].context) == 203  # 200 + "..."
    assert result[0].context.endswith("...")


def test_extract_recent_mentions_empty():
    """Test extracting from empty mentions list."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        mentions = analyzer._extract_recent_mentions([])

    assert len(mentions) == 0


@pytest.mark.asyncio
async def test_analyze_evolution_with_llm_success(
    sample_timeline, mock_llm_evolution_response
):
    """Test LLM-based evolution analysis."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_llm_evolution_response)]
    mock_client.messages.create.return_value = mock_response

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        analyzer = HistoricalContextAnalyzer()
        summary, discussions, stance = await analyzer._analyze_evolution_with_llm(
            theme_name="Large Language Models",
            timeline=sample_timeline,
            recent_mentions=[],
        )

    # Verify parsed results
    assert len(summary) > 0
    assert "performance" in summary.lower()
    assert len(discussions) == 3
    assert "Initial focus" in discussions[0]
    assert stance == "From cautious exploration to confident adoption"

    # Verify LLM was called with correct prompt
    mock_client.messages.create.assert_called_once()
    call_args = mock_client.messages.create.call_args
    assert call_args[1]["model"] == "claude-sonnet-4-20250514"
    assert call_args[1]["temperature"] == 0.3
    assert "Large Language Models" in call_args[1]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_analyze_evolution_with_llm_no_timeline():
    """Test evolution analysis with empty timeline."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        summary, discussions, stance = await analyzer._analyze_evolution_with_llm(
            theme_name="Test Theme",
            timeline=[],
            recent_mentions=[],
        )

    assert summary == "No historical data available."
    assert discussions == []
    assert stance is None


@pytest.mark.asyncio
async def test_analyze_evolution_with_llm_invalid_json():
    """Test handling of invalid JSON from LLM."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is not valid JSON")]
    mock_client.messages.create.return_value = mock_response

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        analyzer = HistoricalContextAnalyzer()
        summary, discussions, stance = await analyzer._analyze_evolution_with_llm(
            theme_name="Test Theme",
            timeline=[{"timestamp": datetime(2025, 1, 1), "title": "Test", "content": "Test"}],
            recent_mentions=[],
        )

    # Should return error defaults
    assert summary == "Unable to analyze evolution."
    assert discussions == []
    assert stance is None


@pytest.mark.asyncio
async def test_analyze_evolution_with_llm_no_markdown():
    """Test parsing response without markdown code blocks."""
    mock_response_no_markdown = """{
  "evolution_summary": "Test summary",
  "previous_discussions": ["Point 1", "Point 2"],
  "stance_change": null
}"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_response_no_markdown)]
    mock_client.messages.create.return_value = mock_response

    with patch("src.processors.historical_context.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        analyzer = HistoricalContextAnalyzer()
        summary, discussions, stance = await analyzer._analyze_evolution_with_llm(
            theme_name="Test Theme",
            timeline=[{"timestamp": datetime(2025, 1, 1), "title": "Test", "content": "Test"}],
            recent_mentions=[],
        )

    assert summary == "Test summary"
    assert discussions == ["Point 1", "Point 2"]
    assert stance is None


def test_build_timeline_context(sample_timeline):
    """Test building timeline context for LLM."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        context = analyzer._build_timeline_context(sample_timeline)

    # Verify all timeline entries are included
    assert "2024-12-20" in context
    assert "AI Newsletter #3" in context
    assert "Early discussion" in context

    assert "2025-01-05" in context
    assert "AI Newsletter #2" in context

    assert "2025-01-10" in context
    assert "AI Newsletter #1" in context


def test_build_timeline_context_empty():
    """Test building timeline context with no data."""
    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        context = analyzer._build_timeline_context([])

    assert context == "No historical mentions found."


def test_build_timeline_context_truncates_long_timeline():
    """Test that timeline context only uses last 10 mentions."""
    # Create 15 timeline entries
    long_timeline = [
        {
            "timestamp": datetime(2024, 12, i),
            "title": f"Newsletter {i}",
            "content": f"Content {i}",
        }
        for i in range(1, 16)
    ]

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        context = analyzer._build_timeline_context(long_timeline)

    # Should only include last 10 (entries 6-15)
    assert "Newsletter 15" in context
    assert "Newsletter 6" in context
    assert "Newsletter 5" not in context  # Should be excluded


def test_generate_continuity_text_new_theme():
    """Test continuity text for new theme."""
    evolution = ThemeEvolution(
        theme_name="New Theme",
        first_mention=datetime.now(),
        total_mentions=0,
        mention_frequency="new",
        evolution_summary="This is a new theme.",
        previous_discussions=[],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="New Theme",
            evolution=evolution,
            current_trend="emerging",
        )

    assert "New Theme" in text
    assert "first time" in text


def test_generate_continuity_text_emerging():
    """Test continuity text for emerging theme."""
    evolution = ThemeEvolution(
        theme_name="Emerging Theme",
        first_mention=datetime.now() - timedelta(days=20),
        total_mentions=5,
        mention_frequency="occasional",
        evolution_summary="Growing in popularity.",
        previous_discussions=["Point 1"],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="Emerging Theme",
            evolution=evolution,
            current_trend="emerging",
        )

    assert "Emerging Theme" in text
    assert "gaining traction" in text
    assert "Growing in popularity" in text


def test_generate_continuity_text_growing():
    """Test continuity text for growing theme."""
    evolution = ThemeEvolution(
        theme_name="Growing Theme",
        first_mention=datetime.now() - timedelta(days=45),
        total_mentions=15,
        mention_frequency="frequent",
        evolution_summary="Increasing adoption.",
        previous_discussions=["Point 1", "Point 2"],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="Growing Theme",
            evolution=evolution,
            current_trend="growing",
        )

    assert "Growing Theme" in text
    assert "increasing in prominence" in text
    assert "frequent" in text


def test_generate_continuity_text_established():
    """Test continuity text for established theme."""
    evolution = ThemeEvolution(
        theme_name="Established Theme",
        first_mention=datetime.now() - timedelta(days=120),
        total_mentions=50,
        mention_frequency="constant",
        evolution_summary="Stable discussion.",
        previous_discussions=["Point 1", "Point 2", "Point 3"],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="Established Theme",
            evolution=evolution,
            current_trend="established",
        )

    assert "Established Theme" in text
    assert "core topic" in text
    assert "50 mentions" in text


def test_generate_continuity_text_declining():
    """Test continuity text for declining theme."""
    evolution = ThemeEvolution(
        theme_name="Declining Theme",
        first_mention=datetime.now() - timedelta(days=60),
        total_mentions=20,
        mention_frequency="rare",
        evolution_summary="Decreasing interest.",
        previous_discussions=["Point 1"],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="Declining Theme",
            evolution=evolution,
            current_trend="declining",
        )

    assert "Declining Theme" in text
    assert "appearing less often" in text
    assert "Decreasing interest" in text


def test_generate_continuity_text_one_off():
    """Test continuity text for one-off/recurring theme."""
    evolution = ThemeEvolution(
        theme_name="Recurring Theme",
        first_mention=datetime.now() - timedelta(days=30),
        total_mentions=8,
        mention_frequency="occasional",
        evolution_summary="Periodic discussion.",
        previous_discussions=["Point 1"],
        recent_mentions=[],
    )

    with patch("src.processors.historical_context.Anthropic"):
        analyzer = HistoricalContextAnalyzer()
        text = analyzer._generate_continuity_text(
            theme_name="Recurring Theme",
            evolution=evolution,
            current_trend="one_off",
        )

    assert "Recurring Theme" in text
    assert "8 times" in text
    assert "Periodic discussion" in text
