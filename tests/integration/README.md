# Integration Tests

Integration tests for the newsletter aggregator core pipeline. These tests verify end-to-end workflows with real database operations.

## Overview

Integration tests cover:
- **Newsletter Summarization**: End-to-end summarization workflow with database storage
- **Theme Analysis**: Multi-newsletter theme extraction with Graphiti integration
- **Hoverfly API Simulation**: HTTP-level testing with simulated external APIs
- **Digest Generation**: Full digest creation pipeline (coming soon)
- **Knowledge Graph**: Entity extraction and historical context (coming soon)

## Setup

### 1. Prerequisites

Ensure these services are running:
```bash
docker compose up -d postgres neo4j
```

### 2. Create Test Database

Run the setup script to create and initialize the test database:
```bash
python scripts/setup_test_db.py
```

This will:
- Create `newsletters_test` database
- Run migrations
- Verify setup

### 3. Configure Environment (Optional)

The default test database URL is:
```
postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters_test
```

To override, set the environment variable:
```bash
export TEST_DATABASE_URL=postgresql://user:pass@host:port/newsletters_test
```

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/ -v
```

### Run Specific Test File
```bash
pytest tests/integration/test_summarization_workflow.py -v
```

### Run Specific Test
```bash
pytest tests/integration/test_summarization_workflow.py::test_summarize_newsletter_success -v
```

### Run with Coverage
```bash
pytest tests/integration/ --cov=src --cov-report=term-missing
```

## Database Isolation

Integration tests use a **separate test database** to ensure:
- ✅ No impact on development database
- ✅ Safe to run tests while developing
- ✅ Test data is isolated
- ✅ Each test runs in a transaction (rolled back after test)

### Safety Mechanisms

1. **Separate Database**: `newsletters_test` vs `newsletters`
2. **Name Check**: Tests verify database name contains "test"
3. **Transaction Rollback**: Each test's changes are rolled back
4. **No Cross-Contamination**: Tests don't affect each other

## Test Structure

### Fixtures (conftest.py)

- `test_db_engine`: Session-scoped database engine
- `db_session`: Test-scoped session with transaction rollback
- `sample_newsletters`: Sample newsletter data
- `sample_summaries`: Sample summary data
- `mock_anthropic_client`: Mock LLM API client
- `mock_graphiti_client`: Mock knowledge graph client

### Test Files

- `test_summarization_workflow.py`: Newsletter summarization end-to-end
- `test_theme_analysis_workflow.py`: Theme analysis with database
- More coming soon...

## Mocking Strategy

Integration tests mock **external services only**:
- ✅ **Real Database**: PostgreSQL operations
- ✅ **Real Transactions**: Commit/rollback behavior
- ✅ **Real HTTP (Hoverfly)**: HTTP-level behavior via simulated responses
- ❌ **Mocked LLM API**: No actual API calls (cost/speed)
- ❌ **Mocked Graphiti**: Simulated knowledge graph responses

This ensures we test:
- Database operations
- Business logic
- Error handling
- Status transitions
- HTTP request/response behavior (headers, status codes, content types)

Without:
- API costs
- External dependencies
- Slow API calls

## Hoverfly API Simulation

Hoverfly provides HTTP-level testing by acting as a simulated webserver. Unlike
unit test mocks that patch at the Python level, Hoverfly tests real HTTP behavior:
headers, content negotiation, error codes, and response formats.

### When to Use Hoverfly vs Mocks

| Scenario | Use Hoverfly | Use Mocks |
|----------|-------------|-----------|
| HTTP status code handling | Yes | No |
| Response header parsing | Yes | No |
| Content-Type negotiation | Yes | No |
| Business logic with DB | No | Yes |
| LLM response processing | No | Yes |
| Fast unit tests | No | Yes |

### Quick Start

```bash
# Start Hoverfly
make hoverfly-up

# Run Hoverfly tests only
make test-hoverfly

# Stop Hoverfly
make hoverfly-down
```

### Writing Hoverfly Tests

```python
import httpx
import pytest

SIMULATIONS_DIR = Path(__file__).parent / "fixtures" / "simulations"

@pytest.mark.hoverfly
@pytest.mark.integration
def test_my_http_feature(hoverfly, hoverfly_url):
    """Test HTTP behavior with simulated responses."""
    # Load simulation (reset automatically after each test)
    hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

    # Make real HTTP request to Hoverfly webserver
    response = httpx.get(f"{hoverfly_url}/feed")

    # Assert on HTTP-level behavior
    assert response.status_code == 200
    assert "application/rss+xml" in response.headers["content-type"]
```

### Creating Simulations

Simulations are JSON files stored in `tests/integration/fixtures/simulations/`.
They follow the [Hoverfly v5 schema](https://docs.hoverfly.io/en/latest/pages/reference/simulationschema.html).

**Option 1: Manual creation** - Write JSON matching request/response pairs:
```json
{
  "data": {
    "pairs": [{
      "request": {
        "path": [{"matcher": "exact", "value": "/feed"}],
        "method": [{"matcher": "exact", "value": "GET"}]
      },
      "response": {
        "status": 200,
        "body": "...",
        "headers": {"Content-Type": ["application/rss+xml"]}
      }
    }]
  },
  "meta": {"schemaVersion": "v5"}
}
```

**Option 2: Capture mode** - Record real API responses. Capture requires
restarting Hoverfly in proxy mode (the default `docker-compose.yml` runs
webserver mode, which has no upstream to record from):
```bash
# Stop webserver-mode instance
make hoverfly-down

# Start Hoverfly in proxy mode (remove -webserver flag)
docker compose --profile test run -d --name newsletter-hoverfly-capture \
  -p 8500:8500 -p 8888:8888 hoverfly

# Switch to capture mode
curl -X PUT http://localhost:8888/api/v2/hoverfly/mode -d '{"mode":"capture"}'

# Make requests through the proxy
HTTP_PROXY=http://localhost:8500 curl http://real-api-endpoint/feed

# Export recorded simulation
curl -s http://localhost:8888/api/v2/simulation | python3 -m json.tool > simulation.json

# Clean up and restart webserver mode
docker rm -f newsletter-hoverfly-capture
make hoverfly-up
```

### Available Fixtures

| Fixture | Scope | Description |
|---------|-------|-------------|
| `hoverfly_available` | session | `True` if Hoverfly is running |
| `requires_hoverfly` | function | Auto-skip `@pytest.mark.hoverfly` tests if down |
| `hoverfly` | function | `HoverflyClient` instance (auto-cleanup) |
| `hoverfly_url` | function | Base URL for HTTP requests (`http://localhost:8500`) |

### Simulation Files

| File | Description |
|------|-------------|
| `rss_feed.json` | RSS feed responses: valid feed, empty feed, 500 error, 404 |

## Troubleshooting

### Test Database Doesn't Exist
```bash
python scripts/setup_test_db.py
```

### PostgreSQL Not Running
```bash
docker compose up -d postgres
```

### Permission Denied
Ensure the database user has CREATE DATABASE permission:
```sql
ALTER USER newsletter_user CREATEDB;
```

### Clean Reset
```bash
# Drop and recreate test database
dropdb newsletters_test
python scripts/setup_test_db.py
```

## Adding New Integration Tests

1. Create test file in `tests/integration/`
2. Use `@pytest.mark.integration` decorator
3. Use fixtures from `conftest.py`
4. Mock external services (LLM, Graphiti)
5. Test with real database operations

Example:
```python
import pytest

@pytest.mark.integration
def test_my_workflow(db_session, sample_newsletters):
    """Test my workflow end-to-end."""
    # Use db_session for database operations
    # Changes will be rolled back after test
    pass
```

## CI/CD Integration

For continuous integration:

```yaml
# Example GitHub Actions
- name: Setup test database
  run: |
    docker compose up -d postgres
    python scripts/setup_test_db.py

- name: Run integration tests
  run: pytest tests/integration/ -v
```

## Performance

Integration tests are slower than unit tests due to database operations:
- **Unit tests**: ~1s for full suite
- **Integration tests**: ~10-30s for full suite

Optimize by:
- Running unit tests during development
- Running integration tests before commit/push
- Using CI/CD for full integration test suite
