# file-storage Specification

## Purpose
TBD - created by archiving change refactor-unified-file-storage. Update Purpose after archive.
## Requirements
### Requirement: Unified File Storage Provider

The system SHALL provide a unified file storage abstraction supporting
multiple storage backends (local filesystem, S3, Supabase Storage).

#### Scenario: Store image to configured provider

- **WHEN** an image is saved with `get_storage("images").save(data, filename, content_type)`
- **THEN** the file is stored using the provider configured for the "images" bucket

#### Scenario: Store podcast audio to cloud

- **WHEN** a podcast is saved with `get_storage("podcasts").save(audio, filename, "audio/mpeg")`
- **AND** the "podcasts" bucket is configured for Supabase
- **THEN** the audio file is uploaded to Supabase Storage

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
