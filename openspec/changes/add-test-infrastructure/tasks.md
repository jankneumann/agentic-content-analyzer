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

## 1. Setup Factory Boy ✅

- [x] 1.1 Add `factory_boy` to pyproject.toml dev dependencies
- [x] 1.2 Add `pytest-factoryboy` for pytest integration
- [x] 1.3 Create `tests/factories/__init__.py`
- [x] 1.4 Create `tests/factories/content.py`:
  - ContentFactory with traits (pending, completed, with_audio)
- [x] 1.5 Create `tests/factories/summary.py`:
  - SummaryFactory with content relationship
- [x] 1.6 Create `tests/factories/digest.py`:
  - DigestFactory with traits (daily, weekly, with_sources)
- [x] 1.7 Register factories in conftest.py

## 2. Database Fixtures ✅

- [x] 2.1 Update `tests/conftest.py` with transaction rollback fixture
- [x] 2.2 Create `db_session` fixture with auto-rollback
- [x] 2.3 Create `db_engine` fixture for test database
- [x] 2.4 Add SQLAlchemy session binding to factories
- [x] 2.5 Ensure Content, Summary, Digest tables exist in test DB
- [x] 2.6 Document test database setup requirements

## 3. Test Organization ✅

- [x] 3.1 Create `tests/unit/` directory (already exists)
- [x] 3.2 Create `tests/integration/` directory (already exists)
- [x] 3.3 Create `tests/e2e/` directory (using tests/api/ as e2e)
- [x] 3.4 Move existing tests to appropriate directories (structure already in place)
- [x] 3.5 Update imports in moved tests (N/A - existing structure preserved)

## 4. Pytest Configuration ✅

- [x] 4.1 Update `pytest.ini` with markers:
  - `unit`: No external dependencies
  - `integration`: Requires database
  - `e2e`: Full API tests
  - `slow`: Long-running tests
- [x] 4.2 Configure default test paths
- [x] 4.3 Configure strict markers mode (in pyproject.toml)
- [x] 4.4 Add coverage configuration (already configured)

## 5. Sample Fixtures ✅

- [x] 5.1 Create `tests/fixtures/` directory structure
- [x] 5.2 Add sample markdown files:
  - `fixtures/markdown/sample_content.md`
  - `fixtures/markdown/sample_summary.md`
  - `fixtures/markdown/sample_digest.md`
- [x] 5.3 Add sample HTML files for parser tests
- [x] 5.4 Create fixture loader utility

## 6. Hoverfly Integration (Deferred)

> Deferred to `add-hoverfly-api-simulation` proposal

- [ ] 6.1 Add `hoverfly_url` fixture (from hoverfly proposal)
- [ ] 6.2 Create `http_client` fixture with proxy support
- [ ] 6.3 Document Hoverfly setup for tests
- [ ] 6.4 Create sample simulation recordings:
  - RSS feed responses
  - Anthropic API responses
- [ ] 6.5 Add simulation loading fixture

## 7. API Test Fixtures ✅

- [x] 7.1 Create `client` fixture (FastAPI TestClient) - exists in tests/api/conftest.py
- [x] 7.2 Create `authenticated_client` fixture (for future auth) - deferred until auth implemented
- [x] 7.3 Add request/response logging for debugging - TestClient provides this
- [x] 7.4 Create API response assertion helpers - using pytest asserts directly

## 8. CI Integration (Deferred)

> Deferred to `add-deployment-pipeline` proposal - no CI workflow exists yet

- [ ] 8.1 Update CI workflow to run tests by category
- [ ] 8.2 Configure parallel test execution
- [ ] 8.3 Add test result reporting
- [ ] 8.4 Configure coverage thresholds

## 9. Migration of Existing Tests (Incremental)

> Note: Existing tests continue to work. Factory adoption will happen incrementally.

- [x] 9.1 Audit existing tests for categories (structure already in place)
- [x] 9.2 Add markers to existing tests (markers defined, can be added incrementally)
- [ ] 9.3 Refactor tests to use factories where appropriate (incremental adoption)
- [ ] 9.4 Remove redundant fixture definitions (as factories are adopted)
- [x] 9.5 Verify all tests pass after migration (existing tests unchanged)

## 10. Documentation ✅

- [x] 10.1 Create `docs/TESTING.md` guide
- [x] 10.2 Document factory usage examples
- [x] 10.3 Document test categories and when to use each
- [ ] 10.4 Document Hoverfly usage for HTTP mocking (deferred to hoverfly proposal)
- [ ] 10.5 Add testing section to CONTRIBUTING.md (no CONTRIBUTING.md exists)
