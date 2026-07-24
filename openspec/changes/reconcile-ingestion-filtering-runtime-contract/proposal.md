# Change: Reconcile the ingestion filtering runtime contract

## Why

The ingestion filtering foundation is implemented, but its historical change
overstates current canonical behavior. Per-source overrides are not passed to
the hook, the historical language gate is absent, dry-run persistence
contradicts the old spec, canonical ingestion commands do not expose the old
flags, rerun/explain and content projection are partial, feedback is not wired,
and observability attributes differ.

These are real product/contract decisions. They must be resolved against the
durable `IngestCommand` and capability model rather than hidden by archiving or
fixed by restoring pre-cutover CLI behavior.

## Source and completed scope

- Extracted from archived `add-ingestion-filtering-prioritization`.
- Completed and excluded: filter models/migration, global configuration,
  tier-evaluation primitives, persisted non-dry-run decisions, filter hook, and
  basic filter commands.
- This change SHALL NOT introduce direct adapter execution or transport-only
  filtering options.

## What Changes

- Decide and specify how global, persona, source, and per-command filtering
  controls compose through the canonical source registry and typed commands.
- Decide whether language filtering remains a supported heuristic; implement
  its detector, fail-open semantics, and tests if retained, or explicitly
  retire it from configuration, documentation, and contracts.
- Align dry-run, rerun, explain, list projection, feedback, and observability
  promises with one implemented contract.
- Add focused regression evidence across workflow, CLI, HTTP, MCP, and
  capability-driven frontend surfaces where the retained behavior is exposed.

## Capability

- `ingestion-filter-runtime-contract`

## Impact

Potential changes to filtering configuration, command contracts, content
projection, CLI/API behavior, tests, and documentation. The durable operation
submission boundary remains authoritative.
