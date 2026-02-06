## ADDED Requirements

### Requirement: Storage Provider Abstraction

The system SHALL provide a file storage provider abstraction that allows different storage backends to be used interchangeably.

#### Scenario: Provider protocol definition
- **WHEN** a new storage provider is implemented
- **THEN** it SHALL implement the `FileStorageProvider` abstract base class
- **AND** the class SHALL define methods for:
  - `save(data, filename, content_type, **metadata)` returning storage path
  - `get(path)` returning file bytes
  - `delete(path)` returning success boolean
  - `exists(path)` checking file existence
  - `get_url(path)` returning access URL
  - `provider_name` property returning provider identifier
  - `bucket` property returning bucket name

#### Scenario: Provider selection via factory
- **WHEN** `get_storage(bucket, provider)` is called
- **THEN** the appropriate provider SHALL be instantiated based on configuration
- **AND** the factory SHALL support per-bucket provider overrides via `STORAGE_BUCKET_PROVIDERS`

### Requirement: Railway MinIO Storage Provider

The system SHALL support Railway-deployed MinIO as an S3-compatible storage provider.

#### Scenario: Railway storage provider selection
- **GIVEN** `STORAGE_PROVIDER=railway` is set
- **WHEN** `get_storage()` is called
- **THEN** the Railway storage provider SHALL be instantiated
- **AND** it SHALL use MinIO's S3-compatible API

#### Scenario: Railway MinIO credential handling
- **GIVEN** the application is deployed on Railway with MinIO
- **AND** Railway has injected `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
- **WHEN** Railway storage provider is initialized
- **THEN** the provider SHALL use the Railway-provided credentials automatically

#### Scenario: Railway MinIO endpoint discovery
- **GIVEN** Railway has injected `RAILWAY_PUBLIC_DOMAIN` for the MinIO service
- **WHEN** `RAILWAY_MINIO_ENDPOINT` is not explicitly set
- **THEN** the provider SHALL construct the endpoint from `https://{RAILWAY_PUBLIC_DOMAIN}`
- **AND** the endpoint SHALL be used for S3 API calls

#### Scenario: Railway MinIO bucket configuration
- **GIVEN** `MINIO_BUCKET` is set to a bucket name
- **WHEN** Railway storage provider saves a file
- **THEN** the file SHALL be stored in the configured bucket
- **AND** the path SHALL follow the date-based organization pattern

#### Scenario: Railway storage URL generation
- **GIVEN** a file is stored in Railway MinIO
- **WHEN** `get_url(path)` is called
- **THEN** it SHALL return a URL using the Railway MinIO endpoint
- **AND** the URL format SHALL be `{endpoint}/{bucket}/{path}`

### Requirement: Storage Provider Factory Extension

The storage factory SHALL support Railway as a valid provider option.

#### Scenario: Storage provider factory with Railway
- **GIVEN** `STORAGE_PROVIDER` is set to a valid provider name
- **WHEN** `get_storage()` is called
- **THEN** the provider SHALL be instantiated based on the value:
  - `"local"` → LocalFileStorage
  - `"s3"` → S3FileStorage
  - `"supabase"` → SupabaseFileStorage
  - `"railway"` → RailwayFileStorage *(NEW)*

#### Scenario: Per-bucket Railway provider override
- **GIVEN** `STORAGE_BUCKET_PROVIDERS='{"podcasts": "railway"}'`
- **WHEN** `get_storage(bucket="podcasts")` is called
- **THEN** the Railway storage provider SHALL be used for podcasts
- **AND** other buckets SHALL use the default `STORAGE_PROVIDER`
