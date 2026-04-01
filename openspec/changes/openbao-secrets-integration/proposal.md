# Change: OpenBao Secrets Management Integration

## Why

The newsletter aggregator manages 30+ secrets (LLM API keys, database credentials, storage keys, auth tokens) via `.secrets.yaml` files and environment variables. This approach has fundamental limitations for production operations:

- **No rotation**: Secrets are static, long-lived strings with no lifecycle management
- **No audit trail**: No record of which process accessed which secret, or when
- **No dynamic credentials**: Database passwords are shared across all processes
- **No cross-project sharing**: The agent-coordinator already runs OpenBao for its own secrets; duplicating API keys (Anthropic, OpenAI, Google) across `.secrets.yaml` files is error-prone
- **No centralized revocation**: Compromised keys require manual replacement across all environments

The agent-coordinator already uses OpenBao with seeding scripts (`bao_seed.py`) and runtime resolution (`api_key_resolver.py`). Extending the central OpenBao deployment to serve this project gives us unified secrets management across both projects with a single operational surface.

## Current State

### Secrets Resolution Chain
```
env var → .secrets.yaml → profile YAML → .env → defaults
```

### Existing OpenBao Tooling (agent-coordinator)
- `.claude/skills/bao-vault/scripts/bao_seed.py` — Seeds `secret/coordinator/` with KV v2 secrets and AppRoles
- `.claude/skills/parallel-infrastructure/scripts/api_key_resolver.py` — Runtime resolution: OpenBao → env var → None

### Settings Architecture
- `src/config/settings.py` — Pydantic `BaseSettings` with custom `settings_customise_sources()` chain
- `src/config/secrets.py` — `resolve_secret()` function with env var → `.secrets.yaml` → default precedence
- `src/config/profiles.py` — Profile YAML loading with `${VAR}` interpolation from `.secrets.yaml`

## What Changes

### New Secrets Resolution Chain
```
env var → OpenBao KV v2 → profile YAML → .secrets.yaml → .env → defaults
```

### Deliverables
1. **Core module** (`src/config/bao_secrets.py`) — OpenBao KV v2 client with `BaoSettingsSource` for Pydantic chain, AppRole + token auth, process-level caching, token refresh
2. **Settings integration** — Wire `BaoSettingsSource` into `settings_customise_sources()` at priority 3 (below env vars, above profiles)
3. **Secret resolution** — Add OpenBao tier to `resolve_secret()` in `secrets.py`
4. **Seeding script** (`scripts/bao_seed_newsletter.py`) — Seeds `.secrets.yaml` → `secret/newsletter/`, creates AppRole, configures dynamic DB credentials, supports `--shared-keys` for cross-project access
5. **Docker overlay** (`docker-compose.openbao.yml`) — Local OpenBao dev server
6. **Profile** (`profiles/local-openbao.yaml`) — Extends `local` for OpenBao development
7. **Optional dependency** — `hvac>=2.1.0` as `[vault]` extra in `pyproject.toml`
8. **Documentation** (`docs/OPENBAO.md`) — Architecture, quick-start, production deployment guide
9. **Audit logging** — Structured log events for secret access, rotation, and failures
10. **Token lifecycle** — Automatic token refresh for long-running processes

### Central Deployment Architecture
```
                   ┌──────────────────┐
                   │   OpenBao KV v2  │
                   │  secret/         │
                   │  ├── coordinator/ │  ← agent-coordinator
                   │  ├── newsletter/  │  ← this project
                   │  └── shared/      │  ← cross-project keys
                   └────────┬─────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                  │
    ┌─────▼──────┐   ┌─────▼──────┐   ┌──────▼─────┐
    │coordinator │   │newsletter  │   │  future    │
    │ AppRole    │   │ AppRole    │   │  project   │
    └────────────┘   └────────────┘   └────────────┘
```

## Approaches Considered

### Approach A: Pydantic Settings Source Integration (Recommended)

Implement OpenBao as a first-class Pydantic `SettingsSource` that slots into the existing settings customization chain. All secrets flow through the same resolution path that profiles, env vars, and `.env` already use.

**How it works**: `BaoSettingsSource` implements the Pydantic settings source protocol, loads all secrets from OpenBao KV v2 on first access, caches them for the process lifetime, and maps UPPER_CASE vault keys to lower_case Settings field names. Token refresh runs on a background timer for long-running API server processes.

**Pros**:
- Zero changes to consuming code — anything using `Settings` or `resolve_secret()` automatically gets OpenBao
- Follows the established provider pattern (like observability, storage providers)
- Graceful degradation: remove `BAO_ADDR` and the system works exactly as before
- Testable: `clear_bao_cache()` + mock hvac client

**Cons**:
- All secrets loaded at startup (not lazy per-key) — acceptable for 30 keys
- Token refresh adds background thread complexity for API server

**Effort**: M

### Approach B: Dedicated Secrets Service

Create a `SecretsService` class (similar to existing service pattern) that wraps OpenBao and provides methods like `get_api_key()`, `get_db_url()`, `rotate_secret()`. All secret consumers explicitly call the service.

**How it works**: `SecretsService` is instantiated in the dependency injection chain. Each component that needs secrets receives it as a dependency. The service manages the hvac client, caching, and token lifecycle internally.

**Pros**:
- Explicit dependency injection — clear which components use secrets
- Can provide typed methods (`get_anthropic_key() -> str`) instead of string lookups
- Natural place for rotation and audit logic

**Cons**:
- Requires refactoring all secret consumers to use the service instead of `Settings`
- Breaks the existing `Settings` pattern where config is a flat dataclass
- Large blast radius — touches every service that reads an API key
- Duplicates resolution logic that Pydantic already handles

**Effort**: L

### Approach C: Environment Variable Injection (Sidecar Pattern)

Instead of integrating OpenBao into the Python runtime, use a sidecar process or init script that fetches secrets from OpenBao and injects them as environment variables before the app starts.

**How it works**: A shell script or `envconsul`-like process authenticates to OpenBao, reads `secret/newsletter/`, and exports all keys as env vars. The Python app sees regular environment variables — no `hvac` dependency needed.

**Pros**:
- Zero application code changes
- Language-agnostic — works for any process
- No `hvac` dependency in the app
- Simpler debugging (just check `env`)

**Cons**:
- No dynamic credential rotation during runtime
- No audit trail at the application level
- Secrets visible in process environment (security concern)
- Additional operational complexity (sidecar lifecycle, restart on rotation)
- Loses ability to distinguish "explicitly set env var" from "vault-injected env var"

**Effort**: S

### Selected Approach

**Approach A: Pydantic Settings Source Integration** — selected because it follows the established provider pattern, requires zero changes to consuming code, and supports the full production scope (token refresh, audit logging, dynamic credentials) within the existing architecture.

## Scope

### In Scope
- `BaoSettingsSource` Pydantic settings source with caching and token refresh
- OpenBao tier in `resolve_secret()` chain
- Newsletter-specific seeding script with AppRole, DB engine, shared keys
- Docker Compose overlay for local dev
- `local-openbao` profile
- `hvac` optional dependency
- Dynamic PostgreSQL credentials via database secrets engine
- Structured audit logging for secret access
- Token lifecycle management (refresh before expiry)
- Documentation (architecture, quick-start, production deployment)

### Out of Scope
- Kubernetes External Secrets / Sealed Secrets operator
- Web UI for secret management (use OpenBao UI directly)
- Modifying the agent-coordinator's existing bao_seed.py
- Secret versioning / rollback UI
