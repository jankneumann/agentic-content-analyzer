# Integration Tests

Integration tests for the newsletter aggregator core pipeline. These tests verify end-to-end workflows with real database operations.

## Overview

Integration tests cover:
- **Newsletter Summarization**: End-to-end summarization workflow with database storage
- **Theme Analysis**: Multi-newsletter theme extraction with Graphiti integration
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
- ❌ **Mocked LLM API**: No actual API calls (cost/speed)
- ❌ **Mocked Graphiti**: Simulated knowledge graph responses

This ensures we test:
- Database operations
- Business logic
- Error handling
- Status transitions

Without:
- API costs
- External dependencies
- Slow API calls

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
