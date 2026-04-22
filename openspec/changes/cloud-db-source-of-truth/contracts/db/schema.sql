-- audit_log table for API request auditing
-- Aligned with Alembic migration (to be generated at wp-audit implementation).
-- Append-only by application code; retention enforced by pg_cron.

CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id      TEXT NOT NULL,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    operation       TEXT,                      -- from @audited decorator; NULL for non-audited routes
    admin_key_fp    TEXT,                      -- last 8 chars of SHA-256 of X-Admin-Key; NULL if no key
    status_code     INTEGER NOT NULL,
    body_size       INTEGER,
    client_ip       INET,
    notes           JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT audit_log_timestamp_check CHECK (timestamp >= '2026-01-01'::timestamptz)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON audit_log (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_operation
    ON audit_log (operation)
    WHERE operation IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_path_timestamp
    ON audit_log (path, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_admin_key_fp
    ON audit_log (admin_key_fp, timestamp DESC)
    WHERE admin_key_fp IS NOT NULL;

-- pg_cron retention job
-- (Applied via Alembic data migration; retention days read from AUDIT_LOG_RETENTION_DAYS)
-- SELECT cron.schedule(
--     'audit-log-retention',
--     '0 4 * * *',
--     $$DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '90 days'$$
-- );
