# Spec: OpenBao Secrets Management

## Overview

Integrates OpenBao as a centralized secrets provider for the newsletter aggregator, using a Pydantic Settings Source that slots into the existing resolution chain.

## Scenarios

### openbao-secrets.1 — Graceful degradation when OpenBao is unconfigured

**Given** `BAO_ADDR` is not set in the environment
**When** the application starts and loads Settings
**Then** the `BaoSettingsSource` SHALL return no values and the existing resolution chain (env var → profile → .env → defaults) SHALL function identically to before.

### openbao-secrets.2 — Secret resolution from OpenBao KV v2

**Given** `BAO_ADDR` is set and OpenBao is reachable
**And** secrets are seeded at `secret/newsletter/` with key `ANTHROPIC_API_KEY=sk-ant-test`
**When** `resolve_secret("ANTHROPIC_API_KEY")` is called
**And** `ANTHROPIC_API_KEY` is NOT set as an environment variable
**Then** the function SHALL return `sk-ant-test` from OpenBao.

### openbao-secrets.3 — Environment variables override OpenBao

**Given** `BAO_ADDR` is set and OpenBao contains `ANTHROPIC_API_KEY=sk-from-vault`
**And** the environment variable `ANTHROPIC_API_KEY=sk-from-env` is set
**When** `resolve_secret("ANTHROPIC_API_KEY")` is called
**Then** the function SHALL return `sk-from-env` (environment variables always win).

### openbao-secrets.4 — AppRole authentication

**Given** `BAO_ADDR`, `BAO_ROLE_ID`, and `BAO_SECRET_ID` are set
**When** the `BaoSettingsSource` initializes
**Then** it SHALL authenticate via AppRole auth method
**And** obtain a time-limited token
**And** use that token for subsequent KV v2 reads.

### openbao-secrets.5 — Token authentication fallback (dev mode)

**Given** `BAO_ADDR` and `BAO_TOKEN` are set (but not `BAO_ROLE_ID`)
**When** the `BaoSettingsSource` initializes
**Then** it SHALL use the provided token directly for authentication.

### openbao-secrets.6 — Token refresh for long-running processes

**Given** the application is running as an API server (long-lived process)
**And** the AppRole token has a TTL of N seconds
**When** 75% of the token TTL has elapsed
**Then** the module SHALL automatically refresh the token
**And** reload secrets from OpenBao
**And** log a structured audit event for the refresh.

### openbao-secrets.7 — Connection failure handling

**Given** `BAO_ADDR` is set but OpenBao is unreachable
**When** the `BaoSettingsSource` attempts to load secrets
**Then** it SHALL log a warning with the connection error
**And** return no values (falling through to profile/dotenv chain)
**And** NOT raise an exception that would prevent application startup.

### openbao-secrets.8 — hvac not installed

**Given** `BAO_ADDR` is set but the `hvac` package is not installed
**When** the `BaoSettingsSource` attempts to load secrets
**Then** it SHALL log a debug message suggesting `pip install '.[vault]'`
**And** return no values gracefully.

### openbao-secrets.9 — Seeding from .secrets.yaml

**Given** a `.secrets.yaml` file exists with N secret key-value pairs
**When** `scripts/bao_seed_newsletter.py` is run with valid `BAO_ADDR` and `BAO_TOKEN`
**Then** it SHALL write all N secrets to `secret/newsletter/` in OpenBao KV v2
**And** print the count and key names (not values) to stdout.

### openbao-secrets.10 — Shared key seeding

**Given** `.secrets.yaml` contains `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`
**When** `bao_seed_newsletter.py --shared-keys ANTHROPIC_API_KEY,OPENAI_API_KEY` is run
**Then** it SHALL write those keys to `secret/shared/` in addition to `secret/newsletter/`
**And** merge with (not overwrite) existing shared secrets from other projects.

### openbao-secrets.11 — AppRole creation

**Given** valid admin credentials (`BAO_TOKEN`)
**When** `bao_seed_newsletter.py --with-approle` is run
**Then** it SHALL create a `newsletter-read` policy granting read access to `secret/data/newsletter` and `secret/data/shared`
**And** create a `newsletter-app` AppRole bound to that policy
**And** print the role_id and instructions for generating a secret_id.

### openbao-secrets.12 — Dynamic database credentials

**Given** `POSTGRES_DSN` is set and the database secrets engine is available
**When** `bao_seed_newsletter.py --with-db-engine` is run
**Then** it SHALL configure a `newsletter-postgres` database connection
**And** create a `newsletter-app` role that generates time-limited PostgreSQL credentials
**And** the generated credentials SHALL have SELECT, INSERT, UPDATE, DELETE on public schema.

### openbao-secrets.13 — Dry run mode

**Given** the `--dry-run` flag is passed to `bao_seed_newsletter.py`
**When** the script executes
**Then** it SHALL print all actions it would take (with key names, counts, policy names)
**And** SHALL NOT write anything to OpenBao.

### openbao-secrets.14 — Audit logging

**Given** OpenBao is configured and secrets are loaded
**When** any of the following events occur: secret load, token refresh, auth failure, connection error
**Then** the module SHALL emit a structured log event at the appropriate level (INFO for loads/refreshes, WARNING for failures)
**And** the log event SHALL include: event type, timestamp, secret count (for loads), error details (for failures)
**And** SHALL NOT include secret values in any log output.

### openbao-secrets.15 — Pydantic Settings chain integration

**Given** `BAO_ADDR` is configured
**When** `Settings()` is instantiated
**Then** the settings source priority SHALL be:
1. init_settings (values passed to constructor)
2. env_settings (environment variables)
3. bao_settings (OpenBao KV v2)
4. profile_settings (profiles/{name}.yaml)
5. dotenv_settings (.env file)
6. file_secret_settings

### openbao-secrets.16 — Cache isolation for testing

**Given** test code calls `clear_bao_cache()`
**When** `BaoSettingsSource` or `resolve_secret()` is subsequently called
**Then** it SHALL re-fetch secrets from OpenBao (or skip if unconfigured)
**And** NOT return stale cached values.

### openbao-secrets.17 — UPPER_CASE to lower_case key mapping

**Given** OpenBao stores secrets as `ANTHROPIC_API_KEY` (UPPER_CASE, matching env var convention)
**And** Pydantic Settings fields are `anthropic_api_key` (lower_case)
**When** `BaoSettingsSource` resolves field values
**Then** it SHALL map UPPER_CASE vault keys to lower_case field names.
