# Storage Provider Capability

## ADDED Requirements

### Requirement: Storage Provider Abstraction

The system SHALL provide a storage provider abstraction that allows different file storage backends to be used interchangeably.

#### Scenario: Provider protocol definition
- **WHEN** a new storage provider is implemented
- **THEN** it SHALL implement the `StorageProvider` protocol
- **AND** the protocol SHALL define methods for:
  - `name` property returning provider identifier
  - `upload(path, data, content_type, public)` uploading files
  - `get_url(path, expires_in)` generating access URLs
  - `delete(path)` removing files
  - `exists(path)` checking file existence

#### Scenario: Provider selection is transparent
- **WHEN** application code uploads or retrieves files
- **THEN** the storage operation SHALL work without knowledge of the underlying provider
- **AND** all existing file operations SHALL work unchanged

### Requirement: Local Storage Provider

The system SHALL support local filesystem storage as the default provider for development.

#### Scenario: Local provider configuration
- **GIVEN** `STORAGE_PROVIDER=local` or no storage provider configured
- **WHEN** the storage provider is initialized
- **THEN** the local storage provider SHALL be selected
- **AND** files SHALL be stored in `STORAGE_PATH` directory (default: `data/uploads/`)

#### Scenario: Local file upload
- **GIVEN** local storage provider is active
- **WHEN** a file is uploaded with `path="audio/digest-123.mp3"`
- **THEN** the file SHALL be stored at `{STORAGE_PATH}/audio/digest-123.mp3`
- **AND** the returned URL SHALL be `/api/files/audio/digest-123.mp3`

#### Scenario: Local file serving
- **GIVEN** a file exists in local storage
- **WHEN** the file URL is accessed
- **THEN** the file SHALL be served via FastAPI static files or file endpoint
- **AND** appropriate `Content-Type` headers SHALL be set

### Requirement: Supabase Storage Provider

The system SHALL support Supabase Storage as a cloud storage backend.

#### Scenario: Supabase provider detection
- **GIVEN** `STORAGE_PROVIDER=supabase`
- **AND** `SUPABASE_URL` and `SUPABASE_ANON_KEY` are configured
- **WHEN** the storage provider is initialized
- **THEN** the Supabase storage provider SHALL be selected

#### Scenario: Supabase bucket configuration
- **GIVEN** Supabase storage provider is active
- **WHEN** files are uploaded
- **THEN** they SHALL be stored in the `SUPABASE_STORAGE_BUCKET` bucket (default: `audio-files`)

#### Scenario: Public file upload to Supabase
- **GIVEN** Supabase storage provider is active
- **WHEN** a file is uploaded with `public=True`
- **THEN** the file SHALL be uploaded to a public bucket path
- **AND** the returned URL SHALL be a permanent public URL
- **AND** the URL format SHALL be `https://{project}.supabase.co/storage/v1/object/public/{bucket}/{path}`

#### Scenario: Private file upload to Supabase
- **GIVEN** Supabase storage provider is active
- **WHEN** a file is uploaded with `public=False`
- **THEN** the file SHALL be uploaded to a private bucket path
- **AND** `get_url()` SHALL return signed URLs with expiration

#### Scenario: Signed URL generation
- **GIVEN** a private file exists in Supabase storage
- **WHEN** `get_url(path, expires_in=3600)` is called
- **THEN** a signed URL valid for 1 hour SHALL be returned
- **AND** the URL SHALL allow unauthenticated access during validity period

### Requirement: Storage Provider Factory

The system SHALL provide a factory function that returns the appropriate storage provider.

#### Scenario: Explicit provider selection
- **GIVEN** `STORAGE_PROVIDER` environment variable is set
- **WHEN** the provider factory is called
- **THEN** the specified provider SHALL be returned

#### Scenario: Provider initialization failure
- **GIVEN** Supabase provider is selected
- **AND** `SUPABASE_URL` or `SUPABASE_ANON_KEY` is missing
- **WHEN** the provider factory is called
- **THEN** a clear error message SHALL be raised
- **AND** the error SHALL indicate which configuration is missing

### Requirement: Audio File Integration

The system SHALL use the storage provider abstraction for all audio file operations.

#### Scenario: TTS audio upload
- **GIVEN** a digest audio file is generated
- **WHEN** the audio is saved
- **THEN** it SHALL be uploaded via the storage provider
- **AND** the returned URL SHALL be stored in the database

#### Scenario: Audio URL retrieval
- **GIVEN** a digest has an associated audio file
- **WHEN** the audio URL is requested
- **THEN** the URL SHALL be retrieved via the storage provider
- **AND** for private files, a fresh signed URL SHALL be generated

#### Scenario: Audio file deletion
- **GIVEN** a digest is deleted
- **WHEN** the deletion is processed
- **THEN** the associated audio file SHALL be deleted from storage
- **AND** deletion failure SHALL be logged but not block digest deletion

### Requirement: Backward Compatibility

The system SHALL maintain compatibility with existing local file paths.

#### Scenario: Existing local paths
- **GIVEN** existing records have local file paths like `data/podcasts/digest-123.mp3`
- **WHEN** the audio URL is accessed
- **THEN** the local provider SHALL serve the file correctly
- **AND** no migration of existing files SHALL be required

#### Scenario: Migration to cloud storage
- **GIVEN** a deployment switches from local to Supabase storage
- **WHEN** new files are uploaded
- **THEN** new files SHALL go to Supabase
- **AND** existing local files SHALL remain accessible via local paths
