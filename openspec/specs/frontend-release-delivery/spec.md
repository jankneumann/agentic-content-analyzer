# frontend-release-delivery Specification

## Purpose

Define the reproducible, audit-gated Railway frontend release and its canonical
production workflow proof.

## Requirements

### Requirement: Reproducible isolated frontend build

The Railway frontend service SHALL build from its checked-in isolated service
configuration using a committed lockfile, package-local build tools, and Node
22. The production build MUST NOT require pnpm, Python, uv, or repository-level
contract generation.

#### Scenario: Clean Railway build

- **GIVEN** the service root is `/web`
- **WHEN** Railpack installs dependencies and builds
- **THEN** it SHALL use the committed frontend lockfile and package-local
  TypeScript/Vite binaries
- **AND** SHALL complete under Node 22 without repository toolchains

### Requirement: CI frontend release parity

CI SHALL run generated workflow-contract drift, the focused workflow-client
test, a production dependency audit that rejects high or critical findings,
and the exact locked frontend build under Node 22.

#### Scenario: A release boundary fails

- **WHEN** contract drift, focused tests, dependency audit, or production build
  fails
- **THEN** the `frontend-release` job SHALL fail

#### Scenario: Every release boundary passes

- **WHEN** all four release boundaries pass for one pushed revision
- **THEN** that exact revision SHALL be eligible for promotion

### Requirement: Canonical production ingestion frontend

The active frontend SHALL discover capabilities and submit ingestion through
`POST /api/v1/ingestions`; it MUST NOT use retired content mutation routes.
Promotion MUST use the exact CI-passed revision and capture rollback data first.

#### Scenario: Production ingestion is submitted

- **WHEN** an operator submits a supported source command
- **THEN** the frontend SHALL use the canonical ingestion endpoint
- **AND** SHALL receive and observe a durable operation

#### Scenario: Candidate revision is promoted

- **GIVEN** rollback identity and command are recorded
- **AND** a clean pushed revision passed `frontend-release`
- **WHEN** Railway deploys that revision
- **THEN** deployment/build evidence SHALL identify the same revision,
  lockfile, install command, and Node 22 runtime

#### Scenario: Retired routes remain unused

- **WHEN** bounded production logs for the verification window are inspected
- **THEN** they SHALL contain no frontend POST to
  `/api/v1/contents/ingest`
- **AND** no frontend POST to `/api/v1/content/save-url`
