# OpenSpec inventory reconciliation evidence

**Change**: `reconcile-openspec-inventory`
**Date**: 2026-07-23
**Status**: Plan-review evidence collected; implementation verification pending

## Initial disposition table

| Initial entry | Initial state | RI-03 disposition | Resulting action |
|---|---:|---|---|
| `repair-canonical-cli-transport-behavior` | 18/18 | archive complete | Manually merge evidenced CLI/test requirements, then archive. |
| `restore-railway-frontend-deployment` | 19/19 | archive complete | Sync its new frontend release capability, then archive. |
| `add-ingestion-filtering-prioritization` | 38/38, overclaimed | archive historical foundation | Publish only evidenced behavior and create `reconcile-ingestion-filtering-runtime-contract`. |
| `db-source-overrides` | 23/23, evidence gaps | archive historical foundation | Publish evidenced backend/CLI behavior and create `closeout-db-source-overrides-evidence`. |
| `add-huggingface-papers-source` | 11/15 stale | archive complete foundation | Reconcile all implemented integrations, publish current durable behavior, archive. |
| `llm-router-evaluation` | 0/34 stale | archive implemented foundation | Publish actual primitives/surfaces and create `operationalize-llm-evaluation-routing`. |
| `use-paradedb-railway-langfuse-default` | 0/17 stale | archive implemented foundation | Publish current profile/image behavior and create `verify-production-paradedb-langfuse`. |
| `unify-mcp-ingest-envelope` | 0/23 obsolete | archive superseded | Skip spec sync; durable `OperationHandle` is authoritative. |
| `feynman-inspired-features` | analysis only | archive analysis | Retain `analysis.md`; skip validation and spec sync. |
| `add-cross-surface-release-smoke-tests` | scaffold, invalid | retain actionable | Add a minimal RI-04 delta; expand in RI-04. |
| `real-ingestion-test-tiers-in-ci` | scaffold, invalid | retain actionable | Add a minimal RI-05 delta; expand in RI-05. |
| `establish-cli-gen-eval-coverage` | scaffold, invalid | retain actionable | Add a minimal RI-06 delta; expand in RI-06. |
| `persisted-ingestion-run-results` | scaffold, invalid | retain actionable | Add a minimal RI-07 delta; expand in RI-07. |
| `stuck-content-sweeper-and-requeue-cli` | scaffold, invalid | retain actionable | Add a minimal RI-08 delta; expand in RI-08. |
| `production-telemetry-and-out-of-band-alerting` | scaffold, invalid | retain actionable | Add a minimal RI-09 delta; expand in RI-09. |
| `add-obsidian-vault-ingest` | 0/34, valid | retain actionable | Refine and implement in RI-10. |
| `add-api-versioning` | 0/42, valid | retain approved decision | Decide concrete compatibility boundary in RI-11; no RI-03 implementation. |
| `reconcile-openspec-inventory` | active RI-03 | self-archive after validation | Sync inventory governance and archive last. |

## Preliminary implementation evidence

- Filtering/source override audit: 99 focused non-PostgreSQL tests passed and
  Alembic has one head. PostgreSQL API and web component evidence remains
  environment- or implementation-limited as recorded in the successors.
- HuggingFace audit: 73 focused source, registry, contract, and integration
  tests passed; production capabilities expose the source across CLI, HTTP,
  MCP, and frontend.
- LLM evaluation audit: 118 focused non-database tests passed. Database tests
  were unavailable locally; more importantly, static evidence proves the
  classifier is not injected into production routing and DB overrides are not
  consumed.
- ParadeDB/Langfuse/MCP audit: 86 tests passed, nine profiles validated, and
  generated workflow contracts were current. GHCR workflow
  `29773046486` published public amd64 digest
  `sha256:ce9d3233b69fd559fc88f45a44bc8f2bd3d1a174e9524390b0855331dc01296d`
  as `ghcr.io/jankneumann/aca-postgres:17-railway`; production database,
  BM25 strategy, and Langfuse trace delivery remain unproven.
- RI-01 and RI-02 already retain passing validation reports, exact test counts,
  and RI-02 exact-SHA production evidence. RI-03 revalidates their focused local
  gates before archival.

## Specification synchronization matrix

| Source change | Durable capability | Evidenced requirements retained | Unsupported/obsolete claims omitted | Merge and archive mode |
|---|---|---|---|---|
| `add-ingestion-filtering-prioritization` | `ingestion-filtering` | Global hook/disable behavior, tiered evaluation primitives, non-dry-run decision persistence | Per-source override plumbing, persisted dry-run decisions, canonical ingest flags, full rerun/explain trace, response projection, feedback wiring, specified span attributes | Create/reduce main spec manually; diff review; archive `--skip-specs`. |
| `db-source-overrides` | `source-configuration` | Validated DB storage, natural keys, YAML/DB precedence and fail-open merge, authenticated runtime CRUD/PATCH shape, CLI management | Top-level request `type` mismatch, unproven component/browser behavior, missing setup/migration evidence, stale enable/disable design | Merge evidenced requirements into existing main spec without replacing newer scenarios; archive `--skip-specs`. |
| `add-huggingface-papers-source` | `huggingface-papers-ingestion` | Discovery, extraction, dedup, source descriptor, typed command, durable submission, capabilities, capability-driven frontend | Integer orchestrator result, direct CLI fallback, immediate MCP result, retired contents-ingest route, static source list | Write a modern truthful main spec; archive legacy delta with `--skip-specs`. |
| `llm-router-evaluation` | `llm-router-evaluation` | ORM/migration foundation, YAML/env config primitives, optional step hook, classifier primitives, criteria/judge/consensus/calibrator, actually implemented service/CLI/API structures | Production classifier injection, DB-effective precedence, paired dataset generation, bootstrap-free training loop, human weighting, distinct configured judges, promised endpoints, durable failures, real cost savings | Write a reduced foundation main spec; archive legacy delta with `--skip-specs`. |
| `use-paradedb-railway-langfuse-default` | `profile-configuration` | Langfuse defaults/profile inheritance and public canonical image publication/configuration | Unreachable-endpoint warning, stale Braintrust scenario, wrong image names/versions, production database/search/trace proof | Manually merge scenarios into existing main spec, preserving unrelated/newer requirements; archive `--skip-specs`. |
| `unify-mcp-ingest-envelope` | none | None; current durable MCP specs already govern | Entire synchronous `IngestionResponse` target | Archive superseded with `--skip-specs`. |
| `repair-canonical-cli-transport-behavior` | `cli-interface`, `test-infrastructure` | Strict output/capability behavior and hermetic transport/warning hygiene | None, but modified requirements must not replace newer main scenarios | Manual merge plus diff review; archive `--skip-specs`. |
| `restore-railway-frontend-deployment` | `frontend-release-delivery` | All three new, production-proven requirements | None | Normal sync/archive after preview and diff review. |
| `feynman-inspired-features` | none | None | Analysis is not a change delta | Archive with validation/spec sync skipped. |

## External evidence boundary

RI-03 performs no production mutation. Missing runtime-contract closeout,
GHCR/Railway, Langfuse, and deployable LLM-routing proof is retained in focused
follow-up changes with explicit authority, rollback, and sanitized-evidence
requirements where external state is involved.
