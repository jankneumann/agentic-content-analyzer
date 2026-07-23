# Design: Evidence-backed OpenSpec inventory reconciliation

## Context

OpenSpec task counts are not implementation truth. Several active changes have
stale unchecked tasks despite landed code and passing validation reports, while
other entries describe pre-cutover synchronous interfaces that now contradict
the canonical durable operation contract. Repository evidence also cannot prove
that a named container image is pullable, deployed on Railway, or that configured
production credentials can reach every selected model.

## Decisions

### D1. Classify by current evidence, not task count alone

Each entry receives one disposition: archive-complete, archive-superseded,
archive-analysis, retain-actionable, or extract-follow-up-and-archive. The
reconciliation report cites implementation files, focused tests, main/delta
spec treatment, and external evidence or its absence.

### D2. Preserve implemented specifications before archival

Modern parseable deltas are synchronized through the normal OpenSpec archive
path. Older scenario-only specifications are converted into valid durable main
specifications that describe current behavior before the historical change is
moved with spec syncing disabled. Superseded changes do not modify main specs.

### D3. Separate foundation completion from genuine residual scope

The broad filtering, source-override, LLM routing/evaluation, and
ParadeDB/Langfuse changes are archived after their landed foundations are
verified and accurately specified. Unsupported filtering promises,
source-override closeout evidence, the missing deployable evaluation/routing
loop, and production ParadeDB/Langfuse proof become four bounded follow-ups.
This prevents real gaps from being erased while avoiding duplicate foundation
implementation.

### D4. Treat canonical durable operations as the governing MCP contract

`unify-mcp-ingest-envelope` is not partially implemented. Its synchronous
`IngestionResponse` target was replaced by typed `IngestCommand` submission,
`OperationHandle`, and shared operation observation. Archival records
supersession; it does not sync the obsolete shape.

### D5. Keep approved roadmap work active

Changes mapped to later approved roadmap items remain active even when their
plans need refinement. `add-api-versioning` remains for RI-11, where a concrete
incompatible contract will decide whether it is refined or archived.
Analysis-only idea collections are historical discovery material, not active
changes.

### D6. Make the resulting inventory executable and checked

A final-state snapshot under this change's `evidence/` directory enumerates the
exact active set and every RI-03 disposition. A reusable validator accepts the
snapshot path explicitly, compares it with the filesystem, requires successor
and archive destinations to exist, and rejects completed or superseded source
changes that remain active. It is an RI-03 completion proof, not a permanent
registry that future lifecycle transitions must update.

Before self-archive, the validator has a transitional mode that permits only
`reconcile-openspec-inventory` beyond the final active set. After self-archive,
the snapshot moves with the change and final mode requires the exact dated
archive destination plus the exact final active set.

Retained roadmap scaffolds that lack delta specifications receive one bounded
acceptance-aligned requirement each. This is lifecycle normalization, not
implementation planning; the owning later roadmap item will expand design,
tasks, contracts, and packages before code changes.

## Failure and rollback

- A failed implementation test blocks archival of the associated completed
  change.
- A main-spec conflict is resolved explicitly; archival never overwrites a
  newer requirement without review.
- A missing external proof is extracted, never represented as completed.
- All moves are committed in one item branch, so a failed integration can be
  reverted without rewriting archive history.

## Validation

- Focused tests for filtering, source overrides, HuggingFace, LLM evaluation,
  profile configuration, MCP durable-operation parity, and completed roadmap
  items.
- Strict OpenSpec validation for the reconciliation change, every retained
  active change, all focused follow-ups, and each touched main spec. Unrelated
  pre-existing main-spec failures are reported but are not silently expanded
  into RI-03 scope.
- Inventory validator tests and a clean validator run.
- Work-package schema, scope, lock, and diff checks.
