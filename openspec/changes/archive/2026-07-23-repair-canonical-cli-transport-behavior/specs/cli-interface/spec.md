## MODIFIED Requirements

### Requirement: Output format

All CLI commands SHALL use Rich console output by default for human-readable
display. When JSON output is requested, stdout MUST contain exactly one valid
JSON document and diagnostics MUST be written to stderr.

#### Scenario: Default Rich output

- **WHEN** any `aca` command is executed without `--json`
- **THEN** output SHALL be formatted using Rich tables, panels, or styled text

#### Scenario: JSON output

- **WHEN** any `aca` command is executed with `--json`
- **THEN** output SHALL be valid JSON printed to stdout
- **AND** progress messages and diagnostics SHALL be suppressed or sent to stderr
- **AND** no human-readable prefix or warning SHALL precede the JSON document

### Requirement: CLI capability discovery

The CLI SHALL provide `aca capabilities` and `aca configured-sources` with
human-readable and JSON output derived from canonical cursor-page documents.
Optional query parameters that are absent MUST NOT be serialized into the HTTP
request.

#### Scenario: Agent discovers source command fields

- **WHEN** `aca capabilities --json` is executed
- **THEN** the result lists every canonical ingestion discriminator and its accepted fields
- **AND** it lists supported operation and resource types

#### Scenario: Configured sources use command-local JSON

- **WHEN** `aca configured-sources --json` is executed
- **THEN** stdout contains exactly one configured-source page JSON document
- **AND** the command exits successfully

#### Scenario: First discovery page omits cursor

- **WHEN** capabilities, configured sources, or operations are listed without a cursor
- **THEN** the serialized HTTP query contains the requested limit
- **AND** the serialized HTTP query does not contain a `cursor` key

#### Scenario: Explicit cursor is preserved

- **WHEN** a caller supplies an opaque cursor to a discovery or operation-list request
- **THEN** the serialized HTTP query contains that exact cursor value
- **AND** pagination continues through the canonical endpoint
