# Plan review findings

## Iteration 1

Independent contract, durable-model, surface, and security reviews found that
the first draft passed structural validation but did not yet make several
reliability and privacy claims enforceable.

Resolved findings:

- retained explicit `IngestionResultV1` and added strict V2 plus a union reader;
- added stable pipeline `result.ingestion_summary` schemas and strict partial
  semantics;
- restricted history to terminal operations and made unknown legacy counts
  nullable;
- replaced forgeable filter digests with size-limited HMAC-signed cursors;
- replaced guessable configured-source hashes with secret-derived public keys
  created at the configuration boundary;
- replaced arbitrary durable details with a closed numeric/boolean allowlist,
  separate omitted counts, adversarial sanitizer tests, and an aggregate
  metadata budget;
- narrowed generic operation list rows to summaries while preserving full
  exact-operation reads;
- defined finite failed-graph retention, validated settings, bounded batches,
  transactional graph rechecks, timeouts, metrics, and maintenance independent
  of optional Gemini batch work;
- added 10,000-row PostgreSQL query-plan evidence before any history index;
- split the oversized cross-surface package into pipeline, operation-summary,
  history-backend, history-CLI, measured-index, and retention packages;
- aligned package dependencies, canonical generated artifacts, integration
  test collection, and canonical spec write scopes with their task DAG.

## Accepted constraints

- Pre-change rows cannot recover source partial status that was never stored;
  they project `unknown` with nullable missing counts.
- The summary-only generic operation list is an intentional response narrowing.
  First-party clients migrate atomically; exact operation reads preserve the
  full handle contract.
- Exact content IDs remain potentially large because they are active workflow
  provenance. They occur once on an exact result and never on list/history
  pages.

## Iteration 2

Final surface and durable-model review found additional compatibility edges.
The plan now:

- emits operation summaries as a wire-compatible subset of the old strict
  handle with no new row keys;
- budgets generic operation traversal, signals truncation, and hydrates the web
  Background Tasks indicator from bounded active/recent queries;
- restricts history status filters to terminal values and bounds every scalar
  filter/projection field;
- requires a dedicated durable configured-source HMAC secret and forbids
  production authentication-secret fallback;
- links `pipeline.run` to its result schema and defines aggregate precedence for
  every lifecycle/child-outcome combination;
- adds frontend tests/type-checking to the summary-list package;
- makes null completion timestamps explicitly ineligible for graph cleanup and
  aligns interval scheduling terminology.
