"""Tests for summary markdown generation utilities."""

import pytest

from src.utils.summary_markdown import (
    enrich_summary_data,
    extract_summary_theme_tags,
    generate_summary_markdown,
    parse_markdown_summary,
)


@pytest.fixture
def sample_summary_data():
    """Sample summary data for testing."""
    return {
        "executive_summary": "AI is transforming enterprise workflows with new automation capabilities.",
        "key_themes": ["AI Automation", "Enterprise Integration", "Cost Optimization"],
        "strategic_insights": [
            "Consider AI-first architecture for new projects",
            "ROI on AI tools typically seen within 6 months",
        ],
        "technical_details": [
            "LangChain 0.2 introduces improved memory management",
            "Vector databases now support hybrid search natively",
        ],
        "actionable_items": [
            "Evaluate current AI tool stack",
            "Start POC with document automation",
        ],
        "notable_quotes": [
            "The future of work is AI-augmented, not AI-replaced",
            "We're seeing 40% productivity gains in early adopters",
        ],
        "relevant_links": [
            {"title": "LangChain Documentation", "url": "https://docs.langchain.com"},
            {"title": "AI ROI Study", "url": "https://example.com/roi-study"},
        ],
        "relevance_scores": {
            "cto_leadership": 0.95,
            "technical_teams": 0.85,
            "individual_developers": 0.75,
        },
    }


class TestGenerateSummaryMarkdown:
    """Tests for generate_summary_markdown function."""

    def test_generates_executive_summary_section(self, sample_summary_data):
        """Executive summary section is generated."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Executive Summary" in md
        assert "AI is transforming enterprise workflows" in md

    def test_generates_key_themes_section(self, sample_summary_data):
        """Key themes section is generated."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Key Themes" in md
        assert "- AI Automation" in md
        assert "- Enterprise Integration" in md

    def test_generates_strategic_insights_section(self, sample_summary_data):
        """Strategic insights section is generated with audience tag."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Strategic Insights" in md
        assert "*For CTOs and Technical Leaders*" in md
        assert "- Consider AI-first architecture" in md

    def test_generates_technical_details_section(self, sample_summary_data):
        """Technical details section is generated with audience tag."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Technical Details" in md
        assert "*For Developers and Practitioners*" in md
        assert "- LangChain 0.2" in md

    def test_generates_actionable_items_section(self, sample_summary_data):
        """Actionable items section is generated."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Actionable Items" in md
        assert "- Evaluate current AI tool stack" in md

    def test_generates_notable_quotes_section(self, sample_summary_data):
        """Notable quotes section is generated as blockquotes."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Notable Quotes" in md
        assert "> The future of work is AI-augmented" in md

    def test_generates_relevant_links_section(self, sample_summary_data):
        """Relevant links section is generated as markdown links."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Relevant Links" in md
        assert "[LangChain Documentation](https://docs.langchain.com)" in md

    def test_generates_relevance_scores_section(self, sample_summary_data):
        """Relevance scores section is generated with formatted values."""
        md = generate_summary_markdown(sample_summary_data)
        assert "## Relevance Scores" in md
        assert "**Cto Leadership**: 0.95" in md
        assert "**Technical Teams**: 0.85" in md

    def test_handles_empty_data(self):
        """Empty data returns empty string."""
        md = generate_summary_markdown({})
        assert md == ""

    def test_handles_partial_data(self):
        """Partial data only generates present sections."""
        partial_data = {
            "executive_summary": "Brief summary",
            "key_themes": ["Theme 1"],
        }
        md = generate_summary_markdown(partial_data)
        assert "## Executive Summary" in md
        assert "## Key Themes" in md
        assert "## Strategic Insights" not in md
        assert "## Technical Details" not in md

    def test_handles_link_without_url(self):
        """Links without URL are handled gracefully."""
        data = {
            "relevant_links": [
                {"title": "Some Resource"},
                {"title": "With URL", "url": "https://example.com"},
            ]
        }
        md = generate_summary_markdown(data)
        assert "- Some Resource" in md
        assert "[With URL](https://example.com)" in md


class TestExtractSummaryThemeTags:
    """Tests for extract_summary_theme_tags function."""

    def test_extracts_from_key_themes(self, sample_summary_data):
        """Extracts themes from key_themes field."""
        themes = extract_summary_theme_tags(sample_summary_data)
        assert "AI Automation" in themes
        assert "Enterprise Integration" in themes
        assert "Cost Optimization" in themes

    def test_deduplicates_themes(self):
        """Duplicate themes are removed."""
        data = {"key_themes": ["AI", "ai", "AI", "ML"]}
        themes = extract_summary_theme_tags(data)
        ai_count = sum(1 for t in themes if t.lower() == "ai")
        assert ai_count == 1

    def test_empty_key_themes(self):
        """Empty key_themes returns empty list."""
        themes = extract_summary_theme_tags({"key_themes": []})
        assert themes == []

    def test_no_key_themes_field(self):
        """Missing key_themes field returns empty list."""
        themes = extract_summary_theme_tags({})
        assert themes == []

    def test_strips_whitespace(self):
        """Themes have whitespace stripped."""
        data = {"key_themes": ["  AI  ", "  ML  "]}
        themes = extract_summary_theme_tags(data)
        assert "AI" in themes
        assert "ML" in themes


class TestEnrichSummaryData:
    """Tests for enrich_summary_data function."""

    def test_adds_markdown_content(self, sample_summary_data):
        """Enrichment adds markdown_content field."""
        enriched = enrich_summary_data(sample_summary_data)
        assert "markdown_content" in enriched
        assert "## Executive Summary" in enriched["markdown_content"]

    def test_adds_theme_tags(self, sample_summary_data):
        """Enrichment adds theme_tags field."""
        enriched = enrich_summary_data(sample_summary_data)
        assert "theme_tags" in enriched
        assert "AI Automation" in enriched["theme_tags"]

    def test_preserves_existing_fields(self, sample_summary_data):
        """Enrichment preserves all existing fields."""
        enriched = enrich_summary_data(sample_summary_data)
        assert enriched["executive_summary"] == sample_summary_data["executive_summary"]
        assert enriched["key_themes"] == sample_summary_data["key_themes"]

    def test_does_not_overwrite_existing_markdown(self):
        """Existing markdown_content is not overwritten."""
        data = {
            "key_themes": ["AI"],
            "markdown_content": "# Custom Markdown",
        }
        enriched = enrich_summary_data(data)
        assert enriched["markdown_content"] == "# Custom Markdown"

    def test_does_not_overwrite_existing_theme_tags(self):
        """Existing theme_tags are not overwritten."""
        data = {
            "key_themes": ["AI", "ML"],
            "theme_tags": ["Custom Tag"],
        }
        enriched = enrich_summary_data(data)
        assert enriched["theme_tags"] == ["Custom Tag"]


class TestParseSummaryMarkdown:
    """Tests for parse_markdown_summary function."""

    def test_parses_executive_summary(self, sample_summary_data):
        """Parses executive summary from markdown."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert "executive_summary" in parsed
        assert "AI is transforming" in parsed["executive_summary"]

    def test_parses_key_themes(self, sample_summary_data):
        """Parses key themes from markdown."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert "key_themes" in parsed
        assert "AI Automation" in parsed["key_themes"]

    def test_parses_strategic_insights(self, sample_summary_data):
        """Parses strategic insights from markdown."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert "strategic_insights" in parsed
        assert len(parsed["strategic_insights"]) == 2

    def test_parses_relevance_scores(self, sample_summary_data):
        """Parses relevance scores from markdown."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert "relevance_scores" in parsed
        assert "cto_leadership" in parsed["relevance_scores"]

    def test_parses_relevant_links(self, sample_summary_data):
        """Parses relevant links from markdown."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert "relevant_links" in parsed
        assert len(parsed["relevant_links"]) == 2
        assert parsed["relevant_links"][0]["title"] == "LangChain Documentation"


class TestRoundTrip:
    """Tests for markdown generation and parsing round-trip."""

    def test_key_themes_round_trip(self, sample_summary_data):
        """Key themes survive round-trip."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        original_themes = set(sample_summary_data["key_themes"])
        parsed_themes = set(parsed.get("key_themes", []))
        assert original_themes == parsed_themes

    def test_strategic_insights_round_trip(self, sample_summary_data):
        """Strategic insights survive round-trip."""
        md = generate_summary_markdown(sample_summary_data)
        parsed = parse_markdown_summary(md)
        assert len(parsed["strategic_insights"]) == len(
            sample_summary_data["strategic_insights"]
        )
