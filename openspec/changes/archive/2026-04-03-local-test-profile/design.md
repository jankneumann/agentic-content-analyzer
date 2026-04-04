# Design: Local Test Profile with Isolated Full-Stack Server

## Architecture Decisions

### D1: Hash-based port allocation over random ephemeral ports

Ports are derived deterministically from the git worktree name: `hash(name) % 1000 + 9000`. This ensures the same worktree always gets the same port (debuggable, bookmarkable) while avoiding collisions across worktrees. When the coordinator MCP is available, its `allocate_ports` takes precedence for guaranteed conflict-free allocation.

All services use the same base offset: API, frontend, Neo4j bolt, and Neo4j HTTP all derive from `hash(worktree_name) % 1000 + 9000` with fixed offsets per service type.

| Service | Offset from base | Main repo default |
|---------|-----------------|-------------------|
| API (uvicorn) | +0 | 9100 |
| Frontend (vite) | +1000 | 10100 |
| Neo4j bolt | +2000 | 11100 |
| Neo4j HTTP | +2001 | 11101 |

**Rejected**: Random ephemeral ports (port 0) — changes every run, breaks bookmarks/curl history, harder to debug.

### D2: Alembic migrations over ORM metadata.create_all()

The test DB schema must match production exactly. Alembic migrations capture triggers, raw SQL columns (pgvector embeddings), partial indexes, and enum types that `Base.metadata.create_all()` misses. The contract tests already prove this pattern works (`tests/contract/conftest.py`).

**Trade-off**: ~2s slower per fresh session, but catches migration bugs that unit tests miss.

### D3: DB export/import for seeding over API-based ingestion

Test data is seeded via the existing `aca manage export`/`aca manage import` facilities (or direct SQL fixtures). This avoids external network dependencies (URL fetching) and is deterministic.

**Fixture file**: `tests/e2e/fixtures/seed_data.sql` (or JSONL via existing export format).

### D4: Profile empty-string override for auth suppression

The test profile sets `admin_api_key: ""` and `app_secret_key: ""`. Due to the profile interpolation behavior (empty env vars override `${VAR:-default}`), these empty strings win over any value in `.secrets.yaml`. The auth middleware checks `keys_configured = settings.app_secret_key or settings.admin_api_key` — empty strings are falsy, so auth is bypassed in dev mode.

### D5: Session-scoped fixture over module-scoped

The server fixture is session-scoped (one server per pytest run) rather than module-scoped (one per test file). This avoids repeated startup/teardown overhead. Tests that need a clean DB state can truncate tables in a function-scoped fixture.

### D6: Vite subprocess for full-stack testing

The frontend dev server runs alongside the backend so Playwright E2E tests can exercise the real frontend. The vite process is configured with `VITE_API_URL` pointing to the test backend port.

## Component Interactions

```
pytest session
    |
    v
ServerFixture (session-scoped)
    |-- allocate_ports() --> coordinator MCP or hash fallback
    |-- ensure_test_db_exists() --> tests/helpers/test_db.py
    |-- alembic upgrade head --> subprocess (DATABASE_URL=test_db)
    |-- seed_test_data() --> SQL fixture import
    |-- start_uvicorn() --> subprocess (PROFILE=test, PORT=api_port)
    |-- start_vite() --> subprocess (VITE_API_URL=http://localhost:api_port)
    |-- poll_health() --> GET http://localhost:api_port/health
    |
    v
yields TestServerInfo(api_url, frontend_url, db_url)
    |
    v
http_client fixture --> httpx.Client(base_url=api_url)
api_client fixture --> ApiClient(base_url=api_url)
    |
    v
test functions run
    |
    v
teardown: kill uvicorn, kill vite, release_ports()
```

### D7: Lazy Neo4j with hash-based port

Neo4j is **on-demand** — the container only starts when a test explicitly requests the `neo4j_test_instance` fixture. Tests that only exercise basic pipeline flows (ingest, summarize, digest) never spin up Neo4j, keeping the default E2E run fast (~5s startup).

When started, the container uses the same hash-based port scheme as other services (bolt: base+2000, HTTP: base+2001).

**Triggering Neo4j**:
- Individual test: `def test_theme_graph(neo4j_test_instance, http_client): ...`
- Full validation: `pytest tests/e2e/ --with-neo4j` (custom pytest option)
- Docker mode: always included in `docker-compose.test.yml`

This mirrors the existing `@pytest.mark.integration` skip pattern — tests declare dependencies, the infrastructure satisfies them lazily.

## Docker Compose Test Stack (Validation Mode)

```yaml
# docker-compose.test.yml
services:
  test-postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: newsletter_user
      POSTGRES_PASSWORD: newsletter_password
      POSTGRES_DB: newsletters_e2e
    ports:
      - "${TEST_DB_PORT:-54320}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U newsletter_user -d newsletters_e2e"]
      interval: 2s
      timeout: 5s
      retries: 10

  test-neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/newsletter_password
    ports:
      - "${TEST_NEO4J_BOLT_PORT:-11100}:7687"
      - "${TEST_NEO4J_HTTP_PORT:-11101}:7474"
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "newsletter_password", "RETURN 1"]
      interval: 5s
      timeout: 10s
      retries: 10

  test-api:
    build: .
    environment:
      PROFILE: test
      DATABASE_URL: postgresql://newsletter_user:newsletter_password@test-postgres/newsletters_e2e
      NEO4J_URI: bolt://test-neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: newsletter_password
      PORT: "8000"
    ports:
      - "${TEST_API_PORT:-9100}:8000"
    depends_on:
      test-postgres:
        condition: service_healthy
      test-neo4j:
        condition: service_healthy

  test-frontend:
    build:
      context: ./web
    environment:
      VITE_API_URL: http://test-api:8000
    ports:
      - "${TEST_FRONTEND_PORT:-10100}:5173"
    depends_on:
      - test-api
```

## File Layout

```
profiles/test.yaml                          # Test profile
tests/e2e/server_fixture.py                 # Server lifecycle fixture
tests/e2e/port_allocator.py                 # Port allocation (coordinator + hash fallback)
tests/e2e/fixtures/seed_data.sql            # Seed data for E2E tests
tests/e2e/conftest.py                       # Updated to use server fixture
docker-compose.test.yml                     # Docker validation stack
Makefile                                    # test-e2e and test-e2e-docker targets
```
