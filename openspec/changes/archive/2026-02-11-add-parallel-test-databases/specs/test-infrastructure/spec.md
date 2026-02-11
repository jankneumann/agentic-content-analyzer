## ADDED Requirements

### Requirement: Test Database Auto-Provisioning

The system SHALL automatically create the test database when tests are run, without requiring manual setup steps.

#### Scenario: Auto-create on first test run
- **GIVEN** the test database does not exist in PostgreSQL
- **WHEN** `pytest tests/api/` is run
- **THEN** the system SHALL create the test database automatically via an admin connection to the `postgres` database
- **AND** create all tables from ORM metadata

#### Scenario: Docker init creates default test DB
- **GIVEN** the postgres Docker container starts for the first time
- **WHEN** initialization scripts execute
- **THEN** the `newsletters_test` database SHALL be created automatically

#### Scenario: Existing database is reused
- **GIVEN** the test database already exists
- **WHEN** `pytest tests/api/` is run
- **THEN** the system SHALL reuse the existing database without error
- **AND** drop and recreate tables for a clean state

#### Scenario: Explicit URL override
- **GIVEN** `TEST_DATABASE_URL` environment variable is set
- **WHEN** tests are run
- **THEN** the system SHALL use the explicit URL regardless of worktree detection

#### Scenario: Admin connection failure
- **GIVEN** the test database does not exist
- **AND** the admin connection to the `postgres` database fails (e.g., permission denied)
- **WHEN** `pytest tests/api/` is run
- **THEN** the system SHALL raise an error with a clear message indicating the auto-create failed
- **AND** suggest running `make test-setup` as a manual fallback

### Requirement: Worktree-Aware Test Isolation

The system SHALL derive unique test database names per git worktree to enable parallel test execution from different feature branches.

#### Scenario: Main repo uses default name
- **GIVEN** tests run from the main repository (not a worktree)
- **WHEN** the test database name is resolved
- **THEN** the name SHALL be `newsletters_test`

#### Scenario: Worktree uses suffixed name
- **GIVEN** tests run from a git worktree named `add-document-search`
- **WHEN** the test database name is resolved
- **THEN** the name SHALL be `newsletters_test_add_document_search`

#### Scenario: Parallel execution safety
- **GIVEN** two worktrees run `pytest tests/api/` simultaneously
- **WHEN** both test sessions execute
- **THEN** each SHALL use its own isolated test database
- **AND** neither session SHALL interfere with the other

#### Scenario: Database name sanitization
- **GIVEN** a worktree name contains special characters (e.g., `feature/add-auth`)
- **WHEN** the test database name is derived
- **THEN** the name SHALL be sanitized to valid PostgreSQL identifier characters (lowercase alphanumeric and underscore)

#### Scenario: Long worktree name truncation
- **GIVEN** a worktree name that would produce a database name exceeding 63 characters
- **WHEN** the test database name is derived
- **THEN** the suffix SHALL be truncated so the total name fits within PostgreSQL's 63-character identifier limit

#### Scenario: Worktree detection failure fallback
- **GIVEN** the `.git` file exists but cannot be read or parsed (e.g., corrupted, permission denied)
- **WHEN** the worktree name is resolved
- **THEN** the system SHALL fall back to the default `newsletters_test` name
- **AND** SHALL NOT raise an error

### Requirement: Shared Test Database Helper

The system SHALL provide a centralized helper module for test database configuration, eliminating duplication across conftest files.

#### Scenario: Single source of truth for test DB URL
- **GIVEN** `tests/helpers/test_db.py` exists
- **WHEN** any conftest file needs the test database URL
- **THEN** it SHALL import from `tests.helpers.test_db` instead of defining its own `TEST_DATABASE_URL`

#### Scenario: Safety check prevents production use
- **GIVEN** the resolved database name
- **WHEN** the name does not contain the string `test`
- **THEN** the system SHALL raise a `ValueError` and refuse to proceed

## MODIFIED Requirements

### Requirement: Database Isolation

The system SHALL isolate database state between tests and between concurrent test runs from different worktrees.

#### Scenario: Transaction rollback
- **GIVEN** a test creates database records
- **WHEN** the test completes
- **THEN** all created records SHALL be rolled back

#### Scenario: Parallel test safety
- **GIVEN** tests run in parallel
- **WHEN** each test uses `db_session` fixture
- **THEN** tests SHALL not interfere with each other

#### Scenario: Cross-worktree isolation
- **GIVEN** two git worktrees run test suites concurrently
- **WHEN** each test session starts
- **THEN** each SHALL connect to a distinct test database derived from the worktree name
- **AND** session-scoped `drop_all`/`create_all` SHALL not affect other worktrees

#### Scenario: Neo4j graceful degradation
- **GIVEN** the Neo4j test instance is unavailable or shared between worktrees
- **WHEN** integration tests start
- **THEN** the `neo4j_driver` fixture SHALL yield `None`
- **AND** tests that mock `GraphitiClient` SHALL still pass
- **AND** a warning SHALL be logged when worktree detection indicates potential port collision
