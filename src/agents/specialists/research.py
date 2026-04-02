"""Research specialist agent.

Wraps HybridSearchService, GraphitiClient, and web search to perform
deep research tasks with iterative tool use.
"""

from typing import Any

from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask
from src.services.llm_router import ToolDefinition
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResearchSpecialist(BaseSpecialist):
    """Specialist for deep research, web search, and knowledge graph queries.

    Uses tools iteratively to research a topic, building up observations
    that can be stored as memories for future recall.
    """

    def __init__(
        self,
        llm_router: Any,
        search_service: Any = None,
        graphiti_client: Any = None,
    ) -> None:
        self._llm_router = llm_router
        self._search_service = search_service
        self._graphiti_client = graphiti_client

    @property
    def name(self) -> str:
        return "research"

    def get_capabilities(self) -> list[str]:
        return [
            "deep_research",
            "web_search",
            "knowledge_graph_query",
            "content_search",
        ]

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="search_content",
                description="Search ingested content using hybrid BM25+vector search.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="query_knowledge_graph",
                description="Query the knowledge graph for entity relationships and temporal context.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language query"},
                        "entity_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by entity types",
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="search_web",
                description="Search the web for additional context on a topic.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Web search query"},
                        "max_results": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="fetch_url",
                description="Fetch and extract content from a URL.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
            ),
        ]

    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute a research task using iterative tool use.

        The specialist uses its LLM router to reason about which tools
        to call, building up findings across multiple iterations.
        """
        logger.info(
            "Research specialist executing task",
            extra={"task_id": task.task_id, "task_type": task.task_type},
        )

        try:
            findings: list[dict[str, Any]] = []

            async def tool_executor(tool_name: str, args: dict[str, Any]) -> str:
                return await self._execute_tool(tool_name, args, findings)

            response = await self._llm_router.generate_with_tools(
                model=task.context.get("model", "claude-sonnet-4-5"),
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
                    "iterations_used": len(findings),
                    "tokens_used": response.input_tokens + response.output_tokens,
                },
            )
        except Exception as e:
            logger.error(
                "Research specialist failed",
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
        if tool_name == "search_content" and self._search_service is not None:
            results = await self._search_service.search(
                query=args["query"],
                limit=args.get("limit", 10),
            )
            result = str(results)
            findings.append({"tool": tool_name, "query": args["query"], "result_count": len(results) if isinstance(results, list) else 0})
        elif tool_name == "query_knowledge_graph" and self._graphiti_client is not None:
            results = await self._graphiti_client.search(query=args["query"])
            result = str(results)
            findings.append({"tool": tool_name, "query": args["query"]})
        elif tool_name == "search_web":
            result = f"Web search for '{args['query']}' — service not yet connected"
            findings.append({"tool": tool_name, "query": args["query"], "status": "stub"})
        elif tool_name == "fetch_url":
            result = f"Fetch URL '{args['url']}' — service not yet connected"
            findings.append({"tool": tool_name, "url": args["url"], "status": "stub"})
        else:
            result = f"Tool '{tool_name}' not available or service not connected"
            findings.append({"tool": tool_name, "status": "unavailable"})

        return result

    def _build_system_prompt(self, task: SpecialistTask) -> str:
        """Build a system prompt for the research reasoning loop."""
        persona_context = task.context.get("persona", "")
        return (
            "You are a research specialist agent. Your goal is to thoroughly "
            "research the given topic using the available tools. Build up "
            "observations iteratively — search content, query the knowledge "
            "graph, and fetch additional sources as needed. Synthesize your "
            "findings into a clear summary.\n\n"
            f"{f'Persona context: {persona_context}' if persona_context else ''}"
        )

    def _compute_confidence(self, findings: list[dict[str, Any]]) -> float:
        """Compute a confidence score based on findings quality."""
        if not findings:
            return 0.0
        successful = sum(1 for f in findings if f.get("status") != "unavailable")
        return min(1.0, successful / max(len(findings), 1) * 0.8 + 0.1)
