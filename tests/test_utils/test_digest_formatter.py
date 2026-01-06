"""Tests for digest formatting utilities."""

from datetime import datetime

import pytest

from src.models.digest import DigestData, DigestSection, DigestType
from src.utils.digest_formatter import DigestFormatter


@pytest.fixture
def sample_digest_data() -> DigestData:
    """Create sample digest data for testing."""
    return DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1, 23, 59, 59),
        title="AI/Tech Digest - January 1, 2025",
        executive_overview=(
            "Major AI developments this week include advancements in multimodal models "
            "and new frameworks for agent orchestration. Key strategic decisions needed "
            "around infrastructure investment for large-scale deployment."
        ),
        strategic_insights=[
            DigestSection(
                title="Enterprise AI Infrastructure Evolution",
                summary="Large organizations are shifting from POCs to production AI systems.",
                details=[
                    "Investment in GPU infrastructure growing 40% YoY",
                    "New governance frameworks emerging for AI deployment",
                    "Focus on cost optimization and efficiency",
                ],
                themes=["Infrastructure", "Cost Optimization"],
                continuity="This builds on last month's discussion of scaling challenges.",
            ),
        ],
        technical_developments=[
            DigestSection(
                title="New RAG Optimization Techniques",
                summary="Advanced retrieval methods improving context relevance.",
                details=[
                    "Hybrid search combining vector and keyword approaches",
                    "Context compression reducing token costs by 60%",
                    "Reranking models improving accuracy",
                ],
                themes=["RAG", "Vector Search"],
                continuity=None,
            ),
        ],
        emerging_trends=[
            DigestSection(
                title="AI Agent Swarms",
                summary="Multi-agent systems gaining traction for complex workflows.",
                details=[
                    "New frameworks for agent coordination",
                    "Use cases in data analysis and research",
                    "Challenges in debugging and observability",
                ],
                themes=["Agents", "Multi-Agent Systems"],
                continuity="First mentioned 3 weeks ago, now seeing production implementations.",
            ),
        ],
        actionable_recommendations={
            "for_leadership": [
                "Evaluate GPU infrastructure needs for Q1",
                "Review AI governance policies",
            ],
            "for_teams": [
                "Experiment with RAG optimization techniques",
                "Prototype agent-based workflows",
            ],
            "for_individuals": [
                "Learn about vector databases",
                "Explore agent frameworks like LangGraph",
            ],
        },
        sources=[
            {
                "title": "The Future of Enterprise AI",
                "publication": "TechCrunch",
                "date": "2025-01-01",
                "url": "https://techcrunch.com/article1",
            },
            {
                "title": "RAG Best Practices",
                "publication": "Towards Data Science",
                "date": "2025-01-01",
                "url": "https://towardsdatascience.com/article2",
            },
        ],
        newsletter_count=15,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=42.5,
    )


def test_to_markdown(sample_digest_data):
    """Test markdown formatting."""
    result = DigestFormatter.to_markdown(sample_digest_data)

    # Check header
    assert "# AI/Tech Digest - January 1, 2025" in result
    assert "**Period**: January 01, 2025 - January 01, 2025" in result
    assert "**Newsletters Analyzed**: 15" in result

    # Check sections
    assert "## Executive Overview" in result
    assert "Major AI developments this week" in result

    assert "## Strategic Insights" in result
    assert "### Enterprise AI Infrastructure Evolution" in result
    assert "Investment in GPU infrastructure" in result
    assert "> This builds on last month's discussion" in result

    assert "## Technical Developments" in result
    assert "### New RAG Optimization Techniques" in result
    assert "Hybrid search combining" in result

    assert "## Emerging Trends" in result
    assert "### AI Agent Swarms" in result
    assert "> 📈 First mentioned 3 weeks ago" in result

    # Check recommendations
    assert "## Actionable Recommendations" in result
    assert "### For Leadership" in result
    assert "Evaluate GPU infrastructure needs" in result
    assert "### For Teams" in result
    assert "Experiment with RAG optimization" in result
    assert "### For Individuals" in result
    assert "Learn about vector databases" in result

    # Check sources
    assert "## Sources" in result
    assert "[TechCrunch: The Future of Enterprise AI](https://techcrunch.com/article1)" in result
    assert (
        "[Towards Data Science: RAG Best Practices](https://towardsdatascience.com/article2)"
        in result
    )

    # Check footer
    assert "---" in result
    assert "*Generated on January 01, 2025 using claude*" in result


def test_to_plain_text(sample_digest_data):
    """Test plain text formatting."""
    result = DigestFormatter.to_plain_text(sample_digest_data)

    # Check header
    assert "AI/Tech Digest - January 1, 2025".upper() in result
    assert "=" * 80 in result
    assert "Period: January 01, 2025 - January 01, 2025" in result
    assert "Newsletters Analyzed: 15" in result

    # Check sections
    assert "EXECUTIVE OVERVIEW" in result
    assert "Major AI developments this week" in result

    assert "STRATEGIC INSIGHTS" in result
    assert "1. Enterprise AI Infrastructure Evolution" in result
    assert "   • Investment in GPU infrastructure" in result
    assert "   ↳ This builds on last month's discussion" in result

    assert "TECHNICAL DEVELOPMENTS" in result
    assert "1. New RAG Optimization Techniques" in result
    assert "   • Hybrid search combining" in result

    assert "EMERGING TRENDS" in result
    assert "1. AI Agent Swarms" in result
    assert "   📈 First mentioned 3 weeks ago" in result

    # Check recommendations
    assert "ACTIONABLE RECOMMENDATIONS" in result
    assert "For Leadership:" in result
    assert "  • Evaluate GPU infrastructure needs" in result
    assert "For Teams:" in result
    assert "  • Experiment with RAG optimization" in result
    assert "For Individuals:" in result
    assert "  • Learn about vector databases" in result

    # Check sources
    assert "SOURCES" in result
    assert "• TechCrunch: The Future of Enterprise AI (2025-01-01)" in result
    assert "• Towards Data Science: RAG Best Practices (2025-01-01)" in result

    # Check footer
    assert "Generated: January 01, 2025 | Framework: claude" in result


def test_markdown_empty_sections():
    """Test markdown formatting with empty optional sections."""
    minimal_digest = DigestData(
        digest_type=DigestType.WEEKLY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 7),
        title="Minimal Digest",
        executive_overview="Summary only.",
        strategic_insights=[],  # Empty
        technical_developments=[],  # Empty
        emerging_trends=[],  # Empty
        actionable_recommendations={},  # Empty
        sources=[],  # Empty
        newsletter_count=5,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    result = DigestFormatter.to_markdown(minimal_digest)

    # Should have header and overview
    assert "# Minimal Digest" in result
    assert "## Executive Overview" in result
    assert "Summary only." in result

    # Empty sections should not appear
    assert "## Strategic Insights" not in result
    assert "## Technical Developments" not in result
    assert "## Emerging Trends" not in result
    assert "## Actionable Recommendations" not in result
    assert "## Sources" not in result


def test_plain_text_empty_sections():
    """Test plain text formatting with empty optional sections."""
    minimal_digest = DigestData(
        digest_type=DigestType.WEEKLY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 7),
        title="Minimal Digest",
        executive_overview="Summary only.",
        strategic_insights=[],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        sources=[],
        newsletter_count=5,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    result = DigestFormatter.to_plain_text(minimal_digest)

    # Should have header and overview
    assert "MINIMAL DIGEST" in result
    assert "EXECUTIVE OVERVIEW" in result
    assert "Summary only." in result

    # Empty sections should not appear
    assert "STRATEGIC INSIGHTS" not in result
    assert "TECHNICAL DEVELOPMENTS" not in result
    assert "EMERGING TRENDS" not in result
    assert "ACTIONABLE RECOMMENDATIONS" not in result


def test_sources_without_url():
    """Test source formatting when URL is missing."""
    digest = DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
        title="Test Digest",
        executive_overview="Test",
        sources=[
            {
                "title": "Article Without URL",
                "publication": "Newsletter",
                "date": "2025-01-01",
                # No URL
            },
        ],
        newsletter_count=1,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    # Markdown - should show plain text without link
    md_result = DigestFormatter.to_markdown(digest)
    assert "- Newsletter: Article Without URL (2025-01-01)" in md_result
    assert "[Newsletter:" not in md_result  # Should not be a link

    # Plain text - should show plain text
    txt_result = DigestFormatter.to_plain_text(digest)
    assert "• Newsletter: Article Without URL (2025-01-01)" in txt_result


def test_section_without_continuity():
    """Test section formatting when continuity is None."""
    digest = DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
        title="Test Digest",
        executive_overview="Test",
        strategic_insights=[
            DigestSection(
                title="New Insight",
                summary="Summary",
                details=["Detail 1"],
                themes=["Theme"],
                continuity=None,  # No continuity
            ),
        ],
        newsletter_count=1,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    # Markdown
    md_result = DigestFormatter.to_markdown(digest)
    assert "### New Insight" in md_result
    assert "Summary" in md_result
    # Should not have continuity markers
    assert ">" not in md_result.split("### New Insight")[1].split("###")[0]

    # Plain text
    txt_result = DigestFormatter.to_plain_text(digest)
    assert "1. New Insight" in txt_result
    # Should not have continuity arrow
    section = txt_result.split("1. New Insight")[1].split("\n\n")[0]
    assert "↳" not in section


def test_to_html(sample_digest_data):
    """Test HTML formatting for email."""
    result = DigestFormatter.to_html(sample_digest_data)

    # Check HTML structure
    assert "<!DOCTYPE html>" in result
    assert "<html>" in result
    assert "</html>" in result
    assert "<head>" in result
    assert "<style>" in result

    # Check title and metadata
    assert "<h1>AI/Tech Digest - January 1, 2025</h1>" in result
    assert "January 01, 2025 - January 01, 2025" in result
    assert "15" in result  # newsletter count

    # Check sections
    assert "<h2>Executive Overview</h2>" in result
    assert "Major AI developments this week" in result

    assert "<h2>Strategic Insights</h2>" in result
    assert "For CTOs and Technical Leaders" in result
    assert "<h3>Enterprise AI Infrastructure Evolution</h3>" in result
    assert "Investment in GPU infrastructure" in result
    assert 'class="continuity"' in result
    assert "This builds on last month's discussion" in result

    assert "<h2>Technical Developments</h2>" in result
    assert "For Developers and Practitioners" in result
    assert "<h3>New RAG Optimization Techniques</h3>" in result
    assert "Hybrid search combining" in result

    assert "<h2>Emerging Trends</h2>" in result
    assert "New and Noteworthy" in result
    assert "<h3><span" in result  # Emoji span
    assert "AI Agent Swarms</h3>" in result
    assert "📈 First mentioned 3 weeks ago" in result

    # Check recommendations
    assert "<h2>Actionable Recommendations</h2>" in result
    assert "For Leadership" in result
    assert "Evaluate GPU infrastructure needs" in result
    assert "For Teams" in result
    assert "For Individuals" in result

    # Check sources with links
    assert "<h2>Sources</h2>" in result
    assert '<a href="https://techcrunch.com/article1">' in result
    assert "TechCrunch: The Future of Enterprise AI</a>" in result
    assert "(2025-01-01)" in result

    # Check footer
    assert "Generated on January 01, 2025 using claude" in result


def test_html_empty_sections():
    """Test HTML formatting with empty optional sections."""
    minimal_digest = DigestData(
        digest_type=DigestType.WEEKLY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 7),
        title="Minimal Digest",
        executive_overview="Summary only.",
        strategic_insights=[],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        sources=[],
        newsletter_count=5,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    result = DigestFormatter.to_html(minimal_digest)

    # Should have header and overview
    assert "<h1>Minimal Digest</h1>" in result
    assert "<h2>Executive Overview</h2>" in result
    assert "Summary only." in result

    # Empty sections should not appear
    assert "<h2>Strategic Insights</h2>" not in result
    assert "<h2>Technical Developments</h2>" not in result
    assert "<h2>Emerging Trends</h2>" not in result
    assert "<h2>Actionable Recommendations</h2>" not in result
    assert "<h2>Sources</h2>" not in result


def test_html_source_without_url():
    """Test HTML source formatting when URL is missing."""
    digest = DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
        title="Test Digest",
        executive_overview="Test",
        sources=[
            {
                "title": "Article Without URL",
                "publication": "Newsletter",
                "date": "2025-01-01",
                # No URL
            },
        ],
        newsletter_count=1,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    result = DigestFormatter.to_html(digest)

    # Should show plain text without link
    assert "Newsletter: Article Without URL" in result
    assert '<a href="' not in result.split("Newsletter: Article Without URL")[0].split("<li>")[-1]


def test_html_multiline_executive_overview():
    """Test HTML formatting with multi-paragraph executive overview."""
    digest = DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
        title="Test Digest",
        executive_overview="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
        newsletter_count=1,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
    )

    result = DigestFormatter.to_html(digest)

    # Each paragraph should be wrapped in <p> tags
    assert "<p>First paragraph.</p>" in result
    assert "<p>Second paragraph.</p>" in result
    assert "<p>Third paragraph.</p>" in result
