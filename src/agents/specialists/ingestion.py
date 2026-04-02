"""Ingestion specialist agent.

Wraps the ingestion orchestrator to ingest content from configured
sources, direct URLs, and file uploads.
"""

from typing import Any

from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask
from src.services.llm_router import ToolDefinition
from src.utils.logging import get_logger

logger = get_logger(__name__)


class IngestionSpecialist(BaseSpecialist):
    """Specialist for content ingestion from various sources.

    Manages ingestion from configured sources (Gmail, RSS, YouTube, etc.),
    direct URLs, and source scanning for new content.
    """

    def __init__(
        self,
        llm_router: Any,
        ingestion_service: Any = None,
    ) -> None:
        self._llm_router = llm_router
        self._ingestion_service = ingestion_service

    @property
    def name(self) -> str:
        return "ingestion"

    def get_capabilities(self) -> list[str]:
        return [
            "source_ingestion",
            "url_ingestion",
            "source_scanning",
        ]

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="ingest_source",
                description="Ingest content from a configured source (e.g., gmail, rss, youtube).",
                parameters={
                    "type": "object",
                    "properties": {
                        "source_type": {
                            "type": "string",
                            "description": "Type of source to ingest from",
                            "enum": [
                                "gmail",
                                "rss",
                                "substack",
                                "youtube",
                                "podcast",
                                "xsearch",
                                "perplexity-search",
                                "scholar",
                            ],
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum items to ingest",
                            "default": 50,
                        },
                    },
                    "required": ["source_type"],
                },
            ),
            ToolDefinition(
                name="scan_sources",
                description="Scan all configured sources for new content without ingesting.",
                parameters={
                    "type": "object",
                    "properties": {
                        "source_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Source types to scan (empty = all)",
                        },
                    },
                },
            ),
            ToolDefinition(
                name="ingest_url",
                description="Ingest content from a specific URL.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to ingest"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Tags to apply to ingested content",
                        },
                    },
                    "required": ["url"],
                },
            ),
        ]

    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute an ingestion task using iterative tool use."""
        logger.info(
            "Ingestion specialist executing task",
            extra={"task_id": task.task_id, "task_type": task.task_type},
        )

        try:
            findings: list[dict[str, Any]] = []

            async def tool_executor(tool_name: str, args: dict[str, Any]) -> str:
                return await self._execute_tool(tool_name, args, findings)

            response = await self._llm_router.generate_with_tools(
                model=task.context.get("model", "claude-haiku-4-5"),
                system_prompt=self._build_system_prompt(task),
                user_prompt=task.prompt,
                tools=self.get_tools(),
                tool_executor=tool_executor,
                max_iterations=task.max_iterations,
            )

            return SpecialistResult(
                task_id=task.task_id,
                success=True,
                findings=findings,
                content=response.text,
                confidence=self._compute_confidence(findings),
                metadata={
                    "tokens_used": response.input_tokens + response.output_tokens,
                },
            )
        except Exception as e:
            logger.error(
                "Ingestion specialist failed",
                extra={"task_id": task.task_id, "error": str(e)},
            )
            return SpecialistResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
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
        if tool_name == "ingest_source" and self._ingestion_service is not None:
            ingested = await self._ingestion_service.ingest(
                source_type=args["source_type"],
                max_items=args.get("max_items", 50),
            )
            result = str(ingested)
            findings.append({
                "tool": tool_name,
                "source_type": args["source_type"],
                "items_ingested": ingested if isinstance(ingested, int) else 0,
            })
        elif tool_name == "ingest_url" and self._ingestion_service is not None:
            ingested = await self._ingestion_service.ingest_url(
                url=args["url"],
                tags=args.get("tags"),
            )
            result = str(ingested)
            findings.append({"tool": tool_name, "url": args["url"]})
        elif tool_name == "scan_sources" and self._ingestion_service is not None:
            scan_result = await self._ingestion_service.scan(
                source_types=args.get("source_types"),
            )
            result = str(scan_result)
            findings.append({"tool": tool_name, "status": "scanned"})
        else:
            result = f"Tool '{tool_name}' not available or service not connected"
            findings.append({"tool": tool_name, "status": "unavailable"})

        return result

    def _build_system_prompt(self, task: SpecialistTask) -> str:
        """Build a system prompt for the ingestion reasoning loop."""
        return (
            "You are an ingestion specialist agent. Your goal is to ingest "
            "content from the requested sources. Determine which sources to "
            "ingest from based on the task, scan for new content if needed, "
            "and report what was ingested."
        )

    def _compute_confidence(self, findings: list[dict[str, Any]]) -> float:
        """Compute a confidence score based on findings quality."""
        if not findings:
            return 0.0
        successful = sum(1 for f in findings if f.get("status") != "unavailable")
        return min(1.0, successful / max(len(findings), 1) * 0.8 + 0.1)
