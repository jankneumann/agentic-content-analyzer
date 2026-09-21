# Tasks: Close out database source override evidence

## Execution contract

- **Tier:** local-parallel after the design decisions in `design.md` are locked.
- **Requirement traceability:** R1 contract, R2 security/privacy, R3 browser
  evidence, R4 migration evidence, R5 operator reproducibility.
- **Integration rule:** each package owns the files named below. If a test
  reveals production UI work outside that ownership, add a dependent package
  rather than editing the same component concurrently.

## WP1 — Durable contract and runtime parity (R1, R2)

**Blocked by:** none. **Owns:** durable OpenAPI, generated contract models,
contract tests, and—only where parity tests expose drift—the source route and
hand-maintained CLI/web transport wrappers.

- [ ] 1.1 Add failing contract assertions for the four source-management
  operations, nested `config.type`, PATCH `{enabled}`, stable response/error
  schemas, session/admin-key security, and opaque private keys.
- [ ] 1.2 Add the paths and schemas to
  `openspec/contracts/content-workflows/openapi/v1.yaml`, regenerate Python and
  TypeScript models, and keep generated artifacts in the same commit.
- [ ] 1.3 Prove FastAPI, CLI, and web wrapper parity, including invalid POST
  (400/no row), unauthenticated or forbidden mutation (401/403/no mutation),
  unknown PATCH (404), and successful version increments.
- [ ] 1.4 Correct the stale web-client comment that describes GET as public.

**Checkpoint:** `make workflow-contracts-check`; `.venv/bin/python -m pytest
 tests/contract/test_canonical_workflow_contracts.py
 tests/api/test_source_write_api.py tests/cli/test_source_commands.py -q`;
`pnpm --dir web test --run src/lib/api/__tests__/sources.test.ts`;
`pnpm --dir web typecheck`.

## WP2 — Rendered component evidence and supported add forms (R2, R3)

### WP2a — Component-test harness

**Blocked by:** none. **Owns:** frontend test dependencies, lockfile, Vitest
browser-like environment configuration, and shared component-test setup.

- [ ] 2.1 Add jsdom, Testing Library, and user-event to the existing Vitest
  toolchain with deterministic cleanup and accessible-query support.

### WP2b — Source configurator behavior

**Blocked by:** WP2a and WP1's public types. **Owns:**
`SourcesConfigurator` behavior/types and its rendered component tests.

- [ ] 2.2 Add Readwise quick-add fields for `source_types` and
  `include_deleted`; credentials remain environment-owned.
- [ ] 2.3 Render existing Obsidian rows with a generic label and opaque key;
  allow enable/disable and deletion but expose no create/edit form or private
  configuration.
- [ ] 2.4 Test mixed YAML/DB origins, enabled states, nested add payloads,
  toggle payloads, DB-only delete, YAML shadow restoration messaging, and a
  failed mutation that surfaces a recoverable error without an optimistic
  state lie.

**Checkpoint:** `pnpm --dir web test --run
src/components/settings/__tests__/SourcesConfigurator.test.tsx` and
`pnpm --dir web typecheck`.

## WP3 — Mocked browser journey (R2, R3)

**Blocked by:** WP1's public types. **Owns:** Playwright source fixtures, page
object helpers, and the source-settings browser spec.

- [ ] 3.1 Add deterministic API mocks for mixed origins, Readwise creation,
  PATCH success/failure, DB deletion, YAML shadow deletion, and an opaque
  Obsidian row.
- [ ] 3.2 Drive direct settings navigation and prove origin badges, enabled
  state, Readwise add, toggle, ownership-aware delete behavior, Obsidian
  redaction, and mutation-error recovery.

**Checkpoint:** `pnpm --dir web exec playwright test
 tests/e2e/settings/sources.spec.ts --project=chromium`.

## WP4 — PostgreSQL migration evidence (R4)

**Blocked by:** none. **Owns:** the source-override migration test only; no
historical migration edit is expected.

- [ ] 4.1 Against the disposable PostgreSQL fixture, rebuild the schema through
  `alembic upgrade head` and assert revision, columns, PostgreSQL JSONB,
  nullability, defaults, primary/unique/index definitions, JSON round trip,
  and preservation of an unrelated sentinel row.
- [ ] 4.2 Prove a second upgrade is a no-op. Separately label the existing-table
  guard as compatible-table safety only; an incompatible manual table must
  produce actionable evidence and follow the documented backup/recreate path.

**Checkpoint:** `.venv/bin/python -m pytest
 tests/migrations/test_source_overrides.py -q` using the repository's
worktree-safe disposable database fixture.

## WP5 — Operator runbook (R5)

**Blocked by:** none. **Owns:** `docs/SETUP.md`.

- [ ] 5.1 Document database/YAML precedence; authentication; add/list/
  enable/disable/remove examples; DB-only deletion; YAML-shadow restoration;
  DB-unavailable fail-open behavior; backup/recovery cautions; and recovery
  from an unsupported schema-incompatible manual table.

**Checkpoint:** examples use the current nested POST, PATCH, DELETE, and CLI
syntax and do not reveal private locators.

## WP6 — Durable architecture record (R1, R2, R5)

**Blocked by:** none. **Owns:** `docs/ARCHITECTURE.md` and the stale
source-merge documentation string if contract tests identify it.

- [ ] 6.1 Record the four methods, nested discriminator, PATCH/shadow behavior,
  auth boundary, opaque-key invariant, version/natural-key rules, complete-
  catalog GET assumption, and rejected alternatives.

**Checkpoint:** current documentation—not the dated archive—matches the
executable contract and runtime.

## WP7 — Integration validation and evidence report (R1–R5)

**Blocked by:** WP1, WP2b, WP3, WP4, WP5, WP6. **Owns:** validation output and
completion evidence; it does not absorb unfinished implementation.

- [ ] 7.1 Run focused contract, API, CLI, component, browser, and migration
  suites; run `pnpm --dir web build`, `pnpm --dir web typecheck`,
  `make workflow-contracts-check`, and
  `openspec validate closeout-db-source-overrides-evidence --strict`.
- [ ] 7.2 Confirm the archived source change is byte-for-byte untouched and
  report which suite proves each requirement and failure path.

## Dependency and ownership summary

After decisions are locked, WP1, WP2a, WP3, WP4, WP5, and WP6 can begin in
parallel (theoretical width 6; practical width follows worker capacity). WP2b
waits for WP2a and public contract types. WP7 waits for all implementation
packages. Only WP7 reads across all owned files.
