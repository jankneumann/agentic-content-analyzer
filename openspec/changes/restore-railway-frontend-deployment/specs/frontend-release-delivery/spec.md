# frontend-release-delivery Specification

## ADDED Requirements

### Requirement: Reproducible isolated frontend build

The Railway frontend service SHALL build from its checked-in isolated service
configuration using only tools and files present in the frontend build
context. Dependency resolution MUST use a committed lockfile, and the
production build MUST NOT invoke repository-level Python contract generation.
The package and CI workflow MUST declare the same Node 22 major used by the
Railway build.

#### Scenario: Clean Railway build

- **GIVEN** the Railway service root is `/web`
- **WHEN** Railpack installs dependencies and runs the production build
- **THEN** dependency installation uses the committed frontend lockfile
- **AND** the build uses package-local TypeScript and Vite binaries
- **AND** the package declares Node 22 as its supported runtime
- **AND** it succeeds without pnpm, Python, or uv in the image

#### Scenario: Production build stays toolchain-local

- **WHEN** the frontend production build script is inspected
- **THEN** it does not invoke `pnpm`
- **AND** it does not invoke `uv`
- **AND** it does not invoke the workflow-contract generator

### Requirement: CI frontend release parity

CI SHALL run the generated workflow-contract drift check and the exact
production frontend build in a full repository checkout under Node 22. It SHALL
also run the focused workflow-client contract test non-interactively. Any
failure MUST fail the `frontend-release` job.

#### Scenario: Generated contracts drift

- **WHEN** generated frontend workflow models differ from canonical contracts
- **THEN** the frontend CI job fails before reporting the release gate as
  successful

#### Scenario: Production frontend does not compile

- **WHEN** a clean locked dependency install cannot build the frontend
- **THEN** the frontend CI job fails

#### Scenario: Both release boundaries pass

- **WHEN** generated contracts are current
- **AND** the locked production frontend build succeeds
- **AND** the focused workflow-client contract test succeeds
- **THEN** the frontend CI release gate succeeds

### Requirement: Canonical production ingestion frontend

The active production frontend SHALL discover ingestion capabilities and
submit ingestion through `POST /api/v1/ingestions`. It MUST NOT submit
ingestion through `POST /api/v1/contents/ingest` or
`POST /api/v1/content/save-url`. Production promotion MUST use the exact clean,
pushed revision that passed the `frontend-release` CI job, and rollback data
MUST be captured before deployment.

#### Scenario: Production ingestion surface loads

- **WHEN** an operator opens the production ingestion route
- **THEN** the frontend requests `/api/v1/capabilities`
- **AND** renders source options from the returned capability document

#### Scenario: Production ingestion is submitted

- **WHEN** the operator submits a supported source command
- **THEN** the frontend sends `POST /api/v1/ingestions`
- **AND** receives the canonical durable operation response
- **AND** evidence records the request status, operation identifier, and
  terminal operation status

#### Scenario: Candidate revision is promoted

- **GIVEN** the current deployment, last successful deployment, public domain,
  target identifiers, and rollback command have been captured
- **AND** a clean pushed commit has a successful `frontend-release` check
- **WHEN** the frontend is deployed
- **THEN** Railway reports that exact commit revision as active
- **AND** the prior successful deployment remains available for rollback

#### Scenario: Retired mutation routes remain unused

- **WHEN** bounded production HTTP logs are inspected for the verification
  window
- **THEN** no frontend request uses `POST /api/v1/contents/ingest`
- **AND** no frontend request uses `POST /api/v1/content/save-url`
