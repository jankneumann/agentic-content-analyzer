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

---

## Phase: Plan Iteration 2 (2026-04-17)

**Agent**: claude-opus-4-6 | **Session**: N/A

### Decisions
1. **Expand tasks to cover all pipeline steps** — user corrected that reducing proposal scope was wrong; the correct fix is to add tasks for Summarizer and PodcastScriptGenerator to match the full proposal intent.

### Alternatives Considered
- Reduce proposal scope to match existing tasks: rejected by user — observability should cover ALL pipeline steps

### Trade-offs
- More tasks in group 5 (7 instead of 5) but all touch separate files — parallelizability unaffected

### Open Questions
- [ ] Summarizer already has `_summarization_span()` OTel helper — should `@observe()` replace it or complement it? (Decision: complement — helper traces per-item within loops, `@observe()` traces the method)

### Context
User feedback: "langfuse observability should cover all pipeline steps including summarizer and script/podcast generator". Added tasks 5.1 (Summarizer methods), 5.4 (PodcastScriptGenerator.generate_script), renumbered 5.3-5.7. Updated proposal and spec to reflect full pipeline coverage.

---

## Phase: Plan Iteration 3 (2026-04-17)

**Agent**: claude-opus-4-6 | **Session**: N/A

### Decisions
1. **Unify raw OTel spans with @observe()** — searched codebase for all `get_tracer()`/`start_as_current_span()` usage outside the telemetry module. Found 3 categories: pipeline tracing (unify), agent metrics (leave), infrastructure trace-ID extraction (leave).
2. **Remove `_summarization_span` and `_get_tracer`** from summarizer.py — `@observe()` replaces both, with `update_current_observation(metadata=...)` for custom per-item attributes.
3. **Replace pipeline_commands.py spans but keep metrics** — `_pipeline_stage_span` mixes OTel spans with metrics counters. Replace span creation with `@observe()`, keep `record_pipeline_stage_*()` metric calls.
4. **Leave agent_metrics.py trace helpers** — 4 context managers defined but never called from outside the module. Dead code, separate cleanup scope.
5. **Leave error_handler/auth_routes/telemetry.py** — these read global OTel context for HTTP response correlation, not LLM tracing.

### Alternatives Considered
- Unify agent_metrics traces too: rejected — out of scope (dead code, would expand proposal to cover conductor/specialist functions)
- Keep _summarization_span alongside @observe(): rejected — creates disconnected parallel trace trees on different TracerProviders

### Trade-offs
- Removing `_summarization_span` means per-item attributes need explicit `update_current_observation()` calls instead of automatic span attributes — slightly more verbose but properly nested in Langfuse

### Open Questions
- None new

### Context
Codebase audit found raw OTel tracing in 3 additional locations beyond summarizer.py. Added task 5.6 to clean up pipeline_commands.py spans. Updated proposal Impact and spec with removal scenarios. Total task count now 8 in group 5.
