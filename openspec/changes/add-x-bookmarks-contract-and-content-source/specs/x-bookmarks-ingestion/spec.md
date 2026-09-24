## ADDED Requirements

### Requirement: X bookmarks ingestion command contract

The canonical workflow contract SHALL declare an `XBookmarksIngestCommand`
with discriminator `kind: x_bookmarks` in the `IngestCommand` union of
`openspec/contracts/content-workflows/openapi/v1.yaml`. The command SHALL be
strict (`additionalProperties: false`) and SHALL expose only the public fields
`max_items` (integer, 1 to 10000, no default), `full` (boolean, default
false), `expand_links` (boolean, no default so an absent value defers to the
source configuration), and `force_reprocess` (boolean, default false), plus the
read-only, internal `configured_sources` scheduler snapshot shared by every
scheduled command. The command SHALL NOT accept any credential, cookie, or
GraphQL query identifier. The runtime model in `src/contracts/workflow_models.py`,
the contract copy in `generated/models.py`, and both TypeScript outputs SHALL be
produced by `scripts/generate_workflow_contracts.py` and never edited by hand.

#### Scenario: Minimal command validates with safe defaults

- **WHEN** a client submits `{"kind": "x_bookmarks"}` through the generated `IngestCommand` union
- **THEN** it validates as `XBookmarksIngestCommand` with `full=false`, `force_reprocess=false`, and `max_items` and `expand_links` unset

#### Scenario: Unbounded or credential-bearing commands are rejected

- **WHEN** a command sets `max_items` to 0 or 10001, or carries an `auth_token` or `ct0` field
- **THEN** validation fails and no operation is submitted

#### Scenario: Generated artifacts match the contract

- **WHEN** `python scripts/generate_workflow_contracts.py --check` runs
- **THEN** it reports that all four generated files are current and the TypeScript `XBookmarksIngestCommand` omits `configured_sources`

### Requirement: X bookmarks content source identity

`ContentSource` SHALL include `X_BOOKMARKS = "x_bookmarks"`, and the
PostgreSQL `contentsource` enum SHALL gain the same value through an Alembic
migration that uses `ALTER TYPE contentsource ADD VALUE IF NOT EXISTS
'x_bookmarks'`, whose downgrade is a documented no-op, and which keeps
`alembic heads` at a single head. The `ContentQuery.source_types` enum in the
contract SHALL list `x_bookmarks` so persisted bookmark rows are filterable.

#### Scenario: Migration is idempotent

- **WHEN** `alembic upgrade head` runs twice, or after a downgrade of the revision followed by a new upgrade
- **THEN** both runs succeed and `contentsource` contains `x_bookmarks` exactly once

#### Scenario: Content query accepts the new source

- **WHEN** a content query filters on `source_types: ["x_bookmarks"]`
- **THEN** the generated `ContentQuery` model accepts it, because its enum equals the set of `ContentSource` values

### Requirement: X bookmarks ingestion response literals

The closed ingestion response registries in `src/ingestion/result.py` SHALL
include the command `ingest.x-bookmarks` in `IngestionCommandLiteral` and the
source `x_bookmarks` in `IngestionSourceLiteral`, following the existing
convention of a hyphenated command and a snake_case source. The command model
SHALL be exported in `COMMAND_MODELS` from `src/ingestion/commands.py`.

#### Scenario: Canonical response literals are accepted

- **WHEN** an `IngestionResponse` is built with `command="ingest.x-bookmarks"` and `source="x_bookmarks"`
- **THEN** it validates

#### Scenario: Misspelled literals are rejected

- **WHEN** an `IngestionResponse` is built with `command="ingest.x_bookmarks"` or `source="x-bookmarks"`
- **THEN** validation fails

### Requirement: Transport surfaces enumerate the X bookmarks command

Every transport surface that enumerates contract commands or content sources
SHALL list the new source: the MCP tool manifest SHALL expose
`ingest_x_bookmarks` with exactly the public contract fields, the contract-driven
CLI SHALL expose `aca ingest x-bookmarks`, and the frontend content-source
display map, source filter, and contents filter SHALL render `x_bookmarks`.

#### Scenario: MCP tool submits only public fields

- **WHEN** `ingest_x_bookmarks(max_items=100, full=True)` is called in HTTP transport mode
- **THEN** the workflow client receives `{"kind": "x_bookmarks", "max_items": 100, "full": true, "force_reprocess": false}` and no `expand_links` key

#### Scenario: Frontend renders persisted bookmark rows

- **WHEN** the contents view renders a row whose source is `x_bookmarks`
- **THEN** it shows the "X Bookmarks" label with an icon
