# Tasks: Local Test Profile

## Phase 1: Test Profile and Port Allocation

- [ ] 1.1 Write tests for test profile loading — verify auth disabled, DB URL, worker disabled
  **Spec scenarios**: Test Profile (all 4 scenarios)
  **Design decisions**: D4 (empty-string override)
  **Dependencies**: None

- [ ] 1.2 Create `profiles/test.yaml` — extends local, no auth, dedicated DB, noop observability
  **Dependencies**: 1.1

- [ ] 1.3 Write tests for port allocator — hash-based allocation, coordinator integration, main repo default, service offsets (API, frontend, Neo4j bolt, Neo4j HTTP)
  **Spec scenarios**: Port Allocation (all 3 scenarios)
  **Design decisions**: D1 (hash-based over random)
  **Dependencies**: None

- [ ] 1.4 Create `tests/e2e/port_allocator.py` — coordinator + hash fallback with service offset table (API +0, frontend +1000, Neo4j bolt +2000, Neo4j HTTP +2001)
  **Dependencies**: 1.3

## Phase 2: Server Lifecycle Fixture

- [ ] 2.1 Write tests for server fixture — startup, teardown, health check, E2E_BASE_URL skip, failure handling
  **Spec scenarios**: Subprocess Server Lifecycle (all 4 scenarios)
  **Design decisions**: D2 (Alembic), D5 (session-scoped)
  **Dependencies**: 1.2, 1.4

- [ ] 2.2 Create `tests/e2e/server_fixture.py` — session-scoped fixture managing uvicorn + vite subprocesses + Neo4j Docker container
  **Spec scenarios**: Test Neo4j Instance (both scenarios)
  **Design decisions**: D7 (dedicated test Neo4j)
  **Dependencies**: 2.1

- [ ] 2.3 Create seed data fixture file `tests/e2e/fixtures/seed_data.sql`
  **Spec scenarios**: Test Data Seeding (both scenarios)
  **Design decisions**: D3 (DB import over API ingestion)
  **Dependencies**: None

## Phase 3: E2E Conftest Integration

- [ ] 3.1 Write integration test verifying server fixture provides working http_client
  **Spec scenarios**: Server starts automatically, Server skipped when E2E_BASE_URL set
  **Dependencies**: 2.2, 2.3

- [ ] 3.2 Update `tests/e2e/conftest.py` — wire server fixture into http_client and api_client
  **Dependencies**: 3.1

- [ ] 3.3 Update existing E2E tests to work with managed server (remove hardcoded port assumptions)
  **Dependencies**: 3.2

## Phase 4: Docker Compose Validation Stack

- [ ] 4.1 Create `docker-compose.test.yml` — PostgreSQL + API + frontend containers with test profile
  **Spec scenarios**: Docker Compose Test Stack (both scenarios)
  **Design decisions**: D6 (full-stack)
  **Dependencies**: 1.2

- [ ] 4.2 Add Makefile targets: `test-e2e` (subprocess) and `test-e2e-docker` (Docker stack)
  **Spec scenarios**: Makefile Integration (both scenarios)
  **Dependencies**: 3.2, 4.1

## Phase 5: Documentation and Validation

- [ ] 5.1 Update `docs/TESTING.md` — add E2E server fixture usage, test-e2e targets, troubleshooting
  **Dependencies**: 4.2

- [ ] 5.2 Run full E2E suite against subprocess server — verify all tests pass
  **Dependencies**: 3.3

- [ ] 5.3 Run full E2E suite against Docker stack — verify all tests pass
  **Dependencies**: 4.2
