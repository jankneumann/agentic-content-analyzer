# E2E Test Infrastructure — Delta Spec

Extends: `openspec/specs/e2e-testing/spec.md`, `openspec/specs/test-infrastructure/spec.md`

## ADDED Requirements

### Requirement: Test Profile

#### Scenario: Profile disables authentication
WHEN the application starts with `PROFILE=test`
THEN the `app_secret_key` setting SHALL be empty
AND the `admin_api_key` setting SHALL be empty
AND the auth middleware SHALL allow all local requests without credentials

#### Scenario: Profile uses dedicated test database
WHEN the application starts with `PROFILE=test`
THEN the `database_url` setting SHALL point to a database containing "e2e" in the name
AND the database SHALL be separate from the development database

#### Scenario: Profile disables background worker
WHEN the application starts with `PROFILE=test`
THEN the `worker_enabled` setting SHALL be false
AND no background job processing SHALL occur

#### Scenario: Profile uses noop observability
WHEN the application starts with `PROFILE=test`
THEN the observability provider SHALL be `noop`
AND no traces or metrics SHALL be exported

### Requirement: Subprocess Server Lifecycle

#### Scenario: Server starts automatically on test session
WHEN `pytest tests/e2e/` is invoked
AND no `E2E_BASE_URL` environment variable is set
THEN the fixture SHALL create the test database if it does not exist
AND the fixture SHALL run `alembic upgrade head` against the test database
AND the fixture SHALL seed test data via DB import
AND the fixture SHALL start a uvicorn process with `PROFILE=test` on an allocated port
AND the fixture SHALL start a vite process on a separate allocated port
AND the fixture SHALL wait for the health endpoint to return 200

#### Scenario: Server skipped when E2E_BASE_URL is set
WHEN `pytest tests/e2e/` is invoked
AND the `E2E_BASE_URL` environment variable is set
THEN the fixture SHALL NOT start any server processes
AND the fixture SHALL use the provided URL for all API requests

#### Scenario: Server teardown on session end
WHEN the pytest session ends
THEN the fixture SHALL terminate the uvicorn process
AND the fixture SHALL terminate the vite process
AND the fixture SHALL release any coordinator-allocated ports

#### Scenario: Startup failure produces clear error
WHEN the uvicorn process fails to start within 15 seconds
THEN the fixture SHALL collect the process stderr
AND the fixture SHALL skip all E2E tests with a message including the error output

### Requirement: Port Allocation

#### Scenario: Coordinator port allocation
WHEN the coordinator MCP server is available
THEN the fixture SHALL call `allocate_ports` with a session identifier
AND the fixture SHALL use the returned `api_port` for uvicorn
AND the fixture SHALL use a derived port for vite (api_port + 1000)

#### Scenario: Hash-based fallback ports
WHEN the coordinator is NOT available
AND the test is running in a git worktree
THEN the base port SHALL be `hash(worktree_name) % 1000 + 9000`
AND the API port SHALL be base port + 0
AND the frontend port SHALL be base port + 1000
AND the Neo4j bolt port SHALL be base port + 2000
AND the Neo4j HTTP port SHALL be base port + 2001

#### Scenario: Default ports for main repo
WHEN the coordinator is NOT available
AND the test is running in the main repository (not a worktree)
THEN the base port SHALL be 9100
AND ports SHALL follow the same offset scheme as worktree allocation

### Requirement: Test Data Seeding

#### Scenario: Seed data on fresh database
WHEN the test database has been migrated but contains no content
THEN the fixture SHALL import seed data from a fixture file
AND the seeded data SHALL include at least 3 content items with different source types
AND the seeded data SHALL include at least 1 summary

#### Scenario: Skip seeding on populated database
WHEN the test database already contains content items
THEN the fixture SHALL NOT import additional seed data

### Requirement: Test Neo4j Instance

#### Scenario: Dedicated Neo4j for E2E
WHEN the subprocess server fixture starts
THEN a Neo4j Docker container SHALL be started on the allocated bolt port
AND the test profile SHALL configure `neo4j_uri` to point to the test instance
AND the container SHALL use neo4j Community edition

#### Scenario: Neo4j cleanup between sessions
WHEN the test session ends
THEN the Neo4j test container SHALL be stopped
AND all graph data SHALL be removed

### Requirement: Docker Compose Test Stack

#### Scenario: Docker stack starts with test profile
WHEN `make test-e2e-docker` is invoked
THEN docker compose SHALL start PostgreSQL, API, and frontend containers
AND the API container SHALL use `PROFILE=test`
AND the containers SHALL use ports that do not conflict with the development stack

#### Scenario: Docker stack teardown
WHEN `make test-e2e-docker` completes (pass or fail)
THEN docker compose SHALL stop and remove all test containers
AND test volumes SHALL be removed

### Requirement: Makefile Integration

#### Scenario: Subprocess E2E target
WHEN `make test-e2e` is invoked
THEN pytest SHALL run `tests/e2e/` with the subprocess server fixture
AND the exit code SHALL reflect the test results

#### Scenario: Docker E2E target
WHEN `make test-e2e-docker` is invoked
THEN the Docker Compose test stack SHALL start
AND pytest SHALL run inside or against the containerized stack
AND the stack SHALL be torn down after tests complete
