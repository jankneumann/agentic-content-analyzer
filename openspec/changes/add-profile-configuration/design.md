# Design: Profile-Based Configuration Management

## Context

The newsletter aggregator has evolved to support multiple infrastructure providers:
- **Database**: local, supabase, neon, railway
- **Neo4j**: local, auradb
- **Storage**: local, s3, supabase, railway (MinIO)
- **Observability**: noop, opik, braintrust, otel

Additionally, API-based services are configured via keys (not explicit provider selection):
- **TTS**: openai, elevenlabs (selected implicitly by which API key is present)
- **LLM**: anthropic, openai, google (configured via ModelConfig, not provider selection)

Each provider requires a specific set of environment variables. Users currently manage this via a single `.env` file with 100+ variables, commenting/uncommenting sections when switching between environments. This is error-prone and makes it difficult to share configurations without exposing secrets.

**Stakeholders**: Solo developers, small teams, CI/CD pipelines, cloud deployment platforms

**Constraints**:
- Must remain backward-compatible with existing `.env` approach
- Must not expose secrets in git-tracked files
- Must work with existing Pydantic Settings pattern
- Must support Railway's automatic environment variable injection

## Goals / Non-Goals

**Goals**:
- Enable named configuration profiles for different environments/deployments
- Separate secrets from shareable configuration
- Validate profile completeness and coherence at startup
- Support profile inheritance to reduce duplication
- Provide CLI tooling for profile management
- Migrate from `.env` with zero disruption

**Non-Goals**:
- Replace Pydantic Settings (profiles feed into existing Settings class)
- Implement a secrets manager (profiles reference secrets, don't manage them)
- Support remote profile storage (profiles are local files)
- Dynamic profile switching at runtime (profile is fixed at startup)

## Decisions

### Decision 1: Profile File Format — YAML with Environment Variable Interpolation

**What**: Profiles are YAML files supporting `${VAR}` interpolation from environment and secrets.

**Why**: YAML is human-readable, supports comments, and handles complex nested structures. Environment variable interpolation allows profiles to reference secrets without embedding them.

**Example**:
```yaml
# profiles/railway.yaml
extends: base
name: railway
description: Railway cloud deployment

providers:
  database: railway
  storage: railway
  neo4j: auradb
  observability: braintrust

settings:
  database:
    railway_database_url: ${RAILWAY_DATABASE_URL}  # Injected by Railway
    railway_pool_size: 3
  neo4j:
    auradb_uri: ${NEO4J_AURADB_URI}
    auradb_password: ${NEO4J_AURADB_PASSWORD}
  observability:
    braintrust_api_key: ${BRAINTRUST_API_KEY}
```

**Alternatives considered**:
- TOML: Less flexible for nested structures, no clear inheritance pattern
- JSON: No comments, harder to read/edit
- Python files: Security concerns, harder to validate statically

### Decision 2: Secrets Storage — Local `.secrets.yaml` with Gitignore

**What**: Secrets stored in `.secrets.yaml` (gitignored), referenced by profiles via `${SECRET_NAME}`.

**Why**: Separates shareable profile definitions from sensitive credentials. Local file avoids external dependencies while still preventing accidental commits.

**Format**:
```yaml
# .secrets.yaml (gitignored)
ANTHROPIC_API_KEY: sk-ant-xxx
NEO4J_AURADB_PASSWORD: xxx
BRAINTRUST_API_KEY: xxx
RAILWAY_DATABASE_URL: postgresql://...
```

**Resolution order** (most specific wins):
1. Environment variables (highest priority — allows CI/CD override)
2. `.secrets.yaml` file
3. Profile defaults (lowest priority)

**Alternatives considered**:
- Vault/AWS Secrets Manager: Overkill for this project, adds external dependency
- Encrypted secrets file: Adds key management complexity
- Separate `.env.secrets`: Less structured than YAML, no typing

### Decision 3: Profile Inheritance — Single `extends` Field

**What**: Profiles can extend one parent profile via `extends: parent-name`.

**Why**: Reduces duplication. Common settings (model configs, token budgets) defined in `base.yaml`, environment-specific overrides in child profiles.

**Inheritance rules**:
- Scalar values: Child overrides parent
- Dictionaries: Deep merge (child keys override parent keys)
- Lists: Child replaces parent (no merge)
- `providers` section: Child fully specifies providers (explicit over implicit)

**Example**:
```yaml
# profiles/base.yaml
providers:
  database: local
  neo4j: local
  storage: local
  observability: noop

settings:
  digest:
    context_window_percentage: 0.5
    newsletter_budget_percentage: 0.6

# profiles/production.yaml
extends: base
providers:
  database: railway
  storage: railway
  observability: braintrust
# settings.digest inherited from base
```

**Alternatives considered**:
- Multiple inheritance: Complex resolution, hard to debug
- No inheritance: More duplication, profiles become large
- Mixins: Adds complexity, less intuitive than single parent

### Decision 4: Profile Activation — `PROFILE` Environment Variable

**What**: Set `PROFILE=railway` to activate `profiles/railway.yaml`.

**Why**: Simple, works with all deployment platforms, doesn't require file system access at runtime.

**Resolution order**:
1. `PROFILE` env var → load `profiles/{PROFILE}.yaml`
2. `profiles/default.yaml` exists → load it
3. Fallback → load from `.env` (backward compatible)

**Alternatives considered**:
- CLI flag only: Doesn't work with Docker/Railway/serverless
- `.profile` file: Another file to manage, less explicit
- Auto-detect from environment: Magic is confusing

### Decision 5: Profile Validation — Pydantic Models with Coherence Checks

**What**: Profile structure validated by Pydantic models. Provider-specific validation ensures required settings are present.

**Why**: Fail fast at startup with clear error messages. Prevent partial configurations that would fail at runtime.

**Validation layers**:
1. **Schema validation**: YAML structure matches expected model
2. **Provider validation**: Selected providers have required settings
3. **Coherence validation**: Provider combinations are compatible (e.g., `storage: supabase` requires Supabase DB config)

**Example error**:
```
ProfileValidationError: Profile 'railway' is invalid:
  - providers.database=railway requires settings.database.railway_database_url
  - providers.neo4j=auradb requires settings.neo4j.auradb_uri
  - Missing secret: NEO4J_AURADB_PASSWORD (referenced but not found)
```

### Decision 6: CLI Commands — Profile Management Subcommands

**What**: Add `newsletter-cli profile` subcommands for listing, validating, and showing profiles.

**Commands**:
```bash
# List available profiles
newsletter-cli profile list

# Show resolved profile (with secrets masked)
newsletter-cli profile show railway

# Validate profile completeness
newsletter-cli profile validate railway

# Create profile from current .env
newsletter-cli profile migrate --from .env --to profiles/migrated.yaml

# Show effective configuration (profile + secrets + env)
newsletter-cli profile inspect
```

**Why**: Provides visibility into configuration without reading raw files. `migrate` eases transition from `.env`.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Users don't adopt profiles | Keep `.env` as full fallback, zero migration pressure |
| Secrets accidentally committed | `.secrets.yaml` in `.gitignore`, CI checks for secret patterns |
| Profile inheritance complexity | Limit to single parent, provide `profile inspect` for debugging |
| Railway env var injection conflicts | Environment variables always win (highest priority) |
| YAML parsing errors | Clear error messages with line numbers, schema validation |

## Migration Plan

### Phase 1: Profile Infrastructure (no user impact)
1. Add profile models and loader in `src/config/profiles.py`
2. Add secrets loader in `src/config/secrets.py`
3. Modify Settings class to check for profile before `.env`
4. Add default profile templates in `profiles/`

### Phase 2: CLI Tooling
1. Add `newsletter-cli profile` commands
2. Add migration script from `.env` to profiles
3. Update documentation

### Phase 3: Profile Templates
1. Ship `profiles/base.yaml` with all defaults
2. Ship `profiles/local.yaml` for Docker Compose development
3. Ship `profiles/railway.yaml` for Railway deployment
4. Ship `profiles/supabase.yaml` for Supabase cloud

**Rollback**: Remove `PROFILE` env var to revert to `.env` behavior. No data migration needed.

## Open Questions

1. **Should profiles support conditional sections?** (e.g., `if: ENVIRONMENT == production`)
   - Current answer: No, keep simple. Use separate profiles instead.

2. **Should we support profile directories?** (e.g., `profiles/railway/base.yaml`, `profiles/railway/staging.yaml`)
   - Current answer: No, flat structure with inheritance is sufficient.

3. **Should secrets support different backends?** (e.g., AWS Secrets Manager, Vault)
   - Current answer: Out of scope. Secrets are always local file + env vars.
