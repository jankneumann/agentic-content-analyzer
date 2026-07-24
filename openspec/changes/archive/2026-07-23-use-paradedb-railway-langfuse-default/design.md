# Design: Use ParadeDB on Railway and Langfuse as Default Observability

**Change ID**: `use-paradedb-railway-langfuse-default`

## Architecture Decisions

### D1: Langfuse Cloud for Railway, Self-Hosted for Local

**Decision**: Local development uses self-hosted Langfuse (via `docker-compose.langfuse.yml`), while Railway/staging/production use Langfuse Cloud (`https://cloud.langfuse.com`).

**Rationale**: Self-hosted Langfuse for local dev avoids requiring internet access and API key configuration for every developer. Langfuse Cloud for production avoids running a full Langfuse infrastructure stack (ClickHouse, Redis, MinIO, PostgreSQL) on Railway, which would consume significant resources on the Hobby plan and double the service count.

**Rejected alternative**: Self-hosted Langfuse on Railway — too heavy (4+ additional services) for a single-project deployment. Would double Railway service count and cost.

**Rejected alternative**: Langfuse Cloud everywhere — requires internet access and API keys for local dev. Breaks offline development workflow.

### D2: GHCR Pre-Built Image for Railway ParadeDB

**Decision**: Publish the existing `railway/postgres/Dockerfile` as a pre-built image to GitHub Container Registry (`ghcr.io/jankneumann/aca-postgres:17-railway`). Railway references this image directly.

**Rationale**: Pre-built images deploy faster (no build step on Railway) and avoid build timeouts on Railway's Hobby plan where Docker builds are resource-constrained. The Dockerfile already exists and is tested locally.

**Rejected alternative**: Let Railway build from Dockerfile — slower deploys, potential timeout on Hobby plan, builds ParadeDB extensions from source each time. The primary risk with pre-built images is staleness — addressed by documenting the manual rebuild process and deferring CI automation to a follow-up.

### D3: Merge Self-Hosted Config into local.yaml

**Decision**: Merge the Langfuse self-hosted configuration from `local-langfuse.yaml` into `local.yaml`. Keep `local-langfuse.yaml` as-is for backward compatibility but it becomes effectively redundant.

**Rationale**: Since Langfuse is now the default, `local.yaml` should include self-hosted Langfuse config directly. Developers who previously used `PROFILE=local` will now get tracing by default. The separate `local-langfuse.yaml` profile was necessary when Langfuse was opt-in; now it's the default.

**Backward compatibility note**: This is a behavior change for `PROFILE=local` users. Previously, no tracing occurred; now Langfuse tracing is enabled with graceful fallback. Users who explicitly want no tracing should set `OBSERVABILITY_PROVIDER=noop`.

**Graceful fallback**: If the Langfuse Docker stack isn't running, the provider logs a warning but doesn't crash. Traces are silently dropped — equivalent to `noop` behavior. See D5 for detailed resilience behavior.

### D4: Keep Braintrust as Available Option

**Decision**: Retain `src/telemetry/providers/braintrust.py` and documentation. Users can override via `OBSERVABILITY_PROVIDER=braintrust`.

**Rationale**: Marginal maintenance cost (provider abstraction keeps it isolated). Removal would break any existing Railway deployments that depend on Braintrust. The provider code is self-contained in `src/telemetry/providers/braintrust.py` and requires no changes.

### D5: Observability Provider Resilience Strategy

**Decision**: Langfuse provider failures are non-blocking. The application SHALL always start and run regardless of observability provider state.

**Behavior by failure mode**:

| Failure Mode | Log Level | Behavior |
|---|---|---|
| Credentials missing (both keys unset) | WARNING (once at startup) | Provider initializes, traces dropped. Message: "Configure LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .secrets.yaml or environment" |
| Credentials partial (one key set) | WARNING (once at startup) | Provider initializes, traces dropped. Message: "Langfuse partially configured — both public and secret keys required" |
| Endpoint unreachable (stack not running) | WARNING (once at startup) | OTel batch exporter queues traces for up to 30s (default batch timeout), then drops without blocking |
| Endpoint returns HTTP 5xx | No log (OTel exporter handles internally) | OTel batch exporter retries with exponential backoff, drops after retry limit |
| Braintrust override without API key | ERROR | Falls back to noop provider. Application continues. |

**Rationale**: Observability is a cross-cutting concern that must never block application functionality. The existing Langfuse provider already uses OTel's `OTLPSpanExporter` which handles network failures gracefully via batching and retry. This design documents the existing behavior rather than adding new code.

## Credential Flow

### Local Development (Self-Hosted Langfuse)

```
┌─────────────────────────────────────────────────┐
│                 Local Dev Machine                │
│                                                 │
│  .secrets.yaml                                  │
│  ├── LANGFUSE_PUBLIC_KEY: pk-lf-...  ◄──┐       │
│  └── LANGFUSE_SECRET_KEY: sk-lf-...  ◄──┤       │
│                                         │       │
│  profiles/local.yaml                    │       │
│  └── langfuse_base_url: localhost:3100  │       │
│                                         │       │
│  ┌──────────┐    OTel traces    ┌───────┴─────┐ │
│  │  App     │ ─────────────────►│  Langfuse   │ │
│  │  :8000   │   Basic Auth:     │  :3100      │ │
│  │          │   pk:sk           │  (Docker)   │ │
│  └──────────┘                   └─────────────┘ │
│                                                 │
│  First start: Create account at localhost:3100   │
│  then get API keys from Settings → API Keys     │
└─────────────────────────────────────────────────┘
```

### Railway Production (Langfuse Cloud)

```
┌──────────────────────────────────────────────────┐
│                 Railway Project                   │
│                                                  │
│  Environment Variables (Railway dashboard)        │
│  ├── LANGFUSE_PUBLIC_KEY: pk-lf-...              │
│  └── LANGFUSE_SECRET_KEY: sk-lf-...              │
│                                                  │
│  ┌──────────┐                                    │
│  │  App     │ ──── OTel traces (HTTPS) ────────► │
│  │  :$PORT  │     Basic Auth: pk:sk              │
│  └──────────┘                                    │
│                                                  │
│  ┌──────────┐                                    │
│  │ ParadeDB │ (GHCR pre-built image)             │
│  │  :5432   │ pgvector + pg_search + pgmq +      │
│  │          │ pg_cron all pre-installed           │
│  └──────────┘                                    │
└──────────────────────────────────────────────────┘
         │
         │ HTTPS (cloud.langfuse.com/api/public/otel)
         ▼
┌──────────────────────────────┐
│  Langfuse Cloud              │
│  https://cloud.langfuse.com  │
│  (managed SaaS)              │
└──────────────────────────────┘
```

## Profile Change Matrix

| Profile | Observability Before | Observability After | Langfuse Mode | OTel |
|---------|---------------------|--------------------|--------------:|------|
| `base.yaml` | `noop` | `langfuse` | (inheritable) | `true` |
| `local.yaml` | `noop` | `langfuse` | self-hosted (:3100) | `true` |
| `local-langfuse.yaml` | `langfuse` | `langfuse` (unchanged) | self-hosted (:3100) | `true` |
| `railway.yaml` | `braintrust` | `langfuse` | cloud | `true` |
| `railway-neon.yaml` | `braintrust` | `langfuse` | cloud | `true` |
| `railway-neon-staging.yaml` | `braintrust` | `langfuse` | cloud (staging keys) | `true` |
| `staging.yaml` | `braintrust` | `langfuse` | cloud (staging keys) | `true` |
| `supabase-cloud.yaml` | `braintrust` | `langfuse` | cloud | `true` |
| `ci-neon.yaml` | `noop` | `noop` (unchanged) | N/A | `false` |
| `local-opik.yaml` | `opik` | `opik` (unchanged) | N/A | `true` |

**Unchanged profiles**: `ci-neon.yaml`, `local-opik.yaml`, `local-openbao.yaml`, `local-supabase.yaml`, `test.yaml` — these explicitly set `providers.observability` to a non-langfuse value and are unaffected by the base.yaml default change.

## GHCR Image Publish Workflow

```bash
# One-time manual steps (until CI automation is added):

# 1. Authenticate to GHCR
echo $GHCR_PAT | docker login ghcr.io -u jankneumann --password-stdin

# 2. Build the image
docker build -t ghcr.io/jankneumann/aca-postgres:17-railway ./railway/postgres/

# 3. Push to GHCR
docker push ghcr.io/jankneumann/aca-postgres:17-railway

# 4. Verify
docker pull ghcr.io/jankneumann/aca-postgres:17-railway
docker run --rm ghcr.io/jankneumann/aca-postgres:17-railway postgres --version
```

Future: Automate via GitHub Actions when `railway/postgres/Dockerfile` changes.
