# Tasks: Add Langfuse Observability Provider

## Phase 1: Provider Implementation (Core)

### Task 1.1: Add Langfuse provider class
- [ ] Create `src/telemetry/providers/langfuse.py`
- [ ] Implement `LangfuseProvider` class satisfying `ObservabilityProvider` protocol
- [ ] Implement `_build_auth_header()` — base64 Basic Auth from public/secret keys
- [ ] Implement `_get_endpoint()` — auto-construct `{base_url}/api/public/otel`
- [ ] Implement `setup()` — OTel TracerProvider + OTLPSpanExporter with Basic Auth headers
- [ ] Implement `trace_llm_call()` — gen_ai.* semantic conventions (duplicate constants in-file, following existing Opik/OTel pattern)
- [ ] Implement `start_span()` — named OTel span with attributes
- [ ] Implement `flush()` and `shutdown()` — lifecycle management
- [ ] Ensure fail-safe design (ImportError for missing OTel packages, graceful degradation)
- [ ] Handle edge case: missing keys with warning (self-hosted may not require auth initially)

**Parallel zone:** Isolated new file, no existing code changes.

### Task 1.2: Update settings and type aliases
- [ ] Add `"langfuse"` to `ObservabilityProviderType` Literal in `src/config/settings.py`
- [ ] Add `"langfuse"` to `ObservabilityProviderType` Literal in `src/config/profiles.py`
- [ ] Add settings fields: `langfuse_public_key`, `langfuse_secret_key`, `langfuse_base_url`
- [ ] Add validation case for `"langfuse"` in `validate_observability_provider_config()`
- [ ] Warn (don't error) when keys are missing — self-hosted Langfuse may start without auth

**Parallel zone:** Settings only, no provider code overlap.

### Task 1.3: Wire factory dispatch
- [ ] Add `case "langfuse":` to `get_observability_provider()` in `src/telemetry/providers/factory.py`
- [ ] Pass settings fields to `LangfuseProvider()` constructor
- [ ] Update factory docstring to list langfuse as an option

**Dependencies:** Task 1.1, Task 1.2

### Task 1.4: Unit tests for provider
- [ ] Create `tests/telemetry/test_langfuse_provider.py`
- [ ] Test initialization with various key combinations (both keys, no keys, partial)
- [ ] Test `_build_auth_header()` produces correct base64 Basic Auth
- [ ] Test `_get_endpoint()` auto-constructs correct URL for cloud and self-hosted
- [ ] Test `trace_llm_call()` sets correct gen_ai.* span attributes (mock OTel)
- [ ] Test `start_span()` creates spans with attributes
- [ ] Test `flush()` and `shutdown()` lifecycle
- [ ] Test graceful degradation when OTel packages missing
- [ ] Test factory creates `LangfuseProvider` when `observability_provider="langfuse"`
- [ ] Test settings validation for langfuse provider

**Dependencies:** Task 1.1, Task 1.2, Task 1.3

## Phase 2: Local Infrastructure

### Task 2.1: Docker Compose for self-hosted Langfuse
- [ ] Create `docker-compose.langfuse.yml`
- [ ] Add `langfuse-postgres` service (postgres:17, internal only, port 5433 if needed for debug)
- [ ] Add `langfuse-clickhouse` service (clickhouse/clickhouse-server, internal only)
- [ ] Add `langfuse-redis` service (redis:7-alpine, internal only)
- [ ] Add `langfuse-minio` service (minio/minio, internal only) with auto-bucket creation
- [ ] Add `langfuse-web` service (langfuse/langfuse:3, port 3100)
- [ ] Add `langfuse-worker` service (langfuse/langfuse:3, no port)
- [ ] Configure health checks for all services
- [ ] Set startup dependency chain: postgres + clickhouse + redis + minio → web → worker
- [ ] Use deterministic dev secrets (NEXTAUTH_SECRET, SALT, ENCRYPTION_KEY) for reproducibility
- [ ] Add volumes for data persistence

**Parallel zone:** Isolated new file.

### Task 2.2: Makefile targets
- [ ] Add `langfuse-up` target — start Langfuse stack with health wait
- [ ] Add `langfuse-down` target — stop Langfuse stack
- [ ] Add `langfuse-logs` target — tail Langfuse logs
- [ ] Add `dev-langfuse` target — start dev servers with `PROFILE=local-langfuse`
- [ ] Add `verify-langfuse` target — verify Langfuse tracing E2E
- [ ] Add `test-langfuse` target — run Langfuse integration tests
- [ ] Update `full-down` to also stop Langfuse if running (NOT `full-up` — Langfuse is resource-heavy, opt-in only via `make langfuse-up`)
- [ ] Add targets to `.PHONY` list

**Dependencies:** Task 2.1

### Task 2.3: Profile configuration
- [ ] Create `profiles/local-langfuse.yaml` extending `local`
- [ ] Set `providers.observability: langfuse`
- [ ] Set `settings.observability.otel_enabled: true`
- [ ] Set `settings.observability.langfuse_base_url: "http://localhost:3100"`
- [ ] Update `profiles/base.yaml` to wire `langfuse_public_key` and `langfuse_secret_key` via `${VAR:-}` in api_keys section
- [ ] Update `profiles/base.yaml` observability provider comment to include `langfuse`

**Dependencies:** Task 1.2

## Phase 3: Integration Tests

### Task 3.1: Integration test fixtures
- [ ] Create `tests/integration/fixtures/langfuse.py`
- [ ] Implement `_langfuse_is_running()` health check via `/api/public/health`
- [ ] Create `requires_langfuse` skip marker
- [ ] Create `langfuse_available` session-scoped fixture
- [ ] Create `langfuse_provider` function-scoped fixture with OTel reset and cleanup
- [ ] Create `LangfuseTestHelpers` class with `wait_for_traces()` polling
- [ ] Register fixtures in `tests/integration/conftest.py`

**Dependencies:** Task 1.1

### Task 3.2: Integration tests
- [ ] Create `tests/integration/test_langfuse_integration.py`
- [ ] Test: provider setup creates valid OTel TracerProvider
- [ ] Test: LLM call trace appears in Langfuse API (via REST polling)
- [ ] Test: trace has correct gen_ai.* attributes (model, tokens, etc.)
- [ ] Test: prompt/completion logging respects `log_prompts` flag
- [ ] Test: span nesting works (pipeline → llm.completion)
- [ ] Test: provider shutdown flushes buffered traces

**Dependencies:** Task 2.1 (Langfuse stack running), Task 3.1

## Phase 4: Documentation

### Task 4.1: Update project documentation
- [ ] Update CLAUDE.md observability table to include Langfuse
- [ ] Add Langfuse configuration section to CLAUDE.md
- [ ] Add Langfuse Makefile targets to CLAUDE.md
- [ ] Add Langfuse gotchas to CLAUDE.md (Basic Auth, port 3100, ClickHouse requirement, first-startup key generation)
- [ ] Update `.env.example` with Langfuse env vars
- [ ] Note: `profiles/base.yaml` updates are in Task 2.3 (avoid file overlap)

**Parallel zone:** Documentation only. Does NOT modify `profiles/base.yaml` (owned by Task 2.3).

### Task 4.2: Verification script
- [ ] Extend `scripts/send_test_trace.py` to support Langfuse provider (if needed)
- [ ] Or create `scripts/verify_langfuse.py` for E2E verification
- [ ] Wire into `make verify-langfuse` target

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
