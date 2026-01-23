# Implementation Tasks

## 0. Critical Bug Fixes (Blocking) ✅

### 0.1 Fix Duplicate Index Definitions in Image Model
- [x] 0.1.1 Remove `index=True` from `video_id` column (line 106) - explicit index exists in `__table_args__`
- [x] 0.1.2 Remove `index=True` from `phash` column (line 132) - explicit index exists in `__table_args__`
- [x] 0.1.3 Verify no other duplicate index definitions exist in codebase

### 0.2 Make Test Database Setup Resilient
- [x] 0.2.1 Update `tests/api/conftest.py` to drop tables before creating
- [x] 0.2.2 Update `tests/integration/conftest.py` to drop tables before creating
- [x] 0.2.3 Add safety check to prevent dropping non-test databases (existing check preserved)
- [x] 0.2.4 Verify all existing tests pass after fix (26 sorting tests pass, 198/212 API tests pass - 14 pre-existing failures in test_summary_api.py unrelated to infrastructure)

## 1. Setup Factory Boy

- [ ] 1.1 Add `factory_boy` to pyproject.toml dev dependencies
- [ ] 1.2 Add `pytest-factoryboy` for pytest integration
- [ ] 1.3 Create `tests/factories/__init__.py`
- [ ] 1.4 Create `tests/factories/content.py`:
  - ContentFactory with traits (pending, completed, with_audio)
- [ ] 1.5 Create `tests/factories/summary.py`:
  - SummaryFactory with content relationship
- [ ] 1.6 Create `tests/factories/digest.py`:
  - DigestFactory with traits (daily, weekly, with_sources)
- [ ] 1.7 Register factories in conftest.py

## 2. Database Fixtures

- [ ] 2.1 Update `tests/conftest.py` with transaction rollback fixture
- [ ] 2.2 Create `db_session` fixture with auto-rollback
- [ ] 2.3 Create `db_engine` fixture for test database
- [ ] 2.4 Add SQLAlchemy session binding to factories
- [ ] 2.5 Ensure Content, Summary, Digest tables exist in test DB
- [ ] 2.6 Document test database setup requirements

## 3. Test Organization

- [ ] 3.1 Create `tests/unit/` directory
- [ ] 3.2 Create `tests/integration/` directory
- [ ] 3.3 Create `tests/e2e/` directory
- [ ] 3.4 Move existing tests to appropriate directories
- [ ] 3.5 Update imports in moved tests

## 4. Pytest Configuration

- [ ] 4.1 Update `pytest.ini` with markers:
  - `unit`: No external dependencies
  - `integration`: Requires database
  - `e2e`: Full API tests
  - `slow`: Long-running tests
- [ ] 4.2 Configure default test paths
- [ ] 4.3 Configure strict markers mode
- [ ] 4.4 Add coverage configuration

## 5. Sample Fixtures

- [ ] 5.1 Create `tests/fixtures/` directory structure
- [ ] 5.2 Add sample markdown files:
  - `fixtures/markdown/sample_content.md`
  - `fixtures/markdown/sample_summary.md`
  - `fixtures/markdown/sample_digest.md`
- [ ] 5.3 Add sample HTML files for parser tests
- [ ] 5.4 Create fixture loader utility

## 6. Hoverfly Integration

- [ ] 6.1 Add `hoverfly_url` fixture (from hoverfly proposal)
- [ ] 6.2 Create `http_client` fixture with proxy support
- [ ] 6.3 Document Hoverfly setup for tests
- [ ] 6.4 Create sample simulation recordings:
  - RSS feed responses
  - Anthropic API responses
- [ ] 6.5 Add simulation loading fixture

## 7. API Test Fixtures

- [ ] 7.1 Create `client` fixture (FastAPI TestClient)
- [ ] 7.2 Create `authenticated_client` fixture (for future auth)
- [ ] 7.3 Add request/response logging for debugging
- [ ] 7.4 Create API response assertion helpers

## 8. CI Integration

- [ ] 8.1 Update CI workflow to run tests by category
- [ ] 8.2 Configure parallel test execution
- [ ] 8.3 Add test result reporting
- [ ] 8.4 Configure coverage thresholds

## 9. Migration of Existing Tests

- [ ] 9.1 Audit existing tests for categories
- [ ] 9.2 Add markers to existing tests
- [ ] 9.3 Refactor tests to use factories where appropriate
- [ ] 9.4 Remove redundant fixture definitions
- [ ] 9.5 Verify all tests pass after migration

## 10. Documentation

- [ ] 10.1 Create `docs/TESTING.md` guide
- [ ] 10.2 Document factory usage examples
- [ ] 10.3 Document test categories and when to use each
- [ ] 10.4 Document Hoverfly usage for HTTP mocking
- [ ] 10.5 Add testing section to CONTRIBUTING.md
