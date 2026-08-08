# ADR-0002: Defer a second API URL version until an incompatible consumer boundary exists

## Status

ACCEPTED — decided 2026-08-07 as roadmap item `ri-11`
(`add-api-versioning`). The speculative change is archived without syncing its
delta spec.

## Context

The API already uses the `/api/v1` URL namespace, but the active
`add-api-versioning` plan proposed 42 implementation tasks before identifying a
`v2` contract. Those tasks would add global version configuration and middleware,
move existing routers, create sunset behavior, and prepare a second router tree.
Its only stated trigger is that breaking changes are expected eventually.

The compatibility boundary is materially stronger than when that proposal was
written:

- Its motivating `/api/v1/newsletters` example is no longer deprecated-but-live;
  that router has been removed through the coordinated content-model migration.
- The durable workflow OpenAPI document is the source for generated Python and
  TypeScript models. CI rejects schema or generated-file drift.
- The CLI and HTTP-mode MCP tools share `WorkflowApiClient`; the frontend consumes
  the generated TypeScript contract; cross-interface tests compare application,
  CLI, HTTP, and MCP behavior.
- Release smoke checks a deployed frontend/API revision pair, exercises real CLI
  discovery, scans browser assets and requests for retired routes, and keeps
  production mutation-free.
- CLI gen-eval declares every command group, evaluates discovery and validation,
  and separately guards staging-only submission and operation-control scenarios.
- Retired workflow mutations have an executable denial baseline. The remaining
  legacy read/error shapes are intentionally scoped rather than accidentally
  reinterpreted by global middleware.

The workflow OpenAPI document currently has `info.version: 2.0.0` while remaining
mounted under `/api/v1`. That was an in-place breaking replacement, not evidence
that a `/api/v2` compatibility window exists.
OpenAPI document versions, event `schema_version` fields, queue protocol versions,
and URL major versions serve different purposes and must not be coupled.

Not every supported consumer is repository-controlled. A manually installed iOS
Shortcut is an independently updated HTTP client: repository evidence still names
the retired `/api/v1/content/save-url` route in its durable spec and user guide,
while the current installation template points to `/api/v1/ingestions`.
`agentic-assistant` is also an external HTTP/OpenAPI and MCP consumer—GitHub issue
#421 records a live dependency on ACA OpenAPI operation IDs—and its historical
lockstep migration evidence is incomplete. These facts make future consumer
inventory and old-client tests mandatory; they do not identify a concrete
incompatible successor contract today. Follow-up issue #492 owns that inventory and
the stale mobile-capture contract.

For a single-developer service whose primary backend, frontend, CLI, generated
models, and release gate are changed together, supporting two live URL contracts
without that successor would impose more migration and testing cost than it avoids.
The proposed router move is stale as well: it names only content, summary, and
digest modules, while the application now composes 45 routers across more than 40
route modules. Applying that partial reorganization would create a mixed layout
without creating a compatibility boundary.

## Decision

Do not implement the existing 42-task proposal. Keep `/api/v1` as the supported URL
boundary and archive `add-api-versioning` without syncing its speculative delta
spec into the durable capability inventory.

Continue evolving `/api/v1` only where executable evidence proves compatibility
with the oldest supported affected client, or where every affected consumer has an
explicitly verified coordinated migration. New endpoints and optional request
fields with compatible defaults may be additive. Optional response fields are not
presumed compatible: canonical Python models forbid unknown fields, so an older
`WorkflowApiClient` can reject them. Contract generation, cross-interface tests,
release smoke, retired-route denial, and CLI gen-eval remain the workflow-surface
controls.

A new URL major becomes justified when both conditions are true:

1. A named change is incompatible at the HTTP contract boundary—for example it
   removes or renames a field or endpoint, narrows accepted input, changes a field
   type or stable meaning, changes authentication semantics, or changes a response
   or error shape that a supported consumer relies on.
2. An affected supported consumer cannot safely migrate in the same coordinated
   release or requires a measured overlap window. Independently installed or
   external consumers are assumed non-lockstep until evidence proves otherwise.

When those conditions first occur, create a focused proposal for the affected
surface. It must define:

- the exact incompatible `v1` and successor contract diff;
- a `v1` compatibility adapter and `v2` implementation only where needed, rather
  than moving every router pre-emptively;
- generated-client ownership and cross-version contract tests;
- migration guidance and a rollback path;
- deprecation and sunset signals that preserve authentication, authorization,
  audit, CORS, error-shape, and cache behavior;
- no authentication downgrade path: security semantics must remain equivalent
  across live majors, and an insecure scheme must not survive for a fixed window;
- version-agnostic audit coverage and explicit middleware ordering for missing,
  invalid, and valid credentials plus handler failures;
- bounded or disabled caching for sunset responses, with rollback tests;
- usage evidence and an explicit removal criterion instead of an automatic fixed
  sunset period; and
- release-smoke and CLI gen-eval scenarios that exercise both versions during the
  overlap.

## Executable evidence

Recorded on 2026-08-07 at roadmap commit base `08e1be4e`:

- `make workflow-contracts-check` — passed; the OpenAPI contract is valid and all
  generated files are current.
- `pytest tests/contract/test_canonical_workflow_contracts.py
  tests/contract/test_cross_interface_workflows.py tests/release_smoke
  tests/cli_gen_eval --no-cov -q` — 285 passed, 2 deselected.
- `openspec validate add-api-versioning --strict` — passed before archival.

The evidence proves the workflow compatibility controls are executable. It does
not cover every legacy `/api/v1` router or the separate legacy CLI client, and it
does not claim that URL versioning will never be needed. It establishes that no
current named incompatibility pays for a second live API surface.

## Consequences

- The router layout and middleware stack remain unchanged.
- There is no inactive version registry, fabricated sunset date, or unused `v2`
  directory to maintain.
- The existing `/api/v1` namespace preserves room for a future major boundary.
- A future breaking proposal must name affected consumers and provide executable
  overlap evidence before implementation begins.
- Reassess this ADR before changing a contract used by the iOS Shortcut,
  `agentic-assistant`, or any other consumer whose deployed version cannot be proven.

## References

- `openspec/contracts/content-workflows/README.md`
- `openspec/contracts/content-workflows/openapi/v1.yaml`
- `openspec/contracts/release-smoke/README.md`
- `openspec/contracts/release-smoke/retired-workflow-mutations.json`
- `openspec/specs/content-capture/spec.md`
- `docs/MOBILE_CAPTURE.md`
- GitHub issues #421 and #492
- `tests/contract/test_canonical_workflow_contracts.py`
- `tests/contract/test_cross_interface_workflows.py`
- `tests/release_smoke/`
- `evaluation/README.md`
- `openspec/roadmaps/workflow-surface-reliability/learnings/ri-03.md`
- `openspec/roadmaps/workflow-surface-reliability/learnings/ri-04.md`
- `openspec/roadmaps/workflow-surface-reliability/learnings/ri-06.md`
