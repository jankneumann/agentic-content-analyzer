# Implementation Tasks

## 1. Create Database Provider Module

- [x] 1.1 Create `src/storage/providers/__init__.py` with provider exports
- [x] 1.2 Create `src/storage/providers/base.py` with `DatabaseProvider` protocol
- [x] 1.3 Create `src/storage/providers/local.py` for local PostgreSQL provider
- [x] 1.4 Create `src/storage/providers/supabase.py` for Supabase provider
- [x] 1.5 Create `src/storage/providers/factory.py` with provider detection and factory

## 2. Update Configuration

- [x] 2.1 Add Supabase database settings to `src/config/settings.py`:
  - `supabase_project_ref: str | None`
  - `supabase_db_password: str | None`
  - `supabase_region: str = "us-east-1"`
  - `supabase_pooler_mode: Literal["transaction", "session"] = "transaction"`
  - `database_provider: Literal["local", "supabase"] | None` (explicit override)
- [x] 2.2 Add `get_database_url()` method to construct URLs from Supabase config
  - Implemented as `get_effective_database_url()` and `_get_supabase_pooler_url()`
- [x] 2.3 Add provider auto-detection property
  - Refactored to explicit selection via `database_provider` field with validation

## 3. Refactor Database Module

- [x] 3.1 Update `src/storage/database.py` to use provider factory
- [x] 3.2 Configure engine with provider-specific options (pool size, SSL, timeouts)
- [x] 3.3 Add connection health check function
  - `SupabaseProvider.health_check()` method
- [x] 3.4 Handle Supabase-specific connection errors gracefully

## 4. Documentation

- [x] 4.1 Add Supabase setup section to `docs/SETUP.md`
  - Comprehensive section with connection string configuration
- [x] 4.2 Document "bring your own Supabase" workflow
  - Included in SETUP.md with component-based and URL-based config options
- [x] 4.3 Add troubleshooting section for common Supabase connection issues
  - Connection pooling modes, SSL requirements documented
- [x] 4.4 Document migration process with direct URL
  - `SUPABASE_DIRECT_URL` and `get_migration_database_url()` documented

## 5. Testing

- [x] 5.1 Create unit tests for provider factory detection logic
  - 44 tests in `tests/test_storage/test_providers.py`
- [x] 5.2 Create unit tests for Supabase URL construction
  - Tests for pooler URL and direct URL construction
- [x] 5.3 Create integration test fixtures with mock Supabase config
  - `tests/integration/fixtures/supabase.py` with real Supabase connection
- [x] 5.4 Test connection pooling behavior with transaction mode
  - `TestSupabaseConnectionPooling` class with concurrent connection tests

## 6. Validation

- [x] 6.1 Test local PostgreSQL still works (regression)
  - Local provider tests pass, no regressions
- [x] 6.2 Test Supabase free tier connection
  - 17 integration tests passing against real Supabase instance
  - Tests: pooled connection, SSL, health check, database version
- [x] 6.3 Verify Alembic migrations work with Supabase direct URL
  - Direct connection tests passing
  - DDL operations verified (CREATE TABLE, DROP TABLE)
  - alembic_version table query works
- [x] 6.4 Test connection pooling under concurrent load
  - Sequential connections: 10 queries
  - Concurrent connections: 5 parallel queries
  - Pool exhaustion recovery: 20 queries with 10 workers
  - Transaction isolation verified
