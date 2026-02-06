## MODIFIED Requirements

### Requirement: Unified File Storage Provider

The system SHALL provide a unified file storage abstraction supporting
multiple storage backends (local filesystem, S3, Supabase Storage, Railway MinIO).

#### Scenario: Store image to configured provider

- **WHEN** an image is saved with `get_storage("images").save(data, filename, content_type)`
- **THEN** the file is stored using the provider configured for the "images" bucket

#### Scenario: Store podcast audio to cloud

- **WHEN** a podcast is saved with `get_storage("podcasts").save(audio, filename, "audio/mpeg")`
- **AND** the "podcasts" bucket is configured for Supabase
- **THEN** the audio file is uploaded to Supabase Storage

#### Scenario: Store file to Railway MinIO

- **WHEN** `STORAGE_PROVIDER=railway` is configured
- **AND** a file is saved via `get_storage("images").save(data, filename, content_type)`
- **THEN** the file SHALL be uploaded to Railway MinIO using S3-compatible API
- **AND** the endpoint SHALL be auto-discovered from `RAILWAY_PUBLIC_DOMAIN` or `RAILWAY_MINIO_ENDPOINT`
- **AND** credentials SHALL be read from `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`

## ADDED Requirements

### Requirement: Railway MinIO Storage Provider

The system SHALL support Railway MinIO as an S3-compatible storage provider for single-platform Railway deployments.

#### Scenario: Railway storage initialization
- **GIVEN** `STORAGE_PROVIDER=railway` is configured
- **WHEN** the storage factory creates a provider
- **THEN** a `RailwayFileStorage` instance SHALL be returned
- **AND** it SHALL extend `S3FileStorage` for MinIO compatibility

#### Scenario: Railway MinIO endpoint discovery
- **GIVEN** `RAILWAY_MINIO_ENDPOINT` is not explicitly set
- **AND** `RAILWAY_PUBLIC_DOMAIN` is set
- **WHEN** Railway storage is initialized
- **THEN** the endpoint SHALL be constructed from `RAILWAY_PUBLIC_DOMAIN`

#### Scenario: Railway MinIO path-style addressing
- **WHEN** Railway storage uploads or retrieves a file
- **THEN** it SHALL use path-style S3 addressing (not virtual-hosted-style)
- **AND** this is required for MinIO compatibility
