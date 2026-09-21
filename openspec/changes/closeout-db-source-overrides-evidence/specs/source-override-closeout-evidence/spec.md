## ADDED Requirements

### Requirement: R1 — One executable source-management contract

The durable OpenAPI, generated Python and TypeScript models, FastAPI models,
and hand-maintained CLI/web transports SHALL describe the same four operations.
POST SHALL use `config.type` as its only discriminator, PATCH SHALL accept only
`enabled`, and public responses SHALL expose stable identity, origin, enabled
state, and version without echoing full configuration.

#### Scenario: A valid source is created and updated

- **WHEN** an authenticated client POSTs `{config: {type: ...}, description?}`
  and later PATCHes the returned key with `{enabled: false}`
- **THEN** the source SHALL be created at version 1 and the effective update
  SHALL advance the version while preserving its public source key
- **AND** generated models and both transport wrappers SHALL accept and return
  the same documented shapes.

#### Scenario: A conflicting or missing discriminator is rejected

- **WHEN** a client omits `config.type`, supplies an unsupported type, or sends
  a redundant top-level discriminator
- **THEN** the request SHALL fail with the documented validation response
- **AND** no override row or version change SHALL be produced.

#### Scenario: Enabled-state mutation is bounded

- **WHEN** a client PATCHes a known key with one boolean `enabled` property
- **THEN** the server SHALL apply the change using the existing shadow/version
  rules
- **AND** an unknown key SHALL return 404 while extra or malformed mutation
  properties SHALL be rejected without mutation.

#### Scenario: Generated artifacts cannot drift

- **WHEN** contract generation and drift checks run
- **THEN** the committed Python and TypeScript models SHALL match the durable
  OpenAPI
- **AND** the test SHALL fail if the runtime or a hand-maintained transport
  wrapper changes its request or response shape incompatibly.

### Requirement: R2 — Authentication and private-source identity are explicit

Outside documented credential-free local development, every source-management
operation SHALL require either an authenticated owner session or a valid
`X-Admin-Key`. Public projections, errors, clients, and logs SHALL identify a
private source only by its HMAC-derived opaque `src_[a-f0-9]{20}` key and SHALL
not expose its locator or worker-local configuration.

#### Scenario: Either supported credential authorizes management

- **WHEN** a caller presents a valid owner session or admin key
- **THEN** each source-management route SHALL apply the same documented
  authentication boundary
- **AND** write-route defense-in-depth checks SHALL accept the same modes.

#### Scenario: Rejected authentication cannot mutate state

- **WHEN** a caller omits required credentials or presents an explicitly
  invalid admin key
- **THEN** the server SHALL return the documented 401 or 403 response
- **AND** no override SHALL be inserted, changed, deleted, or versioned.

#### Scenario: A private source crosses a public boundary

- **WHEN** an Obsidian source appears in a list, mutation response, error,
  browser row, or CLI output
- **THEN** only its generic type/label and opaque public key SHALL identify it
- **AND** `vault_id`, `vault_path`, `ingest_folder`, private tags, and private
  natural keys SHALL be absent.

### Requirement: R3 — Supported browser behavior has rendered evidence

The settings UI SHALL support quick-add for public source types including
Readwise, SHALL clearly represent YAML and database ownership, and SHALL manage
an existing Obsidian source only through its opaque key. Component and browser
tests SHALL exercise the rendered controls and recoverable failures.

#### Scenario: An operator adds Readwise among mixed origins

- **WHEN** the source settings surface contains enabled and disabled YAML and
  database rows and the operator adds Readwise
- **THEN** origins, enabled states, and source labels SHALL be visible
- **AND** the submitted Readwise configuration SHALL contain the selected
  `source_types` and `include_deleted` values inside `config` without a secret.

#### Scenario: Ownership determines deletion behavior

- **WHEN** the operator opens destructive controls for a DB-only source and for
  a YAML source with a database shadow
- **THEN** the DB-only action SHALL be described as removing the source
- **AND** the shadow action SHALL be described as restoring the YAML definition
  rather than deleting worker configuration.

#### Scenario: Existing Obsidian is manageable but not configurable

- **WHEN** an existing Obsidian source is returned by the API
- **THEN** the UI SHALL display a generic label and opaque key and allow
  enable/disable or delete according to origin
- **AND** it SHALL offer no create/edit fields or reveal any private locator.

#### Scenario: A browser mutation fails

- **WHEN** add, toggle, or delete returns an authorization, validation, missing-
  source, or server error
- **THEN** the UI SHALL surface a recoverable error
- **AND** it SHALL not leave the rendered row in an unconfirmed optimistic
  state.

### Requirement: R4 — Migration evidence reflects supported PostgreSQL state

A migration test SHALL build a fresh disposable PostgreSQL schema through the
repository Alembic chain and verify the deployed `source_overrides` schema,
constraints, defaults, JSON behavior, and non-destructive upgrade behavior.

#### Scenario: A clean database reaches head

- **WHEN** `alembic upgrade head` runs against a clean supported PostgreSQL
  schema containing an unrelated sentinel table and row
- **THEN** `source_overrides` SHALL have the expected revision, columns,
  PostgreSQL JSONB config, nullability, server defaults, primary key, unique
  `source_key`, and `source_type` index
- **AND** inserts/defaults and JSON round trips SHALL work while the sentinel
  data remains unchanged.

#### Scenario: The compatible upgrade is repeated

- **WHEN** `alembic upgrade head` runs again on the current compatible schema
- **THEN** it SHALL complete as a no-op without duplicating objects or changing
  data
- **AND** evidence SHALL not mislabel that no-op as proof that the original
  migration recreated the table.

#### Scenario: An incompatible manual table is discovered

- **WHEN** validation encounters a pre-existing `source_overrides` table that
  does not satisfy the supported schema
- **THEN** the condition SHALL fail with actionable evidence rather than be
  reported as a successful migration
- **AND** the runbook SHALL direct the operator to back up and rename/remove the
  incompatible table before recreating it through Alembic.

### Requirement: R5 — Current documentation makes operations reproducible

Current setup and architecture documentation SHALL define the canonical API,
authentication, merge precedence, lifecycle operations, failure behavior, and
recovery boundaries without relying on or modifying the dated archive.

#### Scenario: An operator manages the override lifecycle

- **WHEN** an operator follows the current setup guide to add, list, disable,
  enable, and remove an override
- **THEN** every CLI/API example SHALL match the nested POST, boolean PATCH, and
  DELETE behavior
- **AND** the guide SHALL distinguish DB-only deletion from deletion of a YAML
  shadow and explain private-key redaction.

#### Scenario: Database lookup or schema preparation fails

- **WHEN** source resolution cannot read the override database or an operator
  discovers an unsupported incompatible manual table
- **THEN** the documentation SHALL explain fail-open YAML behavior, observability,
  backup cautions, and the supported recovery sequence
- **AND** it SHALL not promise automatic repair by the shipped migration.
