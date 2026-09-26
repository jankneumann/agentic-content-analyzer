# Change: Close out database source override evidence

## Why

Database-backed source storage, merge precedence, API authentication, and CLI
management are implemented. The historical change still overclaims completion:
its archived OpenAPI requires a redundant top-level source discriminator that
the runtime accepted only as an ignored unknown sibling and never modeled or
used semantically, the durable contract does not publish the source
management surface, component/browser evidence is missing, setup guidance is
incomplete, migration behavior lacks executable PostgreSQL evidence, and the
architecture guide lists only the read endpoint.

This closeout records and verifies the behavior that already governs `/api/v1`.
It must not silently reshape the live API or treat tests of a narrower browser
surface as proof of the historical "every field for every source" promise.

## Source and completed scope

- Extracted from archived `db-source-overrides`.
- Completed and excluded: table/model/service, validated source union, natural
  keys, YAML/DB precedence, disable shadows, fail-open merge, backend
  CRUD/PATCH behavior, authentication middleware, and CLI commands.
- The durable `source-configuration` spec already owns those functional
  behaviors. This change adds contract, UI, migration, and documentation
  evidence without duplicating that specification.
- This closeout SHALL not redesign source resolution or add a second registry.

## What Changes

- Publish `GET`/`POST /api/v1/sources` and `PATCH`/`DELETE
  /api/v1/sources/{key}` in the durable content-workflow OpenAPI. The POST body
  treats only `config.type` as the discriminator; PATCH remains the sole
  enable/disable mutation with `{ "enabled": boolean }`. For `/api/v1`
  compatibility, unknown request siblings remain ignored and have no semantic
  effect rather than becoming a new strict-validation break.
- Generate Python and TypeScript contract models from that OpenAPI and prove
  parity with the FastAPI models and the hand-maintained CLI/web HTTP clients.
  This change does not introduce generated HTTP clients.
- Specify the actual security boundary: source routes require an authenticated
  owner session or `X-Admin-Key` outside the documented credential-free local
  development mode. Rejected writes must not mutate an override.
- Preserve privacy-safe management identity. Ordinary sources use their
  natural key; Obsidian uses only an opaque `src_...` public management key at
  HTTP, CLI, browser, application/audit-log, and server-error boundaries. Source
  path logging redacts a caller-supplied non-public Obsidian locator.
- Add Readwise to the browser add-source form. The browser offers no Obsidian
  create/edit form; trusted CLI/API callers may still submit worker-local
  Obsidian configuration, while browser and response projections may display,
  enable, disable, and delete an existing row only through its opaque key.
  Public-source forms are a reviewed quick-add subset rather than a promise to
  expose every advanced backend field.
- Add rendered-component and mocked-browser evidence for add, origin display,
  enable/disable, truthful generic override-removal messaging, private-source
  redaction, and mutation failures. Backend evidence—not browser inference—
  proves DB-only removal and YAML-shadow restoration.
- Add executable migration evidence against a uniquely named disposable
  PostgreSQL database with its own `public` schema, and document setup,
  precedence, recovery, authentication, and PATCH/delete semantics in current
  durable documentation.
- Amend the durable `source-configuration` requirements so public management
  identity is distinct from internal natural identity and disabled shadows stay
  management-visible while ingestion selection excludes them.

## Scope boundaries and non-goals

- No browser form for Obsidian filesystem paths, allowed roots, parser limits,
  or worker readiness configuration; trusted API/CLI creation remains supported.
- No new partial-update endpoint, PUT endpoint, enable/disable subroutes, or
  incompatible `/api/v1` request shape.
- No generated HTTP client framework; only generated contract models/types and
  explicit parity tests for existing transport wrappers.
- No pagination redesign for `GET /api/v1/sources`. It returns the complete,
  operator-managed configuration catalog, not unbounded content history. A
  future measured cardinality problem requires a separate API proposal.
- No change to database-over-YAML precedence, natural-key derivation, source
  registry behavior, or ingestion execution.
- No modification of
  `openspec/changes/archive/2026-07-23-db-source-overrides/**`.
- No support promise for manually created, schema-incompatible
  `source_overrides` tables; operator recovery for that unsupported state is
  documented instead of rewriting a deployed historical migration.

## Capabilities

- `source-override-closeout-evidence`
- `source-configuration`

## Impact

- **Contracts**: additive source-management paths and schemas in
  `openspec/contracts/content-workflows/openapi/v1.yaml`; regenerated Python
  and TypeScript models; runtime/contract drift tests.
- **Backend and clients**: source route models and hand-maintained CLI/web
  wrappers may change only where parity tests expose drift. Existing `/api/v1`
  payloads remain compatible.
- **Web**: component-test infrastructure, Readwise quick-add support,
  privacy-safe management of existing Obsidian rows, and Playwright evidence.
- **Database**: tests inspect the already-shipped migration on a uniquely named
  disposable PostgreSQL database; no destructive migration is planned.
- **Documentation**: `docs/ARCHITECTURE.md` and `docs/SETUP.md` become the
  durable design and operations references. The dated archive remains
  immutable.
- **Security**: no private Obsidian locator or filesystem field may appear in a
  read/mutation response, server-produced error, browser state derived from a
  response, generated public model, or source-management application/audit log.

## Acceptance outcomes

- One additive durable OpenAPI contract matches each runtime
  POST/PATCH/DELETE/GET success and legacy error shape, security scheme,
  public-key semantic, and stable operation ID.
- Contract generation and drift checks fail if backend, CLI, web types, or the
  durable OpenAPI diverge.
- Browser evidence proves supported public quick-add behavior and makes the
  Obsidian worker-local boundary visible rather than silently omitting it.
- A fresh migrated PostgreSQL database proves the table, JSONB column,
  defaults, uniqueness, and indexes that production relies on.
- Operators can add, disable, re-enable, remove, and recover overrides using
  current CLI/API commands; the UI truthfully warns that removing a database
  override may reveal a YAML baseline without pretending GET exposes that fact.
