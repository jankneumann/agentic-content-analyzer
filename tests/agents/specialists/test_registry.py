"""Tests for the SpecialistRegistry."""

from dataclasses import dataclass
from typing import Any

import pytest

from src.agents.registry import SpecialistRegistry
from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask


# -- Lightweight tool stand-in (avoids heavy src.services import chain) --


@dataclass
class _Tool:
    """Minimal ToolDefinition-compatible object for testing."""

    name: str
    description: str
    parameters: dict[str, Any]


# -- Mock specialists for testing --


class MockResearchSpecialist(BaseSpecialist):
    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        return SpecialistResult(task_id=task.task_id, success=True)

    def get_tools(self) -> list:
        return [
            _Tool(
                name="search_content",
                description="Search content",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_capabilities(self) -> list[str]:
        return ["deep_research", "content_search"]

    @property
    def name(self) -> str:
        return "research"


class MockAnalysisSpecialist(BaseSpecialist):
    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        return SpecialistResult(task_id=task.task_id, success=True)

    def get_tools(self) -> list:
        return [
            _Tool(
                name="analyze_themes",
                description="Analyze themes",
                parameters={"type": "object", "properties": {}},
            ),
            _Tool(
                name="detect_anomalies",
                description="Detect anomalies",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_capabilities(self) -> list[str]:
        return ["theme_detection", "anomaly_detection"]

    @property
    def name(self) -> str:
        return "analysis"


class MockSynthesisSpecialist(BaseSpecialist):
    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        return SpecialistResult(task_id=task.task_id, success=True)

    def get_tools(self) -> list:
        return [
            _Tool(
                name="create_report",
                description="Create report",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_capabilities(self) -> list[str]:
        return ["report_creation", "insight_generation"]

    @property
    def name(self) -> str:
        return "synthesis"


# -- Tests --


class TestSpecialistRegistry:
    def test_register_and_get(self):
        registry = SpecialistRegistry()
        specialist = MockResearchSpecialist()
        registry.register(specialist)

        assert registry.get("research") is specialist

    def test_get_missing_returns_none(self):
        registry = SpecialistRegistry()
        assert registry.get("nonexistent") is None

    def test_register_overwrites(self):
        registry = SpecialistRegistry()
        first = MockResearchSpecialist()
        second = MockResearchSpecialist()
        registry.register(first)
        registry.register(second)

        assert registry.get("research") is second

    def test_list_specialists(self):
        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())
        registry.register(MockAnalysisSpecialist())

        names = registry.list_specialists()
        assert sorted(names) == ["analysis", "research"]

    def test_list_specialists_empty(self):
        registry = SpecialistRegistry()
        assert registry.list_specialists() == []


class TestCapabilityLookup:
    def test_get_by_capability_single_match(self):
        registry = SpecialistRegistry()
        research = MockResearchSpecialist()
        analysis = MockAnalysisSpecialist()
        registry.register(research)
        registry.register(analysis)

        matches = registry.get_by_capability("deep_research")
        assert len(matches) == 1
        assert matches[0] is research

    def test_get_by_capability_no_match(self):
        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())

        matches = registry.get_by_capability("nonexistent_capability")
        assert matches == []

    def test_get_by_capability_multiple_matches(self):
        """Two specialists with overlapping capabilities."""

        class OverlapSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_tools(self) -> list:
                return []

            def get_capabilities(self) -> list[str]:
                return ["deep_research", "custom"]

            @property
            def name(self) -> str:
                return "overlap"

        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())
        registry.register(OverlapSpecialist())

        matches = registry.get_by_capability("deep_research")
        assert len(matches) == 2


class TestToolAggregation:
    def test_get_all_tools_empty(self):
        registry = SpecialistRegistry()
        assert registry.get_all_tools() == []

    def test_get_all_tools_prefixed(self):
        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())

        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "research.search_content"
        assert tools[0].description.startswith("[research]")

    def test_get_all_tools_multiple_specialists(self):
        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())
        registry.register(MockAnalysisSpecialist())
        registry.register(MockSynthesisSpecialist())

        tools = registry.get_all_tools()
        assert len(tools) == 4  # 1 + 2 + 1

        tool_names = [t.name for t in tools]
        assert "research.search_content" in tool_names
        assert "analysis.analyze_themes" in tool_names
        assert "analysis.detect_anomalies" in tool_names
        assert "synthesis.create_report" in tool_names

    def test_tools_no_name_collision(self):
        """Even if two specialists have tools with the same base name,
        prefixing prevents collisions."""

        class AltSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_tools(self) -> list:
                return [
                    _Tool(
                        name="search_content",
                        description="Alt search",
                        parameters={"type": "object", "properties": {}},
                    ),
                ]

            def get_capabilities(self) -> list[str]:
                return ["alt_search"]

            @property
            def name(self) -> str:
                return "alt"

        registry = SpecialistRegistry()
        registry.register(MockResearchSpecialist())
        registry.register(AltSpecialist())

        tools = registry.get_all_tools()
        tool_names = [t.name for t in tools]
        assert "research.search_content" in tool_names
        assert "alt.search_content" in tool_names
        assert len(set(tool_names)) == len(tool_names)  # no duplicates
