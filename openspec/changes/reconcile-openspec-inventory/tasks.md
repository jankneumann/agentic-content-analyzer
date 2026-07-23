# Tasks: Reconcile the OpenSpec inventory

## 1. Evidence and approved plan

- [x] 1.1 Inventory every active entry and record its implementation,
  specification, task, and external-evidence state.
- [x] 1.2 Assign archive, retain, refine, and extracted-follow-up dispositions
  without repeating runtime implementation.
- [x] 1.3 Resolve independent plan-review findings; validate the change, delta
  spec, and work-package graph.

## 2. Verification

- [ ] 2.1 Verify the implemented filtering foundation and identify unsupported
  runtime, CLI, projection, feedback, and observability claims.
- [ ] 2.2 Verify the implemented source-override foundation and identify
  request-contract, UI, docs, design, and migration-evidence gaps.
- [ ] 2.3 Verify HuggingFace extraction plus canonical registry, contract, MCP,
  worker, capability, and frontend integration; reconcile its stale tasks.
- [ ] 2.4 Verify the implemented LLM evaluation/routing foundation and enumerate
  the missing deployable evaluation-to-routing loop.
- [ ] 2.5 Verify Langfuse/profile behavior and the public canonical ParadeDB
  image; separate missing documentation and production proof.
- [ ] 2.6 Verify canonical MCP ingestion returns durable operation handles and
  that `unify-mcp-ingest-envelope` is superseded.
- [ ] 2.7 Re-run or revalidate the recorded focused gates for completed RI-01
  and RI-02.
- [ ] 2.8 Publish the per-change synchronization matrix naming exact retained
  requirements, omitted claims, merge strategy, archive mode, and tests.

## 3. Actionable successors and retained changes

- [ ] 3.1 Create `reconcile-ingestion-filtering-runtime-contract` for the
  canonical CLI, overrides, dry-run, rerun, projection, feedback, and
  observability decisions.
- [ ] 3.2 Create `closeout-db-source-overrides-evidence` for request-contract
  alignment, component/browser coverage, documentation, and migration proof.
- [ ] 3.3 Create `operationalize-llm-evaluation-routing` for DB-effective
  config, classifier injection, paired datasets, calibration/enablement,
  failure/cost semantics, and truthful CLI/API/docs.
- [ ] 3.4 Create `verify-production-paradedb-langfuse` for canonical image
  identity, Railway digest/extensions/search proof, Langfuse trace correlation,
  and rollback.
- [ ] 3.5 Add minimal acceptance-aligned delta requirements to the six retained
  roadmap scaffolds that currently have no parseable delta:
  `add-cross-surface-release-smoke-tests`,
  `establish-cli-gen-eval-coverage`, `persisted-ingestion-run-results`,
  `production-telemetry-and-out-of-band-alerting`,
  `real-ingestion-test-tiers-in-ci`, and
  `stuck-content-sweeper-and-requeue-cli`.

## 4. Specification synchronization and archival

- [ ] 4.1 Manually merge only evidenced filtering, source-override,
  HuggingFace, LLM-evaluation, and profile behavior into durable main specs;
  diff-review the merge; archive each broad source with `--skip-specs`.
- [ ] 4.2 Archive `unify-mcp-ingest-envelope` as superseded with
  `--skip-specs`; do not repair or sync its obsolete synchronous shape.
- [ ] 4.3 Manually merge the evidenced RI-01 CLI/test requirements and archive
  it with `--skip-specs`; normally sync and archive RI-02's new frontend release
  capability after diff review.
- [ ] 4.4 Archive the analysis-only `feynman-inspired-features` entry with
  validation and spec syncing explicitly skipped, retaining `analysis.md`.
- [ ] 4.5 Correct stale MCP inventory documentation that still recommends the
  superseded flat response or completed broad proposals.

## 5. Inventory proof and completion

- [ ] 5.1 Create a final-state disposition snapshot and validator. Before
  self-archive it SHALL allow only the reconciliation change as a transient
  extra; after self-archive it SHALL require the exact final active and dated
  archive sets.
- [ ] 5.2 Validate every retained active change, all four successors, every
  touched main capability, the reconciliation change, and the package graph.
- [ ] 5.3 Record review findings, validation evidence, exact test counts,
  environment-limited checks, and the final active inventory.
- [ ] 5.4 Sync `openspec-inventory-governance`, archive this reconciliation
  change through an explicit post-validation package, and rerun the final-state
  inventory validator against the archived snapshot.
