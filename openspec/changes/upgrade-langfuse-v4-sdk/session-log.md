## Phase: Plan Iteration 1 (2026-04-17)

**Agent**: claude-opus-4-6 | **Session**: N/A

### Decisions
1. **Remove Summarizer and PodcastScriptGenerator from @observe() scope** — proposal listed them but tasks didn't include them. Kept scope to DigestCreator, ThemeAnalyzer, and orchestrator entry points to match what tasks actually implement.
2. **Add metadata sanitization task** — Langfuse SDK v4 requires `dict[str, str]` with 200-char limit; our existing metadata is arbitrary dicts. Must coerce at the provider boundary.
3. **Add duplicate span handling task** — AnthropicInstrumentor + explicit trace_llm_call() can produce duplicate generations. Need a guard.

### Alternatives Considered
- Keep Summarizer/@observe() in scope: rejected because the summarizer is an agent class, not a simple pipeline function — its tracing needs are different and should be a separate proposal
- Make metadata validation a spec requirement: rejected — it's an implementation detail, not a user-visible behavior

### Trade-offs
- Accepted narrower @observe() scope over broader coverage because the current pipeline functions are the highest-value targets, and summarizer/podcast can be added later without breaking changes

### Open Questions
- [ ] Will AnthropicInstrumentor + trace_llm_call() actually produce duplicates, or does OTel context prevent it? Needs testing.

### Context
9 findings identified across consistency, completeness, parallelizability, and testability. 7 at medium+ criticality fixed: proposal/task consistency for @observe() scope, missing failure scenarios in specs, metadata sanitization task, duplicate span task, explicit dependency notes in tasks, markdown fix.
