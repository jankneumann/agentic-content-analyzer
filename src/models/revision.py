"""Revision context and result models for interactive digest refinement."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.models.digest import Digest
from src.models.summary import Summary


@dataclass
class RevisionContext:
    """Complete context for AI-powered digest revision.

    Includes condensed context (digest + summaries + theme analysis) with
    content IDs available for on-demand fetching via tools.
    """

    digest: Digest
    summaries: list[Summary]  # Already condensed summaries
    theme_analysis: Any | None = None  # Theme analysis data (if available)
    content_ids: list[int] | None = None  # IDs for on-demand fetching via tools

    def __post_init__(self) -> None:
        """Initialize content IDs if not provided."""
        if self.content_ids is None:
            self.content_ids = [
                summary.content_id for summary in self.summaries if summary.content_id
            ]

    def _format_theme_analysis(self) -> str:
        """Format theme analysis into readable text.

        Handles both ThemeAnalysisResult objects and dictionary representations.
        Includes theme names, descriptions, trends, key points, and historical context.
        """
        if not self.theme_analysis:
            return ""

        analysis = self.theme_analysis

        # Extract themes
        themes = getattr(analysis, "themes", [])
        if isinstance(analysis, dict):
            themes = analysis.get("themes", [])

        if not themes:
            return "No themes detected."

        parts = []

        # Sort themes by relevance score
        def get_score(t: Any) -> float:
            if isinstance(t, dict):
                return float(t.get("relevance_score", 0.0))
            return getattr(t, "relevance_score", 0.0)

        # Sort by relevance score descending
        sorted_themes = sorted(themes, key=get_score, reverse=True)

        parts.append(f"Analysis of {len(themes)} themes across newsletters:\n")

        for idx, theme in enumerate(sorted_themes, 1):
            # Helper to access attributes or dict keys
            def get_val(obj: Any, key: str, default: Any = None) -> Any:
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            name = get_val(theme, "name", "Untitled")
            trend = get_val(theme, "trend", "unknown")
            description = get_val(theme, "description", "")
            key_points = get_val(theme, "key_points", [])
            continuity = get_val(theme, "continuity_text")
            historical_context = get_val(theme, "historical_context")

            # Format trend (handle Enum or string)
            trend_str = str(trend).upper().replace("THEMETREND.", "")

            parts.append(f"### {idx}. {name} [{trend_str}]")
            parts.append(f"**Description**: {description}")

            if key_points:
                parts.append("**Key Points**:")
                for point in key_points[:5]:  # Limit to top 5 points
                    parts.append(f"- {point}")

            if continuity:
                parts.append(f"**Continuity**: {continuity}")
            elif historical_context:
                evolution = get_val(historical_context, "evolution_summary")
                if evolution:
                    parts.append(f"**Evolution**: {evolution}")

            parts.append("")  # Spacing

        # Cross-theme insights
        insights = getattr(analysis, "cross_theme_insights", [])
        if isinstance(analysis, dict):
            insights = analysis.get("cross_theme_insights", [])

        if insights:
            parts.append("### Cross-Theme Insights")
            for insight in insights:
                parts.append(f"- {insight}")

        return "\n".join(parts)

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

        # Content summaries (condensed)
        parts.append("\n\n## SOURCE CONTENT (CONDENSED SUMMARIES)\n")
        parts.append(
            f"Total: {len(self.summaries)} content items. "
            "Full content available on-demand via tools.\n"
        )

        for idx, summary in enumerate(self.summaries, 1):
            # Get content metadata
            content = summary.content
            if content:
                parts.append(f"\n### [{idx}] {content.title}")
                parts.append(f"**Publication**: {content.publication or 'Unknown'}")
                parts.append(
                    f"**Date**: {content.published_date.strftime('%Y-%m-%d') if content.published_date else 'Unknown'}"
                )
                parts.append(f"**Content ID**: {summary.content_id}")

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
            parts.append(self._format_theme_analysis())

        # Available tools note
        parts.append("\n\n## AVAILABLE TOOLS\n")
        parts.append("You have access to the following tools to retrieve additional details:\n")
        parts.append(
            "- **fetch_content(content_id)**: "
            "Retrieve full content of a specific item when you need detailed information"
        )
        parts.append(
            "- **search_content(query)**: Search across all content for specific topics or keywords"
        )

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
