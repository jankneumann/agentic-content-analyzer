"""Conductor agent — the orchestrating intelligence for agentic tasks.

The conductor is the entry point for all agentic work. It manages the full
lifecycle of a task: loading persona config, querying memory for context,
planning sub-tasks, delegating to specialists, monitoring completion,
synthesizing results, and storing insights.

State machine:
    RECEIVED → PLANNING → DELEGATING → MONITORING → SYNTHESIZING → COMPLETED
                                          ↓
                                      BLOCKED (awaiting approval)
                                          ↓
                                      DELEGATING (resume on approval)
    Any state can transition to FAILED.

See design doc: openspec/changes/agentic-analysis-agent/design.md (D1).
"""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from src.agents.approval.gates import ApprovalGate
from src.agents.memory.provider import MemoryProvider
from src.agents.persona.loader import PersonaLoader
from src.agents.persona.models import PersonaConfig
from src.agents.registry import SpecialistRegistry
from src.agents.specialists.base import SpecialistResult, SpecialistTask
from src.models.agent_task import AgentTaskStatus

logger = logging.getLogger(__name__)

# Retry policy
MAX_RETRIES = 2


class ConductorResult(BaseModel):
    """Result of a conductor-managed task execution."""

    task_id: str
    status: str  # AgentTaskStatus value
    result: dict[str, Any] = Field(default_factory=dict)
    insights: list[dict[str, Any]] = Field(default_factory=list)
    cost_total: float = 0.0
    tokens_total: int = 0
    error: str | None = None
    persona_snapshot: dict[str, Any] | None = None


# Mapping from task type keywords to specialist names.
_TASK_TYPE_TO_SPECIALIST: dict[str, str] = {
    "research": "research",
    "analysis": "analysis",
    "synthesis": "synthesis",
    "ingestion": "ingestion",
}


class Conductor:
    """Orchestrates agentic tasks through planning, delegation, and synthesis.

    The conductor does NOT execute domain work directly — it plans and
    delegates to specialist agents through the registry.

    Args:
        registry: Specialist agent registry for delegation.
        memory_provider: Hybrid memory provider for context recall and storage.
        approval_gate: Risk-tiered approval gate for action control.
        persona_loader: Loader for persona YAML configs (optional, defaults to PersonaLoader).
        llm_router: LLM router for planning decomposition (loosely typed to avoid circular imports).
    """

    def __init__(
        self,
        registry: SpecialistRegistry,
        memory_provider: MemoryProvider,
        approval_gate: ApprovalGate,
        persona_loader: PersonaLoader | None = None,
        llm_router: Any = None,
    ) -> None:
        self.registry = registry
        self.memory_provider = memory_provider
        self.approval_gate = approval_gate
        self.persona_loader = persona_loader or PersonaLoader()
        self.llm_router = llm_router

    async def execute_task(
        self,
        task_id: str,
        task_type: str,
        prompt: str,
        persona: str = "default",
        source: str = "user",
        params: dict[str, Any] | None = None,
    ) -> ConductorResult:
        """Execute a task through the full conductor lifecycle.

        Steps:
            1. Load persona configuration
            2. Query memory for relevant context
            3. Plan: decompose goal into specialist sub-tasks
            4. Check approval gates for each sub-task
            5. Delegate sub-tasks to appropriate specialists
            6. Monitor completion and accumulate costs
            7. Synthesize results into a coherent output
            8. Store insights in memory
            9. Return final result

        Args:
            task_id: Unique identifier for this task.
            task_type: High-level task type (research, analysis, synthesis, ingestion).
            prompt: User/schedule prompt describing the goal.
            persona: Persona name to load (defaults to "default").
            source: How the task was initiated (user, schedule, conductor).
            params: Additional parameters for the task.

        Returns:
            ConductorResult with status, merged results, insights, and cost totals.
        """
        if params is None:
            params = {}

        status = AgentTaskStatus.RECEIVED
        cost_total = 0.0
        tokens_total = 0
        partial_results: list[SpecialistResult] = []

        try:
            # 1. Load persona
            status = AgentTaskStatus.PLANNING
            logger.info("Conductor: loading persona '%s' for task %s", persona, task_id)
            persona_config = self.persona_loader.load(persona)

            # 2. Query memory for context
            memory_context = await self._query_memory(prompt)

            # 3. Plan sub-tasks
            plan = await self._plan_task(prompt, task_type, persona_config, memory_context)
            logger.info(
                "Conductor: planned %d sub-tasks for task %s",
                len(plan),
                task_id,
            )

            # 4-6. Delegate each sub-task to the appropriate specialist
            status = AgentTaskStatus.DELEGATING
            for i, sub_task in enumerate(plan):
                specialist_name = sub_task.get("specialist", self._select_specialist(task_type))
                sub_prompt = sub_task.get("prompt", prompt)
                sub_params = sub_task.get("params", {})

                # Check approval gate
                action_name = f"delegate.{specialist_name}"
                auto_approved, risk_level = self.approval_gate.check_action(action_name)
                if not auto_approved:
                    logger.info(
                        "Conductor: task %s blocked on approval for %s (risk=%s)",
                        task_id,
                        specialist_name,
                        risk_level.value,
                    )
                    return ConductorResult(
                        task_id=task_id,
                        status=AgentTaskStatus.BLOCKED,
                        result={"blocked_on": specialist_name, "risk_level": risk_level.value},
                        insights=[],
                        cost_total=cost_total,
                        tokens_total=tokens_total,
                    )

                # Delegate with retry
                # Resolve model and tool restrictions from persona
                model_override = persona_config.resolve_model(specialist_name)
                specialist_obj = self.registry.get(specialist_name)
                allowed_tool_names = None
                if specialist_obj and persona_config.restricted_tools:
                    filtered = persona_config.filter_tools(specialist_obj.get_tools())
                    allowed_tool_names = [t.name for t in filtered]

                spec_task = SpecialistTask(
                    task_id=f"{task_id}.sub.{i}",
                    task_type=specialist_name,
                    prompt=sub_prompt,
                    params=sub_params,
                    context={
                        "memory": memory_context,
                        "persona": persona,
                        "model": model_override,
                        "allowed_tools": allowed_tool_names,
                    },
                )

                result = await self._delegate_with_retry(specialist_name, spec_task, persona_config)
                partial_results.append(result)

                # Accumulate costs from specialist metadata
                cost_total += result.metadata.get("cost", 0.0)
                tokens_total += result.metadata.get("tokens_used", result.metadata.get("tokens", 0))

            # 6b. Monitor — all delegation complete
            status = AgentTaskStatus.MONITORING
            logger.info(
                "Conductor: all %d sub-tasks complete for task %s",
                len(partial_results),
                task_id,
            )

            # 7. Synthesize results
            status = AgentTaskStatus.SYNTHESIZING
            logger.info("Conductor: synthesizing results for task %s", task_id)
            synthesis = await self._synthesize_results(partial_results, prompt)

            # 8. Store insights in memory
            insights = synthesis.get("insights", [])
            await self._store_insights(task_id, insights)

            status = AgentTaskStatus.COMPLETED
            return ConductorResult(
                task_id=task_id,
                status=status,
                result=synthesis,
                insights=insights,
                cost_total=cost_total,
                tokens_total=tokens_total,
                persona_snapshot=persona_config.model_dump(),
            )

        except Exception as e:
            logger.exception("Conductor: task %s failed: %s", task_id, e)
            # Return partial results on failure
            partial_synthesis: dict[str, Any] = {}
            if partial_results:
                try:
                    partial_synthesis = await self._synthesize_results(partial_results, prompt)
                    partial_synthesis["partial"] = True
                except Exception:
                    logger.warning(
                        "Conductor: failed to synthesize partial results for %s",
                        task_id,
                    )

            return ConductorResult(
                task_id=task_id,
                status=AgentTaskStatus.FAILED,
                result=partial_synthesis,
                insights=[],
                cost_total=cost_total,
                tokens_total=tokens_total,
                error=str(e),
            )

    async def _query_memory(self, prompt: str) -> list[dict[str, Any]]:
        """Query memory provider for context relevant to the prompt.

        Returns a list of memory entry dicts for use in planning context.
        Falls back to an empty list on error.
        """
        try:
            entries = await self.memory_provider.recall(prompt, limit=10)
            return [{"id": e.id, "content": e.content, "score": e.score} for e in entries]
        except Exception as e:
            logger.warning("Conductor: memory query failed: %s", e)
            return []

    async def _plan_task(
        self,
        prompt: str,
        task_type: str,
        persona_config: PersonaConfig,
        memory_context: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Decompose a task into specialist sub-tasks.

        If an LLM router is available, uses it for intelligent decomposition.
        Otherwise, falls back to a single-step plan delegating to the
        default specialist.

        Returns:
            List of sub-task dicts: {specialist: str, prompt: str, params: dict}.
        """
        if self.llm_router is not None and hasattr(self.llm_router, "generate_with_planning"):
            try:
                # Build a planning prompt that instructs the LLM to return
                # structured sub-tasks for the available specialists.
                specialist_names = self.registry.list_specialists()
                planning_goal = (
                    f"Decompose this task into sub-tasks for these specialists: "
                    f"{specialist_names}.\n\n"
                    f"Task: {prompt}\n\n"
                    f"Return a JSON list of objects with keys: specialist, prompt, params."
                )

                response = await self.llm_router.generate_with_planning(
                    goal=planning_goal,
                    model=persona_config.resolve_model("conductor"),
                    tools=[],
                    tool_executor=lambda *a, **kw: None,
                    system_prompt=(
                        "You are a task planner. Decompose the goal into sub-tasks. "
                        "Return a JSON array of {specialist, prompt, params} objects."
                    ),
                    memory_context=memory_context or None,
                )
                # Try to parse a plan from the response text
                import json

                plan_text = response.text if hasattr(response, "text") else str(response)
                # Look for a JSON array in the response
                start = plan_text.find("[")
                end = plan_text.rfind("]") + 1
                if start >= 0 and end > start:
                    plan = json.loads(plan_text[start:end])
                    if isinstance(plan, list) and plan:
                        # Validate plan items have required keys
                        validated = []
                        for item in plan:
                            if isinstance(item, dict) and "specialist" in item and "prompt" in item:
                                validated.append(
                                    {
                                        "specialist": item["specialist"],
                                        "prompt": item["prompt"],
                                        "params": item.get("params", {}),
                                    }
                                )
                        if validated:
                            return validated
            except Exception as e:
                logger.warning("Conductor: LLM planning failed, using fallback: %s", e)

        # Fallback: single sub-task using the appropriate specialist for the task type
        return [{"specialist": self._select_specialist(task_type), "prompt": prompt, "params": {}}]

    async def _delegate_to_specialist(
        self,
        specialist_name: str,
        task: SpecialistTask,
        persona_config: PersonaConfig,
    ) -> SpecialistResult:
        """Delegate a sub-task to a specialist from the registry.

        Raises:
            ValueError: If the specialist is not registered.
        """
        specialist = self.registry.get(specialist_name)
        if specialist is None:
            raise ValueError(f"Specialist not found: {specialist_name}")

        # Filter tools based on persona restrictions
        available_tools = persona_config.filter_tools(specialist.get_tools())

        logger.info(
            "Conductor: delegating to '%s' (tools=%d)",
            specialist_name,
            len(available_tools),
        )
        return await specialist.execute(task)

    async def _delegate_with_retry(
        self,
        specialist_name: str,
        task: SpecialistTask,
        persona_config: PersonaConfig,
    ) -> SpecialistResult:
        """Delegate with retry policy (max MAX_RETRIES attempts on failure).

        Returns the successful result or the last failed result.
        """
        last_result: SpecialistResult | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = await self._delegate_to_specialist(specialist_name, task, persona_config)
                if result.success:
                    return result
                last_result = result
                logger.warning(
                    "Conductor: specialist '%s' returned failure on attempt %d: %s",
                    specialist_name,
                    attempt + 1,
                    result.error,
                )
            except Exception as e:
                logger.warning(
                    "Conductor: specialist '%s' raised on attempt %d: %s",
                    specialist_name,
                    attempt + 1,
                    e,
                )
                last_result = SpecialistResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(e),
                )

            if attempt < MAX_RETRIES:
                backoff_seconds = 2 ** (attempt + 1)  # 2s, 4s
                logger.info(
                    "Conductor: waiting %ds before retry for specialist '%s' (attempt %d/%d)",
                    backoff_seconds,
                    specialist_name,
                    attempt + 2,
                    MAX_RETRIES + 1,
                )
                await asyncio.sleep(backoff_seconds)

        # All retries exhausted — return last result
        assert last_result is not None
        return last_result

    async def _synthesize_results(
        self,
        results: list[SpecialistResult],
        original_prompt: str,
    ) -> dict[str, Any]:
        """Merge specialist results into a coherent output.

        Combines findings, content, and metadata from all specialist results.
        Extracts insights from findings with confidence >= 0.7.

        Returns:
            Dict with keys: content, findings, insights, specialist_count,
            success_count, and total_confidence.
        """
        all_findings: list[dict[str, Any]] = []
        all_content: list[str] = []
        success_count = 0

        for result in results:
            all_findings.extend(result.findings)
            if result.content:
                all_content.append(result.content)
            if result.success:
                success_count += 1

        # Extract high-confidence findings as insights; tag low-confidence as speculative
        insights = []
        for f in all_findings:
            conf = f.get("confidence", 0.0)
            if conf >= 0.7:
                insights.append(
                    {
                        "type": f.get("type", "summary"),
                        "title": f.get("title", "Untitled"),
                        "content": f.get("content", ""),
                        "confidence": conf,
                    }
                )
            elif conf < 0.3:
                insights.append(
                    {
                        "type": f.get("type", "summary"),
                        "title": f.get("title", "Untitled"),
                        "content": f.get("content", ""),
                        "confidence": conf,
                        "speculative": True,
                    }
                )

        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0.0

        synthesis: dict[str, Any] = {
            "content": "\n\n".join(all_content),
            "findings": all_findings,
            "insights": insights,
            "specialist_count": len(results),
            "success_count": success_count,
            "total_confidence": avg_confidence,
            "original_prompt": original_prompt,
        }
        if success_count < len(results):
            synthesis["partial"] = True
        return synthesis

    async def _store_insights(
        self,
        task_id: str,
        insights: list[dict[str, Any]],
    ) -> None:
        """Store generated insights in memory for future recall.

        Each insight is stored as a memory entry. Failures are logged
        but do not block the conductor's result.
        """
        if not insights:
            return

        from src.agents.memory.models import MemoryEntry, MemoryType

        for insight in insights:
            try:
                entry = MemoryEntry(
                    content=f"{insight.get('title', '')}: {insight.get('content', '')}",
                    memory_type=MemoryType.INSIGHT,
                    source_task_id=task_id,
                    confidence=insight.get("confidence", 0.0),
                    tags=[insight.get("type", "summary")],
                )
                await self.memory_provider.store(entry)
            except Exception as e:
                logger.warning(
                    "Conductor: failed to store insight for task %s: %s",
                    task_id,
                    e,
                )

    def _select_specialist(self, task_type: str) -> str:
        """Map a task type to a specialist name.

        Falls back to 'research' for unknown task types.
        """
        return _TASK_TYPE_TO_SPECIALIST.get(task_type, "research")
