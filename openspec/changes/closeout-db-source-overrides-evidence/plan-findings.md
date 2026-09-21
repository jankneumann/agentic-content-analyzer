# Plan review findings

## Iteration 1 — 2026-09-21

**Threshold:** medium  
**Baseline:** `openspec validate closeout-db-source-overrides-evidence --strict`
passed before refinement.

| Severity | Dimension | Finding | Disposition |
|---|---|---|---|
| high | consistency | The design left nested `config.type` versus a duplicate top-level `type` unresolved, although runtime, CLI, web, and tests already use the nested form. | Locked nested `config.type`; rejected archive-only duplication. |
| high | completeness | The durable content-workflows OpenAPI and generated models contain no source-management surface. | Added an explicit additive contract package and drift acceptance criteria. |
| high | security | Runtime protects reads and writes with session/admin-key authentication, while stale evidence describes GET as public and omits session auth. | Specified both credential modes, 401/403 behavior, and no-mutation assertions. |
| high | privacy | Natural-key language did not account for HMAC-derived opaque Obsidian keys or response/error redaction. | Added a public-boundary invariant and negative scenarios. |
| high | scope | Browser support omitted Readwise and Obsidian even though the backend union includes both. | User selected Readwise quick-add; Obsidian create/edit remains worker-local while existing opaque rows are manageable. |
| high | testability | Every original requirement had only a success scenario. | Added validation, authentication, unknown-key, UI failure, schema incompatibility, and fail-open/recovery scenarios. |
| medium | feasibility | No rendered React component-test harness exists; the original task assumed component tests without setup work. | Split the harness from component behavior and named dependencies/checkpoints. |
| medium | parallelism | Tasks were coarse, overlapping, untraced, and had no dependencies or file ownership. | Replaced them with R1–R5 work packages, blockers, owners, checkpoints, and a DAG. |
| medium | migration | “Verify constraints” did not identify PostgreSQL types, indexes, defaults, sentinel preservation, or what a rerun proves. | Enumerated fresh-upgrade and compatible no-op evidence and documented unsupported manual-schema recovery. |
| medium | documentation | Durable targets and exact operational content were unspecified. | Assigned architecture decisions to `docs/ARCHITECTURE.md` and the runbook to `docs/SETUP.md`; the archive is immutable. |
| medium | consistency | “Generated clients” overstated repository capability; only generated models/types exist. | Corrected terminology and required parity tests for hand-maintained transports. |
| medium | scope | Pagination risk was unaddressed for GET. | Retained the complete configuration catalog contract and deferred pagination to a measured compatibility proposal. |
| low | clarity | A stale source-merge documentation string may still describe old behavior. | Assigned correction to the architecture package only if contract tests expose it. |

A suggestion that the durable `source-configuration` spec lacks database source
override behavior was rejected after inspection: the existing spec already owns
merge, shadow, resolution, and failure semantics. This change adds missing
contract/evidence requirements rather than duplicating those behaviors.

No prototype advisory was triggered: after resolving the product-scope choice,
the remaining high findings concern explicit contracts and evidence rather than
three or more unresolved high-severity feasibility questions.

## Iteration 2 — 2026-09-21

| Severity | Dimension | Finding | Disposition |
|---|---|---|---|
| high | feasibility | GET cannot distinguish a DB-only row from a DB shadow, so the UI cannot truthfully predict delete effect. | Chose one generic “remove override; YAML may reappear” action; backend tests own the distinct outcomes. |
| high | compatibility | Current Pydantic models ignore unknown siblings, contradicting rejection scenarios. | Preserved `/api/v1` extra-ignore behavior, made nested `config.type` solely authoritative, and added no-effect tests. |
| high | consistency | “Worker-local Obsidian creation” wrongly implied trusted HTTP/CLI creation was forbidden. | Limited the prohibition to browser create/edit; trusted API/CLI config remains compatible and responses stay redacted. |
| high | feasibility | The shared migrated fixture cannot prove sentinel preservation across the source migration. | Added an isolated predecessor→source migration→head sequence and separate revision-chain assertions. |
| high | testability | An incompatible table cannot produce a production failure without a new validator. | Scoped detection to a test-local schema verifier and documented recovery; no production doctor is claimed. |
| medium | contract | GET, mutation, deletion, validation, service-error, and auth-error projections were conflated. | Named each success and legacy JSON error shape separately. |
| medium | security | Design claimed a server length bound that does not exist. | Retained only actual non-empty/no-NUL validation; no new HTTP bound is invented. |
| medium | scope | The opaque-key promise generalized beyond implemented private-source handling. | Narrowed the normative invariant to Obsidian. |
| medium | parallelism | WP3 both depended on WP1 and was counted as an independent root. | Made WP3 depend on WP1 and corrected maximum width to five in tasks/design. |
| medium | ownership | Frontend DTOs and lockfiles had ambiguous or incomplete owners. | Assigned shared DTOs to WP1, component files to WP2b, and both tracked lockfiles to WP2a. |
| medium | testability | Documentation checkpoints were prose-only. | Added exact section/topic checklists and deterministic anchor/archive checks. |

## Iteration 3 — 2026-09-21

| Severity | Dimension | Finding | Disposition |
|---|---|---|---|
| high | consistency | Durable `source-configuration` management requirements still universalized natural keys and ambiguous disabled-source resolution. | Added a `MODIFIED` delta for public management identity, opaque Obsidian keys, authentication, and management-visible/ingestion-excluded shadows. |
| high | security | Audit middleware persisted and printed raw source paths, allowing a rejected Obsidian natural locator to leak. | Assigned path normalization and persisted/failure-log redaction tests to WP1; retained the application/audit log privacy guarantee. |
| medium | testability | Log privacy had no explicit scenario or test owner. | Added an R2 log-redaction scenario and named audit implementation/tests in WP1. |
| medium | testability | “A failed mutation” did not cover separate add, toggle, and delete handlers. | Required representative recoverable failure evidence for all three handlers in component and browser suites. |
| medium | feasibility | Schema-only isolation is unsafe because the migration hard-codes `public`. | Required a uniquely named disposable database with its own `public` schema and scoped teardown. |
| medium | clarity | Proposal still said the ignored top-level discriminator was never accepted. | Clarified that it was accepted only as an unused unknown sibling. |
