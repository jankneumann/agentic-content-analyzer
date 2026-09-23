## MODIFIED Requirements

### Requirement: Source override management API

The system SHALL expose authenticated source management under
`/api/v1/sources`, accepting either an owner session or `X-Admin-Key` outside
documented credential-free local development. POST SHALL upsert a request whose
`config` contains the full typed source; PATCH on a public management key SHALL
set enabled state; DELETE SHALL remove a database override. For ordinary
sources the public key is the natural key; Obsidian SHALL use only its
HMAC-derived opaque key. POST and PATCH results SHALL report public key,
version, origin, and enabled state. DELETE SHALL report the removed public key
and `deleted=true`.

#### Scenario: Administrator disables a YAML source

- **WHEN** an authenticated PATCH disables a YAML public management key with no
  existing override
- **THEN** the service SHALL create a self-describing database shadow
- **AND** ingestion selection SHALL exclude the source while the management
  projection retains the disabled row.

#### Scenario: Obsidian is managed without exposing natural identity

- **WHEN** an authenticated caller lists, patches, or deletes an Obsidian source
- **THEN** request/response management identity SHALL use only its opaque public
  key
- **AND** no Obsidian locator or worker-local configuration SHALL be returned.

#### Scenario: Unauthenticated mutation is attempted

- **WHEN** a caller without a valid owner session or admin key submits POST,
  PATCH, or DELETE
- **THEN** the API SHALL reject the mutation without changing an override.

### Requirement: Source override CLI

The CLI SHALL provide `aca sources list`, `add`, `remove`, `enable`, and
`disable` commands using the same source union, public management keys, origin,
version, and enabled-state semantics as the API/service. Ordinary sources use
their natural key publicly; Obsidian uses only its opaque public key.

#### Scenario: Operator lists resolved sources

- **WHEN** `aca sources list` runs
- **THEN** it SHALL show each resolved source's type, public management key,
  enabled state, and origin
- **AND** an Obsidian row SHALL reveal no natural locator or private config.

#### Scenario: Operator adds a source

- **WHEN** an operator supplies a valid source type and locator to
  `aca sources add`
- **THEN** the CLI SHALL upsert the validated source
- **AND** SHALL report the resulting public management key and version.
