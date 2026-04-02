"""Analysis specialist agent.

Wraps ThemeAnalyzer and HistoricalContextAnalyzer to perform theme
detection, trend analysis, and anomaly detection.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask
from src.services.llm_router import ToolDefinition
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AnalysisSpecialist(BaseSpecialist):
    """Specialist for theme detection, trend analysis, and historical context.

    Runs theme analysis and historical context queries, identifies trends
    and anomalies across time periods.
    """

    def __init__(
        self,
        llm_router: Any,
        theme_analyzer: Any = None,
        historical_analyzer: Any = None,
    ) -> None:
        self._llm_router = llm_router
        self._theme_analyzer = theme_analyzer
        self._historical_analyzer = historical_analyzer

    @property
    def name(self) -> str:
        return "analysis"

    def get_capabilities(self) -> list[str]:
        return [
            "theme_detection",
            "trend_analysis",
            "historical_context",
            "anomaly_detection",
        ]

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="analyze_themes",
                description="Detect themes and patterns across a set of content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "content_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of content to analyze",
                        },
                        "focus_area": {
                            "type": "string",
                            "description": "Optional focus area for theme detection",
                        },
                    },
                    "required": ["content_ids"],
                },
            ),
            ToolDefinition(
                name="get_historical_context",
                description="Get historical context for a topic or theme.",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic to get context for"},
                        "lookback_days": {
                            "type": "integer",
                            "description": "Number of days to look back",
                            "default": 30,
                        },
                    },
                    "required": ["topic"],
                },
            ),
            ToolDefinition(
                name="detect_anomalies",
                description="Detect anomalies or unexpected patterns in content trends.",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic to check for anomalies"},
                        "threshold": {
                            "type": "number",
                            "description": "Anomaly detection sensitivity (0-1)",
                            "default": 0.7,
                        },
                    },
                    "required": ["topic"],
                },
            ),
            ToolDefinition(
                name="compare_periods",
                description="Compare themes/trends between two time periods.",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic to compare"},
                        "period_a": {
                            "type": "string",
                            "description": "First period (e.g., '7d', '30d')",
                        },
                        "period_b": {"type": "string", "description": "Second period"},
                    },
                    "required": ["topic", "period_a", "period_b"],
                },
            ),
        ]

    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute an analysis task using iterative tool use."""
        findings: list[dict[str, Any]] = []

        async def tool_executor(tool_name: str, args: dict[str, Any]) -> str:
            return await self._execute_tool(tool_name, args, findings)

        return await self._execute_with_tools(
            task,
            self._llm_router,
            findings,
            tool_executor,
            default_model="claude-sonnet-4-5",
        )

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> str:
        """Execute a single tool call and record findings."""
        logger.debug("Executing tool", extra={"tool": tool_name, "args": args})

        result: str
        if tool_name == "analyze_themes" and self._theme_analyzer is not None:
            themes = await self._theme_analyzer.analyze(
                content_ids=args["content_ids"],
                focus_area=args.get("focus_area"),
            )
            result = str(themes)
            findings.append({"tool": tool_name, "content_count": len(args["content_ids"])})
        elif tool_name == "get_historical_context" and self._historical_analyzer is not None:
            context = await self._historical_analyzer.get_context(
                topic=args["topic"],
                lookback_days=args.get("lookback_days", 30),
            )
            result = str(context)
            findings.append({"tool": tool_name, "topic": args["topic"]})
        elif tool_name == "detect_anomalies":
            from src.models import Content
            from src.storage.database import get_db

            topic = args["topic"]
            threshold = args.get("threshold", 0.7)

            with get_db() as db:
                # Get recent content to check for anomalies
                recent_content = (
                    db.query(Content.title, Content.source_type, Content.created_at)
                    .filter(Content.title.ilike(f"%{topic}%"))
                    .order_by(Content.created_at.desc())
                    .limit(20)
                    .all()
                )

            if recent_content:
                content_summary = "\n".join(
                    f"- {c.title} ({c.source_type}, {c.created_at.strftime('%Y-%m-%d')})"
                    for c in recent_content
                )
                result = (
                    f"Anomaly scan for '{topic}' across {len(recent_content)} recent items:\n"
                    f"{content_summary}\n\n"
                    f"(Threshold: {threshold} — LLM analysis would identify deviations "
                    f"from baseline)"
                )
            else:
                result = f"No content found matching topic '{topic}' for anomaly detection"

            findings.append(
                {
                    "tool": tool_name,
                    "topic": topic,
                    "threshold": threshold,
                    "content_count": len(recent_content),
                }
            )
        elif tool_name == "compare_periods":
            from datetime import timedelta

            from src.models import Content
            from src.storage.database import get_db

            topic = args["topic"]
            period_a = args["period_a"]  # e.g., "7d"
            period_b = args["period_b"]  # e.g., "30d"

            def _parse_period(p: str) -> timedelta:
                if p.endswith("d"):
                    return timedelta(days=int(p[:-1]))
                if p.endswith("w"):
                    return timedelta(weeks=int(p[:-1]))
                return timedelta(days=int(p))

            now = datetime.now(UTC)
            delta_a = _parse_period(period_a)
            delta_b = _parse_period(period_b)

            with get_db() as db:
                count_a = (
                    db.query(func.count(Content.id))
                    .filter(
                        Content.title.ilike(f"%{topic}%"),
                        Content.created_at >= now - delta_a,
                    )
                    .scalar()
                )
                count_b = (
                    db.query(func.count(Content.id))
                    .filter(
                        Content.title.ilike(f"%{topic}%"),
                        Content.created_at >= now - delta_b,
                        Content.created_at < now - delta_a,
                    )
                    .scalar()
                )

            result = (
                f"Period comparison for '{topic}':\n"
                f"  Recent ({period_a}): {count_a} items\n"
                f"  Earlier ({period_b} before {period_a}): {count_b} items\n"
                f"  Change: {'↑' if count_a > count_b else '↓' if count_a < count_b else '→'} "
                f"({count_a - count_b:+d})"
            )
            findings.append(
                {
                    "tool": tool_name,
                    "topic": topic,
                    "period_a": {"label": period_a, "count": count_a},
                    "period_b": {"label": period_b, "count": count_b},
                }
            )
        else:
            result = f"Tool '{tool_name}' not available or service not connected"
            findings.append({"tool": tool_name, "status": "unavailable"})

        return result

    def _build_system_prompt(self, task: SpecialistTask) -> str:
        """Build a system prompt for the analysis reasoning loop."""
        persona_context = task.context.get("persona", "")
        return (
            "You are an analysis specialist agent. Your goal is to identify "
            "themes, trends, and anomalies in the content you are given. "
            "Use theme analysis to find patterns, historical context to "
            "understand evolution, and anomaly detection to flag surprises. "
            "Provide a structured analysis with clear findings.\n\n"
            f"{f'Persona context: {persona_context}' if persona_context else ''}"
        )
