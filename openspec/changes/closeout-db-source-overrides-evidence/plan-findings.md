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
