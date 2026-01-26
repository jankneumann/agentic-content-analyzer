# Implementation Tasks

## 1. Custom PostgreSQL Image with Extensions

- [ ] 1.1 Create `railway/postgres/` directory structure
- [ ] 1.2 Create `railway/postgres/Dockerfile` with:
  - Base image: `postgres:16-bookworm`
  - Install build dependencies (build-essential, git, postgresql-server-dev-16)
  - Install Rust and cargo-pgrx for Rust-based extensions
  - Install pgvector v0.7.x from source
  - Install pg_cron v1.6.x from source
  - Install pgmq v1.4.x via cargo-pgrx
  - Install pg_search v0.13.x (ParadeDB) via cargo-pgrx
  - Configure shared_preload_libraries
  - Clean up build dependencies to reduce image size
- [ ] 1.3 Create `railway/postgres/init-extensions.sql` to enable extensions on startup
- [ ] 1.4 Create `railway/postgres/postgresql.conf` with optimized settings
- [ ] 1.5 Add `railway/postgres/README.md` with build and deployment instructions
- [ ] 1.6 Test Docker image locally:
  ```bash
  docker build -t newsletter-postgres:railway ./railway/postgres
  docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test newsletter-postgres:railway
  ```
- [ ] 1.7 Verify all extensions load correctly:
  ```sql
  SELECT * FROM pg_available_extensions
  WHERE name IN ('vector', 'pg_search', 'pgmq', 'pg_cron');
  ```

## 2. Database Provider Implementation

- [ ] 2.1 Update `DatabaseProviderType` in `src/config/settings.py` to include `"railway"`
- [ ] 2.2 Add Railway-specific settings to `Settings` class:
  - `railway_database_url: str | None = None`
  - `railway_pg_cron_enabled: bool = True`
  - `railway_pgvector_enabled: bool = True`
  - `railway_pg_search_enabled: bool = True`
  - `railway_pgmq_enabled: bool = True`
- [ ] 2.3 Add Railway validation in `validate_database_provider_config()` model validator
- [ ] 2.4 Add `get_effective_database_url()` case for Railway provider
- [ ] 2.5 Create `src/storage/providers/railway.py` with `RailwayProvider` class:
  - Implement `name` property returning `"railway"`
  - Implement `get_engine_url()` method
  - Implement `get_engine_options()` with Railway-optimized settings (SSL, pool)
  - Implement `health_check(engine)` method
  - Implement `get_queue_url()` and `get_queue_options()` for workers
  - Implement `supports_pg_cron()` returning `settings.railway_pg_cron_enabled`
- [ ] 2.6 Update `src/storage/providers/factory.py` to handle `"railway"` provider type
- [ ] 2.7 Update `src/storage/providers/__init__.py` to export `RailwayProvider`

## 3. Storage Provider Implementation

- [ ] 3.1 Add Railway MinIO settings to `Settings` class:
  - `railway_minio_endpoint: str | None = None`
  - `railway_minio_bucket: str | None = None`
  - `minio_root_user: str | None = None`
  - `minio_root_password: str | None = None`
- [ ] 3.2 Create `RailwayFileStorage` class in `src/services/file_storage.py`:
  - Extend `S3FileStorage`
  - Auto-discover endpoint from `RAILWAY_PUBLIC_DOMAIN` if not set
  - Auto-use `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` credentials
  - Set `provider_name` property to `"railway"`
- [ ] 3.3 Update `get_storage()` factory function to handle `"railway"` provider

## 4. Testing

- [ ] 4.1 Add `TestRailwayProvider` class in `tests/test_storage/test_providers.py`:
  - Test provider initialization
  - Test engine URL handling
  - Test engine options (SSL, pool settings)
  - Test `supports_pg_cron()` respects settings flag
- [ ] 4.2 Add Railway storage tests in `tests/test_services/test_file_storage.py`:
  - Test `RailwayFileStorage` initialization
  - Test endpoint URL construction from `RAILWAY_PUBLIC_DOMAIN`
  - Test credential handling from environment
- [ ] 4.3 Add integration test fixture in `tests/integration/fixtures/railway.py` (skipped if no Railway credentials)
- [ ] 4.4 Add Docker image test in CI (build and verify extensions)

## 5. Documentation

- [ ] 5.1 Update `CLAUDE.md` Database Providers table to include Railway with extensions
- [ ] 5.2 Update `CLAUDE.md` File Storage Providers table to include Railway
- [ ] 5.3 Add Railway setup section in `docs/SETUP.md`:
  - Custom PostgreSQL image deployment
  - Extension capabilities (pgvector, pg_search, pgmq, pg_cron)
  - Railway MinIO template deployment
  - Environment variable configuration
  - Railway.json example configuration
- [ ] 5.4 Add Railway to Critical Gotchas table:
  - Custom image build time (~10-15 min first build)
  - Extension version pinning for stability
  - Volume persistence requirements
- [ ] 5.5 Create `railway/README.md` with deployment guide

## 6. Validation

- [ ] 6.1 Run `pytest tests/test_storage/test_providers.py -v` to verify provider tests pass
- [ ] 6.2 Run `pytest tests/test_services/test_file_storage.py -v` to verify storage tests pass
- [ ] 6.3 Run `mypy src/storage/providers/railway.py src/services/file_storage.py` for type checking
- [ ] 6.4 Test local development with Railway provider (mock credentials)
- [ ] 6.5 Deploy test instance to Railway and verify:
  - PostgreSQL with all extensions working
  - MinIO storage operations
  - Application connectivity
