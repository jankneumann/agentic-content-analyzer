"""Synthesis specialist agent.

Wraps DigestCreator and insight generation to synthesize research
and analysis results into reports, digests, and briefings.
"""

from typing import Any

from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask
from src.services.llm_router import ToolDefinition
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SynthesisSpecialist(BaseSpecialist):
    """Specialist for insight generation, report creation, and digest drafting.

    Generates insights from research and analysis results, producing
    structured reports and cross-theme analyses.
    """

    def __init__(
        self,
        llm_router: Any,
        digest_creator: Any = None,
    ) -> None:
        self._llm_router = llm_router
        self._digest_creator = digest_creator

    @property
    def name(self) -> str:
        return "synthesis"

    def get_capabilities(self) -> list[str]:
        return [
            "insight_generation",
            "report_creation",
            "digest_drafting",
            "cross_theme_analysis",
        ]

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="create_report",
                description="Create a structured report from findings and analysis.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Report title"},
                        "findings": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Structured findings to include",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["brief", "detailed", "executive"],
                            "description": "Report format",
                            "default": "detailed",
                        },
                    },
                    "required": ["title", "findings"],
                },
            ),
            ToolDefinition(
                name="generate_insight",
                description="Generate a single insight from a set of observations.",
                parameters={
                    "type": "object",
                    "properties": {
                        "observations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Observations to synthesize",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context for insight generation",
                        },
                    },
                    "required": ["observations"],
                },
            ),
            ToolDefinition(
                name="draft_digest",
                description="Draft a digest from summarized content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "digest_type": {
                            "type": "string",
                            "enum": ["daily", "weekly"],
                            "description": "Type of digest",
                        },
                        "content_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Content IDs to include in digest",
                        },
                    },
                    "required": ["digest_type"],
                },
            ),
            ToolDefinition(
                name="create_briefing",
                description="Create a concise briefing on a topic from available data.",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Briefing topic"},
                        "audience": {
                            "type": "string",
                            "description": "Target audience",
                            "default": "technical leaders",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Max length in words",
                            "default": 500,
                        },
                    },
                    "required": ["topic"],
                },
            ),
        ]

    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute a synthesis task using iterative tool use."""
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
        if tool_name == "draft_digest" and self._digest_creator is not None:
            digest = await self._digest_creator.create(
                digest_type=args["digest_type"],
                content_ids=args.get("content_ids"),
            )
            result = str(digest)
            findings.append({"tool": tool_name, "digest_type": args["digest_type"]})
        elif tool_name == "create_report":
            result = (
                f"Report '{args['title']}' with {len(args['findings'])} findings "
                f"in {args.get('format', 'detailed')} format — generated via LLM"
            )
            findings.append(
                {
                    "tool": tool_name,
                    "title": args["title"],
                    "finding_count": len(args["findings"]),
                }
            )
        elif tool_name == "generate_insight":
            result = f"Insight from {len(args['observations'])} observations — generated via LLM"
            findings.append(
                {
                    "tool": tool_name,
                    "observation_count": len(args["observations"]),
                }
            )
        elif tool_name == "create_briefing":
            result = (
                f"Briefing on '{args['topic']}' for {args.get('audience', 'technical leaders')} "
                f"— generated via LLM"
            )
            findings.append({"tool": tool_name, "topic": args["topic"]})
        else:
            result = f"Tool '{tool_name}' not available or service not connected"
            findings.append({"tool": tool_name, "status": "unavailable"})

        return result

    def _build_system_prompt(self, task: SpecialistTask) -> str:
        """Build a system prompt for the synthesis reasoning loop."""
        persona_context = task.context.get("persona", "")
        return (
            "You are a synthesis specialist agent. Your goal is to combine "
            "research findings and analysis results into clear, actionable "
            "insights. Create reports, generate insights, draft digests, "
            "and produce briefings that help the reader understand key "
            "trends and their implications.\n\n"
            f"{f'Persona context: {persona_context}' if persona_context else ''}"
        )
