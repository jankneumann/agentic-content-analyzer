# Session Log: agentic-analysis-agent

---

## Phase: Plan (2026-04-02)

**Agent**: claude-opus-4-6 | **Session**: N/A

### Decisions
1. **Layered Extension approach** — New agent layer on top of existing code rather than deep integration or external MCP agent. Preserves system stability while adding agentic capabilities.
2. **Extend LLMRouter** — Build agentic loop on existing `generate_with_tools()` rather than adopting Claude Agent SDK. Maintains multi-provider routing and full control.
3. **Memory provider with strategy pattern** — Abstracted memory using graph (Graphiti), vector (pgvector), and keyword (BM25) strategies with configurable weighted RRF fusion. Goes beyond OpenClaw's flat MEMORY.md.
4. **Conductor + Specialist topology** — Meta-cognitive conductor delegates to domain-specific specialists (Research, Analysis, Synthesis, Ingestion). Inspired by OpenClaw 2.0.
5. **Tiered approval gates** — NemoClaw-inspired risk classification (low/medium/high/critical) with configurable auto-approve thresholds.
6. **Full proactive pipeline** — Nanobot-inspired heartbeat scheduler using PGQueuer for: source scanning, trend detection, weekly synthesis, knowledge graph maintenance, cross-theme discovery, daily digest drafting.
7. **Configurable YAML persona** — Non-self-modifiable agent identity (unlike OpenClaw's SOUL.md) for predictable, reproducible behavior.

### Alternatives Considered
- **Deep Integration (Approach B)**: Rejected — embedding agentic logic into existing ThemeAnalyzer/Pipeline creates regression risk and mixed concerns
- **MCP-Native Agent (Approach C)**: Rejected — MCP serialization overhead and loss of internal abstractions (LLMRouter, memory provider) constrain capabilities
- **Claude Agent SDK for loop engine**: Rejected — locks orchestration to single provider; existing LLMRouter already has tool-calling support
- **Self-modifiable persona (OpenClaw pattern)**: Rejected — creates unpredictable behavior and makes results non-reproducible
- **Separate scheduler (APScheduler/Celery Beat)**: Rejected — PGQueuer already provides transactional job scheduling with deduplication

### Trade-offs
- Accepted specialist wrapper indirection over direct processor modification because isolation enables independent testing and future extensibility
- Accepted two layers of LLM calls (conductor reasons + specialist executes) over single-agent flat tool palette because complex research tasks benefit from goal decomposition
- Accepted YAML-based (non-self-modifiable) persona over self-improving agent because predictability and reproducibility outweigh marginal adaptation benefits

### Open Questions
- [ ] Should the agent support interactive multi-turn research conversations (chat mode) in v1, or defer to v2?
- [ ] What cost budget limits should be set for proactive heartbeat tasks vs. user-initiated tasks?
- [ ] Should insights be surfaced via push notifications (email/webhook) or only pull (API/CLI)?
- [ ] How should the system handle conflicting insights from different analysis runs?

### Context
Planned the Agentic Analysis Agent feature based on comparative analysis of OpenClaw, Nanobot, NanoClaw, and NemoClaw frameworks. The existing codebase has strong foundations (LLMRouter with tool calling, knowledge graph, hybrid search, job queue) that map well to agentic primitives. The key gap is the orchestrating intelligence — a conductor that decides when and why to invoke existing capabilities. Selected Layered Extension approach to minimize risk while maximizing reuse.

---

## Phase: Plan Iteration 1 (2026-04-02)

**Agent**: claude-opus-4-6 | **Session**: N/A

### Decisions
1. **Added Measurement & Thresholds section to spec** — Concrete numeric criteria for confidence scoring (0.0-1.0 scale), iteration/cost budgets, RRF formula (k=60), and retry policy (max 2, exponential backoff). Prevents ambiguous acceptance criteria.
2. **Added Error Handling scenarios to spec** — 5 new scenarios covering specialist failure, tool failure, memory backend unavailability, approval timeout, and task timeout. Addresses missing failure paths.
3. **Added Integration scenarios to spec** — 3 new scenarios for LLMRouter backward compatibility, Pipeline Runner integration, and Job Queue agent_task entrypoint. Documents how agent layer interacts with existing components.
4. **Added PG enum migration task (1.0) to tasks.md** — Explicit task for designing all new StrEnums and their corresponding CREATE TYPE migrations before implementing ORM models. Addresses the known PG enum gotcha.
5. **Fixed naming consistency** — Replaced all "Heartbeat" references with "Scheduler"/"Proactive" across all 4 proposal documents.
6. **Added Impact section to proposal.md** — Explicit table of which existing files are modified and the risk level of each modification. No existing specs to create deltas for (this is a greenfield capability).
7. **Added Mock Boundaries table to design.md** — Documents exactly what each component mocks in tests, enabling isolated testing at well-defined boundaries.
8. **Added Numeric Thresholds table to design.md** — Consolidated reference of all configurable defaults with their spec cross-references.
9. **Expanded integration test tasks** — Added 3 sub-tasks (8.1a-c) for persona-parameterized flow, error recovery flow, and approval gate flow.
10. **Fixed vague WHEN conditions** — Scenarios .10 and .15 now have precise trigger conditions instead of generic "when strategies are loaded" / "when a user interacts".

### Alternatives Considered
- Separate spec delta files for LLMRouter/Pipeline/Worker changes: rejected because no existing OpenSpec specs exist for these components — the Impact table in proposal.md is sufficient
- Hardcoded thresholds vs configurable: chose configurable with documented defaults; some internal constants (RRF k, confidence bands) are intentionally non-configurable to prevent misconfiguration

### Trade-offs
- Accepted larger spec surface area (14 new scenarios) over minimalism because measurable criteria and error paths are essential for implementation clarity
- Accepted task count increase (52→56) because the new integration tests validate critical cross-component flows that were previously untested

### Open Questions
- [ ] Should circuit breaker state for memory strategies persist across task boundaries, or reset per task?
- [ ] Should partial-success tasks be surfaced differently in the UI than fully completed tasks?

### Context
Four parallel analysis agents identified 53 raw findings (22 unique after dedup). This iteration addressed all 4 CRITICAL and 10 HIGH findings. Key gaps were: missing error/failure scenarios, no measurable acceptance criteria, incomplete naming consistency, missing impact analysis for modified components, and no explicit PG enum migration strategy.
