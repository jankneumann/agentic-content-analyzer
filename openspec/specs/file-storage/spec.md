# file-storage Specification

## Purpose
TBD - created by archiving change refactor-unified-file-storage. Update Purpose after archive.
## Requirements
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

### Requirement: Multi-Bucket Configuration

The system SHALL support configuring different storage providers per bucket type.

#### Scenario: Mixed provider configuration

- **GIVEN** settings configure images=local and podcasts=supabase
- **WHEN** an image is saved to the "images" bucket
- **THEN** it is stored locally
- **AND** when a podcast is saved to the "podcasts" bucket
- **THEN** it is uploaded to Supabase

### Requirement: File Serving Endpoint

The system SHALL provide an HTTP endpoint for serving stored files.

#### Scenario: Serve local file with streaming

- **WHEN** a client requests `GET /api/files/podcasts/{path}`
- **AND** the file is stored locally
- **THEN** the file is served with appropriate Content-Type
- **AND** range requests are supported for audio seeking

#### Scenario: Redirect to cloud URL

- **WHEN** a client requests `GET /api/files/podcasts/{path}`
- **AND** the file is stored in cloud storage
- **THEN** the client is redirected to a signed URL

### Requirement: Backward Compatible Image Storage

The system SHALL maintain backward compatibility with existing image storage code.

#### Scenario: Legacy get_image_storage function

- **WHEN** code calls `get_image_storage()`
- **THEN** it returns a storage provider for the "images" bucket
- **AND** existing code continues to work without modification

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
