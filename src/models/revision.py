"""Revision context and result models for interactive digest refinement."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.models.digest import Digest
from src.models.summary import NewsletterSummary
from src.models.theme import ThemeAnalysisResult


@dataclass
class RevisionContext:
    """Complete context for AI-powered digest revision.

    Includes condensed context (digest + summaries + theme analysis) with
    newsletter IDs available for on-demand fetching via tools.
    """

    digest: Digest
    summaries: list[NewsletterSummary]  # Already condensed summaries
    theme_analysis: Any | None = None  # Theme analysis data (if available)
    newsletter_ids: list[int] | None = None  # IDs for on-demand fetching via tools

    def __post_init__(self) -> None:
        """Initialize newsletter IDs if not provided."""
        if self.newsletter_ids is None:
            self.newsletter_ids = [summary.newsletter_id for summary in self.summaries]

    def to_llm_context(self) -> str:
        """Format context for LLM prompt (token-optimized).

        Returns condensed context suitable for LLM consumption:
        - Full digest content
        - Newsletter summaries (condensed)
        - Theme analysis (if available)
        - Tool availability note

        Returns:
            Formatted context string
        """
        parts = []

        # Current digest (full content)
        parts.append("## CURRENT DIGEST\n")
        parts.append(f"**Type**: {self.digest.digest_type}")
        parts.append(
            f"**Period**: {self.digest.period_start.strftime('%Y-%m-%d')} to "
            f"{self.digest.period_end.strftime('%Y-%m-%d')}"
        )
        parts.append(f"**Newsletter Count**: {self.digest.newsletter_count}\n")

        parts.append("### Executive Overview")
        parts.append(self.digest.executive_overview)

        parts.append("\n### Strategic Insights")
        if isinstance(self.digest.strategic_insights, list):
            for idx, insight in enumerate(self.digest.strategic_insights, 1):
                if isinstance(insight, dict):
                    parts.append(f"\n**{idx}. {insight.get('title', 'Untitled')}**")
                    parts.append(insight.get("summary", ""))
                else:
                    parts.append(f"{idx}. {insight}")
        else:
            parts.append(str(self.digest.strategic_insights))

        parts.append("\n### Technical Developments")
        if isinstance(self.digest.technical_developments, list):
            for idx, dev in enumerate(self.digest.technical_developments, 1):
                if isinstance(dev, dict):
                    parts.append(f"\n**{idx}. {dev.get('title', 'Untitled')}**")
                    parts.append(dev.get("summary", ""))
                else:
                    parts.append(f"{idx}. {dev}")
        else:
            parts.append(str(self.digest.technical_developments))

        parts.append("\n### Emerging Trends")
        if isinstance(self.digest.emerging_trends, list):
            for idx, trend in enumerate(self.digest.emerging_trends, 1):
                if isinstance(trend, dict):
                    parts.append(f"\n**{idx}. {trend.get('title', 'Untitled')}**")
                    parts.append(trend.get("summary", ""))
                else:
                    parts.append(f"{idx}. {trend}")
        else:
            parts.append(str(self.digest.emerging_trends))

        parts.append("\n### Actionable Recommendations")
        if isinstance(self.digest.actionable_recommendations, dict):
            for role, actions in self.digest.actionable_recommendations.items():
                parts.append(f"\n**{role}:**")
                if isinstance(actions, list):
                    for action in actions:
                        parts.append(f"- {action}")
                else:
                    parts.append(str(actions))
        else:
            parts.append(str(self.digest.actionable_recommendations))

        # Newsletter summaries (condensed)
        parts.append("\n\n## SOURCE NEWSLETTERS (CONDENSED SUMMARIES)\n")
        parts.append(
            f"Total: {len(self.summaries)} newsletters. "
            "Full content available on-demand via tools.\n"
        )

        for idx, summary in enumerate(self.summaries, 1):
            # Get newsletter metadata
            newsletter = summary.newsletter
            parts.append(f"\n### [{idx}] {newsletter.title}")
            parts.append(f"**Publication**: {newsletter.publication or 'Unknown'}")
            parts.append(f"**Date**: {newsletter.published_date.strftime('%Y-%m-%d')}")
            parts.append(f"**Newsletter ID**: {summary.newsletter_id}")

            # Include condensed summary content
            parts.append(f"\n**Executive Summary**: {summary.executive_summary}")

            if summary.key_themes:
                parts.append(f"**Key Themes**: {', '.join(summary.key_themes[:5])}")  # Top 5

            if summary.strategic_insights:
                parts.append(
                    f"**Strategic Insights**: "
                    f"{', '.join(str(s) for s in summary.strategic_insights[:3])}"  # Top 3
                )

        # Theme analysis (if available)
        if self.theme_analysis:
            parts.append("\n\n## CROSS-NEWSLETTER THEMES\n")
            parts.append(_format_theme_analysis(self.theme_analysis))

        # Available tools note
        parts.append("\n\n## AVAILABLE TOOLS\n")
        parts.append("You have access to the following tools to retrieve additional details:\n")
        parts.append(
            "- **fetch_newsletter_content(newsletter_id)**: "
            "Retrieve full content of a specific newsletter when you need detailed information"
        )
        parts.append(
            "- **search_newsletters(query)**: "
            "Search across all newsletters for specific topics or keywords"
        )

        return "\n".join(parts)


def _format_theme_analysis(theme_analysis: ThemeAnalysisResult) -> str:
    """Format theme analysis into a string for LLM context."""
    if not theme_analysis or not theme_analysis.themes:
        return "No theme analysis available."

    parts = []
    parts.append(f"Theme Analysis ({theme_analysis.start_date} to {theme_analysis.end_date}):")
    parts.append(f"- {theme_analysis.newsletter_count} newsletters analyzed")
    parts.append(f"- {theme_analysis.total_themes} themes identified")

    for i, theme in enumerate(theme_analysis.themes, 1):
        parts.append(f"\n### {i}. {theme.name} ({theme.category.value})")
        parts.append(f"   - Trend: {theme.trend.value}")
        parts.append(f"   - Relevance: {theme.relevance_score:.2f}")
        parts.append(f"   - Key Points:")
        for point in theme.key_points:
            parts.append(f"     - {point}")

    return "\n".join(parts)


@dataclass
class RevisionResult:
    """Result of a single revision request.

    Contains the revised content, which section was modified,
    AI's explanation, and confidence score.
    """

    revised_content: Any  # Could be str, dict, list depending on section
    section_modified: str  # Which digest section was changed
    explanation: str  # AI explanation of the change
    confidence_score: float = 1.0  # How confident the AI is (0.0-1.0)
    tools_used: list[str] | None = (
        None  # Tools called during revision (e.g., ["fetch_newsletter_content"])
    )

    def __post_init__(self) -> None:
        """Initialize tools_used if not provided."""
        if self.tools_used is None:
            self.tools_used = []


@dataclass
class RevisionTurn:
    """Single turn in revision conversation.

    Tracks user input, AI response, changes made, and acceptance.
    Used for building revision history audit trail.
    """

    turn: int
    user_input: str
    ai_response: str
    section_modified: str
    change_accepted: bool
    timestamp: datetime
    tools_called: list[str] | None = None  # Tools used in this turn

    def __post_init__(self) -> None:
        """Initialize tools_called if not provided."""
        if self.tools_called is None:
            self.tools_called = []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for database storage
        """
        return {
            "turn": self.turn,
            "user_input": self.user_input,
            "ai_response": self.ai_response,
            "section_modified": self.section_modified,
            "change_accepted": self.change_accepted,
            "timestamp": self.timestamp.isoformat(),
            "tools_called": self.tools_called,
        }
