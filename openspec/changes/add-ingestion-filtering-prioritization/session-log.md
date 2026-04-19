# Session Log — add-ingestion-filtering-prioritization

---

## Phase: Plan (2026-04-19)

**Agent**: claude-code (Opus 4.7) | **Session**: N/A

### Decisions

1. **Tier: coordinated** — Coordinator at https://coord.rotkohl.ai is reachable with all capabilities (lock, queue, discover, memory, handoff). Picked coordinated for eventual parallel implementation of the adapter-agnostic filter.
2. **Approach A — synchronous filter service in the orchestrator** — Selected at Gate 1 over async pgqueuer worker (B) and single-pass LLM (C). Reuses `EmbeddingProvider`, `LLMProviderRouter`, `ConfigRegistry`, and `@observe()` with no new infrastructure.
3. **Post-ingest, pre-summarize stage** — Keeps metadata available, preserves audit trail, is the cheapest-to-add insertion point that still blocks expensive summarization.
4. **Three-tier evaluation: heuristic → embedding → LLM** — Heuristic is free, embedding is ~10–50ms, LLM only fires for items in a configurable borderline band. Mirrors the cost-savings goal better than second-brain-ingest's single-pass LLM design.
5. **Persona-extended filter profile** — `filter_profile:` block added to `settings/personas/*.yaml`; profile vectors cached in a new `persona_filter_profiles` table keyed by `(persona_id, provider, model)`.
6. **New `FILTERED_OUT` status, no physical deletion** — Enables reversible threshold tuning via `aca filter rerun`; standalone `ALTER TYPE ADD VALUE` migration per CLAUDE.md gotcha #2.
7. **Two-table auxiliary schema** — `persona_filter_profiles` (profile cache) and `filter_feedback_events` (fire-and-forget v1 feedback log for a future learning change).
8. **Deferred from v1** — Learned user model, BM25 lexical scoring (handled by pending use-paradedb change), multi-persona fusion, and cross-source dedup beyond exact hash.

### Alternatives Considered

- **Approach B — async pgqueuer filter worker**: rejected for v1. Adds a queue hop and state machine without justification at current ingest volumes. Service interface is designed so the same call can move to a worker later without changing callers.
- **Approach C — single-pass LLM filter**: rejected. Pays an LLM call per item, defeating the cost-at-scale goal.
- **Pre-persist filtering**: rejected in discovery. Would lose audit trail, complicate dedup, and make threshold tuning impossible after the fact.
- **`filters.yaml` as a standalone domain**: rejected in favor of extending existing personas, which already carry `relevance_weighting` and other user-preference fields.
- **Physical deletion of filtered items**: rejected. Auditability and threshold reversibility outweigh storage cost; a separate retention job can prune later.

### Trade-offs

- **Synchronous filter latency vs operational simplicity** — Accepted ~10–50ms per ingested item in the common case because the service can be swapped behind a queue later if needed, and current ingest volumes make the synchronous path safe.
- **Cache invalidation cost vs re-encode cost** — Persona profile vectors are cached; invalidation is by hash of `interest_description`. Small complexity cost, big latency win on every filter call.
- **Fail-open vs strict on embedding/LLM errors** — Default is fail-open (keep with `priority_bucket=low`, reason records the error). Config flag `filtering.strict` can flip to fail-closed for operators who prefer it.

### Open Questions

- [ ] Should filter decisions be surfaced in the digest review UI in v1, or wait for the learned-calibration follow-up? (Design currently assumes backend-only in v1.)
- [ ] Does the ParadeDB arrival (pending `use-paradedb-railway-langfuse-default`) change the embedding tier design? Not blocking — BM25 would be an additive signal, not a replacement.

### Context

Planning goal: reduce downstream LLM cost and digest noise as ingestion sources grow (currently 13+ adapters). Decided on a three-tier, persona-aware, post-persist synchronous filter with a reversible `FILTERED_OUT` status. Seven work packages were defined with a clean DAG: `wp-contracts` → `wp-data-model` → `wp-filter-service` → (`wp-orchestrator-integration` ∥ `wp-cli-api` ∥ `wp-feedback`) → `wp-integration`.

**Note on coordinator claims**: The local coordination-bridge helper only exposes `detect`, so planning-intent locks (`ttl_minutes=0`) were not registered programmatically. All lock keys are declared durably in `work-packages.yaml` and will be acquired at implementation time by `/implement-feature`.
