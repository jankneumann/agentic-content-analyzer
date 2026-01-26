# Implementation Tasks

## 1. Custom PostgreSQL Image with Extensions

- [ ] 1.1 Create `railway/postgres/` directory structure
- [ ] 1.2 Create `railway/postgres/Dockerfile` with multi-stage build:
  - **Builder stage**: `postgres:16-bookworm` with build tools
    - Install build dependencies (build-essential, git, postgresql-server-dev-16)
    - Install Rust and cargo-pgrx for Rust-based extensions
    - Install pgvector v0.7.x from source
    - Install pg_cron v1.6.x from source
    - Install pgmq v1.4.x via cargo-pgrx
    - Install pg_search v0.13.x (ParadeDB) via cargo-pgrx
  - **Runtime stage**: Clean `postgres:16-bookworm`
    - Copy compiled extensions from builder
    - Configure shared_preload_libraries
    - Add healthcheck
  - Target image size: ~450 MB (vs ~2.1 GB single-stage)
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

## 2. GHCR Image Publishing (CI Workflow)

- [ ] 2.1 Create `.github/workflows/build-railway-postgres.yml`:
  - Trigger on push to `railway/postgres/**` or manual dispatch
  - Log in to GHCR with `GITHUB_TOKEN`
  - Use Docker Buildx with GitHub Actions cache
  - Push to `ghcr.io/{owner}/newsletter-postgres:16-railway`
  - Tag with commit SHA for traceability
- [ ] 2.2 Test workflow in a feature branch
- [ ] 2.3 After first successful build, make GHCR package public:
  - GitHub → Profile → Packages → newsletter-postgres → Settings
  - Change visibility to Public (allows Railway to pull without auth)
- [ ] 2.4 Document GHCR image usage in `railway/README.md`:
  - How to pull the pre-built image
  - How to reference in Railway dashboard
  - Version pinning recommendations
  - Private package authentication (if needed)

## 3. Database Provider Implementation

- [ ] 3.1 Update `DatabaseProviderType` in `src/config/settings.py` to include `"railway"`
- [ ] 3.2 Add Railway-specific settings to `Settings` class:
  - `railway_database_url: str | None = None`
  - `railway_pg_cron_enabled: bool = True`
  - `railway_pgvector_enabled: bool = True`
  - `railway_pg_search_enabled: bool = True`
  - `railway_pgmq_enabled: bool = True`
  - `railway_pool_size: int = 3`  (Hobby plan default)
  - `railway_max_overflow: int = 2`
  - `railway_pool_recycle: int = 300`
  - `railway_pool_timeout: int = 30`
- [ ] 3.3 Add Railway validation in `validate_database_provider_config()` model validator
- [ ] 3.4 Add `get_effective_database_url()` case for Railway provider
- [ ] 3.5 Create `src/storage/providers/railway.py` with `RailwayProvider` class:
  - Implement `name` property returning `"railway"`
  - Implement `get_engine_url()` method
  - Implement `get_engine_options()` with configurable pool settings
  - Implement `health_check(engine)` method
  - Implement `get_queue_url()` and `get_queue_options()` for workers
  - Implement `supports_pg_cron()` returning `settings.railway_pg_cron_enabled`
- [ ] 3.6 Update `src/storage/providers/factory.py` to handle `"railway"` provider type
- [ ] 3.7 Update `src/storage/providers/__init__.py` to export `RailwayProvider`

## 4. Storage Provider Implementation

- [ ] 4.1 Add Railway MinIO settings to `Settings` class:
  - `railway_minio_endpoint: str | None = None`
  - `railway_minio_bucket: str | None = None`
  - `minio_root_user: str | None = None`
  - `minio_root_password: str | None = None`
- [ ] 4.2 Create `RailwayFileStorage` class in `src/services/file_storage.py`:
  - Extend `S3FileStorage`
  - Auto-discover endpoint from `RAILWAY_PUBLIC_DOMAIN` if not set
  - Auto-use `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` credentials
  - Set `provider_name` property to `"railway"`
- [ ] 4.3 Update `get_storage()` factory function to handle `"railway"` provider

## 5. Backup Strategy Implementation

- [ ] 5.1 Add backup settings to `Settings` class:
  - `railway_backup_enabled: bool = True`
  - `railway_backup_schedule: str = "0 3 * * *"`
  - `railway_backup_retention_days: int = 7`
  - `railway_backup_bucket: str = "backups"`
- [ ] 5.2 Create `railway/postgres/init-backup-job.sql`:
  - pg_cron job for daily pg_dump to MinIO
  - Cleanup job for retention policy
- [ ] 5.3 Document backup and recovery procedures in `docs/SETUP.md`:
  - How backups are stored in MinIO
  - How to restore from backup
  - How to verify backup integrity
- [ ] 5.4 Add backup verification to health checks (optional)

## 6. Testing

- [ ] 6.1 Add `TestRailwayProvider` class in `tests/test_storage/test_providers.py`:
  - Test provider initialization
  - Test engine URL handling
  - Test engine options (SSL, pool settings)
  - Test `supports_pg_cron()` respects settings flag
  - Test pool size configuration from settings
- [ ] 6.2 Add Railway storage tests in `tests/test_services/test_file_storage.py`:
  - Test `RailwayFileStorage` initialization
  - Test endpoint URL construction from `RAILWAY_PUBLIC_DOMAIN`
  - Test credential handling from environment
- [ ] 6.3 Add integration test fixture in `tests/integration/fixtures/railway.py` (skipped if no Railway credentials)
- [ ] 6.4 Add Docker image test in CI (build and verify extensions)

## 7. Documentation

- [ ] 7.1 Update `CLAUDE.md` Database Providers table to include Railway with extensions
- [ ] 7.2 Update `CLAUDE.md` File Storage Providers table to include Railway
- [ ] 7.3 Add Railway setup section in `docs/SETUP.md`:
  - Custom PostgreSQL image deployment (GHCR or build from source)
  - Extension capabilities (pgvector, pg_search, pgmq, pg_cron)
  - Railway MinIO template deployment
  - Environment variable configuration
  - Connection pool sizing by Railway plan
  - Backup configuration and recovery
- [ ] 7.4 Add Railway to Critical Gotchas table:
  - Custom image build time (~10-15 min first build, use GHCR)
  - Extension version pinning for stability
  - Volume persistence requirements
  - No managed backups for custom images (use pg_cron)
  - Connection limits by plan (Hobby: pool_size=3, Pro: pool_size=10)
- [ ] 7.5 Create `railway/README.md` with deployment guide

## 8. Validation

- [ ] 8.1 Run `pytest tests/test_storage/test_providers.py -v` to verify provider tests pass
- [ ] 8.2 Run `pytest tests/test_services/test_file_storage.py -v` to verify storage tests pass
- [ ] 8.3 Run `mypy src/storage/providers/railway.py src/services/file_storage.py` for type checking
- [ ] 8.4 Test local development with Railway provider (mock credentials)
- [ ] 8.5 Deploy test instance to Railway and verify:
  - PostgreSQL with all extensions working
  - MinIO storage operations
  - Application connectivity
  - Backup job execution
  - Connection pool behavior under load
