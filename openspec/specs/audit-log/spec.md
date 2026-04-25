# audit-log Specification

## Purpose
TBD - created by archiving change cloud-db-source-of-truth. Update Purpose after archive.
## Requirements
### Requirement: Audit log persistence for all API requests

The system SHALL record every request to `/api/v1/*` endpoints in an append-only `audit_log` database table — including authentication failures (401 no-credentials, 403 invalid-key), validation failures (422), and server errors (5xx). The log MUST capture: timestamp, request ID, HTTP method, path, admin-key fingerprint (last 8 chars of SHA-256 hash computed from the raw `X-Admin-Key` header when present — regardless of whether the key is valid), status code, body size, client IP, and optional operation name.

Rationale: complete forensic coverage for a single-consumer surface — without logging failed auth we cannot detect credential-probing, and without logging reads we cannot audit data exfiltration patterns.

#### Scenario: Request to any `/api/v1/*` endpoint creates log entry

- **WHEN** a client sends any request to `/api/v1/*` (read or write, authenticated or not)
- **THEN** an `audit_log` row is created with the full metadata
- **AND** the `admin_key_fp` column contains the last 8 characters of the SHA-256 of the raw `X-Admin-Key` header value whenever the header is present, or NULL when the header is absent (so invalid-key attempts can be correlated by fingerprint)

#### Scenario: No credentials (401) is logged

- **WHEN** a client sends a request with no `X-Admin-Key` header and no valid session cookie
- **THEN** the API returns 401 Unauthorized
- **AND** an `audit_log` row is still created with `status_code=401`, `admin_key_fp` NULL
- **AND** the `notes` JSONB field records `{"auth_failure": "missing_key"}`

#### Scenario: Invalid admin key (403) is logged with fingerprint

- **WHEN** a client sends a request with an `X-Admin-Key` header whose value does not match the configured admin key
- **THEN** the API returns 403 Forbidden
- **AND** an `audit_log` row is still created with `status_code=403`, `admin_key_fp` set to the SHA-256 last-8 of the presented (wrong) key value
- **AND** the `notes` JSONB field records `{"auth_failure": "invalid_key"}`

#### Scenario: OPTIONS preflight requests are not logged

- **WHEN** a browser or fetch client sends an `OPTIONS` preflight to `/api/v1/*`
- **THEN** the audit middleware MUST bypass logging and let the CORS middleware handle the response
- **AND** no `audit_log` row is created

Rationale: OPTIONS preflights carry no application intent; logging them adds only noise and forces middleware-ordering complexity between CORS and Auth.

#### Scenario: Request body is not stored

- **WHEN** a client sends a POST with a large JSON body
- **THEN** `audit_log.body_size` records the byte size of the request body
- **AND** the body content itself is NOT persisted in the audit table

#### Scenario: Failed request is still logged

- **WHEN** a request returns a non-2xx status code (4xx client error or 5xx server error)
- **THEN** an `audit_log` row is still created with the correct `status_code`

#### Scenario: Audit write failure does not block the response

- **WHEN** the `audit_log` INSERT fails (e.g., transient DB error, connection loss)
- **THEN** the middleware MUST NOT raise to the client — the original response is still returned
- **AND** the failure is logged to stderr with the request_id, HTTP method, path, and underlying DB error
- **AND** an OpenTelemetry span attribute `audit.write_failure=true` is set on the current trace span

Rationale: audit is best-effort — blocking user-facing responses on a secondary observability concern would be a cure worse than the disease.

#### Scenario: Client IP is extracted via proxy-aware headers

- **WHEN** a request arrives at the application behind Cloudflare/Railway
- **THEN** `audit_log.client_ip` MUST be populated from the first non-empty source in this order: `Cf-Connecting-Ip` header, first IP in `X-Forwarded-For` header, `request.client.host`
- **AND** IPv6 addresses are stored unmodified; IPv4-mapped IPv6 forms (`::ffff:1.2.3.4`) are normalized to IPv4

Rationale: Railway's ingress sits behind Cloudflare; `request.client.host` alone would record the Cloudflare edge IP, not the real client.

### Requirement: Audit middleware observability attributes

The `AuditMiddleware` SHALL enrich the active OpenTelemetry span for every `/api/v1/*` request with the following attributes so audit behavior is observable from traces without inspecting the `audit_log` table:

- `audit.operation` (string, nullable) — the `operation` value written to the audit row (NULL for non-decorated endpoints).
- `audit.status_code` (integer) — the response status code.
- `audit.write_failure` (boolean, only set when `true`) — present on spans where the audit INSERT raised.

`request.state.request_id` (populated upstream by `TraceMiddleware`) SHALL be written verbatim to the `audit_log.request_id` column, enabling join between audit rows and trace logs.

#### Scenario: Audit span attributes populated on success

- **WHEN** a successful request reaches an `@audited(operation="kb.lint.fix")` endpoint
- **THEN** the active OTel span has `audit.operation="kb.lint.fix"` and `audit.status_code=200`
- **AND** `audit.write_failure` is absent (not set)

#### Scenario: Audit span attribute marks write failure

- **WHEN** the `audit_log` INSERT raises
- **THEN** the active OTel span has `audit.write_failure=true`
- **AND** the original response is unaffected (see non-blocking scenario above)

#### Scenario: Trace ID correlation with audit row

- **WHEN** `TraceMiddleware` has set `request.state.request_id="abc-123"` on a request
- **THEN** the resulting `audit_log` row has `request_id='abc-123'`
- **AND** structured logs emitted during the request include `request_id=abc-123` so log-to-audit correlation is trivial

### Requirement: Operation tagging via `@audited` decorator

The system SHALL provide an `@audited(operation="<verb>")` decorator that route handlers MAY apply to tag the audit row with a domain-specific operation name (e.g., `kb.purge`, `graph.extract_entities`). The decorator does NOT control whether a row is written — all `/api/v1/*` requests are logged — it only enriches the `operation` field for easier querying of sensitive/destructive actions.

#### Scenario: Decorated endpoint records operation name

- **WHEN** a client calls an endpoint decorated with `@audited(operation="kb.purge")`
- **THEN** the `audit_log` row has `operation='kb.purge'`

#### Scenario: Non-decorated endpoint records without operation

- **WHEN** a client calls a read-only endpoint (no decorator)
- **THEN** the `audit_log` row has `operation IS NULL` but the row IS still written (middleware handles it)

### Requirement: Audit log query endpoint

The system SHALL expose `GET /api/v1/audit` for querying the audit log. Supports filters: `since` (timestamp), `until` (timestamp), `path` (exact match, constrained to safe characters), `operation` (exact match), `status_code` (exact), `limit` (default 100, max 1000). Requires `X-Admin-Key`.

The `path` filter uses exact-match semantics (not substring) and validates against the pattern `^[/a-zA-Z0-9_-]+$` to prevent malformed queries.

#### Scenario: Query recent audit entries

- **WHEN** a client sends `GET /api/v1/audit?since=2026-04-20T00:00:00Z&limit=50`
- **THEN** the API returns a 200 response with up to 50 entries from the last day
- **AND** entries are ordered by `timestamp DESC`

#### Scenario: Query by operation

- **WHEN** a client sends `GET /api/v1/audit?operation=kb.purge`
- **THEN** only rows with `operation='kb.purge'` are returned

#### Scenario: Query by exact path

- **WHEN** a client sends `GET /api/v1/audit?path=/api/v1/kb/search`
- **THEN** only rows whose `path` column exactly equals `/api/v1/kb/search` are returned

#### Scenario: Invalid path filter is rejected

- **WHEN** a client sends `GET /api/v1/audit?path=/api/v1/kb/%20'; DROP TABLE`
- **THEN** the API returns 422 with a Problem response indicating the path pattern is invalid

#### Scenario: Query respects max limit

- **WHEN** a client requests `limit=5000`
- **THEN** the API clamps the limit to 1000

### Requirement: Audit log retention via pg_cron (migration-time interpolation)

The system SHALL enforce audit log retention via a pg_cron job that deletes entries older than `AUDIT_LOG_RETENTION_DAYS` days (default 90). The retention interval MUST be interpolated into the cron SQL at Alembic migration time (from the environment variable) — NOT read at runtime via `current_setting()` GUCs, because Railway's managed Postgres restricts custom GUCs.

The retention job is the only code path that removes audit rows — application code MUST NOT DELETE or UPDATE audit entries.

#### Scenario: Retention job deletes old entries

- **WHEN** the pg_cron `audit-log-retention` job runs
- **THEN** all `audit_log` rows with `timestamp < now() - INTERVAL '<days> days'` are deleted, where `<days>` was the value of `AUDIT_LOG_RETENTION_DAYS` at migration time

#### Scenario: Retention interval is fixed by migration, not runtime

- **WHEN** the Alembic migration runs with `AUDIT_LOG_RETENTION_DAYS=30`
- **THEN** the registered pg_cron command is literally `DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '30 days'`
- **AND** changing `AUDIT_LOG_RETENTION_DAYS` later has NO effect until a new migration re-registers the cron job

Rationale: pg_cron commands execute outside the application process and cannot read application env vars; persistent reconfigurability would require a second table and a migration-step, which is out of scope. Documenting the migration-time-fix contract prevents user surprise.

