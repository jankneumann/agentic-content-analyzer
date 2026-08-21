# Tasks: Cross-harness session flow display

## Phase 0 — Spike (prove the fold)

- [ ] Run `collect-transcripts` normalize on one real Claude Code session
  and one Codex session; confirm `docs/transcripts/` output shape.
- [ ] Prototype the TypeScript fold over a captured session; verify graph
  topology (agents, subagents via spawn linkage, tool pairing) and the
  shuffled-order equality property.

## Phase 1 — Unify the capture substrate

- [ ] Add `parent_session_id`, `spawned_by_tool_use_id`, `agent_label` to
  `NormalizedEvent`; bump adapter schema versions; regenerate
  `references/event-schema.md`.
- [ ] Rewrite `langfuse/scripts/langfuse_hook.py` to parse via
  `collect-transcripts/scripts/adapters/claude_code_cli.py`; delete
  `group_into_turns()`; keep incremental cursor state and sanitizer.
- [ ] Reconcile self-hosted Langfuse host defaults (`:3050` vs `:3100`)
  across hook, profile, and docs.

## Phase 2 — Capture paths live

- [ ] Register Stop and SubagentStop hooks via `install_stop_hook.py`
  against the verified tracked layout; confirm silent no-op without
  `LANGFUSE_ENABLED`.
- [ ] Add the batch Langfuse uploader to `collect-transcripts` (same
  observation vocabulary: `agent` turn, `tool` child, `session_id`,
  harness tag), opt-in flag, `--dry-run` default.
- [ ] Round-trip test: hook-emitted session fetched from Langfuse folds
  to the same topology as its transcript.

## Phase 3 — Flow API

- [ ] `GET /api/v1/flows/sessions` and
  `GET /api/v1/flows/sessions/{id}/events` — transcript + Langfuse
  sources, transcript preferred, fail-soft `source_warnings`,
  cursor pagination with absent-param serialization.
- [ ] Langfuse observation → fact reverse mapping with unit coverage.
- [ ] Update generated API contracts.

## Phase 4 — Frontend

- [ ] `web/src/lib/flow/fold.ts` with the shuffled-order property test.
- [ ] `flows` route (route file, `routeTree.gen.ts`, `navigation.ts`),
  view switcher, force-graph view, scrubber timeline, live-follow via
  polling query.
- [ ] Playwright coverage: replay a fixture session, seek, assert node
  states (strict-mode-safe locators).

## Phase 5 — Validation and docs

- [ ] `openspec validate add-cross-harness-flow-display`; sync delta
  specs.
- [ ] Document the capability (docs index entry, harness coverage tiers,
  cloud-container Langfuse-only caveat).
