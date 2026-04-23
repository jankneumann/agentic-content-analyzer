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

**Decision**: Add `AuditMiddleware` that records **every** request to `/api/v1/*` — reads, writes, successes, failures, authenticated, unauthenticated. Destructive endpoints are additionally tagged with `@audited(operation="<verb>")` to enrich the log entry. Non-decorated requests get a minimal record (path, method, status, admin-key fingerprint, body_size); decorated requests add operation name and optional `notes` JSONB context.

**Rationale**:
- Middleware captures everything uniformly: no risk of forgetting to log.
- Decorator tagging makes the "what is destructive" list explicit and reviewable in code.
- Two-tier recording (minimal vs enriched) keeps log storage manageable while giving detail where it matters.
- Logging 401/403/404/422 responses is the main forensic value — detecting brute-force attempts, misconfigured clients, and probing. Skipping reads would silently discard this data.

**Alternatives rejected**:
- *Log only destructive endpoints*: loses auth-failure forensics; creates a spec↔design contradiction (spec says "every request").
- *Per-route `await log_audit(...)` calls*: easy to forget; scatters audit logic across handlers.
- *Event-sourced audit via PG trigger*: overengineered; couples audit to DB schema changes.
- *External audit service (e.g., Langfuse)*: heavier setup; prefer DB-local audit that's queryable via same API.

### D3a: Middleware ordering and OPTIONS bypass

**Decision**: The audit middleware registers in this exact order (FastAPI applies middleware in reverse-registration order, so **outermost runs first**): `[TraceMiddleware, AuditMiddleware, AuthMiddleware, CORSMiddleware, ...routes]`. Concretely:

1. `TraceMiddleware` / `RequestIdMiddleware` runs first so every audit row can reference a valid `request_id`.
2. `AuditMiddleware` runs **outside** `AuthMiddleware` so that 401/403 responses (invalid or missing admin key) are still recorded. This is the intended forensic signal — otherwise a caller with a bad key produces no audit trace.
3. `AuthMiddleware` runs next, validating `X-Admin-Key` or session cookie.
4. `CORSMiddleware` runs innermost, handling CORS response headers.

**OPTIONS preflight bypass**: `AuditMiddleware` short-circuits on `request.method == "OPTIONS"` (no row written). Rationale: preflight requests carry no data, triple audit volume, and bypass auth already (per PR #202 fix). OPTIONS audit entries would be noise.

**`admin_key_fp` source**: Since audit runs outside auth, the fingerprint is computed from `request.headers.get("X-Admin-Key")` directly (SHA-256, last 8 chars) **whenever the header is present**, regardless of whether the key is valid. `admin_key_fp` is NULL only when the `X-Admin-Key` header is absent entirely. This is intentional — invalid-key attempts deserve a fingerprint for correlation across requests (e.g., detecting credential-probing from a single attacker across multiple attempts).

**Rationale**:
- Outside-auth placement is non-obvious but necessary for failed-auth audit coverage.
- OPTIONS bypass matches the existing `AuthMiddleware` pattern (PR #202) and avoids CORS regression.
- Memory reference: project memory `project_mcp_sole_consumer.md` context + PR #202 middleware order fix.

**Alternatives rejected**:
- *Inside-auth placement*: auth-failure requests would not be audited — loses the most forensically valuable signal.
- *Inline OPTIONS audit*: triples audit table size with no forensic value; complicates querying.

### D4: Audit log is append-only, schema-stable, and queryable via `/api/v1/audit`

**Decision**: New `audit_log` table with columns: `id`, `timestamp`, `request_id`, `method`, `path`, `operation`, `admin_key_fp` (last 8 chars of SHA256), `status_code`, `body_size`, `client_ip`, `notes` (JSONB). Retention enforced by pg_cron job; default 90 days via `AUDIT_LOG_RETENTION_DAYS`, **interpolated at Alembic migration time** (NOT read via `current_setting()` GUC — see D4a). Never UPDATE or DELETE by application code — only pg_cron retention reads and deletes.

`client_ip` is populated from the first non-empty header of: `Cf-Connecting-Ip` (Cloudflare), `X-Forwarded-For` (first entry), `request.client.host` (direct). Railway sits behind Cloudflare in production, so the direct peer IP is always a Cloudflare edge — without proxy-header handling, `client_ip` would be forensically useless.

`GET /api/v1/audit` query parameters:
- `since`, `until` — timestamp range
- `path` — **exact match** (not LIKE / prefix); OpenAPI declares pattern `^[/a-zA-Z0-9_-]+$` to block wildcard injection
- `operation` — exact match
- `status_code` — exact integer
- `limit` — default 100, max 1000 (server-clamped, never fails)

**Rationale**:
- Append-only shape prevents accidental tampering.
- `admin_key_fp` (not the full key) satisfies "who did this" without creating a secondary credential-leak surface.
- JSONB `notes` column gives forward compatibility for adding richer context without schema changes.
- pg_cron retention mirrors the existing backup approach; no new infra pattern.

**Alternatives rejected**:
- *Log to file/stdout only*: not queryable; hard to correlate; lost on container restart.
- *Store full request body*: PII risk; storage cost; add opt-in tagging instead.
- *Use existing `telemetry` or OpenTelemetry spans*: audit has stronger durability and query requirements; would require permanent trace retention.

### D4a: Retention interval is interpolated at migration time, not read via GUC

**Decision**: The Alembic data migration for pg_cron retention reads `AUDIT_LOG_RETENTION_DAYS` from the environment at migration time and writes the literal integer into the scheduled SQL:

```python
retention_days = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "90"))
op.execute(
    f"""
    SELECT cron.schedule(
        'audit-log-retention',
        '0 4 * * *',
        $$DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '{retention_days} days'$$
    )
    """
)
```

**Rationale**:
- Railway managed Postgres restricts `ALTER SYSTEM SET app.*` GUC variables; `current_setting('app.audit_retention_days')` would either fail or silently return default.
- Migration-time interpolation makes retention fully reproducible: the exact value is visible in `git log` of the migration file.
- Changing retention requires a new migration (small cost for a rarely-changed value).

**Alternatives rejected**:
- *Runtime GUC via `current_setting('app.audit_retention_days')`*: Railway doesn't support setting this reliably; the cron job would fail or use defaults silently.
- *App-managed retention (not pg_cron)*: duplicates scheduling infra; pg_cron is already available per Railway Docker setup.

### D4b: Audit write failure is non-blocking

**Decision**: If the audit-log INSERT raises (connection pool exhausted, disk full, deadlock, bad DB state), the middleware catches the exception, logs it to stderr (with `request_id` for correlation), and allows the original request to complete normally. The response is NOT affected.

**Rationale**:
- A logging failure on the hot path producing production 5xx is user-hostile. Forensic gaps are recoverable; customer-facing outages are not.
- The logged stderr message lets operators detect systematic audit failures via log scanning.
- The audit table itself uses conservative types and indexes — failures here are rare enough that "best effort" is acceptable.

**Alternatives rejected**:
- *Request fails 503 on audit failure*: maximum forensic coverage but worst UX; couples every `/api/v1/*` request's availability to audit subsystem health.
- *Buffer failed audit writes to memory + retry*: extra complexity; memory loss on restart.

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

### D7: Contract-first sequenced execution with explicit lock scopes

**Decision**: Work packages declare `write_allow` globs. The coordinator's file-lock system enforces scope. The actual DAG — driven by real file-scope overlap and logical dependency — is:

```
                          ┌─ wp-audit ─┐
wp-contracts ─────┬───────┤             ├─── wp-api ── wp-mcp ── wp-integration
                  │       └─ wp-ops ──────────────────────────────┘
                  └───────────────────────────────────────────────┘
```

- **`wp-contracts`** (priority 1, no deps): writes `openspec/changes/cloud-db-source-of-truth/contracts/**` only. Foundational.
- **`wp-audit`** (priority 2, deps: wp-contracts): writes `src/api/middleware/audit.py`, `src/api/routes/audit_routes.py`, `src/api/app.py` (middleware registration block), `alembic/versions/*audit_log*.py`, `tests/api/test_audit_*.py`.
- **`wp-ops`** (priority 2, deps: wp-contracts): writes `src/cli/manage_commands.py` (restore subcommand), `src/cli/restore_commands.py`, `docs/SYNC_DOWN.md`, `docs/SETUP.md`, `tests/cli/test_restore_from_cloud.py`. **Non-overlapping with wp-audit** — runs in parallel.
- **`wp-api`** (priority 3, deps: wp-contracts + wp-audit): writes new route modules + `src/api/app.py` (router `include_router` block — different section from wp-audit's middleware block). Serialized after wp-audit because both edit `src/api/app.py`, and `@audited` decorator + `audit_log` table must exist before destructive endpoints are implemented.
- **`wp-mcp`** (priority 4, deps: wp-contracts + wp-api): writes `src/mcp_server.py`, `src/mcp/api_client.py`, MCP tests. Serial after wp-api because the refactor needs working HTTP endpoints to call.
- **`wp-integration`** (priority 5, deps: all): writes `tests/contract/test_openapi_drift.py`, `CLAUDE.md` gotchas table, runs full test suite.

**`src/api/app.py` concurrency handling**: wp-audit appends a middleware registration; wp-api appends `include_router` calls. Non-overlapping sections, but the file is locked at the package level. Serialization via the dependency edge (wp-api deps wp-audit) is sufficient — no concurrent edits ever occur.

**Rationale**:
- Real parallelism lane: `wp-audit ∥ wp-ops` after wp-contracts lands. These touch completely disjoint file sets (middleware/migration vs CLI/docs), so the coordinator's scope enforcement is the primary safety net.
- Contract-first ensures wp-audit/wp-api/wp-mcp all agree on the OpenAPI + DB schema.
- Integration package has single-threaded ownership of merge + full test suite.

**Alternatives rejected**:
- *Claim parallel lanes that aren't actually parallel*: misleading plan narrative; schedulers treat the DAG as authoritative. (This was an earlier iteration of the plan — fixed after PLAN_REVIEW round 1 pointed it out.)
- *No scope enforcement*: relies on human coordination; history shows this breaks down.
- *All packages sequential*: slower wall-clock; forgoes `wp-audit ∥ wp-ops` parallelism.

### D8: Endpoints designed as single-tenant (per-aca-instance persona model)

**Decision**: New endpoints use flat paths: `/api/v1/kb/search`, `/api/v1/graph/query`. No tenant ID, no persona scoping in URLs. Each aca deployment serves one persona; consumer (`agentic-assistant`) composes multiple aca instances at the routing layer.

**Rationale**:
- Simplifies auth model (one admin key per instance).
- Keeps URL structure clean and predictable.
- Multi-instance deployment is the isolation boundary — cleaner than in-app multi-tenancy.

**Alternatives rejected**:
- *`/api/v1/{persona}/kb/search`*: unnecessary complexity for single-tenant service.
- *Tenant ID in request body*: same concern; duplicate auth/routing complexity.

### D9: MCP tool return shapes adopt the new OpenAPI contract (breaking change, accepted)

**Decision**: The 4 refactored MCP tools (`search_knowledge_base`, `search_knowledge_graph`, `extract_references`, `resolve_references`) update their return shapes to match the new OpenAPI response bodies. No adapter layer translates HTTP responses back to legacy MCP shapes.

Shape changes:
| Tool | Before (current in-process) | After (matches OpenAPI) |
|---|---|---|
| `search_knowledge_base` | `list[{name, category, summary, relevance_score, mention_count}]` | `{topics: [{slug, title, score, excerpt, last_compiled_at}], total_count: int}` |
| `extract_references` | `{scanned, references_found, dry_run}` | `{references_extracted, content_processed, has_more, next_cursor? (ISO-8601 when has_more=true), per_content?: [{content_id, references_found}]}` |
| `resolve_references` | `{resolved, batch_size}` | `{resolved_count, still_unresolved_count, has_more}` |
| `search_knowledge_graph` | (current shape preserved) | `{entities: [...], relationships: [...]}` — already matches |

Tool **names and argument schemas** are preserved — no rename, no argument rename/removal. Only return shapes change.

**Rationale**:
- Removes the need for an adapter layer (which would add ~200 LOC of shape-translation code + unit tests for each tool and would need maintenance on every HTTP contract change).
- Project memory `project_mcp_sole_consumer.md`: the MCP consumer set is controlled (@jankneumann's tooling + `agentic-assistant`). External consumers do not exist.
- Consumer migration is one-shot: update the consumer code to read the new field names, redeploy. Shallow change.
- Earlier iteration of the plan (before PLAN_REVIEW round 1) promised "byte-identical" schemas — codex review caught that the current in-process outputs already differ from the new HTTP shapes. The "byte-identical" claim was unachievable without adapter code. Dropping it simplifies wp-mcp substantially.

**Alternatives rejected**:
- *Adapter layer preserving legacy MCP shapes*: ~200 LOC of throwaway code; maintenance burden; delays consumer from adopting the canonical HTTP shape.
- *Keep current in-process shapes, don't refactor to HTTP*: defeats the proposal's core goal.

### D10: Observability inherits from existing FastAPI middleware stack

**Decision**: New endpoints and MCP HTTP calls use the existing observability stack — no new observability infrastructure. Specifically:

- **Request ID** — generated by the existing `TraceMiddleware` at `src/api/app.py:167-168` (implementation context in `src/utils/logging.py:47-91`); populated into `request.state.request_id` and echoed in `X-Request-Id` response header. `AuditMiddleware` reads from `request.state.request_id` so audit rows correlate with trace logs. No new middleware is needed — `wp-audit` has read-only access to the existing `TraceMiddleware` module.
- **Structured logs** — use the project's `src/utils/logging.py` context-aware logger. Route handlers log at INFO on success, WARNING on 4xx, ERROR on 5xx. Each log line includes `request_id` for trace correlation.
- **OTel spans** — inherited from the existing FastAPI instrumentation; each new route automatically becomes a span with `http.route`, `http.method`, `http.status_code` attributes. No per-route instrumentation needed.
- **Audit span enrichment** — the `AuditMiddleware` SHALL additionally enrich the active OTel span with `audit.operation` (string, nullable — matches the `@audited` decorator value), `audit.status_code` (integer — matches `audit_log.status_code`), and on insert failure, `audit.write_failure=true`. These SHALL requirements are encoded in `specs/audit-log/spec.md` §"Audit middleware observability attributes" so they are testable from the normative layer, not just in task 2.10.
- **Langfuse traces** — LLM-invoking endpoints (`extract-entities`, `references/extract`) emit Langfuse spans via the existing client. MCP HTTP-mode calls also emit a span tagged `mcp.tool=<name>`.
- **Metrics** — not in scope for this proposal (we use Langfuse + OTel for now; Prometheus metrics deferred to a later observability-focused proposal).

**Rationale**:
- No new observability infra means zero rollout risk from this proposal's observability side.
- `request_id` correlation between audit and traces enables end-to-end forensics ("who did X at time T and what was the trace context?").

**Alternatives rejected**:
- *Add Prometheus metrics in this proposal*: scope creep; defer to dedicated observability proposal.
- *Skip request_id correlation*: reduces forensic value; already free from existing middleware.

### D11: Explicit timeouts and one-shot retries for external dependencies

**Decision**: All external-dependency calls (Graphiti/Neo4j/FalkorDB, MinIO restore, MCP HTTP roundtrips) declare timeouts and retry policy:

| Dependency | Timeout | Retries | On timeout |
|---|---|---|---|
| `POST /graph/query` (Graphiti read) | 10s | 0 (client retry if needed) | 504 Gateway Timeout |
| `POST /graph/extract-entities` (Graphiti write + LLM) | 30s | 0 (LLM calls are non-idempotent) | 504 Gateway Timeout |
| `POST /references/extract` / `/resolve` (internal + LLM) | 60s per batch | 0 | 504 Gateway Timeout |
| MCP HTTP-mode call (ApiClient) | 30s | 1× with 1s backoff on {429, 502, 503, 504, connection reset} | Tool returns error after second failure |
| MinIO `mc cp` for restore-from-cloud | N/A (subprocess) | 0 — fail fast, user retries | Subprocess nonzero exit surfaces to CLI |
| Audit-log INSERT | 1s | 0 | Log to stderr, non-blocking (see D4b) |

Fatal MCP HTTP status codes (4xx other than 429): fail fast, no retry.

**Rationale**:
- Timeouts bounded: no request hangs indefinitely, protecting FastAPI worker pool.
- Single retry with backoff: catches transient network blips without amplifying overload (two retries with longer backoff would risk cascading failures).
- LLM calls are non-idempotent (different output per call) — retry would produce inconsistent results; fail instead.
- MCP retry matches typical agentic use: one blip per session is absorbed transparently; two blips surface to the agent as tool failure (agent can retry at higher layer if appropriate).

**Alternatives rejected**:
- *No explicit timeouts*: default httpx timeout of 5s is too short for LLM endpoints, too long for health checks. Per-call tuning is clearer.
- *Exponential backoff with N retries*: overkill for this proposal's failure surface.

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

Retention job (Alembic data migration — retention interval is interpolated at migration time per D4a, NOT read via `current_setting()`):
```python
# alembic/versions/<rev>_add_audit_log_retention_job.py
retention_days = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "90"))
op.execute(
    f"""
    SELECT cron.schedule(
        'audit-log-retention',
        '0 4 * * *',  -- 4 AM UTC daily
        $$DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '{retention_days} days'$$
    )
    """
)
```
To change retention: create a new migration that unschedules then reschedules the job with the new interval. Do NOT rely on `current_setting('app.audit_retention_days')` — Railway managed Postgres does not reliably support the `app.*` GUC namespace.

## API Surface Changes (Summary)

See `contracts/openapi/v1.yaml` for full request/response schemas. **All endpoints write at least a minimal `audit_log` entry** (per D3). The "Enriched" column indicates which endpoints also carry a `@audited(operation=...)` decorator tag:

| Method | Path | Enriched | Purpose |
|---|---|---|---|
| GET | `/api/v1/kb/search` | — | Full-text/semantic KB search |
| POST | `/api/v1/graph/query` | — | Graph semantic query (read) |
| POST | `/api/v1/graph/extract-entities` | `graph.extract_entities` | Write content+summary to graph |
| POST | `/api/v1/references/extract` | `references.extract` | Extract references from content batch |
| POST | `/api/v1/references/resolve` | `references.resolve` | Resolve reference batch |
| GET | `/api/v1/kb/lint` | — | KB health check (read) |
| POST | `/api/v1/kb/lint/fix` | `kb.lint.fix` | Apply auto-corrections |
| GET | `/api/v1/audit` | — | Query audit log |

**Error responses** (all paths): 401 (missing/invalid admin key), 422 (validation), 504 (graph/LLM timeout where applicable), plus path-specific codes (404/409 for `extract-entities`). All error bodies use the RFC 7807 `Problem` schema.

## MCP Refactor Pattern

Before (current in-process, returns legacy shape):
```python
@mcp.tool()
async def search_knowledge_base(query: str, limit: int = 10) -> list[dict]:
    from src.services.kb_search import KBSearchService
    service = KBSearchService()
    # Returns list[{name, category, summary, relevance_score, mention_count}]
    return await service.search(query, limit=limit)
```

After (HTTP mode with in-process fallback; **returns NEW OpenAPI shape**, breaking change per D9):
```python
@mcp.tool()
async def search_knowledge_base(query: str, limit: int = 10) -> dict:
    """Returns: {topics: [{slug, title, score, excerpt, last_compiled_at}], total_count}"""
    client = _get_api_client()
    if client is not None:
        return await client.kb_search(q=query, limit=limit)
    # Fallback: in-process. Still returns the NEW shape (in-process handler wraps
    # the KBSearchService result with the OpenAPI envelope).
    from src.services.kb_search import KBSearchService
    results = await KBSearchService().search(query, limit=limit)
    return {
        "topics": [
            {
                "slug": r.slug,
                "title": r.title,
                "score": r.score,
                "excerpt": r.excerpt,
                "last_compiled_at": r.last_compiled_at.isoformat(),
            }
            for r in results
        ],
        "total_count": len(results),
    }


def _get_api_client() -> ApiClient | None:
    """Return HTTP client if configured, else None for in-process fallback."""
    base_url = os.environ.get("ACA_API_BASE_URL") or settings.api_base_url
    admin_key = os.environ.get("ACA_ADMIN_KEY") or settings.admin_api_key
    if base_url == "http://localhost:8000" and not STRICT_HTTP:
        # Treat dev default as "unset"; prefer in-process
        return None
    if admin_key is None:
        if STRICT_HTTP:
            raise RuntimeError("strict-http: ACA_ADMIN_KEY required")
        # Log warning to stderr (not tool response, to avoid polluting MCP output)
        import sys
        print(
            f"WARN: ACA_API_BASE_URL set ({base_url}) but ACA_ADMIN_KEY missing; "
            f"falling back to in-process mode.",
            file=sys.stderr,
        )
        return None
    return ApiClient(base_url=base_url, admin_key=admin_key, timeout=30.0)
```

**Note:** The in-process fallback in the post-refactor code still returns the NEW OpenAPI shape — it just constructs the shape locally from the service result rather than going through HTTP. This ensures consumers see a consistent shape regardless of which mode the tool runs in.

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

- **MCP HTTP roundtrip overhead**: ~5–20 ms localhost, ~50–100 ms over internet. For batch operations, `resolve_references` requires server-side `batch_size` + `has_more` pagination (per revised spec) — no unbounded work.
- **Audit log writes**: single INSERT per request on **every** `/api/v1/*` endpoint (reads AND writes, per D3). Insertion latency ~1–3 ms. Per-request cost is small but non-zero; acceptable for forensic uniform coverage. If observed to matter for a hot endpoint via Langfuse/APM, move to queued async writes (not in scope). **Not counted**: OPTIONS preflight (bypassed per D3a) — would otherwise triple audit volume.
- **Graphiti timeouts**: `/graph/query` 10s, `/graph/extract-entities` 30s. Timeout exhaustion returns 504 (per D11). FastAPI worker pool is protected.
- **Restore-from-cloud throughput**: limited by MinIO download speed + `pg_restore` parallelism. For typical backup size (~500 MB compressed), expect 2–5 minutes end-to-end.
- **Reference-extract bounds**: date-range extraction uses `batch_size` (default 100, max 1000) and `since`-only filters reject 10-year lookbacks by clamping `until - since <= 90 days` at validation time.

## Backwards Compatibility

- **Existing HTTP endpoints**: no changes.
- **Existing MCP tool argument schemas and names**: unchanged.
- **Existing MCP tool return shapes**: **BREAKING** per D9. The 4 refactored tools (`search_knowledge_base`, `extract_references`, `resolve_references`; `search_knowledge_graph` shape is preserved) return the new OpenAPI shapes. Consumers (`agentic-assistant` + @jankneumann's local tooling) migrate in lockstep with this PR. No external public consumers.
- **Existing CLI commands**: no changes. HTTP mode already exists; new commands add methods to `ApiClient`.
- **Existing profiles**: no changes. New env vars (`ACA_API_BASE_URL`, `ACA_ADMIN_KEY`) are additive; when unset, behavior matches pre-change.

## Rollout Plan

**Pre-merge check**: verify the `add-api-versioning` OpenSpec proposal has NOT landed on `/api/v2/`. If it has, rebase this proposal's new endpoints onto v2 before merge. (Currently: add-api-versioning is a deferred/open proposal.)

Under the coordinated tier, implementation ships as a single coordinated PR that merges wp-contracts → wp-audit/wp-ops → wp-api → wp-mcp → wp-integration. Internal ordering reflects the DAG in D7:

1. wp-contracts artifacts commit (OpenAPI, DB schema, generated stubs).
2. wp-audit + wp-ops run in parallel: middleware+migration lands AND sync-down CLI lands.
3. wp-api lands: new HTTP endpoints registered in `src/api/app.py` router block (different section from wp-audit's middleware block).
4. wp-mcp lands: MCP tools refactored to HTTP mode with in-process fallback.
5. wp-integration: drift test, full test suite, MCP E2E smoke, `CLAUDE.md` updates.
6. Final merge + Railway deploy → verify audit table populated + endpoints respond via smoke test.

Consumer migration (`agentic-assistant`): coordinate via a separate changelog entry in `agentic-assistant` that updates its MCP client consumers for the D9 shape change. Ship `agentic-assistant` update in lockstep with this PR's deploy.

## Security Review

- **No new credential distribution**: all remote access still behind `X-Admin-Key`; no DB creds on developer machines.
- **Audit log as forensic tool**: every `/api/v1/*` request is now traceable by admin-key fingerprint + request_id — including failed-auth attempts (401/403 are logged outside AuthMiddleware per D3a). Brute-force and probing attempts will appear in audit rows with NULL or misshapen `admin_key_fp`.
- **MCP HTTP mode**: same auth as direct HTTP calls (`X-Admin-Key` header). When `--strict-http` is enabled, MCP server refuses to start with incomplete config (fail-closed).
- **Restore-from-cloud**: reads MinIO backup (encrypted in transit via HTTPS, encrypted at rest by Railway MinIO); writes local DB only. Never runs against production DB.
- **No new attack surface**: no public Postgres proxy; no new unauthenticated endpoints; middleware can't bypass existing auth. OPTIONS preflight bypass in AuditMiddleware mirrors the AuthMiddleware pattern fixed in PR #202 — CORS continues working.
- **Audit path filter**: `GET /api/v1/audit?path=<exact>` uses **exact match** (per D4), with OpenAPI pattern `^[/a-zA-Z0-9_-]+$` blocking wildcard-injection attempts at the validation layer.
- **client_ip forensics**: logged from `Cf-Connecting-Ip` / `X-Forwarded-For` / `request.client.host` (in priority order) — captures real client IPs behind Cloudflare rather than edge IPs.
- **Admin-key fingerprint**: SHA-256 last 8 chars = 32 bits of entropy. Sufficient for correlation across an admin's own traffic; collision probability across distinct keys is ~0.023% at 10 keys, ~0.1% at 25 — acceptable for audit forensics, not a primary auth mechanism.
