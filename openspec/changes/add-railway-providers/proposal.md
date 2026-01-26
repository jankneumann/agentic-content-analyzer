# Change: Add Railway Database and Storage Providers

## Why

Railway is an increasingly popular deployment platform that simplifies cloud infrastructure management. It provides:
- **Railway PostgreSQL**: A managed PostgreSQL service with automatic provisioning, connection pooling, and SSL
- **Railway MinIO**: S3-compatible object storage via MinIO templates

Adding Railway as a supported provider enables unified deployment on a single platform without external database or storage dependencies. This complements existing providers (Local, Supabase, Neon for database; Local, S3, Supabase for storage) and simplifies the deployment story for teams using Railway.

Railway's default PostgreSQL lacks advanced extensions, so we provide a **custom PostgreSQL Docker image** with:
- **pgvector**: Vector similarity search for AI embeddings
- **pg_search**: Full-text search with BM25 ranking (ParadeDB)
- **pgmq**: Lightweight message queue in PostgreSQL (Tembo)
- **pg_cron**: Job scheduling within PostgreSQL

This achieves feature parity with Supabase and Neon while keeping everything on Railway.

## What Changes

### Custom PostgreSQL Image
- Create `railway/postgres/Dockerfile` with PostgreSQL 16 + extensions
- Include extensions: pgvector, pg_search (ParadeDB), pgmq, pg_cron
- Create init script to enable extensions on database creation
- Document build and deployment process

### Database Provider
- Add `"railway"` to `DatabaseProviderType` enum in settings
- Create `RailwayProvider` class implementing `DatabaseProvider` protocol
- Add Railway-specific environment variables:
  - `RAILWAY_DATABASE_URL` - Override for Railway provider
  - `DATABASE_PRIVATE_URL` / `DATABASE_PUBLIC_URL` - Railway's injected variables
  - `RAILWAY_PG_CRON_ENABLED` - Enable/disable pg_cron support (default: true)
- Update provider factory to instantiate `RailwayProvider`
- Configure appropriate pool settings and SSL for Railway's PostgreSQL

### Storage Provider
- Add `"railway"` as a storage provider option
- Create `RailwayFileStorage` class (extends `S3FileStorage` for MinIO compatibility)
- Add Railway MinIO environment variables:
  - `RAILWAY_MINIO_ENDPOINT` - MinIO service endpoint
  - `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` - Auto-injected credentials
  - `MINIO_BUCKET` - Default bucket name
- Update storage factory to handle Railway provider

### Configuration
- Update `CLAUDE.md` and `docs/SETUP.md` with Railway provider documentation
- Add Railway deployment examples

## Impact

- **Affected specs**: `database-provider`, `storage-provider` (new spec)
- **Affected code**:
  - `railway/postgres/Dockerfile` - Custom PostgreSQL image with extensions
  - `railway/postgres/init-extensions.sql` - Extension initialization script
  - `src/config/settings.py` - New Railway settings
  - `src/storage/providers/railway.py` - New database provider
  - `src/storage/providers/factory.py` - Factory update
  - `src/services/file_storage.py` - Railway storage provider
  - `tests/test_storage/test_providers.py` - Provider tests
  - `CLAUDE.md`, `docs/SETUP.md` - Documentation
- **No breaking changes**: Existing providers remain unchanged
- **Dependencies**: None new for application (boto3 already required for S3)
- **Docker dependencies**: Custom image requires build with Rust toolchain for pgrx-based extensions
