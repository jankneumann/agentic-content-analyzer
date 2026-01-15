# Deployment Pipeline Capability

## ADDED Requirements

### Requirement: CI Quality Gates

The system SHALL enforce quality gates on pull requests.

#### Scenario: Linting check
- **GIVEN** a pull request is created
- **WHEN** CI runs
- **THEN** ruff linting SHALL pass

#### Scenario: Type checking
- **GIVEN** a pull request is created
- **WHEN** CI runs
- **THEN** mypy type checking SHALL pass

#### Scenario: Test suite
- **GIVEN** a pull request is created
- **WHEN** CI runs
- **THEN** pytest SHALL pass with configured coverage threshold

### Requirement: Docker Build

The system SHALL produce Docker images automatically.

#### Scenario: Image build on merge
- **GIVEN** a PR is merged to main
- **WHEN** CD pipeline runs
- **THEN** Docker image SHALL be built
- **AND** image SHALL be pushed to ghcr.io

#### Scenario: Image tagging
- **WHEN** Docker image is built
- **THEN** image SHALL be tagged with commit SHA
- **AND** image SHALL be tagged with `latest`

### Requirement: Database Migrations

The system SHALL run migrations safely in CI.

#### Scenario: Staging migration
- **GIVEN** a new image is built
- **WHEN** staging deployment starts
- **THEN** Alembic migrations SHALL run first
- **AND** deployment SHALL proceed only if migrations succeed

#### Scenario: Production migration
- **GIVEN** staging deployment succeeded
- **WHEN** production deployment is approved
- **THEN** migrations SHALL run before deployment

### Requirement: Environment Management

The system SHALL support multiple deployment environments.

#### Scenario: Staging deployment
- **GIVEN** main branch is updated
- **WHEN** CD pipeline runs
- **THEN** staging SHALL be deployed automatically

#### Scenario: Production deployment
- **GIVEN** staging is deployed successfully
- **WHEN** production deployment is triggered
- **THEN** manual approval SHALL be required
