## MODIFIED Requirements

### Requirement: Default Profile Templates

The system SHALL ship with default profile templates for common deployment scenarios.

Templates:
- `profiles/base.yaml`: All defaults, all providers set to "local"
- `profiles/local.yaml`: Extends base, configured for Docker Compose
- `profiles/railway.yaml`: Extends base, configured for Railway deployment
- `profiles/supabase-cloud.yaml`: Extends base, configured for Supabase cloud
- `profiles/staging.yaml`: Extends base, configured for production-like CI/CD validation

#### Scenario: Base profile provides all defaults
- **WHEN** `profiles/base.yaml` is loaded without any parent
- **THEN** all provider categories SHALL have explicit values
- **AND** all required settings for "local" providers SHALL have defaults

#### Scenario: Railway profile references injected variables
- **GIVEN** `profiles/railway.yaml` template
- **THEN** it SHALL contain `settings.database.railway_database_url: ${RAILWAY_DATABASE_URL}`
- **AND** it SHALL contain `settings.storage.minio_root_user: ${MINIO_ROOT_USER}`
- **AND** it SHALL contain `settings.storage.minio_root_password: ${MINIO_ROOT_PASSWORD}`
- **AND** YAML comments SHALL explain that Railway auto-injects these variables

#### Scenario: Staging profile targets production-like providers
- **GIVEN** `profiles/staging.yaml` template
- **THEN** it SHALL set providers for `database: railway`, `neo4j: auradb`, and `storage: railway`
- **AND** it SHALL set observability to `braintrust` with a staging project name
- **AND** it SHALL support staging-specific environment variable overrides for core connections

#### Scenario: Template profiles are valid structurally
- **WHEN** each template profile is validated for structure only (ignoring unresolved variables)
- **THEN** all required fields SHALL be present
- **AND** all provider values SHALL be valid literals
- **AND** all settings keys SHALL match expected schema

#### Scenario: Template profiles list required secrets
- **GIVEN** a template profile references `${SECRET_VAR}` without defaults
- **WHEN** the profile is validated with secrets checking enabled
- **THEN** validation SHALL list missing secrets as warnings (not errors)
- **AND** the warning SHALL indicate which secrets need to be provided
