# Change: Add Test Infrastructure

## Why

The current test setup has gaps:
- **Critical**: Duplicate index definitions in Image model cause `DuplicateTable` errors
- **Critical**: Test database setup doesn't handle leftover data from interrupted runs
- No standardized fixtures for database models
- Factory patterns not established
- Integration tests rely on ad-hoc mocks
- Database state management inconsistent
- No clear separation between unit/integration/e2e tests

By adding test infrastructure:

1. **Consistent fixtures**: Reusable test data via factories
2. **Database isolation**: Clean state per test, transactions rollback
3. **HTTP simulation**: Hoverfly for external APIs (complementing existing proposal)
4. **Clear test taxonomy**: Unit, integration, e2e with appropriate runners
5. **CI-ready**: Tests run reliably in GitHub Actions

## Relationship to Hoverfly Proposal

The `add-hoverfly-api-simulation` proposal focuses on **HTTP-level simulation** for external services. This proposal provides the **broader test infrastructure** that Hoverfly fits into:

```
┌─────────────────────────────────────────────────────────────┐
│ add-test-infrastructure                                     │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Model Factories │ │ DB Fixtures     │ │ Test Taxonomy   ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ add-hoverfly-api-simulation                             ││
│ │ HTTP mocking for: RSS feeds, LLM APIs, TTS providers    ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## What Changes

### Bug Fix: Duplicate Index Definitions (Critical)

The `Image` model has both `index=True` on columns AND explicit `Index()` in `__table_args__`:

```python
# Line 106 - creates implicit index named 'ix_images_video_id'
video_id = Column(String(20), nullable=True, index=True)
# Line 132 - creates implicit index named 'ix_images_phash'
phash = Column(String(64), nullable=True, index=True)

# Lines 157-158 - explicit indexes with SAME names
__table_args__ = (
    Index("ix_images_phash", "phash"),      # CONFLICT
    Index("ix_images_video_id", "video_id"), # CONFLICT
)
```

**Fix**: Remove `index=True` from column definitions where explicit indexes exist.

### Bug Fix: Resilient Test Database Setup (Critical)

Current `test_db_engine` fixture fails if previous run was interrupted:
- `Base.metadata.create_all()` errors on existing indexes
- No recovery mechanism for stale state

**Fix**: Drop tables before creating them in the session-scoped fixture.

### Model Factories
- **NEW**: `tests/factories/` with factory_boy factories
- **NEW**: `ContentFactory`, `SummaryFactory`, `DigestFactory`
- **NEW**: Traits for different states (pending, completed, with_audio)

### Database Fixtures
- **NEW**: `tests/conftest.py` database session management
- **NEW**: Transaction-based isolation (rollback per test)
- **NEW**: `tests/fixtures/` for sample data files (JSON, markdown)

### Test Organization
- **MODIFIED**: `tests/unit/` for pure unit tests (no DB, no HTTP)
- **MODIFIED**: `tests/integration/` for component integration (with DB)
- **MODIFIED**: `tests/e2e/` for end-to-end API tests
- **NEW**: pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`

### CI Integration
- **NEW**: `pytest.ini` configuration for test categories
- **MODIFIED**: GitHub Actions to run tests by category

## Configuration

```ini
# pytest.ini
[pytest]
markers =
    unit: Pure unit tests (no external dependencies)
    integration: Tests requiring database
    e2e: End-to-end API tests
    slow: Tests that take >1s
testpaths = tests
addopts = -v --strict-markers
```

```python
# tests/factories/content.py
import factory
from src.models.content import Content, ContentSource, ContentStatus

class ContentFactory(factory.Factory):
    class Meta:
        model = Content

    title = factory.Faker('sentence')
    source_type = ContentSource.RSS
    status = ContentStatus.COMPLETED
    markdown_content = factory.Faker('text', max_nb_chars=1000)

    class Params:
        pending = factory.Trait(status=ContentStatus.PENDING)
        with_audio = factory.Trait(audio_url=factory.Faker('url'))
```

## Impact

- **New spec**: `test-infrastructure` - Testing patterns and fixtures
- **New code**:
  - `tests/factories/` - factory_boy factories
  - `tests/fixtures/` - Sample data files
  - `tests/conftest.py` - Shared fixtures
- **Modified**:
  - `pytest.ini` - Test configuration
  - `tests/` - Reorganize by test type
  - `pyproject.toml` - Add factory_boy dependency
- **Dependencies**: `factory_boy`, `pytest-factoryboy`

## Related Proposals

- **add-hoverfly-api-simulation**: HTTP simulation layer (subset of this infrastructure)
- **add-deployment-pipeline**: CI runs these tests
- **add-observability**: Telemetry disabled in tests

## Non-Goals

- Property-based testing (can add hypothesis later)
- Snapshot testing
- Visual regression testing
- Load/performance testing
