"""Tests for specialist base classes and models."""

import pytest

from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask


class TestSpecialistTask:
    """Tests for the SpecialistTask model."""

    def test_minimal_creation(self):
        task = SpecialistTask(
            task_id="t-1",
            task_type="research",
            prompt="Find info about LLMs",
        )
        assert task.task_id == "t-1"
        assert task.task_type == "research"
        assert task.prompt == "Find info about LLMs"
        assert task.params == {}
        assert task.max_iterations == 10
        assert task.context == {}

    def test_full_creation(self):
        task = SpecialistTask(
            task_id="t-2",
            task_type="analysis",
            prompt="Analyze trends",
            params={"depth": "deep"},
            max_iterations=5,
            context={"model": "claude-haiku-4-5", "persona": "analyst"},
        )
        assert task.params == {"depth": "deep"}
        assert task.max_iterations == 5
        assert task.context["persona"] == "analyst"

    def test_serialization_roundtrip(self):
        task = SpecialistTask(
            task_id="t-3",
            task_type="synthesis",
            prompt="Summarize findings",
            params={"format": "brief"},
        )
        data = task.model_dump()
        restored = SpecialistTask.model_validate(data)
        assert restored == task


class TestSpecialistResult:
    """Tests for the SpecialistResult model."""

    def test_success_result(self):
        result = SpecialistResult(
            task_id="t-1",
            success=True,
            findings=[{"theme": "LLM scaling"}],
            content="Found 3 relevant themes.",
            confidence=0.85,
        )
        assert result.success is True
        assert len(result.findings) == 1
        assert result.confidence == 0.85
        assert result.error is None

    def test_failure_result(self):
        result = SpecialistResult(
            task_id="t-1",
            success=False,
            error="Service unavailable",
        )
        assert result.success is False
        assert result.error == "Service unavailable"
        assert result.findings == []
        assert result.content == ""
        assert result.confidence == 0.0

    def test_metadata(self):
        result = SpecialistResult(
            task_id="t-1",
            success=True,
            metadata={"tokens_used": 1500, "iterations": 3},
        )
        assert result.metadata["tokens_used"] == 1500

    def test_serialization_roundtrip(self):
        result = SpecialistResult(
            task_id="t-1",
            success=True,
            findings=[{"a": 1}],
            content="done",
            confidence=0.9,
            metadata={"k": "v"},
        )
        data = result.model_dump()
        restored = SpecialistResult.model_validate(data)
        assert restored == result


class TestBaseSpecialistABC:
    """Tests that BaseSpecialist enforces the abstract interface."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError, match="abstract method"):
            BaseSpecialist()  # type: ignore[abstract]

    def test_must_implement_execute(self):
        class PartialSpecialist(BaseSpecialist):
            def get_tools(self) -> list:
                return []

            def get_capabilities(self) -> list[str]:
                return []

            @property
            def name(self) -> str:
                return "partial"

        with pytest.raises(TypeError, match="abstract method"):
            PartialSpecialist()  # type: ignore[abstract]

    def test_must_implement_get_tools(self):
        class PartialSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_capabilities(self) -> list[str]:
                return []

            @property
            def name(self) -> str:
                return "partial"

        with pytest.raises(TypeError, match="abstract method"):
            PartialSpecialist()  # type: ignore[abstract]

    def test_must_implement_get_capabilities(self):
        class PartialSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_tools(self) -> list:
                return []

            @property
            def name(self) -> str:
                return "partial"

        with pytest.raises(TypeError, match="abstract method"):
            PartialSpecialist()  # type: ignore[abstract]

    def test_must_implement_name(self):
        class PartialSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_tools(self) -> list:
                return []

            def get_capabilities(self) -> list[str]:
                return []

        with pytest.raises(TypeError, match="abstract method"):
            PartialSpecialist()  # type: ignore[abstract]

    def test_complete_implementation_works(self):
        class CompleteSpecialist(BaseSpecialist):
            async def execute(self, task):
                return SpecialistResult(task_id=task.task_id, success=True)

            def get_tools(self) -> list:
                return []

            def get_capabilities(self) -> list[str]:
                return ["test"]

            @property
            def name(self) -> str:
                return "complete"

        specialist = CompleteSpecialist()
        assert specialist.name == "complete"
        assert specialist.get_capabilities() == ["test"]
        assert specialist.get_tools() == []
