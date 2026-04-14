# Critical Gotchas

Things that will bite you if ignored. Organized by area.

## Database & Migrations

| Issue | Solution |
|-------|----------|
| SQLAlchemy duplicate indexes | Don't use `index=True` AND explicit `Index()` with same name |
| Test DB fails on second run | Fixtures must drop tables before creating (handles interrupted runs) |
| Alembic migrations not idempotent | Use `IF EXISTS` for drops; check `information_schema` before FK operations |
| Model-schema drift breaks migrations | Don't assume columns exist in DB; check before creating FK constraints |
| Alembic multiple heads block `upgrade head` | Run `alembic heads` to detect; fix with `alembic merge heads -m "..."` or use `alembic upgrade heads` (plural) |
| PG enum + Python StrEnum mismatch | Adding to Python `StrEnum` requires `ALTER TYPE ... ADD VALUE` migration; without it PG throws `InvalidTextRepresentation` |
| Migrations create existing tables | Make idempotent: check `information_schema.tables` before `create_table` |
| Cloud DB has no tables | Supabase/Neon start empty; run `alembic upgrade head` against production |
| `autoflush=False` + dedup loop | `db.add()` without `db.flush()` leaves rows invisible to subsequent SELECTs; cross-feed duplicates pass dedup then collide on unique constraint at commit |
| pgvector not mapped in ORM | `DocumentChunk.embedding` and `search_vector` are NOT SQLAlchemy columns — access via raw SQL only. `embedding_provider`/`embedding_model` ARE mapped |

## Database Providers

| Issue | Solution |
|-------|----------|
| DATABASE_PROVIDER required for cloud | Must explicitly set `DATABASE_PROVIDER=supabase` or `neon` |
| Neon first connection slow | Scale-to-zero may take 2-5s to wake up; increase timeout |
| Supabase free tier IPv6 only | Direct connections use IPv6; use pooler if on IPv4-only network |
| Local Supabase needs SUPABASE_LOCAL | Set `SUPABASE_LOCAL=true` for auto-configured local endpoints |
| Local Supabase DB needs init scripts | `supabase/postgres` image requires roles (`supabase_admin`, `anon`, etc.) via `supabase/docker/init/` SQL scripts |
| Local Supabase storage IPv6 health check | Use `127.0.0.1` not `localhost` in wget health checks — Node.js binds IPv4 only but `wget` resolves to IPv6 `::1` |
| Local Supabase storage needs DB grants | `supabase_storage_admin` needs `GRANT CREATE ON DATABASE postgres` to run migrations |
| PostgREST container has no curl/wget | Use `bash -c 'echo -n > /dev/tcp/localhost/3000'` for health checks |
| Supabase Storage uses S3 API | Use `SUPABASE_ACCESS_KEY_ID`/`SUPABASE_SECRET_ACCESS_KEY`, NOT service role key |

## Railway Deployment

| Issue | Solution |
|-------|----------|
| Railway custom image build slow | Use GHCR pre-built image; Rust extensions take ~20 min to compile |
| Railway MinIO auto-discovery | Set `RAILWAY_PUBLIC_DOMAIN` or explicit `RAILWAY_MINIO_ENDPOINT` |
| Railway PORT is dynamic | Use `${PORT:-8000}` in shell form CMD; never hardcode port in Dockerfile |
| Railway extension version pinning | Pin git tags in Dockerfile (e.g., `--branch v0.7.4`); unpinned builds break on pgrx mismatches |
| Railway volumes not persistent by default | Attach a volume in Railway dashboard; without it, data lost on redeploy |
| Railway Hobby plan connection limits | Use `pool_size=3`, `max_overflow=2`; exceeding causes connection errors |
| Braintrust extra in Dockerfile | Must add `--extra braintrust` to `uv sync` in Dockerfile; without it `import braintrust` fails silently |
| ParadeDB `listen_addresses` on Railway | Set `POSTGRES_LISTEN_ADDRESSES=*` on the ParadeDB service. Without it, PG listens only on `localhost` inside the container. Public TCP proxy works (proxies from within container), but private network traffic via `.railway.internal` arrives on the external interface and is **refused**. |
| ParadeDB SSL on Railway private network | Append `?sslmode=disable` to `DATABASE_URL` when using `.railway.internal` hostnames. Railway's private network does not terminate TLS — the DB driver's default SSL handshake **hangs until timeout**. |
| ParadeDB volume mount path | Mount persistent volume at `/var/lib/postgresql/data` and set `PGDATA=/var/lib/postgresql/data/pgdata`. Railway creates `lost+found` at the mount root (ext4 filesystem) — PG refuses to init into a non-empty directory. The `PGDATA` subdirectory avoids this. |

## Python & Pydantic

| Issue | Solution |
|-------|----------|
| datetime.utcnow() is deprecated | Use `datetime.now(UTC)` instead (Python 3.12+) |
| feedparser dates are naive | Always add `tzinfo=UTC` when converting `published_parsed` |
| mypy + SQLAlchemy stubs | Don't install `sqlalchemy-stubs` - conflicts with 2.0 |
| Settings tests pick up .env | Pass `_env_file=None` to `Settings()` to isolate tests |
| Pydantic property vs field conflict | Don't make a property with same name as a field in Pydantic models |

## Profiles & Secrets

| Issue | Solution |
|-------|----------|
| Profile not loading | Ensure `PROFILE` env var is set; profiles live in `profiles/` directory |
| Profile validation errors | Run `aca profile validate <name>` to see all errors |
| Secrets not interpolating | Check `.secrets.yaml` exists and key names match `${VAR}` references |
| Profile inheritance cycles | Profiles cannot extend themselves or form circular `extends` chains |
| Profile provider vs settings collision | `providers.*` must be authoritative; don't add `*_provider` keys in `settings.*` sections of child profiles |
| `.secrets.yaml` uses YAML syntax | Must use `:` not `=`; `KEY=value` silently parses as a string instead of a key-value pair |
| `.secrets.yaml` needs profile active | Without `PROFILE` env var, `.secrets.yaml` is never read; secrets only flow via `${VAR}` in profiles |
| New secrets need `base.yaml` wiring | Add `${VAR:-}` reference in `profiles/base.yaml` under the appropriate settings section |

## Auth & Security

| Issue | Solution |
|-------|----------|
| Prompt/settings API returns 500 | Must set `ADMIN_API_KEY` env var (or in `.secrets.yaml` with profile); fail-secure design blocks access when unconfigured |
| Prompt API auth header is `X-Admin-Key` | NOT `X-Admin-API-Key` or `Authorization` — defined in `src/api/dependencies.py:9` as `APIKeyHeader(name="X-Admin-Key")` |
| `APP_SECRET_KEY` is the login password | Used directly for `secrets.compare_digest()` against user input AND as HMAC input for JWT signing key derivation |
| Auth: middleware + route dependency double-check | `AuthMiddleware` and `verify_admin_key` both verify session cookies AND X-Admin-Key — defense-in-depth, not conflicting |
| Auth: Invalid X-Admin-Key returns 403 (not 401) | Middleware distinguishes invalid keys (403 Forbidden) from missing auth (401 Unauthorized). Spec requires this for all environments |
| `ENDPOINT_AUTH_MAP` in `dependencies.py` | Documentation-only constant — lists all routes and their auth requirements. Auth enforced by `AuthMiddleware` + `verify_admin_key` dependency |
| Production CORS returns empty list | When `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is dev defaults (localhost), `get_allowed_origins_list()` returns `[]` — must set explicit origins |
| Production startup warns (doesn't fail) | Missing `ADMIN_API_KEY` or dev CORS in production logs warnings but does NOT prevent startup — intentional per design |
| Upload magic bytes validation | File uploads are validated against `FILE_SIGNATURES` mapping in `upload_routes.py` — mismatched extensions return 415 |
| Upload MIME cross-check | Client `Content-Type` is validated against `EXTENSION_MIME_MAP` — `application/octet-stream` and `None` bypass the check |
| gitleaks pre-commit blocks commit | Check `.gitleaks.toml` allowlist; add path or regex exception for intentional test fixtures |
| Security headers break iframe embedding | `X-Frame-Options: DENY` prevents embedding; if embedding needed, switch to CSP `frame-ancestors` directive |

## API Routes

| Issue | Solution |
|-------|----------|
| FastAPI route ordering: `/{id}` shadows static paths | Define static routes (`/pricing/status`) BEFORE dynamic routes (`/{model_id}`) — FastAPI matches in definition order and `{model_id}` captures any string including "pricing" |
| String-level YAML editing offset drift | When applying multiple replacements to file content, collect `(start, end, new_text)` tuples and apply in **reverse offset order** — forward-order replacements shift subsequent offsets |

## Testing

| Issue | Solution |
|-------|----------|
| Auth: Secure cookies + TestClient | TestClient defaults to `http://testserver` — secure cookies are not sent back. Use `base_url="https://testserver"` in production fixtures |
| Auth: Cookie header dropped on redirect | httpx regenerates `Cookie` headers from its cookie jar on redirect — manually set `Cookie` headers are lost. Use trailing-slash URLs in tests to avoid 307 redirects |
| Worktree test DB naming | Each worktree auto-creates `newsletters_test_<worktree>` (sanitized, max 63 chars). `TEST_DATABASE_URL` env var overrides. Use `make test-clean` to drop all worktree test DBs |
| Test DB auto-created by conftest | Session-scoped fixtures auto-create via admin connection to `postgres` DB. No `make test-setup` needed for PG (still needed for Neo4j) |
| Contract tests excluded by default | `contract` marker excluded in `addopts` — run explicitly with `pytest tests/contract/ -m contract --no-cov` |
| Schemathesis NUL byte skip | Schemathesis generates `%00` in query params causing psycopg2 `ValueError` — contract tests skip these via try/except, tracked as separate input validation issue |
| Contract test savepoints | `tests/contract/conftest.py` uses `begin_nested()` (SAVEPOINTs) so failed API calls don't abort the entire test transaction |
| Integration fixture env vars must use Settings | Use `get_settings()` not `os.getenv()` — fixtures must honor profile/secrets precedence chain |
| Hoverfly webserver mode has no capture | Default `docker-compose.yml` runs `-webserver` flag — no upstream to record. Must restart in proxy mode for capture (see `tests/integration/README.md`) |
| Hoverfly simulation reset between tests | `hoverfly` fixture auto-resets; tests that load simulations should not depend on prior test state |

## E2E Testing (Playwright)

| Issue | Solution |
|-------|----------|
| E2E tests need `--ignore-snapshots` | Default `test:e2e` script adds this flag; snapshot tests not used |
| E2E mock data must use snake_case | API responses use snake_case; mock factories in `fixtures/mock-data.ts` |
| E2E smoke tests need real backend | `pnpm test:e2e:smoke` requires backend running; excluded via `grepInvert: /@smoke/` |
| Import `test` from `../fixtures` | E2E tests must import custom `test` (not `@playwright/test`) for page objects and mocks |
| Playwright strict mode violations | Use `.first()`, `{ exact: true }`, or scope to parent (`.locator("main")`) when locators match multiple elements |
| Playwright route needs trailing `*` | Route patterns like `**/api/v1/items/*/nav` won't match query params; add trailing `*` |
| Mock data must include all array fields | Components accessing `obj.field.length` crash if `field` is undefined; include empty `[]` arrays |
| `getByText` matches substrings | `getByText("Content")` matches "Ingest Content" too; use `{ exact: true }` or `getByRole` |
| Sidebar text duplicates main content | Scope to `page.locator("main")` or `page.locator("aside")` to avoid matching both |
| VitePWA manifest not in dev mode | `/manifest.webmanifest` returns HTML in dev; manifest only generated in production builds |
| Route registration order is LIFO | Playwright matches last-registered route first; register specific routes after general ones |

## Frontend

| Issue | Solution |
|-------|----------|
| VITE_API_URL trailing slash | Causes double-slash (`//api/v1/`); strip with `.replace(/\/$/, "")` |
| CORS blocks cross-origin frontend | Set `ALLOWED_ORIGINS` env var on backend with frontend URL |
| Dialog `min-w-[600px]` breaks mobile | Use `md:min-w-[600px]` — CSS `min-width` overrides `max-width`, causing overflow |
| iOS status bar hides header | Apply `pt-[var(--safe-area-top)]` to AppShell root and fixed overlays |
| Fixed grid-cols-N in dialogs | Use responsive breakpoints: `grid-cols-2 md:grid-cols-4` |
| Tailwind v4 typography plugin overrides | Plugin styles are unlayered; custom `.prose` overrides must be OUTSIDE `@layer` blocks to win cascade |
| Vite "Cannot find module" after dep upgrade | pnpm upgraded Vite (e.g., 7.3.0 → 7.3.2) but stale hard links or `.vite` cache reference old paths; fix with `pnpm install --force` + restart dev server (`make dev-stop && make dev-bg`) |

## Observability & Telemetry

| Issue | Solution |
|-------|----------|
| Telemetry mock patch target | Patch `src.telemetry.get_provider` (source module), NOT `src.services.llm_router.get_provider` — local imports aren't module attrs |
| Telemetry tests need anthropic_api_key | Pass `anthropic_api_key="test-key"` to `Settings(_env_file=None)` in observability tests |
| `logging.basicConfig()` only works once | OTel log bridge uses `addHandler()` directly — never call `basicConfig()` after `setup_logging()` |
| Log bridge needs both flags | Requires `OTEL_ENABLED=true` AND `OTEL_LOGS_ENABLED=true` — logs gate on the parent OTel flag |
| Export level != console level | `OTEL_LOGS_EXPORT_LEVEL` controls OTLP export only; `LOG_LEVEL` still controls console output |
| Frontend OTel needs backend OTel | `VITE_OTEL_ENABLED=true` requires `OTEL_ENABLED=true` on backend for OTLP proxy to accept traces |
| Frontend OTel is no-op by default | Zero overhead when disabled; OTel SDK dynamically imported only when `VITE_OTEL_ENABLED=true` |
| initTelemetry must run before React | Called at module scope in `__root.tsx` so fetch instrumentation is active before TanStack Query fires |
| Langfuse keys are auto-generated | First start Langfuse, create account, get keys from Settings -> API Keys |
| Langfuse self-hosted is resource-heavy | 6 services (PG, ClickHouse, Redis, MinIO, web, worker); use `make langfuse-up` only when needed |
| Langfuse uses Basic Auth for OTLP | `Authorization: Basic base64(public_key:secret_key)` — different from Opik/Braintrust auth |
| Langfuse port 3100 | Avoids conflict with web frontend (3000), Vite (5173), Opik (5174) |

## Ingestion Sources

| Issue | Solution |
|-------|----------|
| Podcast transcription needs STT key | Set `OPENAI_API_KEY` for Whisper; `transcribe: false` in source to skip |
| X search needs xAI API key | Set `XAI_API_KEY`; search prompt configurable via `aca prompts set pipeline.xsearch.search_prompt` |
| Perplexity search needs API key | Set `PERPLEXITY_API_KEY`; model defaults to `sonar`; search prompt configurable via `aca prompts set perplexity_search.search_prompt` |
| Scholar ingestion API key optional | Set `SEMANTIC_SCHOLAR_API_KEY` for higher rate limits (1-10 RPS vs ~20 req/min unauthenticated); free API, no key required for basic use |
| Perplexity uses OpenAI SDK | Zero new dependencies — `openai.OpenAI(base_url="https://api.perplexity.ai")` with `extra_body` for vendor params |
| WebSearchProvider lazy imports | Adapters use lazy imports in `__init__` and `search()` — mock at SOURCE module, not `src.services.web_search` |
| Crawl4AI Docker needs `--shm-size=1g` | Chromium crashes without shared memory; docker-compose sets `shm_size: '1g'` |
| `crawl4ai_enabled` defaults to `False` | Must explicitly enable via env var or profile; prevents accidental browser launches |
| Remote mode needs Docker running | `make crawl4ai-up` first; connection refused errors are fail-safe (returns Trafilatura result) |
| CacheMode string must match enum names | Valid values: `bypass`, `enabled`, `disabled`, `read_only`, `write_only` |
| Crawl4AI lazy import in converter | `get_settings()` imported inside `__init__` — patch at `src.config.settings.get_settings`, not the converter module |

## Search & Embeddings

| Issue | Solution |
|-------|----------|
| Changing embedding provider | Use `aca manage switch-embeddings` — handles clearing, index rebuild, and backfill safely |
| Embedding provider asymmetry | Voyage/Cohere/local have different query vs document encoding — always pass `is_query=True` when embedding search queries |
| `embedding_trust_remote_code` | Defaults to `false` — must explicitly enable for instruction-tuned models like `gte-Qwen2-1.5B-instruct` |
| Embedding config mismatch | Startup warns if DB embeddings are from a different provider than configured — run `switch-embeddings` to fix |
| `index_content()` is fail-safe | Never raises exceptions — failures are logged. Content ingestion always succeeds even if search indexing fails |

## CI & Pre-commit

| Issue | Solution |
|-------|----------|
| pip-audit fails in CI | Check `pip-audit --desc on` locally; known advisories may need `--ignore-vuln` flag |
