# Design: Add Langfuse Observability Provider

## Architecture Overview

The Langfuse provider slots into the existing two-layer telemetry architecture:

```
                    ┌──────────────────────────┐
                    │   Layer 1: LLM Provider   │
                    │  (mutually exclusive)      │
                    ├──────────────────────────┤
                    │ noop │ opik │ braintrust  │
                    │ otel │ LANGFUSE           │
                    └───────────┬──────────────┘
                                │
                    ┌───────────▼──────────────┐
                    │ Layer 2: OTel Infra       │
                    │ (FastAPI, SQLAlchemy,      │
                    │  httpx auto-instrument)    │
                    │ OTEL_ENABLED=true          │
                    └──────────────────────────┘
```

Like `OpikProvider` and `OTelProvider`, `LangfuseProvider` uses the OpenTelemetry SDK with `OTLPSpanExporter` to emit traces. Langfuse's OTLP endpoint (`/api/public/otel`) receives these traces and renders them in its LLM-native UI.

## Provider Implementation

### File: `src/telemetry/providers/langfuse.py`

```python
class LangfuseProvider:
    """Langfuse observability provider using OTel with gen_ai.* attributes.

    Supports both Langfuse Cloud and self-hosted deployments.
    Authentication via HTTP Basic Auth (base64(public_key:secret_key)).

    Cloud:       https://cloud.langfuse.com/api/public/otel
    US Cloud:    https://us.cloud.langfuse.com/api/public/otel
    Self-hosted: http://localhost:3100/api/public/otel  (configurable)
    """

    def __init__(
        self,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
        base_url: str = "https://cloud.langfuse.com",
        service_name: str = "newsletter-aggregator",
        log_prompts: bool = False,
    ) -> None: ...

    @property
    def name(self) -> str:
        return "langfuse"

    def _build_auth_header(self) -> dict[str, str]:
        """Construct Basic Auth header from public + secret key.

        Format: Authorization: Basic base64(public_key:secret_key)
        Returns empty dict if either key is missing (partial auth is invalid).
        """
        ...

    def _get_endpoint(self) -> str:
        """Construct OTLP base endpoint URL.

        Returns: {base_url}/api/public/otel
        Note: setup() appends /v1/traces (following Opik/OTel provider pattern)
        """
        ...

    # Same interface as OpikProvider/OTelProvider:
    # setup(), trace_llm_call(), start_span(), flush(), shutdown()
```

### Key Differences from OTelProvider

| Aspect | OTelProvider | LangfuseProvider |
|--------|-------------|-----------------|
| Authentication | Arbitrary headers (comma-separated string) | Basic Auth from public/secret key pair |
| Endpoint | Raw OTLP URL (user-provided) | Auto-constructed from `base_url + /api/public/otel` |
| Cloud default | None (must be configured) | `https://cloud.langfuse.com` |
| Validation | Requires endpoint | Requires public_key + secret_key (self-hosted can work without for local dev) |

### Authentication Flow

```
LANGFUSE_PUBLIC_KEY=pk-lf-abc123
LANGFUSE_SECRET_KEY=sk-lf-xyz789

→ base64("pk-lf-abc123:sk-lf-xyz789")
→ "cGstbGYtYWJjMTIzOnNrLWxmLXh5ejc4OQ=="

→ Header: Authorization: Basic cGstbGYtYWJjMTIzOnNrLWxmLXh5ejc4OQ==
```

For self-hosted local Langfuse, the default project keys are auto-generated on first startup. Users retrieve them from the Langfuse UI (Settings → API Keys).

## Settings Configuration

### New Fields in `src/config/settings.py`

```python
# Langfuse Configuration (Cloud or self-hosted)
langfuse_public_key: str | None = None   # Langfuse public key (pk-lf-...)
langfuse_secret_key: str | None = None   # Langfuse secret key (sk-lf-...)
langfuse_base_url: str = "https://cloud.langfuse.com"  # Base URL (override for self-hosted)
```

### Type Alias Update

```python
ObservabilityProviderType = Literal["noop", "opik", "braintrust", "otel", "langfuse"]
```

### Validation

```python
case "langfuse":
    has_public = bool(self.langfuse_public_key)
    has_secret = bool(self.langfuse_secret_key)
    if has_public != has_secret:
        # Partial keys — one without the other is always wrong
        logger.warning(
            "Langfuse provider has only one of public/secret key. "
            "Both are required for authentication. Auth header will not be sent."
        )
    elif not has_public and not has_secret:
        # No keys — valid for self-hosted without auth
        logger.warning(
            "Langfuse provider configured without API keys. "
            "Traces will not be authenticated. "
            "Get keys from Langfuse Settings → API Keys."
        )
```

## Factory Dispatch

### Update: `src/telemetry/providers/factory.py`

```python
case "langfuse":
    from src.telemetry.providers.langfuse import LangfuseProvider

    return LangfuseProvider(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        service_name=settings.otel_service_name,
        log_prompts=settings.otel_log_prompts,
    )
```

## Profile Configuration

### `profiles/base.yaml` — Add secrets wiring

```yaml
settings:
  api_keys:
    langfuse_public_key: "${LANGFUSE_PUBLIC_KEY:-}"
    langfuse_secret_key: "${LANGFUSE_SECRET_KEY:-}"
```

### `profiles/local-langfuse.yaml` — New profile

```yaml
name: local-langfuse
extends: local
description: Local development with Langfuse self-hosted LLM tracing

providers:
  observability: langfuse

settings:
  observability:
    otel_enabled: true
    otel_service_name: newsletter-aggregator
    langfuse_base_url: "http://localhost:3100"
```

Note: `langfuse_public_key` and `langfuse_secret_key` are loaded from `.secrets.yaml` or env vars (not hardcoded in profiles since they're generated by Langfuse on first startup).

## Docker Compose: Self-Hosted Langfuse

### File: `docker-compose.langfuse.yml`

Runs as a separate Docker Compose project (`-p langfuse`) to avoid conflicts with the main stack, following the same pattern as `docker-compose.opik.yml`.

**Services:**

| Service | Image | Port (host) | Purpose |
|---------|-------|-------------|---------|
| langfuse-web | `langfuse/langfuse:3` | 3100 | Langfuse web + API + OTLP endpoint |
| langfuse-worker | `langfuse/langfuse:3` | — | Background worker (ingestion processing) |
| langfuse-postgres | `postgres:17` | — (internal) | Langfuse metadata storage |
| langfuse-clickhouse | `clickhouse/clickhouse-server` | — (internal) | Trace analytics storage |
| langfuse-redis | `redis:7-alpine` | — (internal) | Queue + cache |
| langfuse-minio | `minio/minio` | — (internal) | S3-compatible event storage |

**Port Strategy:**
- Port 3100 for Langfuse UI (avoids 3000 conflict with web frontend, 5173 with Vite, 5174 with Opik)
- All infrastructure services are internal (no host ports) to minimize conflicts

**Health Checks:**
- Langfuse web: `curl http://localhost:3000/api/public/health` (container-internal port)
- PostgreSQL: `pg_isready`
- ClickHouse: `wget --spider http://127.0.0.1:8123/ping`
- Redis: `redis-cli ping`
- MinIO: `curl http://localhost:9000/minio/health/live`

**Environment Variables (langfuse-web):**
```
DATABASE_URL=postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse
NEXTAUTH_URL=http://localhost:3100
NEXTAUTH_SECRET=<random-dev-secret>
SALT=<random-dev-salt>
ENCRYPTION_KEY=<64-hex-chars>
CLICKHOUSE_URL=http://langfuse-clickhouse:8123
CLICKHOUSE_MIGRATION_URL=clickhouse://langfuse-clickhouse:9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=langfuse
REDIS_HOST=langfuse-redis
REDIS_PORT=6379
REDIS_AUTH=langfuse
LANGFUSE_S3_EVENT_UPLOAD_ENABLED=true
LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://langfuse-minio:9000
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse-events
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=langfuse
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=langfuse123
LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true
LANGFUSE_S3_EVENT_UPLOAD_REGION=us-east-1
```

## Makefile Targets

Following the Opik pattern:

```makefile
langfuse-up:     ## Start Langfuse observability stack (LLM tracing)
langfuse-down:   ## Stop Langfuse observability stack
langfuse-logs:   ## Tail Langfuse stack logs
dev-langfuse:    ## Start dev servers with Langfuse tracing (requires: make langfuse-up)
verify-langfuse: ## Verify Langfuse tracing works E2E
test-langfuse:   ## Run Langfuse integration tests (requires: make langfuse-up)
```

**Note:** Langfuse is NOT included in `full-up` (unlike Opik) because its 6-service stack is resource-heavy. Users opt in explicitly via `make langfuse-up`. However, `full-down` SHALL stop Langfuse if running (defensive cleanup).

## Integration Tests

### File: `tests/integration/fixtures/langfuse.py`

Following the Opik fixture pattern:

```python
# Settings-derived URLs
LANGFUSE_BASE_URL = _settings.langfuse_base_url
LANGFUSE_OTLP_ENDPOINT = f"{LANGFUSE_BASE_URL}/api/public/otel"

def _langfuse_is_running() -> bool:
    """Check Langfuse health via /api/public/health."""
    ...

requires_langfuse = pytest.mark.skipif(
    not _langfuse_is_running(),
    reason="Langfuse not running (start with: make langfuse-up)",
)

@pytest.fixture
def langfuse_provider(unique_project_name: str) -> Generator:
    """Create a LangfuseProvider configured for testing."""
    ...
```

### File: `tests/integration/test_langfuse_integration.py`

Tests:
1. Provider initialization and setup
2. LLM call tracing with gen_ai.* attributes
3. Span creation and nesting
4. Flush and shutdown lifecycle
5. Traces visible in Langfuse API (verify via `GET /api/public/traces` with Basic Auth, polling until traces appear)

## Documentation Updates

1. **CLAUDE.md** — Add Langfuse to observability provider table, add configuration section, add Makefile targets, add gotchas
2. **docs/SETUP.md** — Add Langfuse self-hosted setup instructions
3. **profiles/base.yaml** — Add Langfuse secrets wiring, update provider options comment
4. **.env.example** — Add Langfuse env vars

## Migration Path

No migration needed. This is purely additive — the `langfuse` provider is a new option alongside existing providers. Users opt in by setting `OBSERVABILITY_PROVIDER=langfuse`.
