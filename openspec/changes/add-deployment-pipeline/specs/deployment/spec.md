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
- **WHEN** pytest runs with coverage
- **THEN** coverage SHALL be at least 25% (adjustable threshold)
- **AND** coverage report SHALL be visible in PR summary

#### Scenario: Coverage below threshold
- **GIVEN** test coverage drops below the configured threshold
- **WHEN** CI runs
- **THEN** the CI job SHALL fail
- **AND** the coverage delta SHALL be reported

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

### Requirement: Continuous Deployment

The system SHALL deploy automatically to staging and with approval to production.

#### Scenario: Staging deployment on merge
- **GIVEN** a PR is merged to main
- **AND** CI has passed
- **WHEN** the CD pipeline runs
- **THEN** Alembic migrations SHALL run against the staging database
- **AND** the application SHALL be deployed to Railway staging environment

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
