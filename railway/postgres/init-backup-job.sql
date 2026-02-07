-- Railway PostgreSQL Automated Backup Jobs
-- Creates pg_cron scheduled jobs for pg_dump backups to MinIO
-- Requires: pg_cron extension enabled via shared_preload_libraries
--
-- Environment variables used by the backup command:
--   POSTGRES_DB       - Database name to back up
--   MINIO_ENDPOINT    - MinIO endpoint URL (e.g., http://minio.railway.internal:9000)
--   MINIO_ROOT_USER   - MinIO access key
--   MINIO_ROOT_PASSWORD - MinIO secret key
--   BACKUP_BUCKET     - MinIO bucket name (default: backups)
--   BACKUP_RETENTION_DAYS - Days to keep backups (default: 7)

-- Only proceed if pg_cron is available
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'
    ) THEN
        RAISE NOTICE 'pg_cron not available — skipping backup job setup';
        RETURN;
    END IF;

    -- Unschedule existing jobs to avoid duplicates on re-init
    BEGIN
        PERFORM cron.unschedule('railway-backup');
    EXCEPTION WHEN OTHERS THEN
        -- Job may not exist yet, that's fine
        NULL;
    END;

    BEGIN
        PERFORM cron.unschedule('railway-backup-cleanup');
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    -- Schedule daily compressed backup
    -- Uses pg_dump custom format (-Fc) for efficient compression and selective restore
    -- Writes to MinIO using the mc (MinIO Client) command
    PERFORM cron.schedule(
        'railway-backup',
        COALESCE(current_setting('app.backup_schedule', TRUE), '0 3 * * *'),
        format(
            $cmd$
            DO $inner$
            DECLARE
                db_name text := current_setting('app.backup_db', TRUE);
                minio_ep text := current_setting('app.minio_endpoint', TRUE);
                minio_user text := current_setting('app.minio_user', TRUE);
                minio_pass text := current_setting('app.minio_password', TRUE);
                bucket text := COALESCE(current_setting('app.backup_bucket', TRUE), 'backups');
                backup_file text;
                backup_cmd text;
            BEGIN
                IF minio_ep IS NULL THEN
                    RAISE NOTICE 'MINIO_ENDPOINT not configured — skipping backup';
                    RETURN;
                END IF;

                backup_file := format('%%s-%%s.dump', COALESCE(db_name, 'railway'), to_char(now(), 'YYYY-MM-DD-HH24MI'));

                -- Configure mc alias and run backup
                backup_cmd := format(
                    'mc alias set railway %%s %%s %%s --api S3v4 && '
                    'pg_dump -Fc %%s | mc pipe railway/%%s/%%s',
                    minio_ep, minio_user, minio_pass,
                    COALESCE(db_name, 'railway'), bucket, backup_file
                );

                RAISE NOTICE 'Starting backup: %%', backup_file;
                -- Note: COPY TO PROGRAM requires superuser
                EXECUTE format('COPY (SELECT 1) TO PROGRAM %%L', backup_cmd);
                RAISE NOTICE 'Backup completed: %%', backup_file;
            END
            $inner$;
            $cmd$
        )
    );

    -- Schedule daily cleanup of old backups (runs 1 hour after backup)
    PERFORM cron.schedule(
        'railway-backup-cleanup',
        COALESCE(current_setting('app.backup_cleanup_schedule', TRUE), '0 4 * * *'),
        format(
            $cmd$
            DO $inner$
            DECLARE
                minio_ep text := current_setting('app.minio_endpoint', TRUE);
                minio_user text := current_setting('app.minio_user', TRUE);
                minio_pass text := current_setting('app.minio_password', TRUE);
                bucket text := COALESCE(current_setting('app.backup_bucket', TRUE), 'backups');
                retention text := COALESCE(current_setting('app.backup_retention_days', TRUE), '7');
                cleanup_cmd text;
            BEGIN
                IF minio_ep IS NULL THEN
                    RAISE NOTICE 'MINIO_ENDPOINT not configured — skipping cleanup';
                    RETURN;
                END IF;

                -- Remove backups older than retention period
                cleanup_cmd := format(
                    'mc alias set railway %%s %%s %%s --api S3v4 && '
                    'mc rm --recursive --older-than %%sd railway/%%s/',
                    minio_ep, minio_user, minio_pass,
                    retention, bucket
                );

                RAISE NOTICE 'Starting backup cleanup (retention: %% days)', retention;
                EXECUTE format('COPY (SELECT 1) TO PROGRAM %%L', cleanup_cmd);
                RAISE NOTICE 'Backup cleanup completed';
            END
            $inner$;
            $cmd$
        )
    );

    RAISE NOTICE 'Railway backup jobs configured:';
    RAISE NOTICE '  - railway-backup: Scheduled daily pg_dump to MinIO';
    RAISE NOTICE '  - railway-backup-cleanup: Scheduled daily cleanup of old backups';
END $$;
