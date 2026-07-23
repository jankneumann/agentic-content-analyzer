# OpenSpec inventory reconciliation evidence

**Change**: `reconcile-openspec-inventory`
**Date**: 2026-07-23
**Status**: Complete; governance synced and final state validated

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

- Filtering/source override audit: 68 focused tests passed and Alembic has one
  head. PostgreSQL production migration and real web component evidence remain
  implementation- or environment-limited as recorded in the successors.
- HuggingFace audit: 73 focused source, registry, contract, and integration
  tests passed; production capabilities expose the source across CLI, HTTP,
  MCP, and frontend.
- LLM evaluation audit: 127 focused tests passed and two were skipped. Static
  evidence proves the classifier is not injected into production routing and
  DB overrides are not consumed.
- ParadeDB/Langfuse/MCP audit: 86 tests passed, nine profiles validated, and
  generated workflow contracts were current. GHCR workflow
  `29773046486` published public amd64 digest
  `sha256:ce9d3233b69fd559fc88f45a44bc8f2bd3d1a174e9524390b0855331dc01296d`
  as `ghcr.io/jankneumann/aca-postgres:17-railway`; production database,
  BM25 strategy, and Langfuse trace delivery remain unproven.
- RI-01 and RI-02 already retain passing validation reports, exact test counts,
  and RI-02 exact-SHA production evidence. Their combined focused local
  revalidation passed 426 tests with one skip and two pre-existing warnings.

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
| `restore-railway-frontend-deployment` | `frontend-release-delivery` | All three new, production-proven requirements | None | Create the reviewed main capability manually, then archive `--skip-specs` to avoid a duplicate merge. |
| `feynman-inspired-features` | none | None | Analysis is not a change delta | Archive with validation/spec sync skipped. |

## External evidence boundary

RI-03 performs no production mutation. Missing runtime-contract closeout,
GHCR/Railway, Langfuse, and deployable LLM-routing proof is retained in focused
follow-up changes with explicit authority, rollback, and sanitized-evidence
requirements where external state is involved.

## Reconciled inventory

- Transitional active set: 13 entries, consisting of 12 exact retained or
  successor changes plus `reconcile-openspec-inventory`.
- Final active set: 12 entries after self-archive, enumerated in
  `inventory-dispositions.yaml`.
- Historical archive set: nine dated entries created on 2026-07-23. The final
  validator additionally requires
  `2026-07-23-reconcile-openspec-inventory`.
- Every broad implemented foundation was archived only after its evidenced
  requirements were manually merged into durable main specs. Unsupported claims
  remain actionable in four focused successors.
- `openspec archive` emitted only network errors while flushing optional
  PostHog telemetry; each local archive operation completed successfully.

The transition-state inventory validator and its seven tests pass.
`openspec-inventory-governance` was then synced, the reconciliation change was
self-archived, and final-state validation passed against this dated snapshot.

## Validation results

- Strict active-change validation: 13/13 passed.
- Strict touched-main-spec validation: 8/8 passed (`ingestion-filtering`,
  `source-configuration`, `huggingface-papers-ingestion`,
  `llm-router-evaluation`, `profile-configuration`, `cli-interface`,
  `test-infrastructure`, and `frontend-release-delivery`).
- Repository-wide strict main-spec baseline: 52/60 passed. The eight failures
  are untouched legacy specs missing the modern `## Purpose` section:
  `agent-db-integration`, `agentic-analysis`, `content-ingestion`,
  `content-references`, `graph-provider`, `openbao-secrets`,
  `specialist-tools`, and `validate-api-contracts`.
- Work-package schema, dependency references, acyclic ordering, lock overlap,
  scope overlap, and contract presence all passed. The execution graph is a
  deliberate six-package sequence ending in self-archive.
- Inventory validator tests: 7/7 passed, including rejection of an unexpected
  active entry, missing successor, missing self-archive, unexpected archive on
  the reconciliation date, and incomplete disposition coverage.
- Ruff, mypy, JSON parsing, and `git diff --check` passed for the new validator,
  its tests, and documentation updates.
- Independent implementation and security reviewers returned clean sign-off
  after all rework. Security review used the embedded OWASP checklist because
  the skill's deeper checklist file was absent.
- GitHub issue `#471` tracks normalization of the eight unrelated legacy main
  specs so the repository-wide strict baseline can become fully green without
  expanding RI-03 scope.
- Post-archive validation: exact 12-entry active set, exact ten-entry
  2026-07-23 archive set, 12/12 strict active changes, and strict-valid
  `openspec-inventory-governance`.
