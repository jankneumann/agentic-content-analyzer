# Change: Reconcile the OpenSpec inventory

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `reconcile-openspec-inventory`
> Effort: M
> Priority: 3

## Why

The active OpenSpec directory mixes executable proposals with completed work,
superseded designs, stale task state, and an analysis-only idea inventory. This
creates a material risk that agents repeat already-landed implementation or
restore obsolete synchronous workflow behavior.

The repository now has a canonical durable-operation architecture. Planning
state must reflect that implementation reality while retaining explicit,
actionable follow-ups for the external production checks that repository tests
cannot prove.

## What Changes

- Verify the implemented filtering and database-source-override foundations,
  reconcile overclaimed task/spec state, archive the broad historical changes,
  and retain their genuine runtime/contract gaps as bounded closeout changes.
- Reconcile stale tasks for HuggingFace ingestion and LLM router evaluation
  against current implementation, sync their implemented specifications, and
  archive the completed foundations.
- Reconcile the implemented Langfuse/profile configuration separately from the
  unresolved ParadeDB image-name and Railway deployment proof.
- Archive `unify-mcp-ingest-envelope` as superseded by canonical
  `OperationHandle` submission and observation.
- Archive completed RI-01 and RI-02 changes so they do not remain active after
  roadmap integration.
- Remove the analysis-only `feynman-inspired-features` directory from the
  executable inventory without promoting its broad idea list into a feature.
- Create focused, schema-valid changes for filtering contract reconciliation,
  source-override evidence closeout, LLM evaluation/routing operationalization,
  and ParadeDB/Langfuse production proof.
- Retain `add-api-versioning` for its approved RI-11 compatibility decision;
  no speculative implementation begins in this item.
- Add bounded delta requirements to retained roadmap scaffolds that currently
  lack them, so every active entry passes strict validation before its later
  item expands the plan.

## Capabilities

### New Capability

- `openspec-inventory-governance`: Evidence-backed disposition, traceable gap
  extraction, and an actionable-only active change inventory.

### Modified Capabilities

- Implemented delta specifications from archived changes are synchronized into
  their durable main specifications where applicable.

## Impact

- OpenSpec planning/specification artifacts and reusable inventory-validation
  tooling only; no application runtime behavior, database schema, public API,
  or deployment is changed.
- Historical change evidence is retained under
  `openspec/changes/archive/2026-07-23-*`.
- Four focused follow-up proposals retain genuine gaps without reopening
  completed foundation code.

## Acceptance Outcomes

- `add-ingestion-filtering-prioritization` and `db-source-overrides` are
  evidence-reconciled and archived without synchronizing unsupported claims.
- `add-huggingface-papers-source`, `llm-router-evaluation`, and
  `use-paradedb-railway-langfuse-default` are reconciled against implementation
  and external evidence.
- `unify-mcp-ingest-envelope` is archived as superseded by canonical durable
  operations.
- Unresolved filtering, source-override, image/deployment, and model-routing
  operationalization gaps are represented by focused schema-valid changes.
- Completed roadmap changes and analysis-only entries no longer pollute the
  active inventory.
- Every remaining active entry is actionable and schema-valid for its current
  lifecycle stage.
