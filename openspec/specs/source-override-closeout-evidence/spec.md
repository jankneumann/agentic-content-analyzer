# source-override-closeout-evidence Specification

## Purpose
TBD - created by archiving change closeout-db-source-overrides-evidence. Update Purpose after archive.
## Requirements
### Requirement: R1 — One executable source-management contract

The durable OpenAPI, generated Python and TypeScript models, FastAPI models,
and hand-maintained CLI/web transports SHALL describe the same four operations.
Only `config.type` SHALL determine a POST source type, and PATCH SHALL mutate
only `enabled`. Compatibility tests SHALL preserve the existing behavior that
unknown request siblings are ignored and have no semantic effect.

#### Scenario: A valid source is created and updated

- **WHEN** an authenticated client POSTs `{config: {type: ...}, description?}`
  and later PATCHes the returned key with `{enabled: false}`
- **THEN** the source SHALL be created at version 1 and the effective update
  SHALL advance the version while preserving its public source key
- **AND** generated models and both transport wrappers SHALL accept and return
  the same documented shapes.

#### Scenario: The nested discriminator is authoritative

- **WHEN** a client omits `config.type` or supplies an unsupported nested type
- **THEN** semantic validation SHALL return the documented 400 response without
  creating or versioning an override
- **AND** an unknown top-level `type` sibling SHALL be ignored and SHALL NOT
  override, conflict with, or become an alternative to `config.type`.

#### Scenario: Enabled-state mutation is bounded semantically

- **WHEN** a client PATCHes a known key with boolean `enabled`
- **THEN** the server SHALL apply the change using existing shadow/version rules
- **AND** an unknown key SHALL return 404, a malformed body SHALL return 422,
  and ignored sibling properties SHALL have no mutation effect.

#### Scenario: Each operation has its actual projection and errors

- **WHEN** the durable contract describes source-management responses
- **THEN** POST/PATCH SHALL expose key/version/origin/enabled, DELETE SHALL
  expose key/deleted, and GET SHALL expose the existing overview and source
  projection without claiming a mutation version
- **AND** service 400/404 `{detail}`, validation 422 `{detail: errors[]}`, and
  auth 401/403 `{error, detail, trace_id?}` JSON schemas SHALL remain distinct.

#### Scenario: Generated artifacts cannot drift

- **WHEN** contract generation and drift checks run
- **THEN** the committed Python and TypeScript models SHALL match the durable
  OpenAPI
- **AND** the test SHALL fail if the runtime or a hand-maintained transport
  wrapper changes its request or response shape incompatibly.

### Requirement: R2 — Authentication and Obsidian identity are explicit

Outside documented credential-free local development, every source-management
operation SHALL require either an authenticated owner session or a valid
`X-Admin-Key`. Public projections, errors, clients, and logs SHALL identify an
Obsidian source only by its HMAC-derived opaque `src_[a-f0-9]{20}` key and SHALL
not expose its locator or worker-local configuration.

#### Scenario: Either supported credential authorizes management

- **WHEN** a caller presents a valid owner session or admin key
- **THEN** each source-management route SHALL apply the same documented
  authentication boundary
- **AND** write-route defense-in-depth checks SHALL accept the same modes.

#### Scenario: Rejected authentication cannot mutate state

- **WHEN** a caller omits required credentials or presents an explicitly
  invalid admin key
- **THEN** the server SHALL return the documented 401 or 403 legacy JSON body
- **AND** no override SHALL be inserted, changed, deleted, or versioned.

#### Scenario: Obsidian crosses a public boundary

- **WHEN** an Obsidian source appears in a list, mutation response, error,
  browser row, or CLI output
- **THEN** only its generic type/label and opaque public key SHALL identify it
- **AND** `vault_id`, `vault_path`, `ingest_folder`, private tags, and private
  natural keys SHALL be absent.

#### Scenario: Source-management logs redact private identity

- **WHEN** a valid or rejected Obsidian management request is recorded in an
  application log, persisted audit row, or audit-writer failure message
- **THEN** the recorded path SHALL contain the valid opaque key or a fixed
  redacted token, never a caller-supplied private locator
- **AND** `vault_id`, `vault_path`, `ingest_folder`, private tags, and an
  `obsidian_vault:<locator>` natural key SHALL be absent.

### Requirement: R3 — Supported browser behavior has rendered evidence

The settings UI SHALL support quick-add for non-worker-filesystem source types,
including Readwise, SHALL clearly represent YAML and database origins, and
SHALL manage an existing Obsidian source only through its opaque key. It SHALL
not infer YAML-baseline provenance that GET does not expose.

#### Scenario: An operator adds Readwise among mixed origins

- **WHEN** the source settings surface contains enabled and disabled YAML and
  database rows and the operator adds Readwise
- **THEN** origins, enabled states, and source labels SHALL be visible
- **AND** the submitted Readwise configuration SHALL contain the selected
  `source_types` and `include_deleted` values inside `config` without a secret.

#### Scenario: The operator removes a database override

- **WHEN** the operator opens delete controls for a row with `origin="db"`
- **THEN** the UI SHALL say that it removes the database override and that a
  YAML definition may reappear
- **AND** backend evidence SHALL separately prove DB-only removal and YAML-shadow
  restoration instead of browser mocks fabricating which outcome applies.

#### Scenario: Existing Obsidian is manageable but not browser-configurable

- **WHEN** an existing Obsidian source is returned by the API
- **THEN** the UI SHALL display a generic label and opaque key and allow
  enable/disable or database-override removal according to origin
- **AND** it SHALL offer no create/edit fields or reveal any private locator,
  while trusted CLI/API creation remains compatible.

#### Scenario: A browser mutation fails

- **WHEN** add, toggle, or delete returns an authorization, validation, missing-
  source, or server error
- **THEN** the UI SHALL surface a recoverable error
- **AND** it SHALL not leave the rendered row in an unconfirmed optimistic
  state.

### Requirement: R4 — Migration evidence reflects supported PostgreSQL state

A migration-local fixture SHALL build a uniquely named disposable PostgreSQL
database with its own `public` schema through the repository Alembic chain and verify the deployed source-override
schema, constraints, defaults, JSON behavior, and non-destructive upgrade.

#### Scenario: The source migration upgrades its predecessor

- **WHEN** an isolated disposable database is upgraded to `b8f8b5ededed`,
  receives an unrelated sentinel table/row, and is then upgraded through `c3d4e5f6a7b8` to
  current head
- **THEN** `source_overrides` SHALL have the expected columns, PostgreSQL JSONB,
  nullability, server defaults, primary key, unique key, and source-type index
- **AND** insert/default and JSON round trips SHALL work while the sentinel data
  remains unchanged and the recorded revision reaches current head
- **AND** fixture teardown SHALL drop the disposable database without mutating
  the session-shared test database.

#### Scenario: The compatible upgrade is repeated

- **WHEN** `alembic upgrade head` runs again on the current compatible schema
- **THEN** it SHALL complete as a no-op without duplicating objects or changing
  data
- **AND** evidence SHALL not mislabel that no-op as proof of initial creation.

#### Scenario: Test-local verification detects an incompatible manual table

- **WHEN** the historical table-exists guard skips a pre-existing incompatible
  `source_overrides` table in an isolated migration test
- **THEN** a test-local schema verifier SHALL report the mismatch rather than
  treating Alembic's successful return as compatibility
- **AND** the runbook SHALL direct operators to back up and rename/remove the
  unsupported table before recreating it through Alembic, without claiming a
  production preflight exists.

### Requirement: R5 — Current documentation makes operations reproducible

Current setup and architecture documentation SHALL define the canonical API,
authentication, merge precedence, lifecycle operations, failure behavior, and
recovery boundaries without relying on or modifying the dated archive.

#### Scenario: An operator manages the override lifecycle

- **WHEN** an operator follows the current setup guide to add, list, disable,
  enable, and remove an override
- **THEN** every CLI/API example SHALL match the nested POST, boolean PATCH, and
  DELETE behavior
- **AND** the guide SHALL explain that removing a DB override may reveal a YAML
  baseline and that GET does not distinguish that case in advance.

#### Scenario: Database lookup or schema preparation fails

- **WHEN** source resolution cannot read the override database or an operator
  discovers an unsupported incompatible manual table
- **THEN** the documentation SHALL explain fail-open YAML behavior, observability,
  backup cautions, and the supported recovery sequence
- **AND** it SHALL not promise automatic repair or a production schema doctor.
