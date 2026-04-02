"""Base classes for specialist agents.

Specialists are tool-equipped wrappers around existing services, providing
a uniform interface for the conductor to delegate tasks. Each specialist
has its own mini reasoning loop via LLMRouter.generate_with_tools().
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


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
