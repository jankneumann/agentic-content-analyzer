# test-infrastructure Specification

## Purpose
TBD - created by archiving change add-test-infrastructure. Update Purpose after archive.
## Requirements
### Requirement: Model Factories

The system SHALL provide factory classes for test data generation.

#### Scenario: Create content with factory
- **GIVEN** ContentFactory is available
- **WHEN** `ContentFactory()` is called
- **THEN** a Content instance SHALL be created with valid default values

#### Scenario: Factory traits
- **GIVEN** ContentFactory with `pending` trait
- **WHEN** `ContentFactory(pending=True)` is called
- **THEN** Content SHALL have `status=PENDING`

### Requirement: Database Isolation

The system SHALL isolate database state between tests.

#### Scenario: Transaction rollback
- **GIVEN** a test creates database records
- **WHEN** the test completes
- **THEN** all created records SHALL be rolled back

#### Scenario: Parallel test safety
- **GIVEN** tests run in parallel
- **WHEN** each test uses `db_session` fixture
- **THEN** tests SHALL not interfere with each other

### Requirement: Test Categorization

The system SHALL support categorizing tests with markers.

#### Scenario: Unit test marker
- **GIVEN** a test marked with `@pytest.mark.unit`
- **WHEN** `pytest -m unit` is run
- **THEN** only unit tests SHALL execute

#### Scenario: Integration test marker
- **GIVEN** a test marked with `@pytest.mark.integration`
- **WHEN** `pytest -m integration` is run
- **THEN** only integration tests SHALL execute

### Requirement: HTTP Simulation Integration

The system SHALL integrate with Hoverfly for HTTP mocking.

#### Scenario: Hoverfly proxy fixture
- **GIVEN** Hoverfly is running
- **WHEN** `http_client` fixture is used
- **THEN** HTTP requests SHALL route through Hoverfly

#### Scenario: Simulation loading
- **GIVEN** simulation files exist in fixtures
- **WHEN** integration tests run
- **THEN** Hoverfly SHALL return recorded responses
