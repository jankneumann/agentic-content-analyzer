# Design: Cloud DB as Source of Truth

## Architectural Decisions

### D1: HTTP is the single source-of-truth transport; MCP and CLI become clients

**Decision**: All data access from outside the server process goes through `/api/v1/*`. MCP tools, the CLI (in HTTP mode), and external consumers (agentic-assistant) all use the same HTTP surface.

**Rationale**:
- One code path for authorization, rate limiting, auditing, and telemetry.
- MCP can run anywhere: locally against `http://localhost:8000`, remotely against `https://api.aca.rotkohl.ai`, or embedded in a consumer process.
- API contract becomes the stable boundary; service internals can refactor without breaking external clients.

**Alternatives rejected**:
- *Deploy MCP remotely on Railway with SSE transport*: adds a second service to operate; MCP still tightly coupled to service internals; consumers can't use MCP against localhost from their own process.
- *Keep MCP stdio-only, local-only*: blocks agentic-assistant's multi-persona workflow from using MCP tooling conventions against cloud instances.

### D2: MCP tools get in-process fallback when HTTP config is absent

**Decision**: Each refactored MCP tool checks for `ACA_API_BASE_URL` + `ACA_ADMIN_KEY`. If set, use `ApiClient`. If unset, fall back to the existing in-process service call. Fallback is silent by default; a `--strict-http` MCP server flag makes unset config an error.

**Rationale**:
- Preserves backwards compatibility: existing MCP setups that run embedded in the same process keep working with no config.
- Enables gradual rollout: consumers can opt into HTTP by setting config; defaults don't change.
- `--strict-http` gives deployment mode confidence when HTTP is intended (e.g., multi-process production).

**Alternatives rejected**:
- *Always require HTTP config*: breaks existing single-process embedded MCP deployments.
- *Remove in-process mode entirely*: forces every MCP consumer to run an API server, overkill for embedded use.

### D3: Audit logging via middleware + decorator tagging, not explicit per-route calls

**Decision**: Add `AuditMiddleware` that records every request to `/api/v1/*`. Destructive endpoints are tagged with `@audited(operation="<verb>")` decorator to enrich the log entry. Non-decorated requests get a minimal record (path, method, status, admin-key fingerprint); decorated requests add operation name and optional body snapshot.

**Rationale**:
- Middleware captures everything uniformly: no risk of forgetting to log.
- Decorator tagging makes the "what is destructive" list explicit and reviewable in code.
- Two-tier recording (minimal vs enriched) keeps log storage manageable while giving detail where it matters.

**Alternatives rejected**:
- *Per-route `await log_audit(...)` calls*: easy to forget; scatters audit logic across handlers.
- *Event-sourced audit via PG trigger*: overengineered; couples audit to DB schema changes.
- *External audit service (e.g., Langfuse)*: heavier setup; prefer DB-local audit that's queryable via same API.

### D4: Audit log is append-only, schema-stable, and queryable via `/api/v1/audit`

**Decision**: New `audit_log` table with columns: `id`, `timestamp`, `request_id`, `method`, `path`, `operation`, `admin_key_fp` (last 8 chars of SHA256), `status_code`, `body_size`, `client_ip`, `notes` (JSONB). Retention enforced by pg_cron job; default 90 days via `AUDIT_LOG_RETENTION_DAYS`. Never UPDATE or DELETE by application code — only pg_cron retention reads and deletes.

**Rationale**:
- Append-only shape prevents accidental tampering.
- `admin_key_fp` (not the full key) satisfies "who did this" without creating a secondary credential-leak surface.
- JSONB `notes` column gives forward compatibility for adding richer context without schema changes.
- pg_cron retention mirrors the existing backup approach; no new infra pattern.

**Alternatives rejected**:
- *Log to file/stdout only*: not queryable; hard to correlate; lost on container restart.
- *Store full request body*: PII risk; storage cost; add opt-in tagging instead.
- *Use existing `telemetry` or OpenTelemetry spans*: audit has stronger durability and query requirements; would require permanent trace retention.

### D5: `aca manage restore-from-cloud` is a thin shell wrapper, not a reimplementation

**Decision**: The restore-from-cloud command is a subprocess orchestrator that calls `mc` (MinIO client) and `pg_restore` with the right flags. It does NOT reimplement database restore logic in Python. It reads MinIO credentials from the local profile (e.g., `railway-cli.yaml` augmented for backup access) and the target DB from `DATABASE_URL`.

**Rationale**:
- The real work is already done by `pg_restore` — reinventing it in Python would add bugs without value.
- Thin wrapper means we can fix and iterate on restore semantics (parallelism, clean mode, specific schema) without changing ACA code.
- Users get exact `pg_restore` behavior — no surprises.

**Alternatives rejected**:
- *Build a Python `DatabaseRestorer` service*: duplicates `pg_restore` features; error-prone.
- *Use Python-native libraries (`psycopg[binary]`)*: requires re-parsing pg_dump format; overengineered.

### D6: OpenAPI contract is generated and committed, not runtime-inferred

**Decision**: `contracts/openapi/v1.yaml` is hand-authored (with help of FastAPI's generated schema as scaffold) and committed. At integration time, a test verifies FastAPI's runtime `/openapi.json` matches the committed contract (drift check).

**Rationale**:
- Consumers can generate clients from a stable file without running the server.
- Committed contract is reviewable in PRs.
- Drift check in CI catches accidental server-side changes that break the contract.

**Alternatives rejected**:
- *Contracts live in code only (FastAPI schema as truth)*: consumers can't generate clients without running the server; harder to review changes.
- *Auto-generate contract from code on every commit*: reviews become noisy with schema churn.

### D7: Contract-first parallel execution with explicit lock scopes

**Decision**: Work packages declare `write_allow` globs that are non-overlapping. The coordinator's file-lock system enforces scope: `wp-api` cannot touch `src/mcp/`, `wp-mcp` cannot touch `src/api/middleware/`, etc. `wp-contracts` runs first (no dependencies); `wp-api`, `wp-mcp`, `wp-ops`, `wp-audit` run in parallel after contracts; `wp-integration` runs last.

**Rationale**:
- Non-overlapping scopes let parallel agents work without merge conflicts.
- Contract-first ensures all four parallel packages agree on the interface.
- Integration package has single-threaded ownership of merge + full test suite.

**Alternatives rejected**:
- *No scope enforcement*: relies on human coordination; history shows this breaks down.
- *All packages sequential*: slower wall-clock; forgoes coordinator capabilities.

### D8: Endpoints designed as single-tenant (per-aca-instance persona model)

**Decision**: New endpoints use flat paths: `/api/v1/kb/search`, `/api/v1/graph/query`. No tenant ID, no persona scoping in URLs. Each aca deployment serves one persona; consumer (`agentic-assistant`) composes multiple aca instances at the routing layer.

**Rationale**:
- Simplifies auth model (one admin key per instance).
- Keeps URL structure clean and predictable.
- Multi-instance deployment is the isolation boundary — cleaner than in-app multi-tenancy.

**Alternatives rejected**:
- *`/api/v1/{persona}/kb/search`*: unnecessary complexity for single-tenant service.
- *Tenant ID in request body*: same concern; duplicate auth/routing complexity.

## Data Model Additions

```sql
-- contracts/db/schema.sql (excerpt)
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    operation TEXT,                     -- from @audited decorator
    admin_key_fp TEXT,                  -- last 8 chars of sha256
    status_code INTEGER NOT NULL,
    body_size INTEGER,
    client_ip INET,
    notes JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT audit_log_timestamp_check CHECK (timestamp >= '2026-01-01')
);

CREATE INDEX idx_audit_log_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_log_operation ON audit_log (operation) WHERE operation IS NOT NULL;
CREATE INDEX idx_audit_log_path_timestamp ON audit_log (path, timestamp DESC);
```

Retention job (Alembic data migration or pg_cron):
```sql
SELECT cron.schedule(
    'audit-log-retention',
    '0 4 * * *',  -- 4 AM UTC daily
    $$DELETE FROM audit_log WHERE timestamp < now() - (current_setting('app.audit_retention_days')::int || ' days')::interval$$
);
```

## API Surface Changes (Summary)

See `contracts/openapi/v1.yaml` for full request/response schemas. New endpoints:

| Method | Path | Audited | Purpose |
|---|---|---|---|
| GET | `/api/v1/kb/search` | No | Full-text/semantic KB search |
| POST | `/api/v1/graph/query` | No | Graph semantic query (read) |
| POST | `/api/v1/graph/extract-entities` | Yes | Write content+summary to graph |
| POST | `/api/v1/references/extract` | Yes | Extract references from content batch |
| POST | `/api/v1/references/resolve` | Yes | Resolve reference batch |
| GET | `/api/v1/kb/lint` | No | KB health check (read) |
| POST | `/api/v1/kb/lint/fix` | Yes | Apply auto-corrections |
| GET | `/api/v1/audit` | No | Query audit log |

## MCP Refactor Pattern

Before:
```python
@mcp.tool()
async def search_knowledge_base(query: str, limit: int = 10) -> list[dict]:
    from src.services.kb_search import KBSearchService
    service = KBSearchService()
    return await service.search(query, limit=limit)
```

After:
```python
@mcp.tool()
async def search_knowledge_base(query: str, limit: int = 10) -> list[dict]:
    client = _get_api_client()
    if client is not None:
        return await client.kb_search(query=query, limit=limit)
    # Fallback: in-process
    from src.services.kb_search import KBSearchService
    return await KBSearchService().search(query, limit=limit)


def _get_api_client() -> ApiClient | None:
    """Return HTTP client if configured, else None for in-process fallback."""
    base_url = os.environ.get("ACA_API_BASE_URL") or settings.api_base_url
    admin_key = os.environ.get("ACA_ADMIN_KEY") or settings.admin_api_key
    if base_url == "http://localhost:8000" and not STRICT_HTTP:
        # Treat dev default as "unset"; prefer in-process
        return None
    if not admin_key:
        return None
    return ApiClient(base_url=base_url, admin_key=admin_key)
```

## Sync-Down CLI Flow

```
aca manage restore-from-cloud [--backup-date YYYY-MM-DD] [--target-db newsletters_dev]
    │
    ├─ 1. Read MinIO creds from profile
    ├─ 2. `mc alias set aca-backups https://minio.railway.internal <key> <secret>`
    ├─ 3. `mc ls aca-backups/backups/` → pick matching date (or latest)
    ├─ 4. `mc cp aca-backups/backups/railway-YYYY-MM-DD-*.dump /tmp/`
    ├─ 5. `pg_restore --clean --if-exists --dbname <target> /tmp/railway-*.dump`
    └─ 6. Delete local dump file
```

Errors surface from subprocess exit codes; no silent failures.

## Performance Considerations

- **MCP HTTP roundtrip overhead**: ~5–20 ms localhost, ~50–100 ms over internet. For batch operations (`resolve_references` with 100+ items), contracts support client-side chunking (default batch size 50) — no new endpoint needed.
- **Audit log writes**: single INSERT per request on destructive endpoints, zero on read endpoints. Insertion latency ~1–3 ms. If observed to matter, move to queued async writes (not in scope).
- **Restore-from-cloud throughput**: limited by MinIO download speed + `pg_restore` parallelism. For typical backup size (~500 MB compressed), expect 2–5 minutes end-to-end.

## Backwards Compatibility

- **Existing HTTP endpoints**: no changes.
- **Existing MCP tool schemas**: no changes. Tools gain optional HTTP routing internally.
- **Existing CLI commands**: no changes. HTTP mode already exists; new commands add methods to `ApiClient`.
- **Existing profiles**: no changes. New env vars (`ACA_API_BASE_URL`, `ACA_ADMIN_KEY`) are additive; when unset, behavior matches pre-change.

## Rollout Plan

1. Ship contracts + schema migration (PR #1).
2. Ship HTTP endpoints + audit middleware together (PR #2) — audit coverage lands atomically with destructive endpoints.
3. Ship MCP refactor (PR #3) — MCP tools default to in-process (backwards compatible); HTTP mode is opt-in via env vars.
4. Ship sync-down CLI + docs (PR #4) — fully independent.
5. Integration/validation PR — runs full test suite, verifies no regressions.

PRs 1 → 2 are sequential; PRs 3 and 4 can land in parallel after PR 2.

## Security Review

- **No new credential distribution**: all remote access still behind `X-Admin-Key`; no DB creds on developer machines.
- **Audit log as forensic tool**: destructive operations now traceable by admin-key fingerprint.
- **MCP HTTP mode**: same auth as direct HTTP calls (`X-Admin-Key` header).
- **Restore-from-cloud**: reads MinIO backup (encrypted in transit via HTTPS, encrypted at rest by Railway MinIO); writes local DB only.
- **No new attack surface**: no public Postgres proxy; no new unauthenticated endpoints; middleware can't bypass existing auth.
