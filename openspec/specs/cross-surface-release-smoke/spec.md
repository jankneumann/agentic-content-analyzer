# cross-surface-release-smoke Specification

## Purpose

Define release-time compatibility verification across the deployed API, CLI,
and frontend, including immutable revision identity, production-safe discovery,
guarded staging mutation, retired-route detection, and sanitized promotion
evidence.

## Requirements
### Requirement: Deployed revisions are observed at the network boundary

The release gate SHALL derive backend and frontend revision identity from the
responses and assets served by the target environment. Promotion revisions
SHALL be immutable full commit SHAs with an allowlisted build-platform
provenance; permissive diagnostic values SHALL be local-only.

#### Scenario: Expected revisions match served revisions

- **WHEN** an operator supplies expected frontend and API revisions
- **THEN** the gate SHALL compare each expectation with the corresponding
  revision observed from the deployed service
- **AND** SHALL fail on an absent, malformed, placeholder, untrusted-provenance,
  or mismatched revision

#### Scenario: Evidence does not trust operator labels

- **WHEN** the gate writes release evidence
- **THEN** the recorded observed revisions SHALL originate from network responses
- **AND** operator-supplied expectations SHALL be recorded separately

### Requirement: Read-only smoke spans API, CLI, and deployed frontend

The default release-smoke tier SHALL be safe to run against production and
SHALL exercise canonical discovery through direct HTTP, a real `aca`
subprocess, and a deployed browser.

#### Scenario: Default tier is read-only

- **WHEN** the smoke gate runs without explicit mutation authorization
- **THEN** it SHALL issue only read-only discovery, authentication, liveness,
  document, and static-asset requests
- **AND** SHALL reject configuration containing mutation inputs

#### Scenario: First discovery page omits cursor

- **WHEN** the CLI subprocess and frontend request the first configured-source
  page
- **THEN** the emitted query SHALL omit the `cursor` key
- **AND** SHALL not serialize an empty, null, or placeholder cursor

#### Scenario: Frontend consumes capability discovery

- **WHEN** a fresh browser context loads the deployed ingestion surface
- **THEN** it SHALL observe successful capability discovery from the configured
  API origin
- **AND** SHALL exercise the configured-source first-page request through the
  frontend client

### Requirement: Credential-bearing targets are pinned

Release smoke SHALL attach credentials only to exact HTTPS origins from an
approval-protected target policy. Workflow callers SHALL NOT supply or override
release origins.

#### Scenario: Origin or redirect escapes target policy

- **WHEN** an origin differs from the protected allowlist or any request
  redirects across origins
- **THEN** the gate SHALL fail before attaching credentials to the destination
- **AND** mutation SHALL not be constructed

#### Scenario: Frontend targets a different API

- **WHEN** the served frontend sends workflow traffic to an API origin other
  than the protected API origin
- **THEN** the gate SHALL fail

### Requirement: Retired workflow mutations fail the release

The release gate SHALL reject a deployed frontend that calls or ships a retired
workflow mutation from the checked-in baseline policy. Runtime policy MAY add
entries and SHALL NOT remove or replace baseline entries.

#### Scenario: Browser observes a retired mutation

- **WHEN** any browser request targets a baseline or additive retired mutation
- **THEN** the gate SHALL fail even if the response succeeds

#### Scenario: Served asset contains a retired mutation

- **WHEN** the loaded document or any same-origin first-party JavaScript asset
  contains a baseline or additive retired mutation literal
- **THEN** the gate SHALL fail even if no interaction executed that code

#### Scenario: Revision-bound asset manifest is incomplete

- **WHEN** the served asset manifest is missing, mismatches the frontend
  revision, omits an observed first-party JavaScript asset, redirects, exceeds
  count/byte/deadline bounds, or an asset fails its declared digest
- **THEN** the gate SHALL fail rather than claim complete retired-route coverage

### Requirement: Mutation smoke is explicit and non-production

The mutation tier SHALL require affirmative authorization and an exact
deployment identity declared as `staging` or `ephemeral` by an
approval-protected policy. It SHALL reject production identities and aliases,
missing, ambiguous, or unrecognized targets before sending a mutation.

#### Scenario: Production mutation is rejected

- **WHEN** mutation authorization is requested for a production target
- **THEN** the runner SHALL fail before issuing a workflow mutation

#### Scenario: Staging mutation reaches successful terminal state

- **WHEN** an operator explicitly enables mutation for a staging or ephemeral
  target and selects a checked-in, schema-validated JSON fixture
- **THEN** the runner SHALL submit exactly one `POST /api/v1/ingestions` request
  with an idempotency key deterministically derived from the evidence run ID
- **AND** SHALL poll the returned durable operation until `completed` or timeout
- **AND** SHALL treat `failed`, `cancelled`, an ambiguous submission response,
  or timeout as a failed smoke

#### Scenario: Fixture path escapes the approved directory

- **WHEN** a fixture path is absolute, traverses, resolves through a symlink,
  exceeds the size bound, fails `IngestCommand` validation, or requests shell
  execution
- **THEN** the runner SHALL reject it before mutation

### Requirement: Release evidence is sanitized and machine-verifiable

Every run SHALL emit a JSON report conforming to the checked-in release-smoke
evidence schema. The report SHALL be bounded and SHALL contain enough facts to
reproduce the compatibility decision without containing authentication
material or user content.

#### Scenario: Passing evidence is complete

- **WHEN** a smoke run passes
- **THEN** the report SHALL contain target classification, safe frontend and API
  origins, observed and expected revisions plus provenance, bounded UTC timestamps, per-surface
  check results, retired-route counts, first-party asset hashes, and an overall
  result
- **AND** a mutation report SHALL additionally contain only the opaque operation
  ID and terminal status

#### Scenario: Sensitive evidence is rejected

- **WHEN** evidence contains credentials, cookies, request headers, query
  strings, raw command payloads, content bodies, canary URLs, or natural
  resource identifiers
- **THEN** schema or semantic validation SHALL fail

#### Scenario: Failure occurs before a surface is observed

- **WHEN** DNS, TLS, origin-policy, redirect, timeout, or malformed metadata
  prevents safe surface observation
- **THEN** a conforming failure envelope MAY use null for the unobserved safe
  origin, revision, or provenance
- **AND** SHALL contain a stable failure code and failed check
- **AND** passing evidence SHALL never contain a null or placeholder observation

### Requirement: Release automation retains promotion evidence

The repository SHALL provide CI and runbook entry points that retain the
validated evidence artifact and distinguish production read-only verification
from staging or ephemeral mutation verification.

#### Scenario: Production promotion gate

- **WHEN** the production read-only workflow runs
- **THEN** it SHALL require expected immutable frontend and API revisions
- **AND** SHALL validate the sanitized report before upload
- **AND** SHALL upload either that valid report or a separately generated and
  validated minimal validator-failure envelope
- **AND** SHALL fail promotion when report validation or any compatibility check
  fails

#### Scenario: Staging mutation workflow

- **WHEN** the mutation workflow runs
- **THEN** it SHALL require an approval-controlled staging or ephemeral
  environment
- **AND** SHALL keep credentials in environment secrets rather than command-line
  arguments or artifacts
