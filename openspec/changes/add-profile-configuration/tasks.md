# Tasks: Add Profile-Based Configuration Management

## 1. Profile Data Models

- [ ] 1.1 Create `src/config/profiles.py` with core models:
  - `ProviderChoices` model (database, storage, neo4j, observability literals)
  - `Profile` model (name, extends, description, providers, settings)
- [ ] 1.2 Add provider-specific settings models to `src/config/profiles.py`:
  - `DatabaseSettings` model (all database-related settings by provider)
  - `Neo4jSettings` model (all Neo4j-related settings by provider)
  - `StorageSettings` model (all storage-related settings by provider)
  - `ObservabilitySettings` model (all observability settings by provider)
  - `ProfileSettings` model (nested settings sections combining above)
- [ ] 1.3 Implement environment variable interpolation (`${VAR}` syntax) in YAML values:
  - Support `${VAR}` for required variables
  - Support `${VAR:-default}` for optional variables with defaults
  - Support `$${VAR}` escape sequence to produce literal `${VAR}`
- [ ] 1.4 Add unit tests for profile models in `tests/test_config/test_profiles.py`:
  - Model validation (required fields, type checking)
  - Interpolation with missing vars, defaults, and escaping
  - Invalid YAML structure handling

## 2. Secrets Loading

> **Note**: Tasks 2.1-2.4 can run in parallel with Task 1 (no dependencies)

- [ ] 2.1 Create `src/config/secrets.py` with secrets loader:
  - `load_secrets()` function reading `.secrets.yaml`
  - `SecretValue` wrapper class for masking in logs/output
  - `resolve_secret()` with env var → secrets file → default precedence
- [ ] 2.2 Add `.secrets.yaml` to `.gitignore` and verify in tests
- [ ] 2.3 Add `.secrets.yaml.example` template with placeholder values
- [ ] 2.4 Add unit tests for secrets loading in `tests/test_config/test_secrets.py`:
  - Load from file
  - Env var precedence over file
  - Missing file returns empty dict
  - Secret masking in string representation
  - Malformed YAML raises `SecretsParseError` with line number

## 3. Profile Inheritance

> **Depends on**: 1.1, 1.2 (profile models must exist)
> **Can parallel with**: 2.x (secrets loading)

- [ ] 3.1 Implement profile loading with `extends` resolution in `src/config/profiles.py`:
  - `load_profile(name)` function
  - Recursive parent loading with cycle detection
  - Deep merge for settings dictionaries (child keys override parent)
  - List replacement (child replaces parent entirely)
- [ ] 3.2 Implement profile resolution order in `src/config/profiles.py`:
  - Check `PROFILE` env var first
  - Fall back to `profiles/default.yaml` if exists
  - Fall back to None (signals .env loading)
- [ ] 3.3 Add unit tests for inheritance in `tests/test_config/test_profiles.py`:
  - Single-level inheritance
  - Multi-level inheritance (grandparent → parent → child)
  - Override behavior (child wins)
  - Cycle detection error
  - Missing parent error

## 4. Profile Validation

> **Depends on**: 1.x, 2.x, 3.x (full profile system)

- [ ] 4.1 Implement provider-specific validation rules in `src/config/profiles.py`:
  - Database provider requires corresponding URL/credentials
  - Neo4j provider requires corresponding URI/credentials
  - Storage provider requires corresponding bucket/credentials
  - Observability provider requires corresponding API key (except noop)
- [ ] 4.2 Implement coherence validation:
  - `storage: supabase` requires Supabase database config present
  - `storage: railway` requires Railway database config present
- [ ] 4.3 Implement error aggregation and messaging:
  - Collect ALL validation errors before raising
  - Include profile name in error context
  - List missing required settings with provider context
  - List unresolved secret references
- [ ] 4.4 Add unit tests for validation in `tests/test_config/test_profile_validation.py`:
  - Valid profile passes
  - Missing required setting fails with specific message
  - Multiple errors aggregated
  - Coherence rules enforced

## 5. Settings Integration

> **Depends on**: 1.x, 2.x, 3.x, 4.x

- [ ] 5.1 Modify `src/config/settings.py` to support profile loading:
  - Add `model_validator` to check for active profile before `.env` loading
  - Load and resolve profile if `PROFILE` env var set
  - Merge profile values into Settings fields
  - Fall back to `.env` if no profile active
- [ ] 5.2 Ensure backward compatibility:
  - All existing `.env` configurations continue working unchanged
  - No behavior change when `PROFILE` env var is not set
  - Existing model validators (database, neo4j, observability) still run
- [ ] 5.3 Add integration tests in `tests/test_config/test_profile_integration.py`:
  - Profile loading overrides `.env` values
  - Environment variables win over profile values (highest precedence)
  - Missing profile raises `ProfileNotFoundError` with available profiles listed
  - Backward compatibility with `.env` only
- [ ] 5.4 Update `get_settings()` to log active profile name at startup

## 6. Default Profile Templates

> **Depends on**: 5.x (working integration)
> **Can parallel with**: 7.x, 8.x

- [ ] 6.1 Create `profiles/base.yaml`:
  - All providers set to `local`
  - All settings with sensible development defaults
  - Comments explaining each section and setting
- [ ] 6.2 Create `profiles/local.yaml` extending base:
  - Configured for Docker Compose local development
  - Local PostgreSQL, Neo4j, Redis connection URLs
  - Observability set to `noop`
- [ ] 6.3 Create `profiles/railway.yaml` extending base:
  - Database and storage providers set to `railway`
  - Neo4j provider set to `auradb`
  - Observability set to `braintrust`
  - References `${RAILWAY_DATABASE_URL}`, `${MINIO_ROOT_USER}`, `${MINIO_ROOT_PASSWORD}`
  - Comments explaining Railway auto-injection
- [ ] 6.4 Create `profiles/supabase-cloud.yaml` extending base:
  - Database and storage providers set to `supabase`
  - Neo4j provider set to `auradb`
  - References Supabase-specific env vars
- [ ] 6.5 Add template validation tests ensuring structural correctness

## 7. CLI Profile Commands

> **Depends on**: 5.x (working profile system)
> **Can parallel with**: 6.x, 8.x

- [ ] 7.1 Create `src/cli/profile_commands.py` with Typer app
- [ ] 7.2 Implement `profile list` command:
  - Scan `profiles/` directory for `.yaml` files
  - Display: name, extends (if any), description (if any)
  - Mark currently active profile (from `PROFILE` env var)
- [ ] 7.3 Implement `profile show <name>` command:
  - Load and resolve profile with inheritance
  - Display all settings with source annotations
  - Mask secret values as `***`
- [ ] 7.4 Implement `profile validate <name>` command:
  - Run all validation checks
  - Print success message or list all errors
  - Exit code 0 if valid, 1 if invalid
- [ ] 7.5 Implement `profile inspect` command:
  - Show effective Settings (profile + secrets + env merged)
  - Annotate each value's source (profile, secrets, env, default)
  - Mask secrets
- [ ] 7.6 Register profile commands in main CLI entrypoint (`src/cli/main.py`)
- [ ] 7.7 Add CLI command tests in `tests/test_cli/test_profile_commands.py`

## 8. Migration Tooling

> **Depends on**: 5.x (working profile system)
> **Can parallel with**: 6.x, 7.x

- [ ] 8.1 Implement `profile migrate` command in `src/cli/profile_commands.py`:
  - Parse existing `.env` file
  - Detect provider choices from `*_PROVIDER` variables
  - Generate profile YAML with non-secret settings
  - Generate `.secrets.yaml` with detected secrets
- [ ] 8.2 Implement secret detection heuristics:
  - Variables containing `KEY`, `SECRET`, `PASSWORD`, `TOKEN` in name
  - Variables with URL credentials (password in connection string)
  - Configurable patterns via `--secret-patterns` flag
- [ ] 8.3 Add `--dry-run` flag:
  - Print would-be profile and secrets content to stdout
  - Do not create or modify any files
- [ ] 8.4 Add `--preserve-comments` flag:
  - Parse `.env` comments as section headers
  - Convert to YAML comments in output
- [ ] 8.5 Add migration tests in `tests/test_cli/test_profile_migrate.py`:
  - Basic migration
  - Secret detection
  - Dry run output
  - Comment preservation

## 9. Documentation

> **Depends on**: 6.x, 7.x, 8.x

- [ ] 9.1 Update `CLAUDE.md` with profile configuration section:
  - Quick reference for profile commands
  - Environment variable (`PROFILE`) documentation
  - Link to detailed guide
- [ ] 9.2 Update `docs/SETUP.md` with profile setup instructions:
  - Quick start: choosing a profile
  - Creating custom profiles
  - Secrets management best practices
- [ ] 9.3 Add `docs/PROFILES.md` comprehensive guide:
  - Profile file format reference
  - Inheritance behavior and examples
  - Provider validation rules
  - CLI command reference with examples
  - Migration guide from `.env`
- [ ] 9.4 Update `.env.example` header to reference profile alternative

## 10. CI/CD Integration

> **Depends on**: 6.x (profile templates exist)

- [ ] 10.1 Add profile validation to CI workflow (`.github/workflows/ci.yml`):
  - Run `newsletter-cli profile validate` on all profiles in `profiles/`
  - Fail CI if any profile has structural errors
- [ ] 10.2 Add secret pattern detection to pre-commit (`.pre-commit-config.yaml`):
  - Scan `profiles/*.yaml` for hardcoded secret patterns
  - Patterns: API keys, passwords, tokens (regex-based)
  - Fail if patterns detected in tracked files
- [ ] 10.3 Update Railway deployment docs with profile usage example

## Dependency Graph

```
Phase 1 (parallel):
  1.1 ──┬── 1.2 ──┬── 1.3 ──── 1.4
        │         │
  2.1 ──┴── 2.2 ──┴── 2.3 ──── 2.4

Phase 2 (after 1.x and 2.x):
  3.1 ──── 3.2 ──── 3.3

Phase 3 (after 3.x):
  4.1 ──── 4.2 ──── 4.3 ──── 4.4

Phase 4 (after 4.x):
  5.1 ──── 5.2 ──── 5.3 ──── 5.4

Phase 5 (parallel after 5.x):
  6.1 ──── 6.2 ──── 6.3 ──── 6.4 ──── 6.5
  7.1 ──── 7.2 ──── 7.3 ──── 7.4 ──── 7.5 ──── 7.6 ──── 7.7
  8.1 ──── 8.2 ──── 8.3 ──── 8.4 ──── 8.5

Phase 6 (after 6-8):
  9.1 ──── 9.2 ──── 9.3 ──── 9.4
  10.1 ─── 10.2 ─── 10.3
```

## Parallelization Summary

- **Phase 1**: Tasks 1.x and 2.x can run in parallel (2 agents)
- **Phase 2-4**: Sequential (validation depends on full system)
- **Phase 5**: Tasks 6.x, 7.x, 8.x can run in parallel (3 agents)
- **Phase 6**: Tasks 9.x and 10.x can run in parallel (2 agents)

**Max parallel width**: 3 agents (during Phase 5)
**Independent task groups**: 1.x, 2.x | 6.x, 7.x, 8.x | 9.x, 10.x
