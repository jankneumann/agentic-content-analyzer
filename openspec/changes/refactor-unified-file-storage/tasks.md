# Tasks: Unified File Storage

## Phase 1: Refactor Image Storage to Generic File Storage

- [x] 1.1 Rename `ImageStorageProvider` → `FileStorageProvider` (ABC)
- [x] 1.2 Rename `LocalImageStorage` → `LocalFileStorage`
- [x] 1.3 Rename `S3ImageStorage` → `S3FileStorage`
- [x] 1.4 Rename `SupabaseImageStorage` → `SupabaseFileStorage`
- [x] 1.5 Rename module `image_storage.py` → `file_storage.py`
- [x] 1.6 Add `bucket` parameter to provider constructors
- [x] 1.7 Update `get_image_storage()` → `get_storage(bucket: str)`
- [x] 1.8 Update `src/services/__init__.py` exports
- [x] 1.9 Update all imports in `image_extractor.py`

## Phase 2: Add Bucket Configuration

- [x] 2.1 Add bucket settings to `src/config/settings.py`:
  - `storage_provider: str` - default provider for all buckets
  - `storage_bucket_providers: dict[str, str]` - per-bucket provider overrides
- [x] 2.2 Add bucket-specific path settings:
  - `storage_local_paths: dict[str, str]` for local storage directories
- [x] 2.3 Add bucket-specific cloud bucket names:
  - `storage_s3_buckets: dict[str, str]` for S3 bucket mapping
  - `storage_supabase_buckets: dict[str, str]` for Supabase bucket mapping

## Phase 3: Integrate Podcast Audio

- [x] 3.1 Deprecate `get_output_path()` in `audio_generator_v2.py` (kept for backward compatibility)
- [x] 3.2 Update `podcast_creator.py` to use `get_storage(bucket="podcasts")`
- [x] 3.3 Save audio via `storage.save(audio_bytes, filename, "audio/mpeg")`
- [x] 3.4 Store storage path (not local path) in `Podcast.audio_url`
- [x] 3.5 Update `podcast_routes.py` to serve via storage provider

## Phase 4: Add File Serving Endpoint

- [x] 4.1 Create `GET /api/files/{bucket}/{path:path}` endpoint
- [x] 4.2 Add `Content-Type` detection via mimetypes
- [x] 4.3 Add `Accept-Ranges: bytes` header for audio seeking
- [x] 4.4 Implement HTTP range request support for streaming
- [x] 4.5 Add caching headers (`Cache-Control`)
- [x] 4.6 For cloud storage, redirect to signed URL

## Phase 5: Testing

- [x] 5.1 Update existing image storage tests (renamed to test_file_storage.py)
- [x] 5.2 Add tests for bucket configuration (TestGetStorage class)
- [x] 5.3 Add tests for podcast storage integration (via get_storage bucket tests)
- [x] 5.4 Add tests for file serving endpoint (test_files_api.py)
- [x] 5.5 Add integration test for audio streaming with range requests

## Phase 6: Documentation

- [x] 6.1 Update CLAUDE.md with unified storage docs
- [x] 6.2 Update docs/SETUP.md storage configuration section
- [x] 6.3 Add migration notes (existing files continue working via backward-compatible aliases)
