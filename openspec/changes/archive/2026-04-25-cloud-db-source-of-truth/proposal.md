# Cloud DB as Source of Truth — HTTP/MCP Parity for External Consumers

## Why

ACA is now deployed to Railway at `api.aca.rotkohl.ai` (backend) and `app.aca.rotkohl.ai` (frontend), backed by Railway's internal PostgreSQL, FalkorDB/Neo4j, and MinIO. Per the deployment model established in the recent Cloudflare + Railway cutover, **the cloud DB is the authoritative data store**; local development DBs are scratch environments for experimentation.

Three gaps currently block this model from being coherent end-to-end:

1. **MCP tools bypass HTTP** — `search_knowledge_base`, `search_knowledge_graph`, `extract_references`, and `resolve_references` call services/DB in-process. An MCP client running on a laptop cannot target Railway without either local DB access (which defeats "cloud as source of truth") or a refactor of MCP to use HTTP.

2. **CLI direct-mode commands can't be used remotely** — `aca graph extract-entities`, `aca graph query`, `aca kb lint` have no HTTP path. Running them against Railway requires `railway run` (container exec) or running them locally against a stale snapshot.

3. **No local-dev sync-down workflow** — Backups run nightly via pg_cron → MinIO (see `docs/SETUP.md:771-850`), but developers have no one-command way to pull a recent snapshot into their local DB for experiments.

The consumer project at `~/Coding/agentic-assistant` is awaiting its `http-tools-layer` phase to integrate with this backend. Shipping this proposal unblocks that integration and cements HTTP as the single source-of-truth path.

## What Changes

### 1. HTTP endpoints (new)

Close the MCP↔HTTP parity gaps identified in discovery:

- `GET /api/v1/kb/search?q=<text>&limit=<n>` — Full-text / semantic search over compiled KB topics
- `POST /api/v1/graph/query` — Semantic knowledge-graph query (Graphiti-backed)
- `POST /api/v1/graph/extract-entities` — Push content+summary into the graph
- `POST /api/v1/references/extract` — Extract citations/references from a content batch
- `POST /api/v1/references/resolve` — Resolve a batch of references against existing content
- `GET /api/v1/kb/lint` — Read-only KB health check (stale topics, orphans, score anomalies)
- `POST /api/v1/kb/lint/fix` — Apply auto-corrections flagged by the linter

All behind `X-Admin-Key` auth (consistent with existing admin surface).

### 2. MCP refactor

- Rewrite the 4 gap MCP tools to call `/api/v1/*` via the shared `ApiClient` (new reuse of `src/cli/api_client.py` or a new `src/mcp/api_client.py` adapter).
- MCP gains config: `ACA_API_BASE_URL`, `ACA_ADMIN_KEY`. Falls back to in-process service calls when unset (preserves offline/embedded use).
- **Breaking change (accepted)**: MCP tool return shapes are updated to match the new OpenAPI contract — `search_knowledge_base` now returns `{topics, total_count}` instead of a flat list with `name/category/summary/relevance_score/mention_count`; `extract_references` returns `{references_extracted, content_processed, has_more, next_cursor?, per_content?}` instead of `{scanned, references_found, dry_run}` (where `has_more` is always present, `next_cursor` appears only when `has_more=true`, and `per_content` is optional enriched detail); `resolve_references` returns `{resolved_count, still_unresolved_count, has_more}` instead of `{resolved, batch_size}`. Consumers migrate in lockstep. (Rationale: the MCP consumer set is controlled — @jankneumann's local tooling + `agentic-assistant` project, both controlled by the same owner. A shape-identity adapter layer would cost more engineering than a coordinated migration.)
- Tool **names and argument schemas** are preserved (no rename, no argument rename/removal).

### 3. Sync-down developer UX

- New CLI: `aca manage restore-from-cloud [--backup-date YYYY-MM-DD] [--target-db <name>]`
- Thin wrapper over the existing MinIO → `pg_restore` pipeline (`mc cp` + `pg_restore --clean --if-exists`).
- New doc: `docs/SYNC_DOWN.md` covering prerequisites, examples, freshness tradeoffs, PII caveats.

### 4. Audit logging for all `/api/v1/*` requests

- New middleware `src/api/middleware/audit.py` logs **every** request to `/api/v1/*` — reads and writes, successes and failures, authenticated and unauthenticated. Minimal record: endpoint, method, admin-key fingerprint (last 8 chars of SHA-256, or NULL), request ID, timestamp, request body size, response status, client IP. **Failed-auth requests (401/403) are also logged** — this is the main forensic value, so the middleware runs OUTSIDE AuthMiddleware.
- Destructive endpoints additionally tagged via `@audited(operation="<verb>")` decorator — adds `operation` name and optional `notes` JSONB for enriched context. Destructive set: `POST /kb/lint/fix`, `POST /graph/extract-entities`, `POST /references/extract`, `POST /references/resolve`, plus any existing `DELETE /topics/{slug}`, `POST /kb/purge`, `POST /manage/switch-embeddings` that already exist.
- Admin read endpoint: `GET /api/v1/audit?since=<ts>&until=<ts>&path=<exact>&operation=<str>&status_code=<int>&limit=<n>` (max 1000).
- New Alembic migration for `audit_log` table. Retention: 90 days, configurable via `AUDIT_LOG_RETENTION_DAYS` — retention value is interpolated into the pg_cron schedule SQL at migration time (Railway managed Postgres does not support runtime `current_setting('app.*')` GUCs reliably).
- **Audit write is best-effort, non-blocking**: if the audit INSERT fails (disk full, connection pool exhaustion), the error is logged to stderr and the original request proceeds normally. Rationale: forensic gaps are recoverable; production 5xx caused by a logging failure is not.
- OPTIONS preflight requests bypass audit logging (they bypass auth too; logging CORS preflights would triple audit volume with no forensic value).

### Out of Scope

- **`aca worker *`, `aca evaluate *`** — server-local concerns (worker lifecycle, LLM evaluation runs). Use `railway run` or dashboard for these.
- **`aca sync obsidian`** — writes to developer's local Obsidian vault; inherently local-only.
- **`aca manage setup-gmail`** — interactive browser OAuth; not HTTP-shaped.
- **Public Postgres TCP proxy** — explicitly avoided. Remote data access stays behind API auth, not DB creds on developer machines.
- **HTTP-ification of `aca manage` batch commands beyond the listed ones** — deferred; add later as `agentic-assistant` surfaces concrete needs (extract-refs and resolve-refs are in scope because they have existing MCP tools).
- **Breaking changes to existing HTTP endpoints** — stay within `/api/v1/`; coordinate with the deferred `add-api-versioning` proposal on v2 naming conventions when those become relevant.

## Impact

### Code touched (approximate)

- `src/api/routes/` — new `graph_routes.py`, `kb_search_routes.py`, `audit_routes.py`; extend `reference_routes.py` (coordinate with `add-content-references` proposal); extend `kb_routes.py` with lint endpoints
- `src/api/middleware/audit.py` — new
- `src/mcp_server.py` — refactor 4 tools; add HTTP client config
- `src/cli/api_client.py` — add methods for new endpoints
- `src/cli/manage_commands.py` — add `restore-from-cloud` subcommand
- `alembic/versions/` — new migration for `audit_log` table
- `docs/SYNC_DOWN.md` — new
- Tests: API route tests, MCP integration tests, audit middleware tests

### External consumers

- **`agentic-assistant`** can proceed with `http-tools-layer` phase against a stable OpenAPI contract. This proposal's contracts/ directory provides a generation-ready spec.
- **Persona isolation is per-aca-instance, not multi-tenant within one aca.** Different `agentic-assistant` personas (work, personal) will each point at a separate aca deployment — distinct Railway projects with different subdomains (e.g., `api.aca-personal.rotkohl.ai`, `api.aca-work.rotkohl.ai`), or different local ports for development. This proposal therefore does **not** require tenant-scoped URL paths, tenant IDs in requests, or per-tenant auth. Each aca instance is a single-tenant service; composition into multi-persona workflows happens at the consumer (agentic-assistant) layer.
- **Existing MCP clients**: transparent — same tool names, same schemas. Tools gain HTTP-client mode; fall back to in-process when unconfigured.
- **Existing CLI users**: unaffected — direct mode still works; HTTP mode gains additional commands.

### Performance

- MCP HTTP mode adds ~5–20 ms per tool call on localhost, ~50–100 ms over internet. Acceptable for interactive and agentic use.
- Batch MCP tools (`resolve_references` on large batches) use server-side pagination via `batch_size` + `has_more` — no unbounded work. Reference-extract is bounded by the same `batch_size` parameter.
- Audit write adds ~1–3 ms per request (single `INSERT`) on every `/api/v1/*` path. Not free, but the forensic value and uniform coverage are worth the cost. If observed to matter for a hot endpoint, move to queued async writes (not in scope).
- Graphiti (Neo4j/FalkorDB) calls have enforced timeouts: 10s for `/graph/query` (read), 30s for `/graph/extract-entities` (write with LLM). Exceeding the timeout returns 504 Gateway Timeout.
- MCP HTTP mode retries transient failures (429, 502, 503, 504, connection reset) **once** with 1s backoff. Fatal status codes (other 4xx) fail fast.

### Security

- No new DB-credential distribution. All remote access stays behind `X-Admin-Key`.
- Audit log provides forensic capability for destructive operations.
- Admin-key fingerprinting (not full key) in audit log prevents accidental leak.

## Approaches Considered

### Approach 1: Sequential phases

**Description**: Ship in strict order — (1) HTTP endpoints, (2) MCP refactor, (3) sync-down wrapper, (4) audit logging. Each phase is a separate PR, gated on the previous.

**Pros**:
- Simplest to reason about; easy to pause/resume
- Minimum merge-conflict risk
- Natural for single-contributor work
- Clear rollback points if a phase has issues

**Cons**:
- Longest wall-clock time (~4 PRs sequentially)
- MCP refactor blocked behind HTTP endpoints
- Audit logging arrives last — destructive endpoints ship without audit trail during the intermediate window
- Doesn't leverage available parallel-coordinator infrastructure

**Effort**: L (estimated 4–5 sessions)

### Approach 2: Contract-first sequenced lanes (Recommended)

**Description**: Define OpenAPI contracts + MCP tool schemas + audit log schema up-front. Then dispatch work packages with a mix of parallel and serial ordering, reflecting real file-scope overlap (notably `src/api/app.py`):

- **wp-contracts** (priority 1, no deps): OpenAPI 3.1 spec for new endpoints + JSON schemas + DB schema. Foundational.
- **wp-audit** (priority 2, deps: wp-contracts): Audit middleware + `@audited` decorator + `audit_log` migration + `GET /api/v1/audit` endpoint. Registers middleware in `src/api/app.py`.
- **wp-ops** (priority 2, deps: wp-contracts): `aca manage restore-from-cloud` CLI wrapper + `docs/SYNC_DOWN.md`. Independent of all other packages (touches only `src/cli/` + `docs/`). **Runs in parallel with wp-audit.**
- **wp-api** (priority 3, deps: wp-contracts + wp-audit): New HTTP endpoints. Registers routers in `src/api/app.py` (serialized after wp-audit to avoid app.py conflict). Depends on wp-audit so `@audited` decorator and `audit_log` table are in place when destructive endpoints land.
- **wp-mcp** (priority 4, deps: wp-contracts + wp-api): MCP refactor to HTTP client with in-process fallback. Depends on wp-api for the endpoints to exist.
- **wp-integration** (priority 5, deps: wp-api + wp-audit + wp-mcp + wp-ops): OpenAPI drift test, full test suite, MCP E2E, smoke test, `CLAUDE.md` updates.

Parallel lanes: `wp-audit` ∥ `wp-ops` after wp-contracts lands. Then serial: `wp-api` → `wp-mcp` → `wp-integration`.

**Pros**:
- Shortest wall-clock time when parallelism is available
- Contracts force interface clarity before implementation — reduces rework
- Matches coordinator tier's parallel capabilities (`CAN_LOCK`, `CAN_QUEUE_WORK`, `CAN_DISCOVER` all available)
- Audit logging ships *with* destructive endpoints (atomic safety)
- `agentic-assistant` can consume the OpenAPI contract to generate its typed client *before* endpoints are live

**Cons**:
- Higher up-front design cost (contracts must be tight)
- Integration phase has larger merge (mitigated by non-overlapping write_allow scopes)
- Requires coordinator + work-package discipline
- Over-design risk if scope shifts mid-flight

**Effort**: L (longer calendar design phase, shorter wall-clock execution)

### Approach 3: Minimum-viable slice

**Description**: Ship only the 4 MCP-bypass HTTP endpoints (kb/search, graph/query, references/extract, references/resolve) plus the MCP refactor for those 4 tools. Skip graph extract-entities, kb lint HTTP, sync-down, and audit logging. Defer each to separate follow-up proposals.

**Pros**:
- Smallest scope (~5 files changed)
- Fastest to ship (1–2 sessions)
- Validates the HTTP-first pattern before bigger commitment
- Easy review and merge

**Cons**:
- Leaves `aca graph extract-entities` and `aca kb lint` direct-only indefinitely
- No sync-down workflow — developers still manually handle dumps
- Destructive ops ship without audit logging (elevated risk during rollout)
- `agentic-assistant` integration still requires follow-up proposals for missing surface
- Fragmented roadmap — more proposal overhead relative to total work

**Effort**: M (1–2 sessions)

## Selected Approach

**Approach 2 — Contract-first parallel lanes.**

Rationale:
- The coordinator is fully available (`COORDINATOR_AVAILABLE=true`, all capabilities green), so parallel execution is on the table with proper lock/scope discipline.
- Contract-first has direct consumer-side payoff: `agentic-assistant` can generate its HTTP client before server code is finalized, shortening the critical path to integration.
- Shipping audit logging *alongside* destructive endpoint additions is materially safer than adding it after. Phased delivery (Approach 1) would put endpoints in production briefly without audit coverage.
- Approach 3's narrow scope is tempting but leaves known gaps (graph extract-entities, kb lint, sync-down) that would need to be re-proposed within weeks, each with its own review/merge overhead.

## Resolved Decisions (formerly open questions)

- **`/api/v1/` vs `/api/v2/`**: Stay on `/api/v1/`. Before merging wp-integration, verify `add-api-versioning` proposal hasn't landed on `/api/v2/`. If it has, rebase new endpoints onto v2. Documented in design §Rollout.
- **MCP in-process fallback**: Silent fallback when `ACA_API_BASE_URL` is unset; warning emitted to **stderr** (not tool response) when config is partial (e.g., base URL set but admin key missing). `--strict-http` flag enforces HTTP mode on MCP server startup — server refuses to start if strict-http is set and config is missing.
- **Audit log write-path performance**: Accept 1–3 ms per request for now. Move to async queue if Langfuse or APM shows hot-path regression. Not in scope.
- **Audit scope**: Log ALL `/api/v1/*` requests (reads, writes, auth failures). Picks the broader audit-log spec interpretation. Enriched `@audited(operation=...)` tagging for destructive endpoints only.
- **MCP byte-identical response shapes**: Dropped. MCP adopts the new OpenAPI response shapes directly (breaking change, accepted — sole consumers are @jankneumann's tooling + `agentic-assistant`, both controlled).
