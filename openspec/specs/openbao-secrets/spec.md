# Spec: OpenBao Secrets Management

## Purpose

Integrates OpenBao as a centralized secrets provider for the newsletter aggregator, using a Pydantic Settings Source that slots into the existing resolution chain.

## Requirements

### Requirement: Optional, Non-Fatal Integration

The OpenBao integration SHALL be entirely optional: when `BAO_ADDR` is unset the
settings source SHALL return an empty dict silently, and the existing resolution
chain SHALL behave identically to a build without OpenBao.

#### Scenario: Graceful degradation when OpenBao is unconfigured

**Given** `BAO_ADDR` is not set in the environment
**When** the application starts and loads Settings
**Then** the `BaoSettingsSource` SHALL return an empty dict
**And** SHALL NOT emit any log messages (complete silence when unconfigured)
**And** the existing resolution chain (env_settings → profile_settings → dotenv_settings → defaults) SHALL function identically to before.

### Requirement: Secret Resolution and Precedence

The system SHALL resolve secrets from the OpenBao KV v2 store, and environment
variables SHALL always take precedence over values held in the vault.

#### Scenario: Secret resolution from OpenBao KV v2

**Given** `BAO_ADDR` is set and OpenBao is reachable
**And** secrets are seeded at `secret/newsletter/` with key `ANTHROPIC_API_KEY=sk-ant-test`
**When** `resolve_secret("ANTHROPIC_API_KEY")` is called
**And** `ANTHROPIC_API_KEY` is NOT set as an environment variable
**Then** the function SHALL return `sk-ant-test` from OpenBao.

#### Scenario: Environment variables override OpenBao

**Given** `BAO_ADDR` is set and OpenBao contains `ANTHROPIC_API_KEY=sk-from-vault`
**And** the environment variable `ANTHROPIC_API_KEY=sk-from-env` is set
**When** `resolve_secret("ANTHROPIC_API_KEY")` is called
**Then** the function SHALL return `sk-from-env` (environment variables always win).

### Requirement: Authentication and Token Lifecycle

The system SHALL authenticate to OpenBao via AppRole when role credentials are
present, SHALL fall back to direct token authentication for development, and
SHALL refresh time-limited tokens for long-running processes.

#### Scenario: AppRole authentication

**Given** `BAO_ADDR`, `BAO_ROLE_ID`, and `BAO_SECRET_ID` are set
**When** the `BaoSettingsSource` initializes
**Then** it SHALL authenticate via AppRole auth method
**And** obtain a time-limited token
**And** use that token for subsequent KV v2 reads.

#### Scenario: Token authentication fallback (dev mode)

**Given** `BAO_ADDR` and `BAO_TOKEN` are set (but not `BAO_ROLE_ID`)
**When** the `BaoSettingsSource` initializes
**Then** it SHALL use the provided token directly for authentication.

#### Scenario: Token refresh for long-running processes

**Given** the application is running as an API server (long-lived process)
**And** the AppRole token has a TTL of N seconds
**When** 75% of the token TTL has elapsed
**Then** the module SHALL re-authenticate via AppRole
**And** reload secrets from OpenBao
**And** update the in-memory cache atomically (replace dict reference, not mutate)
**And** schedule the next refresh at 75% of the new token's TTL
**And** log a structured INFO-level audit event for the refresh.

### Requirement: Failure Isolation

A failure to reach OpenBao, or an absent `hvac` dependency, SHALL degrade to the
remaining resolution sources rather than failing application startup.

#### Scenario: Connection failure handling

**Given** `BAO_ADDR` is set but OpenBao is unreachable
**When** the `BaoSettingsSource` attempts to load secrets
**Then** it SHALL log a WARNING-level message including the connection error and `BAO_ADDR` value
**And** return an empty dict (falling through to profile_settings → dotenv_settings chain)
**And** NOT raise an exception that would prevent application startup.

#### Scenario: hvac not installed

**Given** `BAO_ADDR` is set but the `hvac` package is not installed
**When** the `BaoSettingsSource` attempts to load secrets
**Then** it SHALL log a DEBUG-level message: "hvac not installed — install with: pip install '.[vault]'"
**And** return an empty dict.

### Requirement: Seeding From Local Configuration

The system SHALL provide seeding that populates OpenBao from `.secrets.yaml`,
including shared keys, AppRole creation, and dynamic database credentials, and
SHALL support a dry-run mode that writes nothing.

#### Scenario: Seeding from .secrets.yaml

**Given** a `.secrets.yaml` file exists with N secret key-value pairs
**When** `scripts/bao_seed_newsletter.py` is run with valid `BAO_ADDR` and `BAO_TOKEN`
**Then** it SHALL write all N secrets to `secret/newsletter/` in OpenBao KV v2
**And** print the count and key names (not values) to stdout.

#### Scenario: Shared key seeding

**Given** `.secrets.yaml` contains `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`
**When** `bao_seed_newsletter.py --shared-keys ANTHROPIC_API_KEY,OPENAI_API_KEY` is run
**Then** it SHALL write those keys to `secret/shared/` in addition to `secret/newsletter/`
**And** SHALL read existing `secret/shared/` data first
**And** SHALL merge newsletter keys into the existing data (newsletter values win for duplicate keys; keys from other projects are preserved)
**And** SHALL write the merged result back to `secret/shared/`.

#### Scenario: AppRole creation

**Given** valid admin credentials (`BAO_TOKEN`)
**When** `bao_seed_newsletter.py --with-approle` is run
**Then** it SHALL create a `newsletter-read` policy granting read access to `secret/data/newsletter` and `secret/data/shared`
**And** create a `newsletter-app` AppRole bound to that policy
**And** print the role_id and instructions for generating a secret_id.

#### Scenario: Dynamic database credentials

**Given** `POSTGRES_DSN` is set and the database secrets engine is available
**When** `bao_seed_newsletter.py --with-db-engine` is run
**Then** it SHALL configure a `newsletter-postgres` database connection
**And** create a `newsletter-app` role that generates PostgreSQL credentials with default TTL of 1 hour and max TTL of 24 hours
**And** the generated credentials SHALL have SELECT, INSERT, UPDATE, DELETE on all tables in the public schema.

#### Scenario: Dry run mode

**Given** the `--dry-run` flag is passed to `bao_seed_newsletter.py`
**When** the script executes
**Then** it SHALL print all actions it would take (with key names, counts, policy names)
**And** SHALL NOT write anything to OpenBao.

### Requirement: Audit Logging

Secret access SHALL be auditable through structured events that never contain
secret values.

#### Scenario: Audit logging

**Given** OpenBao is configured and secrets are loaded
**When** any of the following events occur:
- `bao.secrets_loaded` — initial or refreshed secret fetch (INFO)
- `bao.token_refreshed` — AppRole token refreshed (INFO)
- `bao.auth_failure` — authentication rejected (WARNING)
- `bao.connection_error` — OpenBao unreachable (WARNING)
- `bao.token_manager_stopped` — background refresh stopped on shutdown (DEBUG)
**Then** the module SHALL emit a structured log event at the level indicated above
**And** the log event SHALL include: event name, timestamp, secret count (for loads), error details (for failures)
**And** SHALL NOT include secret values in any log output.

### Requirement: Pydantic Settings Chain Integration

`BaoSettingsSource` SHALL slot into the Pydantic Settings resolution chain,
SHALL expose cache isolation for testing, and SHALL map UPPER_CASE vault keys
onto lower_case settings fields.

#### Scenario: Pydantic Settings chain integration

**Given** `BAO_ADDR` is configured
**When** `Settings()` is instantiated
**Then** the settings source priority SHALL be:
1. init_settings (values passed to constructor)
2. env_settings (environment variables)
3. bao_settings (OpenBao KV v2)
4. profile_settings (profiles/{name}.yaml)
5. dotenv_settings (.env file)
6. file_secret_settings

#### Scenario: Cache isolation for testing

**Given** test code calls `clear_bao_cache()`
**When** `BaoSettingsSource` or `resolve_secret()` is subsequently called
**Then** it SHALL re-fetch secrets from OpenBao (or skip if unconfigured)
**And** NOT return stale cached values.

#### Scenario: UPPER_CASE to lower_case key mapping

**Given** OpenBao stores secrets as `ANTHROPIC_API_KEY` (UPPER_CASE, matching env var convention)
**And** Pydantic Settings fields are `anthropic_api_key` (lower_case)
**When** `BaoSettingsSource` resolves field values
**Then** it SHALL map UPPER_CASE vault keys to lower_case field names.

### Requirement: Concurrency and Vault Response Handling

Secret loading SHALL be thread-safe under concurrent access, and SHALL handle
partial, empty, and special-character vault responses without corrupting or
truncating values.

#### Scenario: Concurrent access thread safety

**Given** the application runs as a multi-threaded FastAPI server
**And** `BAO_ADDR` is configured
**When** multiple threads call `get_bao_secret()` or `BaoSettingsSource.__call__()` simultaneously during initial load
**Then** the module SHALL use a threading lock to ensure only one thread fetches from OpenBao
**And** other threads SHALL block until the cache is populated
**And** all threads SHALL receive the same cached dict reference.

#### Scenario: Partial vault response

**Given** `BAO_ADDR` is configured and OpenBao is reachable
**And** `secret/newsletter/` contains only 10 of the expected 30 keys
**When** `_load_bao_secrets()` fetches the secrets
**Then** it SHALL cache and return all 10 available keys
**And** the 20 missing keys SHALL fall through to the next resolution source (profile_settings, dotenv_settings)
**And** it SHALL NOT log a warning for missing keys (the vault stores what was seeded).

#### Scenario: Special characters in secret values

**Given** OpenBao stores a secret with value containing `$`, `{`, `}`, newlines, or Unicode characters
**When** `get_bao_secret()` or `BaoSettingsSource` retrieves the value
**Then** it SHALL return the value exactly as stored — no interpolation, escaping, or truncation.

#### Scenario: Empty vault path

**Given** `BAO_ADDR` is configured and OpenBao is reachable
**And** `secret/newsletter/` exists but contains zero keys
**When** `_load_bao_secrets()` fetches the secrets
**Then** it SHALL cache an empty dict
**And** return no values (falling through to profile_settings)
**And** log an INFO-level `bao.secrets_loaded` event with secret count 0.

### Requirement: Lifecycle and Exception Isolation

The token manager SHALL shut down cleanly, and any unexpected exception inside
the settings source SHALL be contained so that `Settings()` instantiation never
fails because of OpenBao.

#### Scenario: Token manager shutdown

**Given** the `_BaoTokenManager` is running with a scheduled refresh timer
**When** `_BaoTokenManager.stop()` is called (e.g., during process shutdown)
**Then** it SHALL cancel any pending timer
**And** log a DEBUG-level `bao.token_manager_stopped` event
**And** NOT attempt any further OpenBao operations.

#### Scenario: BaoSettingsSource exception isolation

**Given** `BAO_ADDR` is configured
**And** an unexpected exception occurs during `BaoSettingsSource.__call__()` or `get_field_value()`
**When** `Settings()` is being instantiated
**Then** the exception SHALL be caught within the source
**And** a WARNING-level log SHALL be emitted with the exception details
**And** the source SHALL return an empty dict
**And** `Settings()` instantiation SHALL NOT fail.
