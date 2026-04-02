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
