## MODIFIED Requirements

### Requirement: Default Profile Templates

The system SHALL ship with default profile templates for common deployment scenarios. All profiles SHALL default to Langfuse for observability. Local profiles SHALL use self-hosted Langfuse; cloud profiles SHALL use Langfuse Cloud.

This modifies the existing requirement to reflect the change from `noop`/`braintrust` observability defaults to `langfuse` across all profiles, and to document the ParadeDB GHCR image for Railway database deployment.

#### Scenario: Base profile defaults to Langfuse observability
- **WHEN** `profiles/base.yaml` is loaded without any parent
- **THEN** `providers.observability` SHALL be `langfuse`
- **AND** `settings.observability.otel_enabled` SHALL be `true`
- **AND** `settings.observability.otel_service_name` SHALL be `newsletter-aggregator`

#### Scenario: Local profile uses self-hosted Langfuse
- **GIVEN** `profiles/local.yaml` template
- **THEN** `providers.observability` SHALL be `langfuse`
- **AND** `settings.observability.langfuse_base_url` SHALL be `http://localhost:3100`
- **AND** `settings.observability.otel_enabled` SHALL be `true`
- **AND** YAML comments SHALL explain that Langfuse stack must be running via `make langfuse-up` or `docker compose -f docker-compose.langfuse.yml`

#### Scenario: Railway profile uses Langfuse Cloud
- **GIVEN** `profiles/railway.yaml` template
- **THEN** `providers.observability` SHALL be `langfuse`
- **AND** `settings.observability.langfuse_base_url` SHALL default to `https://cloud.langfuse.com`
- **AND** `settings.observability.langfuse_public_key` SHALL reference `${LANGFUSE_PUBLIC_KEY}`
- **AND** `settings.observability.langfuse_secret_key` SHALL reference `${LANGFUSE_SECRET_KEY}`
- **AND** `settings.observability.otel_enabled` SHALL be `true`

#### Scenario: Railway-Neon profile uses Langfuse Cloud
- **GIVEN** `profiles/railway-neon.yaml` template
- **THEN** `providers.observability` SHALL be `langfuse`
- **AND** observability settings SHALL match `railway.yaml` Langfuse Cloud configuration

#### Scenario: Staging profile uses Langfuse Cloud with staging project isolation
- **GIVEN** `profiles/staging.yaml` template
- **THEN** `providers.observability` SHALL be `langfuse`
- **AND** `settings.observability.langfuse_public_key` SHALL reference `${STAGING_LANGFUSE_PUBLIC_KEY:-${LANGFUSE_PUBLIC_KEY:-}}`
- **AND** `settings.observability.langfuse_secret_key` SHALL reference `${STAGING_LANGFUSE_SECRET_KEY:-${LANGFUSE_SECRET_KEY:-}}`
- **AND** `settings.observability.otel_service_name` SHALL be `newsletter-aggregator-staging`

#### Scenario: Braintrust remains available as non-default override
- **GIVEN** any profile with `providers.observability: langfuse`
- **WHEN** the environment variable `OBSERVABILITY_PROVIDER=braintrust` is set
- **THEN** the Braintrust provider SHALL be used instead of Langfuse
- **AND** no code changes SHALL be required — the override works via standard settings precedence

#### Scenario: Railway profile documents ParadeDB GHCR image
- **GIVEN** `profiles/railway.yaml` template
- **THEN** YAML comments SHALL document that Railway database uses the ParadeDB GHCR image (`ghcr.io/jankneumann/aca-postgres:17-railway`)
- **AND** YAML comments SHALL list the pre-installed extensions: pgvector, pg_search, pgmq, pg_cron

#### Scenario: Graceful degradation when Langfuse credentials are missing
- **GIVEN** a profile with `providers.observability: langfuse`
- **WHEN** `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` are not set
- **THEN** the system SHALL log a warning about missing credentials
- **AND** the system SHALL NOT crash or refuse to start
- **AND** tracing data SHALL be silently dropped (noop-equivalent behavior)

#### Scenario: Template profiles list required secrets
- **GIVEN** a template profile references `${SECRET_VAR}` without defaults
- **WHEN** the profile is validated with secrets checking enabled
- **THEN** validation SHALL report the first missing secret as a warning (not an error)
- **AND** the warning SHALL indicate the secret name that needs to be provided
- **NOTE**: Current implementation reports one missing secret at a time (interpolation fails fast). Collecting all missing secrets in a single pass is deferred to a future improvement
