# Implementation Tasks

## 1. Create Database Provider Module

- [ ] 1.1 Create `src/storage/providers/__init__.py` with provider exports
- [ ] 1.2 Create `src/storage/providers/base.py` with `DatabaseProvider` protocol
- [ ] 1.3 Create `src/storage/providers/local.py` for local PostgreSQL provider
- [ ] 1.4 Create `src/storage/providers/supabase.py` for Supabase provider
- [ ] 1.5 Create `src/storage/providers/factory.py` with provider detection and factory

## 2. Update Configuration

- [ ] 2.1 Add Supabase database settings to `src/config/settings.py`:
  - `supabase_project_ref: str | None`
  - `supabase_db_password: str | None`
  - `supabase_region: str = "us-east-1"`
  - `supabase_pooler_mode: Literal["transaction", "session"] = "transaction"`
  - `database_provider: Literal["local", "supabase"] | None` (explicit override)
- [ ] 2.2 Add `get_database_url()` method to construct URLs from Supabase config
- [ ] 2.3 Add provider auto-detection property

## 3. Refactor Database Module

- [ ] 3.1 Update `src/storage/database.py` to use provider factory
- [ ] 3.2 Configure engine with provider-specific options (pool size, SSL, timeouts)
- [ ] 3.3 Add connection health check function
- [ ] 3.4 Handle Supabase-specific connection errors gracefully

## 4. Documentation

- [ ] 4.1 Add Supabase setup section to `docs/SETUP.md`
- [ ] 4.2 Document "bring your own Supabase" workflow
- [ ] 4.3 Add troubleshooting section for common Supabase connection issues
- [ ] 4.4 Document migration process with direct URL

## 5. Testing

- [ ] 5.1 Create unit tests for provider factory detection logic
- [ ] 5.2 Create unit tests for Supabase URL construction
- [ ] 5.3 Create integration test fixtures with mock Supabase config
- [ ] 5.4 Test connection pooling behavior with transaction mode

## 6. Validation

- [ ] 6.1 Test local PostgreSQL still works (regression)
- [ ] 6.2 Test Supabase free tier connection
- [ ] 6.3 Verify Alembic migrations work with Supabase direct URL
- [ ] 6.4 Test connection pooling under concurrent load
