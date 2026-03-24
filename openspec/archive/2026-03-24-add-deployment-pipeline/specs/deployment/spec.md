# Deployment Pipeline Capability

## EXISTING Requirements (already implemented in ci.yml)

### Requirement: CI Quality Gates

The system SHALL enforce quality gates on pull requests.

#### Scenario: Linting check
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs
- **THEN** ruff linting and formatting checks SHALL pass

#### Scenario: Alembic single head
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs
- **THEN** Alembic SHALL have exactly one migration head

#### Scenario: Test suite
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs with PostgreSQL service container
- **THEN** pytest SHALL pass against a real database

#### Scenario: Contract and fuzz tests
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs
- **THEN** Schemathesis contract and fuzz tests SHALL pass against the OpenAPI schema

#### Scenario: Profile validation
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs
- **THEN** all profiles in `profiles/*.yaml` SHALL validate without errors
- **AND** no hardcoded secrets SHALL be present in profile files

## ADDED Requirements

### Requirement: Type Checking in CI

The system SHALL enforce type checking on pull requests.

#### Scenario: mypy check
- **GIVEN** a pull request is created or updated
- **WHEN** CI runs
- **THEN** mypy type checking SHALL pass for `src/`

#### Scenario: mypy failure blocks merge
- **GIVEN** mypy reports type errors
- **WHEN** a developer attempts to merge
- **THEN** the merge SHALL be blocked by branch protection

### Requirement: Coverage Gate

The system SHALL enforce a minimum test coverage threshold.

#### Scenario: Coverage meets threshold
- **GIVEN** a pull request is created or updated
- **WHEN** pytest runs with `--cov --cov-fail-under=25`
- **THEN** line coverage SHALL be at least 25%
- **AND** a coverage summary SHALL be posted as a GitHub Actions job summary

#### Scenario: Coverage below threshold
- **GIVEN** line coverage drops below 25%
- **WHEN** CI runs
- **THEN** the pytest job SHALL fail with a non-zero exit code
- **AND** the job summary SHALL show current coverage percentage and the threshold

### Requirement: PostgreSQL Service Container

The system SHALL use ParadeDB as the PostgreSQL image for all environments.

#### Scenario: Service container in CI
- **GIVEN** CI runs test or contract-test jobs
- **WHEN** PostgreSQL service container starts
- **THEN** the image SHALL be `paradedb/paradedb` with a pinned version tag
- **AND** pgvector, pg_search, pg_cron, and pgmq extensions SHALL be available

#### Scenario: Local development
- **GIVEN** a developer runs `docker compose up`
- **WHEN** the postgres service starts
- **THEN** the image SHALL be `paradedb/paradedb` with the same pinned version tag as CI

#### Scenario: ParadeDB image unavailable
- **GIVEN** the `paradedb/paradedb` image cannot be pulled
- **WHEN** CI or docker compose attempts to start PostgreSQL
- **THEN** the job or service SHALL fail with a clear image pull error
- **AND** the pinned version tag SHALL be documented in CLAUDE.md for manual fallback

#### Scenario: Extension availability verification
- **GIVEN** PostgreSQL starts with the ParadeDB image
- **WHEN** migrations run
- **THEN** `CREATE EXTENSION IF NOT EXISTS pgvector` SHALL succeed
- **AND** `CREATE EXTENSION IF NOT EXISTS pg_search` SHALL succeed
- **AND** `CREATE EXTENSION IF NOT EXISTS pg_cron` SHALL succeed

### Requirement: Continuous Deployment

The system SHALL deploy automatically to staging and with approval to production.

#### Scenario: Staging deployment on merge
- **GIVEN** a PR is merged to main
- **AND** CI has passed
- **WHEN** the CD pipeline runs
- **THEN** Alembic migrations SHALL run against the staging database
- **AND** the `alembic_version` table SHALL reflect the latest migration revision
- **AND** the application SHALL be deployed to Railway staging environment
- **AND** an HTTP GET to the staging `/health` endpoint SHALL return 200 within 3 minutes

#### Scenario: Staging migration failure
- **GIVEN** Alembic migration fails against staging
- **WHEN** the CD pipeline processes the migration step
- **THEN** deployment SHALL be aborted
- **AND** the failure SHALL be reported in the workflow summary

#### Scenario: Production deployment with approval
- **GIVEN** staging deployment has succeeded
- **WHEN** production deployment is triggered
- **THEN** manual approval SHALL be required from a designated reviewer
- **AND** Alembic migrations SHALL run before deployment

#### Scenario: Production migration failure
- **GIVEN** Alembic migration fails against production
- **WHEN** the CD pipeline processes the migration step
- **THEN** deployment SHALL be aborted
- **AND** the failure SHALL be reported and alert the team

### Requirement: Dependency Management

The system SHALL automate dependency update tracking.

#### Scenario: Dependabot creates PR
- **GIVEN** a dependency has a newer version available
- **WHEN** Dependabot runs on its weekly schedule
- **THEN** a pull request SHALL be created with the version update
- **AND** CI SHALL run automatically on the PR

#### Scenario: Security vulnerability detected
- **GIVEN** a dependency has a known CVE
- **WHEN** Dependabot detects the vulnerability
- **THEN** a security PR SHALL be created
- **AND** the PR SHALL be flagged as security-related

### Requirement: Branch Protection

The system SHALL enforce branch protection on the main branch.

#### Scenario: CI required for merge
- **GIVEN** a pull request targets main
- **WHEN** a developer attempts to merge
- **THEN** all CI jobs SHALL have passed

#### Scenario: Review required for merge
- **GIVEN** a pull request targets main
- **WHEN** a developer attempts to merge
- **THEN** at least one approval SHALL be required
