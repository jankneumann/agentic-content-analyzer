"""Base classes for specialist agents.

Specialists are tool-equipped wrappers around existing services, providing
a uniform interface for the conductor to delegate tasks. Each specialist
has its own mini reasoning loop via LLMRouter.generate_with_tools().
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SpecialistTask(BaseModel):
    """A task delegated to a specialist by the conductor."""

    task_id: str
    task_type: str
    prompt: str
    params: dict[str, Any] = Field(default_factory=dict)
    max_iterations: int = 10
    context: dict[str, Any] = Field(default_factory=dict)


class SpecialistResult(BaseModel):
    """Result from a specialist execution."""

    task_id: str
    success: bool
    findings: list[dict[str, Any]] = Field(default_factory=list)
    content: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BaseSpecialist(ABC):
    """Base class for all specialist agents.

    Each specialist wraps one or more existing processors/services and
    exposes them through a uniform interface. Specialists have their own
    mini reasoning loops (via generate_with_tools()) and can execute
    multi-step sub-tasks autonomously.
    """

    @abstractmethod
    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute a specialist task."""

    @abstractmethod
    def get_tools(self) -> list:
        """Return tools this specialist can use in its reasoning loop.

        Returns a list of ToolDefinition instances from the LLM router.
        """

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Describe what this specialist can do (for conductor's planning)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The specialist's unique name."""

    async def _execute_with_tools(
        self,
        task: SpecialistTask,
        llm_router: Any,
        findings: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[str]],
        default_model: str = "claude-sonnet-4-5",
    ) -> SpecialistResult:
        """Template method: shared execute pattern for tool-using specialists.

        Subclasses call this from their ``execute()`` method, passing their
        specific *findings* list, *tool_executor* callback, and optional
        *default_model*.  The method handles logging, persona-based tool
        filtering, the ``generate_with_tools`` call, confidence computation,
        and error handling.
        """
        logger.info(
            "%s specialist executing task %s (type=%s)",
            self.name,
            task.task_id,
            task.task_type,
        )

        try:
            # Respect persona tool restrictions from context
            tools = self.get_tools()
            allowed = task.context.get("allowed_tools")
            if allowed is not None:
                tools = [t for t in tools if t.name in allowed]

            response = await llm_router.generate_with_tools(
                model=task.context.get("model", default_model),
                system_prompt=self._build_system_prompt(task),
                user_prompt=task.prompt,
                tools=tools,
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
                "%s specialist failed on task %s: %s",
                self.name,
                task.task_id,
                e,
            )
            return SpecialistResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    def _build_system_prompt(self, task: SpecialistTask) -> str:
        """Build system prompt for the reasoning loop.

        Override in subclasses to provide specialist-specific prompts.
        """
        return ""

    def _compute_confidence(self, findings: list[dict[str, Any]]) -> float:
        """Compute a confidence score based on findings quality.

        Default implementation scores based on the ratio of successful
        (non-unavailable) findings.
        """
        if not findings:
            return 0.0
        successful = sum(1 for f in findings if f.get("status") != "unavailable")
        return min(1.0, successful / max(len(findings), 1) * 0.8 + 0.1)
