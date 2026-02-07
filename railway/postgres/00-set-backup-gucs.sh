#!/bin/bash
# Wire environment variables to PostgreSQL custom GUC settings for pg_cron backup jobs.
# This runs during docker-entrypoint-initdb.d initialization, before SQL init scripts.
#
# The backup job (init-backup-job.sql) reads these GUCs via current_setting().
# Without this script, the GUCs are NULL and backups are silently skipped.

set -e

# Only set GUCs if MinIO endpoint is configured
if [ -z "$MINIO_ENDPOINT" ]; then
    echo "MINIO_ENDPOINT not set — skipping backup GUC configuration"
    exit 0
fi

echo "Configuring backup GUC settings from environment variables..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    ALTER SYSTEM SET app.minio_endpoint = '${MINIO_ENDPOINT}';
    ALTER SYSTEM SET app.minio_user = '${MINIO_ROOT_USER:-minioadmin}';
    ALTER SYSTEM SET app.minio_password = '${MINIO_ROOT_PASSWORD:-minioadmin}';
    ALTER SYSTEM SET app.backup_db = '${POSTGRES_DB:-railway}';
    ALTER SYSTEM SET app.backup_bucket = '${BACKUP_BUCKET:-backups}';
    ALTER SYSTEM SET app.backup_retention_days = '${BACKUP_RETENTION_DAYS:-7}';
    ALTER SYSTEM SET app.backup_schedule = '${RAILWAY_BACKUP_SCHEDULE:-0 3 * * *}';
    ALTER SYSTEM SET app.backup_cleanup_schedule = '${RAILWAY_BACKUP_CLEANUP_SCHEDULE:-0 4 * * *}';
    SELECT pg_reload_conf();
EOSQL

echo "Backup GUC settings configured successfully"
