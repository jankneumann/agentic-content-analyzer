"""Specialist agent registry.

Provides lookup by name and capability, and aggregates tools from
all registered specialists for the conductor's planning phase.
"""

from src.agents.specialists.base import BaseSpecialist
from src.services.llm_router import ToolDefinition
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SpecialistRegistry:
    """Registry for specialist agents. Supports lookup by capability."""

    def __init__(self) -> None:
        self._specialists: dict[str, BaseSpecialist] = {}

    def register(self, specialist: BaseSpecialist) -> None:
        """Register a specialist. Overwrites if name already registered."""
        name = specialist.name
        if name in self._specialists:
            logger.warning(
                "Overwriting existing specialist registration: %s",
                name,
            )
        self._specialists[name] = specialist
        logger.info(
            "Registered specialist",
            extra={"name": name, "capabilities": specialist.get_capabilities()},
        )

    def get(self, name: str) -> BaseSpecialist | None:
        """Look up a specialist by name."""
        return self._specialists.get(name)

    def get_by_capability(self, capability: str) -> list[BaseSpecialist]:
        """Find all specialists that support a given capability."""
        return [
            s for s in self._specialists.values()
            if capability in s.get_capabilities()
        ]

    def get_all_tools(self) -> list[ToolDefinition]:
        """Aggregate tools from all registered specialists.

        Tool names are prefixed with the specialist name to avoid
        collisions (e.g., "research.search_content").
        """
        tools: list[ToolDefinition] = []
        for specialist in self._specialists.values():
            for tool in specialist.get_tools():
                tools.append(
                    ToolDefinition(
                        name=f"{specialist.name}.{tool.name}",
                        description=f"[{specialist.name}] {tool.description}",
                        parameters=tool.parameters,
                    )
                )
        return tools

    def list_specialists(self) -> list[str]:
        """Return names of all registered specialists."""
        return list(self._specialists.keys())
