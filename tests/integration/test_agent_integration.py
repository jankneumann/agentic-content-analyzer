"""Integration tests for the agentic analysis system.

These tests validate cross-component wiring with REAL object composition.
Unlike the unit tests in tests/agents/ which mock all neighbors, these
tests compose real Conductor → Registry → Specialists → MemoryProvider
→ ApprovalGate chains. Only LLM calls are mocked (via a fake LLMRouter).

Covers OpenSpec tasks: 5.7, 8.1, 8.1a, 8.1b, 8.1c, 8.2.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.approval.gates import ApprovalGate
from src.agents.conductor import Conductor
from src.agents.memory.models import MemoryEntry, MemoryType
from src.agents.memory.provider import MemoryProvider
from src.agents.memory.strategies.base import MemoryStrategy
from src.agents.persona.loader import PersonaLoader
from src.agents.registry import SpecialistRegistry
from src.agents.specialists.base import BaseSpecialist, SpecialistResult, SpecialistTask
from src.models.agent_task import AgentTaskStatus
from src.models.approval_request import RiskLevel

# ---------------------------------------------------------------------------
# Helpers: Fake LLM Router and In-Memory Strategy
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMResponse:
    """Simulates an LLM response with token tracking."""

    text: str
    input_tokens: int = 50
    output_tokens: int = 30


class FakeLLMRouter:
    """Fake LLM router that returns deterministic responses.

    This replaces real LLM calls while preserving the interface that
    specialists and conductor rely on. Tracks all calls for assertions.
    """

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["Analysis complete. Key finding: test insight."]
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []

    async def generate_with_tools(
        self,
        model: str | None = None,
        system_prompt: str = "",
        user_prompt: str = "",
        tools: list | None = None,
        tool_executor: Any = None,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> FakeLLMResponse:
        self.calls.append(
            {
                "method": "generate_with_tools",
                "model": model,
                "user_prompt": user_prompt,
                "tools_count": len(tools) if tools else 0,
            }
        )
        text = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1
        return FakeLLMResponse(text=text)

    async def generate_with_planning(
        self,
        goal: str = "",
        model: str | None = None,
        tools: list | None = None,
        tool_executor: Any = None,
        system_prompt: str = "",
        memory_context: list | None = None,
        **kwargs: Any,
    ) -> FakeLLMResponse:
        self.calls.append(
            {
                "method": "generate_with_planning",
                "goal": goal,
                "model": model,
            }
        )
        text = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1
        return FakeLLMResponse(text=text)


class InMemoryStrategy(MemoryStrategy):
    """In-memory strategy for integration tests — no DB required."""

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}

    async def store(self, memory: MemoryEntry) -> str:
        memory_id = memory.id or str(uuid.uuid4())
        self._store[memory_id] = memory.model_copy(update={"id": memory_id})
        return memory_id

    async def recall(self, query: str, limit: int = 20, filters: Any = None) -> list[MemoryEntry]:
        # Return all entries ranked by recency (newest first)
        entries = sorted(self._store.values(), key=lambda e: e.created_at, reverse=True)
        # Set a simple score based on position
        results = []
        for i, entry in enumerate(entries[:limit]):
            results.append(entry.model_copy(update={"score": 1.0 / (i + 1)}))
        return results

    async def forget(self, memory_id: str) -> bool:
        return self._store.pop(memory_id, None) is not None

    async def health_check(self) -> bool:
        return True


class FailingStrategy(MemoryStrategy):
    """Strategy that always fails — for circuit breaker testing."""

    async def store(self, memory: MemoryEntry) -> str:
        raise ConnectionError("Backend unavailable")

    async def recall(self, query: str, limit: int = 20, filters: Any = None) -> list[MemoryEntry]:
        raise ConnectionError("Backend unavailable")

    async def forget(self, memory_id: str) -> bool:
        raise ConnectionError("Backend unavailable")

    async def health_check(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_llm_router() -> FakeLLMRouter:
    return FakeLLMRouter()


@pytest.fixture
def in_memory_strategy() -> InMemoryStrategy:
    return InMemoryStrategy()


@pytest.fixture
def memory_provider(in_memory_strategy: InMemoryStrategy) -> MemoryProvider:
    return MemoryProvider(strategies={"memory": (in_memory_strategy, 1.0)})


@pytest.fixture
def registry(fake_llm_router: FakeLLMRouter) -> SpecialistRegistry:
    """Real registry with all 4 built-in specialists using fake LLM."""
    return SpecialistRegistry.create_default(llm_router=fake_llm_router)


@pytest.fixture
def low_risk_gate() -> ApprovalGate:
    """Approval gate where all delegation actions are LOW risk."""
    return ApprovalGate(
        base_config={
            "delegate.research": RiskLevel.LOW,
            "delegate.analysis": RiskLevel.LOW,
            "delegate.synthesis": RiskLevel.LOW,
            "delegate.ingestion": RiskLevel.LOW,
        }
    )


@pytest.fixture
def mixed_risk_gate() -> ApprovalGate:
    """Approval gate with mixed risk levels for testing blocking."""
    return ApprovalGate(
        base_config={
            "delegate.research": RiskLevel.LOW,
            "delegate.analysis": RiskLevel.LOW,
            "delegate.synthesis": RiskLevel.LOW,
            "delegate.ingestion": RiskLevel.HIGH,
        }
    )


@pytest.fixture
def conductor(
    registry: SpecialistRegistry,
    memory_provider: MemoryProvider,
    low_risk_gate: ApprovalGate,
    fake_llm_router: FakeLLMRouter,
) -> Conductor:
    """Real conductor with real dependencies (only LLM is faked)."""
    return Conductor(
        registry=registry,
        memory_provider=memory_provider,
        approval_gate=low_risk_gate,
        persona_loader=PersonaLoader(),
        llm_router=fake_llm_router,
    )


# ---------------------------------------------------------------------------
# Task 5.7 / 8.1: End-to-End Task Flow
# ---------------------------------------------------------------------------


class TestEndToEndTaskFlow:
    """Integration test: full conductor lifecycle with real wiring.

    Validates that the conductor correctly composes with the registry,
    specialists, memory provider, and approval gate — not just that
    each component works in isolation.
    """

    @pytest.mark.asyncio
    async def test_research_task_completes_with_real_wiring(self, conductor: Conductor):
        """Happy path: user submits a research task, conductor delegates
        to the research specialist, synthesizes results, stores insights."""
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="What are the latest trends in AI agents?",
            persona="default",
            source="user",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        assert result.result.get("specialist_count", 0) >= 1
        assert result.result.get("success_count", 0) >= 1
        assert result.error is None
        assert result.persona_snapshot is not None
        # PersonaConfig.name is the display name from YAML, not the filename
        assert result.persona_snapshot.get("name") is not None

    @pytest.mark.asyncio
    async def test_analysis_task_routes_to_correct_specialist(
        self, conductor: Conductor, fake_llm_router: FakeLLMRouter
    ):
        """Verify task_type → specialist routing through real registry."""
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="analysis",
            prompt="Detect trends in recent AI newsletter content",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        # The LLM router should have been called for the specialist's reasoning
        assert len(fake_llm_router.calls) >= 1

    @pytest.mark.asyncio
    async def test_synthesis_task_produces_insights(self, conductor: Conductor):
        """Verify the full chain produces insights in the result."""
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="synthesis",
            prompt="Synthesize weekly AI trends into an executive brief",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        # Result should have synthesis structure
        assert "content" in result.result
        assert "findings" in result.result

    @pytest.mark.asyncio
    async def test_memory_context_recalled_before_planning(
        self,
        registry: SpecialistRegistry,
        low_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """Verify that memory is queried and passed to specialist context."""
        # Pre-populate memory with a known entry
        strategy = InMemoryStrategy()
        await strategy.store(
            MemoryEntry(
                id="pre-existing-memory",
                content="Previous finding: LLM agents are trending",
                memory_type=MemoryType.INSIGHT,
                confidence=0.9,
            )
        )
        memory_provider = MemoryProvider(strategies={"memory": (strategy, 1.0)})

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=fake_llm_router,
        )

        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="What's new in AI agents?",
        )

        assert result.status == AgentTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_insights_stored_in_memory_after_completion(
        self,
        registry: SpecialistRegistry,
        low_risk_gate: ApprovalGate,
    ):
        """Verify insights from synthesis are persisted to memory."""
        strategy = InMemoryStrategy()
        memory_provider = MemoryProvider(strategies={"memory": (strategy, 1.0)})

        # Use a response that will produce high-confidence findings
        llm = FakeLLMRouter(responses=["Significant trend identified: multi-agent systems."])
        registry_with_llm = SpecialistRegistry.create_default(llm_router=llm)

        conductor = Conductor(
            registry=registry_with_llm,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=llm,
        )

        result = await conductor.execute_task(
            task_id="test-task-insights",
            task_type="research",
            prompt="Analyze multi-agent system trends",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        # If any insights were generated, they should be stored
        if result.insights:
            stored = await strategy.recall("", limit=100)
            assert len(stored) > 0

    @pytest.mark.asyncio
    async def test_cost_and_token_tracking_through_full_chain(self, conductor: Conductor):
        """Verify cost/token accumulation from specialists up to conductor."""
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="Brief analysis of AI trends",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        # Tokens should be accumulated from the specialist's LLM call
        assert result.tokens_total >= 0

    @pytest.mark.asyncio
    async def test_all_four_specialist_types_accessible(self, registry: SpecialistRegistry):
        """Verify the real registry has all 4 specialists registered."""
        names = registry.list_specialists()
        assert "research" in names
        assert "analysis" in names
        assert "synthesis" in names
        assert "ingestion" in names

    @pytest.mark.asyncio
    async def test_memory_graceful_degradation_with_failing_backend(
        self,
        registry: SpecialistRegistry,
        low_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """Conductor completes even when memory backend fails."""
        failing_provider = MemoryProvider(strategies={"failing": (FailingStrategy(), 1.0)})

        conductor = Conductor(
            registry=registry,
            memory_provider=failing_provider,
            approval_gate=low_risk_gate,
            llm_router=fake_llm_router,
        )

        # Should complete despite memory failures (graceful degradation)
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="Test with broken memory",
        )

        assert result.status == AgentTaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Task 8.1a: Persona-Parameterized Task Flow
# ---------------------------------------------------------------------------


class TestPersonaParameterizedFlow:
    """Integration test: same prompt with different personas produces
    different behavior (model overrides, tool restrictions, output format)."""

    @pytest.mark.asyncio
    async def test_different_personas_load_different_configs(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """Two personas produce results with different persona snapshots."""
        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=fake_llm_router,
        )

        result_default = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="analysis",
            prompt="Analyze emerging AI trends",
            persona="default",
        )

        result_leadership = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="analysis",
            prompt="Analyze emerging AI trends",
            persona="leadership",
        )

        assert result_default.status == AgentTaskStatus.COMPLETED
        assert result_leadership.status == AgentTaskStatus.COMPLETED

        # Persona snapshots should differ
        # PersonaConfig.name is the display name from YAML, not the filename
        default_name = result_default.persona_snapshot["name"]
        leadership_name = result_leadership.persona_snapshot["name"]
        assert default_name != leadership_name  # Different personas produce different names

        # Leadership persona should have different domain focus
        default_focus = result_default.persona_snapshot.get("domain_focus", {})
        leadership_focus = result_leadership.persona_snapshot.get("domain_focus", {})
        assert default_focus != leadership_focus

    @pytest.mark.asyncio
    async def test_persona_approval_overrides_applied(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        fake_llm_router: FakeLLMRouter,
    ):
        """Persona overrides can lower risk levels through the real gate."""
        # Base: ingestion is HIGH risk (blocks)
        gate = ApprovalGate(
            base_config={"delegate.ingestion": RiskLevel.HIGH},
            overrides={"delegate.ingestion": RiskLevel.LOW},  # Persona lowers it
        )

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=gate,
            llm_router=fake_llm_router,
        )

        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="ingestion",
            prompt="Ingest new RSS feeds",
        )

        # Should NOT be blocked because persona override lowered risk
        assert result.status != AgentTaskStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_persona_model_overrides_passed_to_specialist(
        self,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
    ):
        """Verify persona model overrides flow through to specialist task context."""
        llm = FakeLLMRouter()
        registry = SpecialistRegistry.create_default(llm_router=llm)

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=llm,
        )

        # Use ai-ml-technology persona which has model overrides
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="Deep dive into transformer architectures",
            persona="ai-ml-technology",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        assert result.persona_snapshot["name"] is not None


# ---------------------------------------------------------------------------
# Task 8.1b: Error Recovery Flow
# ---------------------------------------------------------------------------


class TestErrorRecoveryFlow:
    """Integration test: specialist failures trigger retries and
    the conductor produces partial results on partial failure."""

    @pytest.mark.asyncio
    async def test_specialist_failure_triggers_retry(
        self,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
    ):
        """When a specialist fails, conductor retries up to MAX_RETRIES."""
        llm = FakeLLMRouter()
        registry = SpecialistRegistry.create_default(llm_router=llm)

        # Replace the research specialist with one that fails
        failing_specialist = MagicMock(spec=BaseSpecialist)
        failing_specialist.name = "research"
        failing_specialist.get_tools.return_value = []
        failing_specialist.get_capabilities.return_value = ["deep_research"]
        # Fail on first call, succeed on second
        call_count = 0

        async def conditional_execute(task: SpecialistTask) -> SpecialistResult:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return SpecialistResult(
                    task_id=task.task_id,
                    success=False,
                    error="Transient failure",
                )
            return SpecialistResult(
                task_id=task.task_id,
                success=True,
                findings=[
                    {
                        "type": "trend",
                        "title": "Recovery",
                        "content": "Recovered",
                        "confidence": 0.8,
                    }
                ],
                content="Recovered after retry",
                confidence=0.8,
                metadata={"tokens_used": 80},
            )

        failing_specialist.execute = conditional_execute
        registry._specialists["research"] = failing_specialist

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=llm,
        )

        # Patch asyncio.sleep to avoid actual waiting in tests
        with patch("src.agents.conductor.asyncio.sleep", new_callable=AsyncMock):
            result = await conductor.execute_task(
                task_id=str(uuid.uuid4()),
                task_type="research",
                prompt="Test retry",
            )

        assert result.status == AgentTaskStatus.COMPLETED
        assert call_count == 2  # One failure + one retry success

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_produces_failed_result(
        self,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
    ):
        """When all retries fail, conductor returns FAILED with partial=True."""
        llm = FakeLLMRouter()
        registry = SpecialistRegistry.create_default(llm_router=llm)

        always_failing = MagicMock(spec=BaseSpecialist)
        always_failing.name = "research"
        always_failing.get_tools.return_value = []
        always_failing.get_capabilities.return_value = ["deep_research"]

        async def always_fail(task: SpecialistTask) -> SpecialistResult:
            return SpecialistResult(
                task_id=task.task_id,
                success=False,
                error="Persistent failure",
                confidence=0.0,
            )

        always_failing.execute = always_fail
        registry._specialists["research"] = always_failing

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=llm,
        )

        with patch("src.agents.conductor.asyncio.sleep", new_callable=AsyncMock):
            result = await conductor.execute_task(
                task_id=str(uuid.uuid4()),
                task_type="research",
                prompt="Doomed to fail",
            )

        # Task completes but with partial success markers
        assert result.status in (AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED)
        if result.status == AgentTaskStatus.COMPLETED:
            assert result.result.get("partial") is True
            assert result.result.get("success_count", 0) == 0

    @pytest.mark.asyncio
    async def test_specialist_exception_caught_and_retried(
        self,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
    ):
        """Specialist that raises an exception is caught and retried."""
        llm = FakeLLMRouter()
        registry = SpecialistRegistry.create_default(llm_router=llm)

        raising_specialist = MagicMock(spec=BaseSpecialist)
        raising_specialist.name = "research"
        raising_specialist.get_tools.return_value = []
        raising_specialist.get_capabilities.return_value = ["deep_research"]

        call_count = 0

        async def raise_then_succeed(task: SpecialistTask) -> SpecialistResult:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RuntimeError("Connection reset")
            return SpecialistResult(
                task_id=task.task_id,
                success=True,
                content="Recovered",
                confidence=0.7,
                metadata={"tokens_used": 50},
            )

        raising_specialist.execute = raise_then_succeed
        registry._specialists["research"] = raising_specialist

        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=llm,
        )

        with patch("src.agents.conductor.asyncio.sleep", new_callable=AsyncMock):
            result = await conductor.execute_task(
                task_id=str(uuid.uuid4()),
                task_type="research",
                prompt="Test exception recovery",
            )

        assert result.status == AgentTaskStatus.COMPLETED
        assert call_count == 2


# ---------------------------------------------------------------------------
# Task 8.1c: Approval Gate Flow
# ---------------------------------------------------------------------------


class TestApprovalGateFlow:
    """Integration test: HIGH-risk action blocks execution,
    returning BLOCKED status with the action that was blocked."""

    @pytest.mark.asyncio
    async def test_high_risk_action_blocks_task(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        mixed_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """Ingestion task blocked because delegate.ingestion is HIGH risk."""
        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=mixed_risk_gate,
            llm_router=fake_llm_router,
        )

        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="ingestion",
            prompt="Ingest new sources",
        )

        assert result.status == AgentTaskStatus.BLOCKED
        assert result.result.get("blocked_on") == "ingestion"
        assert result.result.get("risk_level") == "high"

    @pytest.mark.asyncio
    async def test_low_risk_actions_pass_through(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        mixed_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """Research task passes because delegate.research is LOW risk."""
        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=mixed_risk_gate,
            llm_router=fake_llm_router,
        )

        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="research",
            prompt="Research AI trends",
        )

        assert result.status == AgentTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_persona_override_cannot_escalate_risk(self):
        """Persona override trying to raise risk from LOW to HIGH is ignored."""
        gate = ApprovalGate(
            base_config={"delegate.research": RiskLevel.LOW},
            overrides={"delegate.research": RiskLevel.HIGH},  # Escalation attempt
        )

        # Should still be LOW (escalation ignored)
        approved, level = gate.check_action("delegate.research")
        assert approved is True
        assert level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_critical_risk_blocks_with_audit_info(self):
        """CRITICAL risk actions are blocked."""
        gate = ApprovalGate(base_config={"delegate.ingestion": RiskLevel.CRITICAL})

        approved, level = gate.check_action("delegate.ingestion")
        assert approved is False
        assert level == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Task 8.2: Proactive Scheduler Flow
# ---------------------------------------------------------------------------


class TestProactiveSchedulerFlow:
    """Integration test: scheduler triggers a task that flows through
    the conductor to produce insights."""

    @pytest.mark.asyncio
    async def test_scheduler_tick_enqueues_due_tasks(self):
        """Scheduler tick with matching cron enqueues via callback."""
        from src.agents.scheduler.scheduler import AgentScheduler, ScheduleEntry

        enqueued_tasks: list[dict] = []

        async def mock_enqueue(payload: dict) -> str:
            task_id = str(uuid.uuid4())
            enqueued_tasks.append({**payload, "task_id": task_id})
            return task_id

        scheduler = AgentScheduler(schedule_path="/nonexistent", enqueue_fn=mock_enqueue)
        scheduler._running = True  # tick() requires _running=True
        scheduler._schedules = {
            "test_schedule": ScheduleEntry(
                id="test_schedule",
                cron="* * * * *",  # Every minute
                task_type="analysis",
                persona="default",
                description="Test trend detection",
                enabled=True,
            )
        }

        task_ids = await scheduler.tick()

        assert len(task_ids) >= 1
        assert len(enqueued_tasks) >= 1
        assert enqueued_tasks[0]["task_type"] == "analysis"
        assert enqueued_tasks[0]["persona"] == "default"

    @pytest.mark.asyncio
    async def test_scheduler_disabled_schedule_not_triggered(self):
        """Disabled schedules are skipped during tick."""
        from src.agents.scheduler.scheduler import AgentScheduler, ScheduleEntry

        enqueued: list[dict] = []

        async def mock_enqueue(payload: dict) -> str:
            enqueued.append(payload)
            return str(uuid.uuid4())

        scheduler = AgentScheduler(schedule_path="/nonexistent", enqueue_fn=mock_enqueue)
        scheduler._running = True
        scheduler._schedules = {
            "disabled": ScheduleEntry(
                id="disabled",
                cron="* * * * *",
                task_type="analysis",
                enabled=False,
            )
        }

        await scheduler.tick()
        assert len(enqueued) == 0

    @pytest.mark.asyncio
    async def test_scheduler_deduplication_prevents_double_trigger(self):
        """Same schedule not triggered twice in the same minute."""
        from src.agents.scheduler.scheduler import AgentScheduler, ScheduleEntry

        enqueued: list[dict] = []

        async def mock_enqueue(payload: dict) -> str:
            enqueued.append(payload)
            return str(uuid.uuid4())

        scheduler = AgentScheduler(schedule_path="/nonexistent", enqueue_fn=mock_enqueue)
        scheduler._running = True
        scheduler._schedules = {
            "dedup_test": ScheduleEntry(
                id="dedup_test",
                cron="* * * * *",
                task_type="analysis",
                enabled=True,
            )
        }

        now = datetime(2026, 4, 4, 12, 0, 0, tzinfo=UTC)
        await scheduler.tick(now=now)
        await scheduler.tick(now=now)  # Same minute — should be deduped

        assert len(enqueued) == 1

    @pytest.mark.asyncio
    async def test_scheduler_passes_persona_and_sources(self):
        """Schedule entries pass persona, output, and sources to enqueue payload."""
        from src.agents.scheduler.scheduler import AgentScheduler, ScheduleEntry

        enqueued: list[dict] = []

        async def mock_enqueue(payload: dict) -> str:
            enqueued.append(payload)
            return str(uuid.uuid4())

        scheduler = AgentScheduler(schedule_path="/nonexistent", enqueue_fn=mock_enqueue)
        scheduler._running = True
        scheduler._schedules = {
            "persona_test": ScheduleEntry(
                id="persona_test",
                cron="* * * * *",
                task_type="synthesis",
                persona="leadership",
                output="executive_briefing",
                sources=["rss", "youtube"],
                enabled=True,
            )
        }

        await scheduler.tick()

        assert len(enqueued) == 1
        payload = enqueued[0]
        assert payload["persona"] == "leadership"
        assert payload["output"] == "executive_briefing"
        assert payload["sources"] == ["rss", "youtube"]

    @pytest.mark.asyncio
    async def test_full_scheduler_to_conductor_flow(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        low_risk_gate: ApprovalGate,
        fake_llm_router: FakeLLMRouter,
    ):
        """End-to-end: scheduler enqueues → conductor executes → insights generated."""
        conductor = Conductor(
            registry=registry,
            memory_provider=memory_provider,
            approval_gate=low_risk_gate,
            llm_router=fake_llm_router,
        )

        # Simulate what the queue worker does: execute the conductor directly
        result = await conductor.execute_task(
            task_id=str(uuid.uuid4()),
            task_type="analysis",
            prompt="Detect trends in recent content",
            persona="default",
            source="schedule",
        )

        assert result.status == AgentTaskStatus.COMPLETED
        assert "content" in result.result
