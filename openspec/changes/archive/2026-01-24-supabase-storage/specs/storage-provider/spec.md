# Storage Provider Capability

## ADDED Requirements

### Requirement: Storage Provider Abstraction

The system SHALL provide a storage provider abstraction for file operations.

#### Scenario: Provider protocol definition
- **WHEN** a storage provider is implemented
- **THEN** it SHALL implement the `StorageProvider` protocol with:
  - `name` property
  - `upload(path, data, content_type, public)` method
  - `get_url(path, expires_in)` method
  - `delete(path)` method
  - `exists(path)` method

### Requirement: Local Storage Provider

The system SHALL support local filesystem storage as the default.

#### Scenario: Local file upload
- **GIVEN** local storage provider is active
- **WHEN** a file is uploaded
- **THEN** the file SHALL be stored in `STORAGE_PATH` directory
- **AND** the returned URL SHALL be `/api/files/{path}`

#### Scenario: Local file serving
- **GIVEN** `GET /api/files/{path}` is requested
- **WHEN** the file exists
- **THEN** the file SHALL be served with correct `Content-Type`
- **AND** `Accept-Ranges: bytes` header SHALL be included

### Requirement: Supabase Storage Provider

The system SHALL support Supabase Storage for cloud deployments.

#### Scenario: Public file upload
- **GIVEN** Supabase storage is configured
- **WHEN** a file is uploaded with `public=True`
- **THEN** the file SHALL be accessible via permanent public URL

#### Scenario: Signed URL generation
- **GIVEN** a private file exists
- **WHEN** `get_url(path, expires_in=3600)` is called
- **THEN** a signed URL valid for the specified duration SHALL be returned

### Requirement: Backward Compatibility

#### Scenario: Existing local paths
- **GIVEN** existing records have local paths like `data/podcasts/file.mp3`
- **WHEN** the audio URL is accessed
- **THEN** the file SHALL be served correctly
