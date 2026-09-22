# Tasks: Close out database source override evidence

## Execution contract

- **Tier:** local-parallel after the design decisions in `design.md` are locked.
- **Requirement traceability:** R1 contract, R2 security/privacy, R3 browser
  evidence, R4 migration evidence, R5 operator reproducibility.
- **Integration rule:** each package owns the exact files named below. New
  production files stay within that package's directory scope; cross-package
  fixes become an explicit dependent package rather than concurrent edits.

## WP1 — Durable contract and runtime parity (R1, R2)

**Blocked by:** none. **Owns:**
`openspec/contracts/content-workflows/openapi/v1.yaml`, generated contract
outputs, `tests/contract/test_canonical_workflow_contracts.py`, source API tests,
`src/api/middleware/audit.py`, `tests/api/test_audit_middleware.py`,
`web/src/types/settings.ts`, and—only where parity tests expose drift—the source
routes and hand-maintained CLI/web transport wrappers plus their tests.

- [ ] 1.1 Add failing assertions for all four operations, authoritative nested
  `config.type`, ignored siblings with no semantic effect, PATCH `{enabled}`,
  operation-specific success bodies, legacy error bodies, both credential
  schemes, and opaque Obsidian keys.
- [ ] 1.2 Add paths/schemas to the durable OpenAPI, regenerate Python/TypeScript
  models, and keep generated artifacts in the same commit.
- [ ] 1.3 Prove FastAPI, CLI, and web parity: semantic config failure
  (400/no row), malformed body (422/no row), missing/invalid auth
  (401/403/no mutation), unknown PATCH (404), ignored extras, and versioning.
- [ ] 1.4 Normalize source-management audit paths before persistence and
  writer-failure logging. Prove valid opaque keys remain useful while rejected
  Obsidian natural locators, filesystem fields, tags, and identifiers never
  appear in stored audit rows or captured application logs.
- [ ] 1.5 Correct stale comments that describe GET as public or every key as a
  natural key; add Readwise and Obsidian to shared response DTO unions without
  creating a browser Obsidian form.

**Checkpoint:** `make workflow-contracts-check`; `.venv/bin/python -m pytest
 tests/contract/test_canonical_workflow_contracts.py
 tests/api/test_source_write_api.py tests/api/test_audit_middleware.py
 tests/cli/test_source_commands.py -q`;
`pnpm --dir web test --run src/lib/api/__tests__/sources.test.ts`;
`pnpm --dir web typecheck`.

## WP2 — Rendered component evidence and supported add forms (R2, R3)

### WP2a — Component-test harness

**Blocked by:** none. **Owns:** `web/package.json`, `web/package-lock.json`,
root `pnpm-lock.yaml`, `web/vite.config.ts`, and a new shared component-test
setup file.

- [x] 2.1 Add jsdom, Testing Library, and user-event to the existing Vitest
  toolchain with deterministic cleanup and accessible-query support. Update
  both tracked lockfiles because CI and local workflows use different installers.

### WP2b — Source configurator behavior

**Blocked by:** WP2a, WP1. **Owns:**
`web/src/components/settings/SourcesConfigurator.tsx`, an optional new UI-local
form-definition module, and the rendered component test. Shared API DTOs remain
WP1-owned.

- [ ] 2.2 Add Readwise quick-add fields for `source_types` and
  `include_deleted`; credentials remain environment-owned.
- [ ] 2.3 Render existing Obsidian rows with a generic label and opaque key;
  allow enable/disable and DB-override removal but expose no create/edit form or
  private configuration.
- [ ] 2.4 Test mixed origins, states, nested add/toggle payloads, the generic
  “remove override; YAML may reappear” message, and representative add, toggle,
  and delete failures; every independent handler surfaces a recoverable error
  without an optimistic state lie.

**Checkpoint:** `pnpm --dir web test --run
src/components/settings/__tests__/SourcesConfigurator.test.tsx` and
`pnpm --dir web typecheck`.

## WP3 — Mocked browser journey (R2, R3)

**Blocked by:** WP1. **Owns:** Playwright source fixtures, page-object helpers,
and the source-settings browser spec; it does not edit production components.

- [ ] 3.1 Add deterministic API mocks for mixed origins, Readwise creation,
  add/PATCH/delete success and representative failures, DB-override deletion,
  and an opaque Obsidian row.
- [ ] 3.2 Prove origin badges, enabled state, Readwise add, toggle, generic
  override-removal copy, Obsidian redaction, and recoverable add, toggle, and
  delete failures. Use representative status classes rather than a Cartesian
  matrix, and do not mock unavailable YAML-baseline provenance.

**Checkpoint:** `pnpm --dir web exec playwright test
 tests/e2e/settings/sources.spec.ts --project=chromium`.

## WP4 — PostgreSQL migration evidence (R4)

**Blocked by:** none. **Owns:** a new migration-local fixture/helper under
`tests/migrations/` and `tests/migrations/test_source_overrides.py`; no
historical migration edit or session-shared database mutation is expected.

- [ ] 4.1 Provision a uniquely named, worktree-safe disposable database with
  its own `public` schema, upgrade to `b8f8b5ededed`, create a sentinel,
  upgrade through `c3d4e5f6a7b8` to current head, and assert the revision chain,
  columns, PostgreSQL JSONB, nullability, defaults, constraints/indexes, JSON
  round trip, and sentinel preservation.
- [ ] 4.2 Prove a second head upgrade is a no-op. Separately use a test-local
  verifier to demonstrate that the existing-table guard does not validate an
  incompatible manual schema; this evidence must not be presented as a
  production doctor. Teardown drops only the uniquely named disposable
  database.

**Checkpoint:** `.venv/bin/python -m pytest
 tests/migrations/test_source_overrides.py -q` against the uniquely named,
worktree-safe disposable PostgreSQL database fixture.

## WP5 — Operator runbook (R5)

**Blocked by:** none. **Owns:** `docs/SETUP.md`.

- [ ] 5.1 Document precedence; auth; add/list/enable/disable/remove examples;
  generic deletion semantics; DB-unavailable fail-open behavior; backup
  cautions; and incompatible-manual-table recovery without claiming a schema
  doctor.

**Checkpoint:** reviewer checks the new “Database source overrides” section in
`docs/SETUP.md` against every R5 lifecycle/failure clause and verifies its
examples against WP1 tests. This command finds every required topic:
`rg -n "Database source overrides|X-Admin-Key|may reappear|fail-open|backup" docs/SETUP.md`.

## WP6 — Durable architecture and source-spec alignment (R1, R2, R5)

**Blocked by:** none. **Owns:** `docs/ARCHITECTURE.md`,
`openspec/changes/closeout-db-source-overrides-evidence/specs/source-configuration/spec.md`,
and a stale source-merge docstring only if contract tests identify it.

- [ ] 6.1 Modify the durable source-configuration requirements to distinguish
  internal natural identity from public management identity and to keep a
  disabled shadow management-visible while ingestion selection excludes it.
- [ ] 6.2 Record all four methods, nested discriminator and ignored-sibling
  compatibility, PATCH/shadow behavior, auth, Obsidian opaque keys, exact
  response families, version/identity rules, complete-catalog GET, audit-path
  redaction, generic deletion copy, and rejected alternatives.

**Checkpoint:** reviewer checks the “Source override management” section in
`docs/ARCHITECTURE.md` against D1–D9. This command finds the required anchors:
`rg -n "Source override management|config.type|PATCH|opaque|complete.*catalog" docs/ARCHITECTURE.md`.

## WP7 — Integration validation and evidence report (R1–R5)

**Blocked by:** WP1, WP2b, WP3, WP4, WP5, WP6. **Owns:** validation output and
completion evidence; it does not absorb unfinished implementation.

- [ ] 7.1 Run focused contract, API, CLI, component, browser, and migration
  suites; run `pnpm --dir web build`, `pnpm --dir web typecheck`,
  `make workflow-contracts-check`, and
  `openspec validate closeout-db-source-overrides-evidence --strict`.
- [ ] 7.2 Confirm the archived source change is untouched with
  `git diff --exit-code $(git merge-base HEAD origin/main) --
  openspec/changes/archive/2026-07-23-db-source-overrides` and report which
  suite proves each requirement and failure path.

## Dependency and ownership summary

WP1, WP2a, WP4, WP5, and WP6 are independent roots (theoretical width 5;
practical width follows worker capacity). WP2b waits for WP1 and WP2a. WP3
waits for WP1. WP7 waits for all implementation packages. Only WP7 reads across
all owned files.
