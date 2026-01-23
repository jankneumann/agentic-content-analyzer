# Design: Refactor Database Provider Selection

## Context

The newsletter aggregator supports three database providers:
- **Local**: Development PostgreSQL via Docker
- **Supabase**: Managed PostgreSQL with component-based or URL config
- **Neon**: Serverless PostgreSQL with branching capabilities

Current detection logic in `src/config/settings.py:163-189` uses implicit detection from env vars and URL patterns, leading to confusion when multiple providers are partially configured.

### Stakeholders
- Developers setting up local environments
- CI/CD pipelines switching between providers
- Production deployments targeting specific providers

## Goals / Non-Goals

### Goals
- Single, explicit configuration point for provider selection
- Fast failure with clear error messages on misconfiguration
- Backwards-compatible migration path (warning period before hard failure)
- Simplified codebase with less branching logic

### Non-Goals
- Runtime provider switching (requires engine recreation, schema sync)
- GUI-based configuration
- Auto-migration between providers

## Decisions

### Decision 1: `DATABASE_PROVIDER` as Single Source of Truth

**What**: The `database_provider` field in Settings becomes the authoritative selector.

**Why**:
- Explicit is better than implicit (Python Zen)
- Eliminates "which env var wins?" confusion
- Aligns with 12-Factor App principles (config from environment)

**Implementation**:
```python
class Settings(BaseSettings):
    database_provider: Literal["local", "supabase", "neon"] = "local"
```

### Decision 2: Pydantic Validator for Configuration Consistency

**What**: Add `@model_validator` to check provider config at startup.

**Why**:
- Fail fast before any database operations
- Clear error messages guide users to fix config
- Prevents silent misconfiguration

**Implementation**:
```python
@model_validator(mode="after")
def validate_database_provider_config(self) -> "Settings":
    match self.database_provider:
        case "neon":
            if ".neon.tech" not in self.database_url:
                raise ValueError(
                    "DATABASE_PROVIDER=neon requires DATABASE_URL containing .neon.tech. "
                    f"Got: {self._mask_url(self.database_url)}"
                )
        case "supabase":
            has_supabase_config = (
                self.supabase_project_ref
                or ".supabase." in self.database_url
            )
            if not has_supabase_config:
                raise ValueError(
                    "DATABASE_PROVIDER=supabase requires SUPABASE_PROJECT_REF "
                    "or DATABASE_URL containing .supabase."
                )
        case "local":
            # Warn if URL looks like a cloud provider
            if ".neon.tech" in self.database_url:
                logger.warning(
                    "DATABASE_URL contains .neon.tech but DATABASE_PROVIDER=local. "
                    "Set DATABASE_PROVIDER=neon to use Neon features."
                )
            elif ".supabase." in self.database_url:
                logger.warning(
                    "DATABASE_URL contains .supabase. but DATABASE_PROVIDER=local. "
                    "Set DATABASE_PROVIDER=supabase to use Supabase features."
                )
    return self
```

### Decision 3: Simplified URL Resolution

**What**: Replace cascading `if/elif` chains with `match` statement on explicit provider.

**Why**:
- Clearer code flow
- Each provider's logic is isolated
- Easier to add new providers

**Implementation**:
```python
def get_effective_database_url(self) -> str:
    match self.database_provider:
        case "supabase":
            return self._get_supabase_pooler_url()
        case "neon":
            return self._get_neon_pooler_url()
        case "local" | _:
            return self.database_url

def get_migration_database_url(self) -> str:
    match self.database_provider:
        case "supabase":
            return self._get_supabase_direct_url()
        case "neon":
            return self._get_neon_direct_url()
        case "local" | _:
            return self.database_url
```

### Decision 4: Deprecation Path for Implicit Detection

**What**: Keep `get_database_provider()` as deprecated method that logs warning.

**Why**:
- Allows gradual migration
- External code using this method gets notified
- Can be removed in future version

**Implementation**:
```python
def get_database_provider(self) -> str:
    """Deprecated: Use settings.database_provider directly."""
    warnings.warn(
        "get_database_provider() is deprecated. Use settings.database_provider instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.database_provider
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Breaking existing deployments | Clear error message with fix instructions |
| Users forget to update `.env` | Validation fails with actionable message |
| CI/CD pipelines break | Document required env var in migration guide |

## Migration Plan

### Phase 1: Add Validation with Warnings (Non-Breaking)
1. Add `database_provider` field with default `"local"`
2. Add validator that warns when implicit detection would differ from explicit setting
3. Update documentation

### Phase 2: Require Explicit Provider (Breaking)
1. Change validator to fail instead of warn for cloud URLs with `local` provider
2. Remove implicit detection logic from `get_database_provider()`
3. Deprecate `get_database_provider()` method

### Rollback
- Revert to previous Settings class
- No database schema changes involved

## Open Questions

1. **Should we support a `DATABASE_PROVIDER=auto` mode?**
   - Pro: Backwards compatible
   - Con: Defeats the purpose of explicit configuration
   - **Decision**: No, explicit is better

2. **Environment variable prefix for provider-specific settings?**
   - Current: `NEON_*`, `SUPABASE_*`
   - Alternative: `DB_NEON_*`, `DB_SUPABASE_*`
   - **Decision**: Keep current naming for backwards compatibility
