# Tasks: Add Langfuse Observability Provider

## Phase 1: Provider Implementation (Core)

### Task 1.1: Add Langfuse provider class
- [x] Create `src/telemetry/providers/langfuse.py`
- [x] Implement `LangfuseProvider` class satisfying `ObservabilityProvider` protocol
- [x] Implement `_build_auth_header()` — base64 Basic Auth from public/secret keys
- [x] Implement `_get_endpoint()` — auto-construct `{base_url}/api/public/otel`
- [x] Implement `setup()` — OTel TracerProvider + OTLPSpanExporter with Basic Auth headers
- [x] Implement `trace_llm_call()` — gen_ai.* semantic conventions (duplicate constants in-file, following existing Opik/OTel pattern)
- [x] Implement `start_span()` — named OTel span with attributes
- [x] Implement `flush()` and `shutdown()` — lifecycle management
- [x] Ensure fail-safe design (ImportError for missing OTel packages, graceful degradation)
- [x] Handle edge case: missing keys with warning (self-hosted may not require auth initially)

**Parallel zone:** Isolated new file, no existing code changes.

### Task 1.2: Update settings and type aliases
- [x] Add `"langfuse"` to `ObservabilityProviderType` Literal in `src/config/settings.py`
- [x] Add `"langfuse"` to `ObservabilityProviderType` Literal in `src/config/profiles.py`
- [x] Add settings fields: `langfuse_public_key`, `langfuse_secret_key`, `langfuse_base_url`
- [x] Add validation case for `"langfuse"` in `validate_observability_provider_config()`
- [x] Warn (don't error) when keys are missing — self-hosted Langfuse may start without auth

**Parallel zone:** Settings only, no provider code overlap.

### Task 1.3: Wire factory dispatch
- [x] Add `case "langfuse":` to `get_observability_provider()` in `src/telemetry/providers/factory.py`
- [x] Pass settings fields to `LangfuseProvider()` constructor
- [x] Update factory docstring to list langfuse as an option

**Dependencies:** Task 1.1, Task 1.2

### Task 1.4: Unit tests for provider
- [x] Create `tests/telemetry/test_langfuse_provider.py`
- [x] Test initialization with various key combinations (both keys, no keys, partial)
- [x] Test `_build_auth_header()` produces correct base64 Basic Auth
- [x] Test `_get_endpoint()` auto-constructs correct URL for cloud and self-hosted
- [x] Test `trace_llm_call()` sets correct gen_ai.* span attributes (mock OTel)
- [x] Test `start_span()` creates spans with attributes
- [x] Test `flush()` and `shutdown()` lifecycle
- [x] Test graceful degradation when OTel packages missing
- [x] Test factory creates `LangfuseProvider` when `observability_provider="langfuse"`
- [x] Test settings validation for langfuse provider

**Dependencies:** Task 1.1, Task 1.2, Task 1.3

## Phase 2: Local Infrastructure

### Task 2.1: Docker Compose for self-hosted Langfuse
- [x] Create `docker-compose.langfuse.yml`
- [x] Add `langfuse-postgres` service (postgres:17, internal only — no host port)
- [x] Add `langfuse-clickhouse` service (clickhouse/clickhouse-server, internal only)
- [x] Add `langfuse-redis` service (redis:7-alpine, internal only)
- [x] Add `langfuse-minio` service (minio/minio, internal only) with auto-bucket creation
- [x] Add `langfuse-web` service (langfuse/langfuse:3, port 3100)
- [x] Add `langfuse-worker` service (langfuse/langfuse:3, no port)
- [x] Configure health checks for all services
- [x] Set startup dependency chain: postgres + clickhouse + redis + minio → web → worker
- [x] Use deterministic dev secrets (NEXTAUTH_SECRET, SALT, ENCRYPTION_KEY) for reproducibility
- [x] Add volumes for data persistence

**Parallel zone:** Isolated new file.

### Task 2.2: Makefile targets
- [x] Add `langfuse-up` target — start Langfuse stack with health wait
- [x] Add `langfuse-down` target — stop Langfuse stack
- [x] Add `langfuse-logs` target — tail Langfuse logs
- [x] Add `dev-langfuse` target — start dev servers with `PROFILE=local-langfuse`
- [x] Add `verify-langfuse` target — verify Langfuse tracing E2E
- [x] Add `test-langfuse` target — run Langfuse integration tests
- [x] Update `full-down` to also stop Langfuse if running (NOT `full-up` — Langfuse is resource-heavy, opt-in only via `make langfuse-up`)
- [x] Add targets to `.PHONY` list

**Dependencies:** Task 2.1

### Task 2.3: Profile configuration
- [x] Create `profiles/local-langfuse.yaml` extending `local`
- [x] Set `providers.observability: langfuse`
- [x] Set `settings.observability.otel_enabled: true`
- [x] Set `settings.observability.langfuse_base_url: "http://localhost:3100"`
- [x] Update `profiles/base.yaml` to wire `langfuse_public_key` and `langfuse_secret_key` via `${VAR:-}` in api_keys section
- [x] Update `profiles/base.yaml` observability provider comment to include `langfuse`

**Dependencies:** Task 1.2

## Phase 3: Integration Tests

### Task 3.1: Integration test fixtures
- [x] Create `tests/integration/fixtures/langfuse.py`
- [x] Implement `_langfuse_is_running()` health check via `/api/public/health`
- [x] Create `requires_langfuse` skip marker
- [x] Create `langfuse_available` session-scoped fixture
- [x] Create `langfuse_provider` function-scoped fixture with OTel reset and cleanup
- [x] Create `LangfuseTestHelpers` class with `wait_for_traces()` polling
- [x] Register fixtures in `tests/integration/conftest.py`

**Dependencies:** Task 1.1

### Task 3.2: Integration tests
- [x] Create `tests/integration/test_langfuse_integration.py`
- [x] Test: provider setup creates valid OTel TracerProvider
- [x] Test: LLM call trace appears in Langfuse API (via REST polling)
- [x] Test: trace has correct gen_ai.* attributes (model, tokens, etc.)
- [x] Test: prompt/completion logging respects `log_prompts` flag
- [x] Test: span nesting works (pipeline → llm.completion)
- [x] Test: provider shutdown flushes buffered traces

**Dependencies:** Task 2.1 (Langfuse stack running), Task 3.1

## Phase 4: Documentation

### Task 4.1: Update project documentation
- [x] Update CLAUDE.md observability table to include Langfuse
- [x] Add Langfuse configuration section to CLAUDE.md
- [x] Add Langfuse Makefile targets to CLAUDE.md
- [x] Add Langfuse gotchas to CLAUDE.md (Basic Auth, port 3100, ClickHouse requirement, first-startup key generation)
- [x] Update `.env.example` with Langfuse env vars
- [x] Note: `profiles/base.yaml` updates are in Task 2.3 (avoid file overlap)

**Parallel zone:** Documentation only. Does NOT modify `profiles/base.yaml` (owned by Task 2.3).

### Task 4.2: Verification script
- [x] Extend `scripts/send_test_trace.py` to support Langfuse provider (if needed)
- [x] Or create `scripts/verify_langfuse.py` for E2E verification
- [x] Wire into `make verify-langfuse` target

**Dependencies:** Task 2.2

## Parallelization Plan

```
Wave 1 (independent — max 5 parallel agents):
  Task 1.1  [src/telemetry/providers/langfuse.py]     — new file
  Task 1.2  [src/config/settings.py, src/config/profiles.py] — settings only
  Task 2.1  [docker-compose.langfuse.yml]              — new file
  Task 2.3  [profiles/local-langfuse.yaml, profiles/base.yaml] — new file + base.yaml
  Task 4.1  [CLAUDE.md, .env.example]                  — docs only (NOT base.yaml)

Wave 2 (after Wave 1):
  Task 1.3  [src/telemetry/providers/factory.py]       — depends on 1.1, 1.2
  Task 2.2  [Makefile]                                 — depends on 2.1
  Task 3.1  [tests/integration/fixtures/langfuse.py]   — depends on 1.1

Wave 3 (after Wave 2):
  Task 1.4  [tests/telemetry/test_langfuse_provider.py] — depends on 1.1, 1.2, 1.3
  Task 3.2  [tests/integration/test_langfuse_integration.py] — depends on 2.1, 3.1

Wave 4 (after Wave 2):
  Task 4.2  [scripts/verify_langfuse.py]               — depends on 2.2
```

**File ownership:** Each task owns distinct files — no shared-file conflicts within any wave.
**Maximum parallel width:** 5 (Wave 1)
