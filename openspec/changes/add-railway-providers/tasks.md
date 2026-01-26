# Implementation Tasks

## 1. Database Provider Implementation

- [ ] 1.1 Update `DatabaseProviderType` in `src/config/settings.py` to include `"railway"`
- [ ] 1.2 Add Railway-specific settings to `Settings` class:
  - `railway_database_url: str | None = None`
- [ ] 1.3 Add Railway validation in `validate_database_provider_config()` model validator
- [ ] 1.4 Add `get_effective_database_url()` case for Railway provider
- [ ] 1.5 Create `src/storage/providers/railway.py` with `RailwayProvider` class:
  - Implement `name` property
  - Implement `get_engine_url()` method
  - Implement `get_engine_options()` with Railway-optimized settings
  - Implement `health_check(engine)` method
  - Implement `get_queue_url()` and `get_queue_options()` for workers
  - Implement `supports_pg_cron()` returning `False`
- [ ] 1.6 Update `src/storage/providers/factory.py` to handle `"railway"` provider type
- [ ] 1.7 Update `src/storage/providers/__init__.py` to export `RailwayProvider`

## 2. Storage Provider Implementation

- [ ] 2.1 Add Railway MinIO settings to `Settings` class:
  - `railway_minio_endpoint: str | None = None`
  - `railway_minio_bucket: str | None = None`
  - `minio_root_user: str | None = None`
  - `minio_root_password: str | None = None`
- [ ] 2.2 Create `RailwayFileStorage` class in `src/services/file_storage.py`:
  - Extend `S3FileStorage`
  - Auto-discover endpoint from `RAILWAY_PUBLIC_DOMAIN` if not set
  - Auto-use `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` credentials
  - Set `provider_name` property to `"railway"`
- [ ] 2.3 Update `get_storage()` factory function to handle `"railway"` provider

## 3. Testing

- [ ] 3.1 Add `TestRailwayProvider` class in `tests/test_storage/test_providers.py`:
  - Test provider initialization
  - Test engine URL handling
  - Test engine options (SSL, pool settings)
  - Test `supports_pg_cron()` returns `False`
- [ ] 3.2 Add Railway storage tests in `tests/test_services/test_file_storage.py`:
  - Test `RailwayFileStorage` initialization
  - Test endpoint URL construction
  - Test credential handling
- [ ] 3.3 Add integration test fixture in `tests/integration/fixtures/railway.py` (skipped if no Railway credentials)

## 4. Documentation

- [ ] 4.1 Update `CLAUDE.md` Database Providers table to include Railway
- [ ] 4.2 Update `CLAUDE.md` File Storage Providers table to include Railway
- [ ] 4.3 Add Railway setup section in `docs/SETUP.md`:
  - Railway PostgreSQL service setup
  - Railway MinIO template deployment
  - Environment variable configuration
  - Railway.json example configuration
- [ ] 4.4 Add Railway to Critical Gotchas table if any Railway-specific issues emerge

## 5. Validation

- [ ] 5.1 Run `pytest tests/test_storage/test_providers.py -v` to verify provider tests pass
- [ ] 5.2 Run `pytest tests/test_services/test_file_storage.py -v` to verify storage tests pass
- [ ] 5.3 Run `mypy src/storage/providers/railway.py src/services/file_storage.py` for type checking
- [ ] 5.4 Test local development with Railway provider (mock credentials)
