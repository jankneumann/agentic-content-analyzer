# Change: Add Profile-Based Configuration Management

## Why

Managing configuration across multiple environments (local development, staging, production) and deployment targets (Docker, Railway, Supabase cloud, local services) is increasingly complex with the current single `.env` file approach. Users must manually comment/uncomment sections, remember which variables go together, and risk exposing secrets in version control. The current system has grown to 100+ environment variables across 7 provider categories (database, storage, Neo4j, observability, LLM, TTS, ingestion), making it difficult to:

1. **Switch contexts**: Moving from local Docker development to Railway deployment requires changing 15+ variables
2. **Maintain consistency**: Provider choices have implicit dependencies (e.g., `DATABASE_PROVIDER=railway` should use `RAILWAY_DATABASE_URL`)
3. **Separate secrets from settings**: Non-secret configuration (provider choices, feature flags) is mixed with sensitive credentials
4. **Share configurations**: Teams cannot share profile configurations without also sharing secrets
5. **Validate coherence**: No automated checks that provider combinations are valid and complete

## What Changes

- **Profile files**: YAML-based profiles in `profiles/` directory defining named configurations
- **Profile inheritance**: Profiles can extend other profiles (e.g., `railway.yaml` extends `base.yaml`)
- **Secrets separation**: `.secrets.yaml` files (gitignored) store sensitive values referenced by profiles
- **CLI commands**: `newsletter-cli profile` commands for listing, activating, and validating profiles
- **Environment integration**: `PROFILE` environment variable selects active profile, falls back to `.env`
- **Startup validation**: Enhanced Settings class validates profile coherence at startup
- **Migration tooling**: Script to migrate existing `.env` to profile structure

## Impact

- **Affected specs**:
  - NEW: `profile-configuration` (this change creates a new capability)
  - RELATED: `database-provider`, `source-configuration` (patterns inform design)
- **Affected code**:
  - `src/config/settings.py` — Profile loading, inheritance resolution
  - `src/config/profiles.py` — NEW: Profile models and loader
  - `src/config/secrets.py` — NEW: Secrets loading and masking
  - `src/cli/profile_commands.py` — NEW: CLI commands
  - `profiles/` — NEW: Default profile templates
- **Breaking changes**: None — `.env` continues to work as fallback
- **Migration**: Optional migration script, profiles enhance but don't replace `.env`
