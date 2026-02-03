# Profile Configuration Guide

This guide covers the profile-based configuration system that replaces or augments traditional `.env` file configuration.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Profile File Format](#profile-file-format)
- [Inheritance](#inheritance)
- [Variable Interpolation](#variable-interpolation)
- [Secrets Management](#secrets-management)
- [Provider Validation](#provider-validation)
- [CLI Commands](#cli-commands)
- [Migration from .env](#migration-from-env)
- [Available Profiles](#available-profiles)
- [Creating Custom Profiles](#creating-custom-profiles)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Profiles provide named configuration bundles that replace scattered environment variables with structured YAML files. Benefits include:

- **Organized configuration**: Group related settings together
- **Inheritance**: Share common settings via `extends`
- **Validation**: Catch configuration errors before runtime
- **Secrets separation**: Keep sensitive values in a gitignored file
- **Environment portability**: Switch configurations with a single env var

### Configuration Precedence

When resolving settings, the system uses this priority order (highest first):

1. **Environment variables** — Always win, even over profile values
2. **Profile settings** — From `profiles/{name}.yaml`
3. **Secrets file** — From `.secrets.yaml`
4. **`.env` file** — Traditional dotenv (only when no profile active)
5. **Default values** — Hardcoded in Settings model

## Quick Start

### Using an Existing Profile

```bash
# List available profiles
newsletter-cli profile list

# Validate a profile before using
newsletter-cli profile validate local

# Activate a profile
export PROFILE=local

# Verify effective configuration
newsletter-cli profile inspect
```

### Creating Your First Profile

```bash
# Migrate from existing .env (preview first)
newsletter-cli profile migrate --dry-run

# Create the profile
newsletter-cli profile migrate --output my-profile

# Review and activate
newsletter-cli profile show my-profile
export PROFILE=my-profile
```

## Profile File Format

Profiles are YAML files in the `profiles/` directory. Here's the complete schema:

```yaml
# Required: Profile identifier (should match filename without .yaml)
name: my-profile

# Optional: Inherit settings from another profile
extends: base

# Optional: Human-readable description
description: My custom development profile

# Required: Provider choices for each subsystem
providers:
  database: local      # local | supabase | neon | railway
  neo4j: local         # local | auradb
  storage: local       # local | s3 | supabase | railway
  observability: noop  # noop | opik | braintrust | otel

# Optional: All configuration settings
settings:
  # General settings
  environment: development
  log_level: INFO

  # Database settings
  database_url: postgresql://localhost:5432/newsletters
  redis_url: redis://localhost:6379

  # Neo4j settings
  neo4j_uri: bolt://localhost:7687
  neo4j_user: neo4j
  neo4j_password: ${NEO4J_PASSWORD}  # Reference from secrets

  # API keys (reference from secrets)
  anthropic_api_key: ${ANTHROPIC_API_KEY}
  openai_api_key: ${OPENAI_API_KEY:-}  # Optional with empty default
```

### Provider Options

| Provider Category | Values | Description |
|-------------------|--------|-------------|
| `database` | `local`, `supabase`, `neon`, `railway` | PostgreSQL provider |
| `neo4j` | `local`, `auradb` | Knowledge graph provider |
| `storage` | `local`, `s3`, `supabase`, `railway` | File storage provider |
| `observability` | `noop`, `opik`, `braintrust`, `otel` | Telemetry provider |

## Inheritance

Profiles can inherit from other profiles using the `extends` field. This enables DRY configuration:

### Base Profile (profiles/base.yaml)

```yaml
name: base
description: Base development defaults

providers:
  database: local
  neo4j: local
  storage: local
  observability: noop

settings:
  environment: development
  log_level: INFO
  database_url: postgresql://localhost:5432/newsletters
```

### Child Profile (profiles/staging.yaml)

```yaml
name: staging
extends: base
description: Staging environment

providers:
  database: supabase    # Override database provider
  observability: opik   # Override observability

settings:
  environment: staging
  log_level: WARNING
  # database_url inherited from base, but Supabase URL from secrets
  database_url: ${SUPABASE_DATABASE_URL}
```

### Inheritance Rules

1. **Deep merge for settings**: Child keys override parent keys at any nesting level
2. **Provider replacement**: Child providers completely replace parent providers section
3. **Multi-level inheritance**: `child → parent → grandparent` chains work
4. **Cycle detection**: Circular inheritance is detected and raises an error

## Variable Interpolation

Profile values can reference environment variables or secrets using `${VAR}` syntax:

### Syntax Options

```yaml
settings:
  # Required variable (error if not set)
  api_key: ${ANTHROPIC_API_KEY}

  # Optional with default value
  log_level: ${LOG_LEVEL:-INFO}

  # Literal dollar sign (escaped)
  price: $${PRICE}  # Results in "${PRICE}" literally
```

### Resolution Order for Variables

1. Environment variables
2. `.secrets.yaml` file
3. Default value (if `:-default` syntax used)
4. Error (if required and not found)

## Secrets Management

Secrets are stored in `.secrets.yaml` (gitignored) and referenced via `${VAR}` in profiles.

### Creating .secrets.yaml

```yaml
# .secrets.yaml - DO NOT COMMIT
ANTHROPIC_API_KEY: sk-ant-xxxxx
OPENAI_API_KEY: sk-xxxxx
NEO4J_PASSWORD: your-password
SUPABASE_DATABASE_URL: postgresql://user:pass@host/db
```

### Security Notes

- `.secrets.yaml` is automatically added to `.gitignore`
- Never commit secrets to version control
- Use environment variables in CI/CD instead of secrets file
- The `profile migrate` command auto-detects secrets by key patterns

### Secret Detection Patterns

The migration tool recognizes these patterns as secrets:

- `*_KEY` (API keys)
- `*_SECRET` (secrets)
- `*_PASSWORD` (passwords)
- `*_TOKEN` (tokens)
- `*_CREDENTIAL` (credentials)

## Provider Validation

Each provider has required settings that are validated at profile load time.

### Database Provider Requirements

| Provider | Required Settings |
|----------|-------------------|
| `local` | `database_url` (falls back to `local_database_url`) |
| `supabase` | `supabase_database_url` or `database_url` |
| `neon` | `neon_database_url` |
| `railway` | `railway_database_url` |

### Neo4j Provider Requirements

| Provider | Required Settings |
|----------|-------------------|
| `local` | `neo4j_uri`, `neo4j_user`, `neo4j_password` |
| `auradb` | `neo4j_auradb_uri`, `neo4j_auradb_user`, `neo4j_auradb_password` |

### Storage Provider Requirements

| Provider | Required Settings |
|----------|-------------------|
| `local` | None (uses default paths) |
| `s3` | `aws_region`, bucket configuration |
| `supabase` | `supabase_access_key_id`, `supabase_secret_access_key` |
| `railway` | MinIO credentials (auto-discovered if Railway environment) |

### Observability Provider Requirements

| Provider | Required Settings |
|----------|-------------------|
| `noop` | None |
| `opik` | `opik_api_key` or `opik_url_override` |
| `braintrust` | `braintrust_api_key` |
| `otel` | `otel_exporter_otlp_endpoint` |

### Coherence Rules

Some provider combinations have additional requirements:

- `storage: supabase` requires Supabase database configuration present
- `storage: railway` requires Railway database configuration present

## CLI Commands

### profile list

List all available profiles:

```bash
newsletter-cli profile list
newsletter-cli profile list --dir /path/to/profiles
```

Output shows profile name, description, extends relationship, and marks the active profile.

### profile show

Display a profile with resolved inheritance:

```bash
newsletter-cli profile show local
newsletter-cli profile show local --raw          # Show unresolved YAML
newsletter-cli profile show local --show-secrets # Reveal secret values
```

### profile validate

Validate a profile for completeness and correctness:

```bash
newsletter-cli profile validate local
newsletter-cli profile validate local --strict  # Also check unresolved variables
```

Exit codes:
- `0`: Profile is valid
- `1`: Validation errors found

### profile inspect

Show effective Settings (profile + env + secrets merged):

```bash
newsletter-cli profile inspect
newsletter-cli profile inspect --show-secrets
```

### profile migrate

Convert `.env` file to profile format:

```bash
# Preview migration
newsletter-cli profile migrate --dry-run

# Create profile
newsletter-cli profile migrate --output production

# Custom source file
newsletter-cli profile migrate --env-file .env.production --output production

# Additional secret patterns
newsletter-cli profile migrate --secret-patterns "PRIVATE,INTERNAL"
```

## Migration from .env

### Step-by-Step Migration

1. **Preview the migration**:
   ```bash
   newsletter-cli profile migrate --dry-run
   ```

2. **Review the output** for:
   - Correct provider detection
   - Proper secret separation
   - Setting categorization

3. **Run the migration**:
   ```bash
   newsletter-cli profile migrate --output my-profile
   ```

4. **Review generated files**:
   - `profiles/my-profile.yaml` — Non-secret settings
   - `.secrets.yaml` — Detected secrets

5. **Validate the profile**:
   ```bash
   newsletter-cli profile validate my-profile --strict
   ```

6. **Test with the profile**:
   ```bash
   export PROFILE=my-profile
   newsletter-cli profile inspect
   ```

7. **Remove or keep .env**:
   - Keep `.env` as backup initially
   - Remove once profile is confirmed working

### What Gets Migrated

| Source | Destination |
|--------|-------------|
| `*_PROVIDER` variables | `providers:` section |
| Secret-pattern variables | `.secrets.yaml` |
| URL/connection settings | `settings:` section |
| Other variables | `settings:` section |

### Manual Adjustments

After migration, you may want to:

1. Add `extends: base` if using standard base profile
2. Remove redundant settings that match base
3. Organize settings into logical groups
4. Add comments for documentation

## Available Profiles

### base.yaml

The foundation profile with sensible development defaults:

- All providers set to `local`
- Standard connection URLs for Docker Compose
- Observability disabled (`noop`)

### local.yaml

Docker Compose local development:

```bash
export PROFILE=local
docker compose up -d
```

### railway.yaml

Railway platform deployment:

- Database and storage use Railway providers
- Neo4j uses AuraDB (cloud)
- Observability enabled (Braintrust)

### supabase-cloud.yaml

Supabase cloud deployment:

- Database and storage use Supabase
- Neo4j uses AuraDB
- Full cloud configuration

## Creating Custom Profiles

### Template

```yaml
name: custom-profile
extends: base  # Start from base to inherit defaults
description: My custom configuration

providers:
  # Only override what differs from base
  database: neon

settings:
  # Only include settings that differ from base
  neon_database_url: ${NEON_DATABASE_URL}
```

### Naming Conventions

- Use lowercase with hyphens: `my-profile.yaml`
- Name should match the `name:` field
- Descriptive names: `staging`, `production`, `local-supabase`

## Best Practices

### 1. Use Inheritance

Start from `base` and only override what differs:

```yaml
# Good
extends: base
providers:
  database: neon  # Only override database

# Avoid
providers:  # Repeating all providers
  database: neon
  neo4j: local
  storage: local
  observability: noop
```

### 2. Keep Secrets Separate

Never hardcode secrets in profiles:

```yaml
# Good
api_key: ${ANTHROPIC_API_KEY}

# Never do this
api_key: sk-ant-actual-secret
```

### 3. Validate Before Use

Always validate after changes:

```bash
newsletter-cli profile validate my-profile --strict
```

### 4. Document Custom Profiles

Add descriptions to explain purpose:

```yaml
name: integration-tests
description: Configuration for CI integration test suite
```

### 5. Use Environment Variables for CI/CD

In CI/CD, set variables directly rather than using secrets file:

```bash
export PROFILE=staging
export ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }}
```

## Troubleshooting

### Profile Not Loading

```bash
# Check PROFILE is set
echo $PROFILE

# Verify profile exists
ls profiles/

# Check for syntax errors
newsletter-cli profile validate $PROFILE
```

### Validation Errors

```bash
# See all errors at once
newsletter-cli profile validate my-profile

# Check with strict mode for unresolved variables
newsletter-cli profile validate my-profile --strict
```

### Secrets Not Resolving

```bash
# Check secrets file exists
ls -la .secrets.yaml

# Verify variable name matches
grep "ANTHROPIC_API_KEY" .secrets.yaml
grep "ANTHROPIC_API_KEY" profiles/my-profile.yaml

# Check env var override
echo $ANTHROPIC_API_KEY
```

### Inheritance Issues

```bash
# Show raw profile to see extends
newsletter-cli profile show my-profile --raw

# Verify parent exists
ls profiles/base.yaml
```

### Provider Validation Failures

Check the [Provider Validation](#provider-validation) section for required settings per provider. Common issues:

- Using `database: neon` without `neon_database_url`
- Using `observability: braintrust` without `braintrust_api_key`
- Using `storage: supabase` without Supabase storage credentials
