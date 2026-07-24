# Design: Reconcile ingestion filtering behavior

## Planning constraints

1. Start from current canonical `IngestCommand` and capability descriptors.
2. Do not restore deleted adapter-specific CLI execution or flags.
3. Preserve already-persisted filter columns and `FILTERED_OUT` semantics.
4. Decide unsupported historical promises explicitly before implementation.

## Required planning decisions

- Whether source-level controls belong in resolved source configuration,
  normalized command input, or both, including precedence.
- Whether the language gate remains supported; if retained, define detection,
  unknown-language fail-open behavior, configuration, and short-circuit tests.
  If retired, remove the promise consistently from current contracts and docs.
- Whether dry-run persists a would-be decision and how it affects operation
  results and summarization.
- Which rows rerun may revisit and which completed statuses are immutable.
- Which filter fields and explanations are safe and useful in public
  projections.
- Whether reviewer feedback remains in scope, and the exact event owner.
- The stable span name and non-sensitive attributes.

## Verification boundary

The refined plan must include contract and behavior tests for every retained
surface. It may deliberately remove a historical promise, but proposal, main
spec, runtime, docs, and tests must agree.
