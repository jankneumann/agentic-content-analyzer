# Implementation Tasks

## 1. Create Storage Provider Module

- [ ] 1.1 Create `src/storage/file_providers/__init__.py` with exports
- [ ] 1.2 Create `src/storage/file_providers/base.py` with `StorageProvider` protocol
- [ ] 1.3 Create `src/storage/file_providers/local.py` for local filesystem
- [ ] 1.4 Create `src/storage/file_providers/supabase_storage.py` for Supabase
- [ ] 1.5 Create `src/storage/file_providers/factory.py` with provider factory

## 2. Update Configuration

- [ ] 2.1 Add storage settings to `src/config/settings.py`:
  - `storage_provider: Literal["local", "supabase"] = "local"`
  - `storage_path: str = "data/uploads"`
  - `supabase_storage_bucket: str = "audio-files"`
- [ ] 2.2 Add `supabase_url` and `supabase_anon_key` if not already present
- [ ] 2.3 Add `get_storage_provider()` helper method

## 3. Add File Serving Endpoint

- [ ] 3.1 Create `GET /api/files/{path:path}` endpoint
- [ ] 3.2 Add proper `Content-Type` detection via mimetypes
- [ ] 3.3 Add `Accept-Ranges: bytes` header for audio seeking
- [ ] 3.4 Add range request support for streaming
- [ ] 3.5 Add caching headers (`Cache-Control`, `ETag`)

## 4. Integrate with TTS/Podcast Generation

- [ ] 4.1 Update `src/tts/` to use storage provider for uploads
- [ ] 4.2 Update audio URL generation in podcast service
- [ ] 4.3 Handle both local paths and full URLs in existing records
- [ ] 4.4 Add audio URL field to relevant Pydantic schemas

## 5. Add Dependencies

- [ ] 5.1 Add `supabase` to pyproject.toml dependencies
- [ ] 5.2 Update requirements documentation

## 6. Testing

- [ ] 6.1 Unit tests for storage provider factory
- [ ] 6.2 Unit tests for local storage operations
- [ ] 6.3 Unit tests for Supabase storage (mocked)
- [ ] 6.4 Integration test for file upload/download flow
- [ ] 6.5 Test audio streaming with range requests

## 7. Documentation

- [ ] 7.1 Document storage provider configuration
- [ ] 7.2 Add Supabase Storage setup instructions
- [ ] 7.3 Document bucket creation and permissions
