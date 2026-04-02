"""Tests for the Conductor agent.

All external dependencies (specialists, memory, approval, persona) are mocked.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.conductor import Conductor, ConductorResult, MAX_RETRIES
from src.agents.memory.models import MemoryEntry, MemoryType
from src.agents.persona.models import PersonaConfig
from src.agents.specialists.base import SpecialistResult, SpecialistTask
from src.models.agent_task import AgentTaskStatus
from src.models.approval_request import RiskLevel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_persona_config(**overrides) -> PersonaConfig:
    """Create a minimal PersonaConfig for testing."""
    defaults = {
        "name": "default",
        "role": "AI analyst",
        "domain_focus": {"primary": ["ai"], "secondary": []},
    }
    defaults.update(overrides)
    return PersonaConfig(**defaults)


def _make_specialist_result(
    task_id: str = "t1.sub.0",
    success: bool = True,
    content: str = "Result content",
    findings: list | None = None,
    confidence: float = 0.85,
    cost: float = 0.01,
    tokens: int = 100,
    error: str | None = None,
) -> SpecialistResult:
    """Create a SpecialistResult for testing."""
    return SpecialistResult(
        task_id=task_id,
        success=success,
        content=content,
        findings=findings or [],
        confidence=confidence,
        metadata={"cost": cost, "tokens": tokens},
        error=error,
    )


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.list_specialists.return_value = ["research", "analysis", "synthesis"]
    specialist = MagicMock()
    specialist.name = "research"
    specialist.get_tools.return_value = []
    specialist.get_capabilities.return_value = ["search", "retrieve"]
    specialist.execute = AsyncMock(return_value=_make_specialist_result())
    registry.get.return_value = specialist
    return registry


@pytest.fixture
def mock_memory_provider():
    provider = MagicMock()
    provider.recall = AsyncMock(return_value=[])
    provider.store = AsyncMock(return_value="mem-1")
    return provider


@pytest.fixture
def mock_approval_gate():
    gate = MagicMock()
    gate.check_action.return_value = (True, RiskLevel.LOW)
    return gate


@pytest.fixture
def mock_persona_loader():
    loader = MagicMock()
    loader.load.return_value = _make_persona_config()
    return loader


@pytest.fixture
def conductor(mock_registry, mock_memory_provider, mock_approval_gate, mock_persona_loader):
    return Conductor(
        registry=mock_registry,
        memory_provider=mock_memory_provider,
        approval_gate=mock_approval_gate,
        persona_loader=mock_persona_loader,
        llm_router=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExecuteTaskLifecycle:
    """Verify the conductor transitions through all lifecycle states."""

    @pytest.mark.asyncio
    async def test_happy_path_completes(self, conductor):
        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Find AI trends",
        )
        assert result.task_id == "task-1"
        assert result.status == AgentTaskStatus.COMPLETED
        assert result.error is None

    @pytest.mark.asyncio
    async def test_result_is_conductor_result(self, conductor):
        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Find AI trends",
        )
        assert isinstance(result, ConductorResult)

    @pytest.mark.asyncio
    async def test_default_params(self, conductor):
        """Default persona and source are used when not specified."""
        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="test",
        )
        conductor.persona_loader.load.assert_called_with("default")
        assert result.status == AgentTaskStatus.COMPLETED


class TestPersonaLoading:
    """Verify that persona configuration affects conductor behavior."""

    @pytest.mark.asyncio
    async def test_loads_specified_persona(self, conductor):
        custom_config = _make_persona_config(name="researcher", role="Deep researcher")
        conductor.persona_loader.load.return_value = custom_config

        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Deep research",
            persona="researcher",
        )
        conductor.persona_loader.load.assert_called_with("researcher")

    @pytest.mark.asyncio
    async def test_persona_with_restricted_tools(self, conductor):
        """Persona restrictions are passed through delegation."""
        config = _make_persona_config(
            name="restricted",
            role="Restricted analyst",
            restricted_tools=["dangerous_tool"],
        )
        conductor.persona_loader.load.return_value = config

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="analysis",
            prompt="Analyze safely",
            persona="restricted",
        )
        assert result.status == AgentTaskStatus.COMPLETED


class TestSpecialistDelegation:
    """Verify correct specialist is selected and called."""

    @pytest.mark.asyncio
    async def test_delegates_to_correct_specialist(self, conductor):
        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Find info",
        )
        conductor.registry.get.assert_called_with("research")

    @pytest.mark.asyncio
    async def test_unknown_task_type_defaults_to_research(self, conductor):
        await conductor.execute_task(
            task_id="task-1",
            task_type="unknown_type",
            prompt="Something",
        )
        conductor.registry.get.assert_called_with("research")

    @pytest.mark.asyncio
    async def test_specialist_receives_task(self, conductor):
        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Find info",
        )
        specialist = conductor.registry.get.return_value
        specialist.execute.assert_called_once()
        call_args = specialist.execute.call_args
        task_arg = call_args[0][0]
        assert isinstance(task_arg, SpecialistTask)
        assert task_arg.prompt == "Find info"

    @pytest.mark.asyncio
    async def test_select_specialist_mapping(self, conductor):
        assert conductor._select_specialist("research") == "research"
        assert conductor._select_specialist("analysis") == "analysis"
        assert conductor._select_specialist("synthesis") == "synthesis"
        assert conductor._select_specialist("ingestion") == "ingestion"
        assert conductor._select_specialist("bogus") == "research"


class TestFailureRecovery:
    """Verify retry policy and partial result handling."""

    @pytest.mark.asyncio
    async def test_retries_on_specialist_failure(self, conductor):
        specialist = conductor.registry.get.return_value
        fail_result = _make_specialist_result(success=False, error="transient error")
        success_result = _make_specialist_result(success=True)
        specialist.execute = AsyncMock(side_effect=[fail_result, success_result])

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Retry me",
        )
        assert result.status == AgentTaskStatus.COMPLETED
        assert specialist.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, conductor):
        specialist = conductor.registry.get.return_value
        fail_result = _make_specialist_result(success=False, error="persistent error")
        specialist.execute = AsyncMock(return_value=fail_result)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Always fails",
        )
        # After MAX_RETRIES+1 attempts, still completes (synthesis of failed results)
        assert specialist.execute.call_count == MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_exception_in_specialist_retries(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            side_effect=[RuntimeError("boom"), _make_specialist_result()]
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Exception then success",
        )
        assert result.status == AgentTaskStatus.COMPLETED
        assert specialist.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_specialist_not_found_retries_then_continues(self, conductor):
        """When specialist is not found, retries are exhausted and a failed result is synthesized."""
        conductor.registry.get.return_value = None

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="No specialist",
        )
        # Conductor completes synthesis even with failed sub-tasks
        assert result.status == AgentTaskStatus.COMPLETED
        assert result.result["success_count"] == 0

    @pytest.mark.asyncio
    async def test_partial_results_on_unexpected_failure(self, conductor):
        """When an unexpected error occurs, partial results are returned with FAILED status."""
        # Force an error during planning by making persona_loader raise
        conductor.persona_loader.load.side_effect = RuntimeError("Persona broken")

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Fails in planning",
        )
        assert result.status == AgentTaskStatus.FAILED
        assert result.error is not None
        assert "Persona broken" in result.error


class TestApprovalBlocking:
    """Verify HIGH/CRITICAL risk actions block the task."""

    @pytest.mark.asyncio
    async def test_high_risk_blocks_task(self, conductor):
        conductor.approval_gate.check_action.return_value = (False, RiskLevel.HIGH)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Risky operation",
        )
        assert result.status == AgentTaskStatus.BLOCKED
        assert result.result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_critical_risk_blocks_task(self, conductor):
        conductor.approval_gate.check_action.return_value = (False, RiskLevel.CRITICAL)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Critical operation",
        )
        assert result.status == AgentTaskStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_low_risk_auto_approves(self, conductor):
        conductor.approval_gate.check_action.return_value = (True, RiskLevel.LOW)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Safe operation",
        )
        assert result.status == AgentTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_medium_risk_auto_approves(self, conductor):
        conductor.approval_gate.check_action.return_value = (True, RiskLevel.MEDIUM)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Medium risk",
        )
        assert result.status == AgentTaskStatus.COMPLETED


class TestSynthesis:
    """Verify results from specialists are merged correctly."""

    @pytest.mark.asyncio
    async def test_synthesis_merges_content(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(
                content="Analysis result",
                findings=[
                    {"title": "Finding 1", "content": "Detail", "confidence": 0.9}
                ],
            )
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Analyze this",
        )
        assert result.status == AgentTaskStatus.COMPLETED
        assert "Analysis result" in result.result["content"]
        assert len(result.result["findings"]) == 1

    @pytest.mark.asyncio
    async def test_high_confidence_findings_become_insights(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(
                findings=[
                    {"title": "Strong", "content": "Detail", "confidence": 0.9, "type": "trend"},
                    {"title": "Weak", "content": "Detail", "confidence": 0.3, "type": "trend"},
                ],
            )
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Insights test",
        )
        # Only the high-confidence finding should appear as an insight
        assert len(result.insights) == 1
        assert result.insights[0]["title"] == "Strong"

    @pytest.mark.asyncio
    async def test_synthesis_counts_successes(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(success=True)
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Count test",
        )
        assert result.result["specialist_count"] == 1
        assert result.result["success_count"] == 1


class TestMemoryQueryBeforePlanning:
    """Verify memory is queried before planning and context is used."""

    @pytest.mark.asyncio
    async def test_memory_recall_called(self, conductor):
        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Use memory",
        )
        conductor.memory_provider.recall.assert_called_once()
        call_args = conductor.memory_provider.recall.call_args
        assert call_args[0][0] == "Use memory"

    @pytest.mark.asyncio
    async def test_memory_context_passed_to_specialist(self, conductor):
        memory_entry = MemoryEntry(
            id="mem-1",
            content="Previous insight about AI trends",
            memory_type=MemoryType.INSIGHT,
            score=0.95,
        )
        conductor.memory_provider.recall = AsyncMock(return_value=[memory_entry])

        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="AI trends",
        )
        specialist = conductor.registry.get.return_value
        call_args = specialist.execute.call_args
        task_arg = call_args[0][0]
        # Memory context should be in the task context
        assert "memory" in task_arg.context
        assert len(task_arg.context["memory"]) == 1
        assert task_arg.context["memory"][0]["id"] == "mem-1"

    @pytest.mark.asyncio
    async def test_memory_failure_graceful_degradation(self, conductor):
        conductor.memory_provider.recall = AsyncMock(
            side_effect=RuntimeError("Memory unavailable")
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Memory fails",
        )
        # Should still complete successfully with empty memory context
        assert result.status == AgentTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_insights_stored_after_completion(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(
                findings=[
                    {"title": "Stored insight", "content": "Detail", "confidence": 0.9}
                ],
            )
        )

        await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Store insights",
        )
        conductor.memory_provider.store.assert_called()


class TestCostTracking:
    """Verify cost and token counts are accumulated across specialist calls."""

    @pytest.mark.asyncio
    async def test_cost_accumulated(self, conductor):
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(cost=0.05, tokens=500)
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Track costs",
        )
        assert result.cost_total == pytest.approx(0.05)
        assert result.tokens_total == 500

    @pytest.mark.asyncio
    async def test_cost_zero_on_blocked(self, conductor):
        conductor.approval_gate.check_action.return_value = (False, RiskLevel.HIGH)

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Blocked",
        )
        assert result.cost_total == 0.0
        assert result.tokens_total == 0

    @pytest.mark.asyncio
    async def test_cost_on_failure(self, conductor):
        """Cost should reflect the final specialist result even when it failed."""
        specialist = conductor.registry.get.return_value
        specialist.execute = AsyncMock(
            return_value=_make_specialist_result(
                success=False, cost=0.02, tokens=200, error="failed"
            )
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Partial cost",
        )
        # Cost comes from the single result returned by _delegate_with_retry
        assert result.cost_total == pytest.approx(0.02)
        assert result.tokens_total == 200


class TestLLMRouterPlanning:
    """Verify LLM router is used for planning when available."""

    @pytest.mark.asyncio
    async def test_llm_planning_used_when_available(
        self, mock_registry, mock_memory_provider, mock_approval_gate, mock_persona_loader
    ):
        import json

        plan_json = json.dumps([
            {"specialist": "research", "prompt": "Step 1", "params": {}},
            {"specialist": "analysis", "prompt": "Step 2", "params": {}},
        ])
        llm_response = MagicMock()
        llm_response.text = plan_json
        llm_router = MagicMock()
        llm_router.generate_with_planning = AsyncMock(return_value=llm_response)
        # Set up both specialists
        research_spec = MagicMock()
        research_spec.name = "research"
        research_spec.get_tools.return_value = []
        research_spec.execute = AsyncMock(
            return_value=_make_specialist_result(task_id="t1.sub.0")
        )
        analysis_spec = MagicMock()
        analysis_spec.name = "analysis"
        analysis_spec.get_tools.return_value = []
        analysis_spec.execute = AsyncMock(
            return_value=_make_specialist_result(task_id="t1.sub.1")
        )
        mock_registry.get.side_effect = lambda name: {
            "research": research_spec,
            "analysis": analysis_spec,
        }.get(name)

        conductor = Conductor(
            registry=mock_registry,
            memory_provider=mock_memory_provider,
            approval_gate=mock_approval_gate,
            persona_loader=mock_persona_loader,
            llm_router=llm_router,
        )

        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Multi-step",
        )
        assert result.status == AgentTaskStatus.COMPLETED
        llm_router.generate_with_planning.assert_called_once()
        research_spec.execute.assert_called_once()
        analysis_spec.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_plan_when_no_llm_router(self, conductor):
        """Without LLM router, falls back to single sub-task plan."""
        result = await conductor.execute_task(
            task_id="task-1",
            task_type="research",
            prompt="Simple task",
        )
        assert result.status == AgentTaskStatus.COMPLETED
        # Single specialist call expected
        conductor.registry.get.return_value.execute.assert_called_once()
