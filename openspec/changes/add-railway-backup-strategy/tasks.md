# Implementation Tasks

## 1. Backup Settings

- [ ] 1.1 Add backup settings to `Settings` class in `src/config/settings.py`:
  - `railway_backup_enabled: bool = True`
  - `railway_backup_schedule: str = "0 3 * * *"` (daily at 3 AM UTC)
  - `railway_backup_retention_days: int = 7`
  - `railway_backup_bucket: str = "backups"`
- [ ] 1.2 Add validation: backup settings only apply when `DATABASE_PROVIDER=railway`
- [ ] 1.3 Add Railway backup bucket to storage provider bucket list

## 2. Backup SQL Jobs

- [ ] 2.1 Create `railway/postgres/init-backup-job.sql`:
  - pg_cron job for daily `pg_dump` compressed backup
  - Retention cleanup job for old backups
  - Conditional execution (only if pg_cron extension is available)
- [ ] 2.2 Update `railway/postgres/init-extensions.sql` to source backup job setup
- [ ] 2.3 Verify backup job creates valid, restorable dumps

## 3. Documentation

- [ ] 3.1 Add backup section to `docs/SETUP.md`:
  - How backups are stored in MinIO
  - How to restore from backup (`pg_restore` steps)
  - How to verify backup integrity
  - How to change schedule and retention
- [ ] 3.2 Add backup configuration to Railway deployment section in `docs/MOBILE_DEPLOYMENT.md`

## 4. Health Check Integration (Optional)

- [ ] 4.1 Add backup recency check to `/ready` endpoint
  - Query pg_cron job run history
  - Warn if last successful backup > 2x schedule interval
- [ ] 4.2 Add backup status to `aca manage verify-setup` output

## 5. Testing

- [ ] 5.1 Add unit tests for backup settings validation
- [ ] 5.2 Add integration test for backup job creation (requires pg_cron)
- [ ] 5.3 Verify backup job SQL syntax is valid
