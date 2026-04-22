# audit-log Specification

## ADDED Requirements

### Requirement: Audit log persistence for API requests

The system SHALL record every request to `/api/v1/*` endpoints in an append-only `audit_log` database table. The log MUST capture: timestamp, request ID, HTTP method, path, admin-key fingerprint (last 8 chars of SHA-256 hash), status code, body size, client IP, and optional operation name.

#### Scenario: Request to audited endpoint creates log entry

- **WHEN** a client sends any request to `/api/v1/*`
- **THEN** an `audit_log` row is created with the full metadata
- **AND** the `admin_key_fp` column contains only the last 8 characters of the SHA-256 of the provided `X-Admin-Key` (or NULL if no key was provided)

#### Scenario: Request body is not stored

- **WHEN** a client sends a POST with a large JSON body
- **THEN** `audit_log.body_size` records the byte size
- **AND** the body content itself is NOT persisted in the audit table

#### Scenario: Failed request is still logged

- **WHEN** a request returns a non-2xx status code
- **THEN** an `audit_log` row is still created with the correct `status_code`

### Requirement: Destructive operation tagging via decorator

The system SHALL provide an `@audited(operation="<verb>")` decorator that route handlers apply to destructive endpoints. Decorated handlers cause the audit log entry to include the `operation` name and optional `notes` JSONB for additional context.

#### Scenario: Decorated endpoint records operation name

- **WHEN** a client calls an endpoint decorated with `@audited(operation="kb.purge")`
- **THEN** the `audit_log` row has `operation='kb.purge'`

#### Scenario: Non-decorated endpoint records without operation

- **WHEN** a client calls a read-only endpoint (no decorator)
- **THEN** the `audit_log` row has `operation IS NULL`

### Requirement: Audit log query endpoint

The system SHALL expose `GET /api/v1/audit` for querying the audit log. Supports filters: `since` (timestamp), `until` (timestamp), `path` (substring), `operation` (exact match), `status_code` (exact), `limit` (default 100, max 1000). Requires `X-Admin-Key`.

#### Scenario: Query recent audit entries

- **WHEN** a client sends `GET /api/v1/audit?since=2026-04-20T00:00:00Z&limit=50`
- **THEN** the API returns a 200 response with up to 50 entries from the last day
- **AND** entries are ordered by `timestamp DESC`

#### Scenario: Query by operation

- **WHEN** a client sends `GET /api/v1/audit?operation=kb.purge`
- **THEN** only rows with `operation='kb.purge'` are returned

#### Scenario: Query respects max limit

- **WHEN** a client requests `limit=5000`
- **THEN** the API clamps the limit to 1000

### Requirement: Audit log retention via pg_cron

The system SHALL enforce audit log retention via a pg_cron job that deletes entries older than `AUDIT_LOG_RETENTION_DAYS` days (default 90). The retention job is the only code path that removes audit rows — application code MUST NOT DELETE or UPDATE audit entries.

#### Scenario: Retention job deletes old entries

- **WHEN** the pg_cron `audit-log-retention` job runs
- **THEN** all `audit_log` rows with `timestamp < now() - AUDIT_LOG_RETENTION_DAYS days` are deleted

#### Scenario: Retention is configurable

- **WHEN** `AUDIT_LOG_RETENTION_DAYS` is set to 30 on startup
- **THEN** the retention job deletes entries older than 30 days on its next run
