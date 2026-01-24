# Tasks: Unified File Storage

## Phase 1: Refactor Image Storage to Generic File Storage

- [ ] 1.1 Rename `ImageStorageProvider` → `FileStorageProvider` (ABC)
- [ ] 1.2 Rename `LocalImageStorage` → `LocalFileStorage`
- [ ] 1.3 Rename `S3ImageStorage` → `S3FileStorage`
- [ ] 1.4 Rename `SupabaseImageStorage` → `SupabaseFileStorage`
- [ ] 1.5 Rename module `image_storage.py` → `file_storage.py`
- [ ] 1.6 Add `bucket` parameter to provider constructors
- [ ] 1.7 Update `get_image_storage()` → `get_storage(bucket: str)`
- [ ] 1.8 Update `src/services/__init__.py` exports
- [ ] 1.9 Update all imports in `image_extractor.py`

## Phase 2: Add Bucket Configuration

- [ ] 2.1 Add bucket settings to `src/config/settings.py`:
  - `storage_buckets: dict[str, str]` mapping bucket names to providers
  - Default: `{"images": "local", "podcasts": "local", "audio-digests": "local"}`
- [ ] 2.2 Add bucket-specific path settings:
  - `storage_paths: dict[str, str]` for local storage directories
- [ ] 2.3 Add bucket-specific cloud bucket names:
  - `s3_buckets: dict[str, str]` for S3 bucket mapping
  - `supabase_buckets: dict[str, str]` for Supabase bucket mapping

## Phase 3: Integrate Podcast Audio

- [ ] 3.1 Remove `get_output_path()` from `audio_generator_v2.py`
- [ ] 3.2 Update `podcast_creator.py` to use `get_storage(bucket="podcasts")`
- [ ] 3.3 Save audio via `storage.save(audio_bytes, filename, "audio/mpeg")`
- [ ] 3.4 Store storage path (not local path) in `Podcast.audio_url`
- [ ] 3.5 Update `podcast_routes.py` to serve via storage provider

## Phase 4: Add File Serving Endpoint

- [ ] 4.1 Create `GET /api/files/{bucket}/{path:path}` endpoint
- [ ] 4.2 Add `Content-Type` detection via mimetypes
- [ ] 4.3 Add `Accept-Ranges: bytes` header for audio seeking
- [ ] 4.4 Implement HTTP range request support for streaming
- [ ] 4.5 Add caching headers (`Cache-Control`, `ETag`)
- [ ] 4.6 For cloud storage, redirect to signed URL

## Phase 5: Testing

- [ ] 5.1 Update existing image storage tests
- [ ] 5.2 Add tests for bucket configuration
- [ ] 5.3 Add tests for podcast storage integration
- [ ] 5.4 Add tests for file serving endpoint
- [ ] 5.5 Add integration test for audio streaming with range requests

## Phase 6: Documentation

- [ ] 6.1 Update CLAUDE.md with unified storage docs
- [ ] 6.2 Update docs/SETUP.md storage configuration section
- [ ] 6.3 Add migration notes (existing files continue working)
