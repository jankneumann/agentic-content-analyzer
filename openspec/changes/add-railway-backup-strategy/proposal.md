# Change: Add Railway Backup Strategy

## Why

Railway's custom PostgreSQL image lacks managed backups (unlike Supabase or Neon which provide automatic backups). Since the custom image includes pg_cron, we can implement automated pg_dump-based backups to MinIO, providing data protection without leaving the Railway platform.

## What Changes

### Backup Configuration
- Add `railway_backup_*` settings to `Settings` class for schedule, retention, and target bucket
- Settings are Railway-provider-specific and inert when using other providers

### Backup SQL Jobs
- Create `railway/postgres/init-backup-job.sql` with pg_cron scheduled jobs:
  - Daily `pg_dump` compressed backup written to MinIO via `pgmq` or shell
  - Retention cleanup job to remove backups older than N days

### Documentation
- Document backup and recovery procedures in `docs/SETUP.md`
- Cover: backup storage location, restore steps, integrity verification

### Health Check Integration (Optional)
- Add backup recency check to health endpoint (warn if last backup > 2x schedule interval)

## Impact

- **Affected specs**: `database-provider` (backup settings and scenarios)
- **Affected code**:
  - `src/config/settings.py` - New `railway_backup_*` settings
  - `railway/postgres/init-backup-job.sql` - New file with pg_cron jobs
  - `docs/SETUP.md` - Backup documentation
  - `src/api/health_routes.py` - Optional backup health check
- **No breaking changes**: All new settings have defaults; existing behavior unchanged
- **Dependencies**: Requires Railway provider (from `add-railway-providers`) and pg_cron extension
