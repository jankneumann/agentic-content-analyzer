# Session Log: llm-router-evaluation

---

## Phase: Plan Creation (2026-04-02)

**Agent**: claude-opus-4-6 | **Session**: plan-feature

### Decisions
1. **Approach B selected** — Custom router with domain-trained LLM-as-judge over RouteLLM library adoption
2. **Binary pass/fail over Likert scales** — Forces judges to commit to concrete deficiencies

### Context
Created initial proposal, design (7 decisions), spec (19 scenarios), and tasks (40 items across 8 phases). Committed and pushed to openspec/llm-router-evaluation branch.

---

## Phase: Plan Iteration 1 (2026-04-02)

**Agent**: claude-opus-4-6 | **Session**: iterate-on-plan

### Decisions
1. **Standardized on binary evaluation throughout** — Eliminated all residual Likert-scale language from proposal, spec, and tasks
2. **Added position bias mitigation** — A/B randomization in judge prompts is essential for unbiased evaluation data
3. **Defined tie-breaking rules** — 2-judge split and 3-judge 3-way split both resolve to `tie` (conservative)
4. **Merged coupled tasks** — Tasks modifying same files merged to prevent churn (40→34 tasks)
5. **Added parallel execution streams** — Phases 1-3 and Phase 4 run independently, merge at Phase 5

### Alternatives Considered
- Numeric scoring aggregation for calibration: rejected because it requires arbitrary conversion from binary verdicts to numbers
- Win-or-tie rate metric chosen for calibration: cleaner mapping from binary preferences to a percentage threshold

### Trade-offs
- Accepted fewer but larger tasks (34 vs 40) over more granular tasks to reduce file-overlap merge conflict risk
- Accepted `tie` as default for judge disagreement over random selection — conservative but may inflate tie counts

### Open Questions
- [ ] Should `_default` fallback dimensions be configurable per-organization or fixed?
- [ ] Should judge prompt templates be cached or regenerated each evaluation?

### Context
4-way parallel analysis (completeness, clarity, feasibility, testability) identified 16 findings at medium+ criticality. Root cause: proposal written before binary pass/fail decision was finalized, leaving stale numeric scoring language. All 16 findings addressed. Added 7 new spec scenarios (10a, 15a-g), 3 new design decisions (D5a-c), and restructured tasks with explicit parallel streams.
