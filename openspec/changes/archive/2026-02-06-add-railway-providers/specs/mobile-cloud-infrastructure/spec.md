## MODIFIED Requirements

### Requirement: Railway Cloud Deployment

The system SHALL deploy to Railway as two services (web API and worker) with proper configuration for cloud hosting, using a custom PostgreSQL image with extensions and Braintrust LLM tracing.

#### Scenario: Web service deployment
- **WHEN** the web service is deployed
- **THEN** it SHALL be accessible via HTTPS
- **AND** accept requests from mobile clients (CORS configured)
- **AND** the Docker image SHALL include profiles/ and sources.d/ for runtime configuration
- **AND** the Braintrust SDK SHALL be installed via `--extra braintrust` in the build

#### Scenario: Worker service deployment
- **WHEN** the worker service is deployed
- **THEN** it SHALL connect to the same database as the web service
- **AND** process queued jobs independently
- **AND** initialize telemetry with `setup_telemetry(app=None)` for LLM tracing
- **AND** shut down telemetry cleanly on worker termination

#### Scenario: Custom PostgreSQL image with extensions
- **WHEN** the PostgreSQL service is deployed on Railway
- **THEN** it SHALL use a custom Docker image from GHCR
- **AND** the image SHALL include pgvector, pg_search, pgmq, and pg_cron extensions
- **AND** the image SHALL use an external postgresql.conf optimized for Railway Hobby plan (512 MB RAM)
- **AND** extensions SHALL be initialized via init-extensions.sql on first container start

#### Scenario: Profile-based configuration in production
- **GIVEN** `PROFILE=railway` is set on the API service
- **WHEN** the application starts
- **THEN** it SHALL load profiles/railway.yaml from the Docker image
- **AND** all provider choices (database, storage, neo4j, observability) SHALL be configured by the profile
