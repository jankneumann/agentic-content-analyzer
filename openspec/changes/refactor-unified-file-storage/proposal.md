# Change: Refactor to Unified File Storage with Multi-Bucket Support

## Why

The codebase has two separate storage patterns:
1. Image storage with full provider abstraction (Local, S3, Supabase)
2. Podcast audio with hardcoded local filesystem writes

This creates maintenance burden and blocks podcast audio from cloud deployment.
A unified storage system enables:
- Single abstraction for all file types
- Configurable buckets per content type
- Cloud-ready podcast/audio delivery
- Mobile-accessible audio URLs

## What Changes

- **REFACTOR**: Rename `ImageStorageProvider` → `FileStorageProvider`
- **REFACTOR**: Rename `src/services/image_storage.py` → `src/services/file_storage.py`
- **NEW**: Multi-bucket support via `get_storage(bucket="podcasts")`
- **NEW**: File serving endpoint `GET /api/files/{bucket}/{path:path}`
- **MODIFIED**: Podcast creator uses storage provider instead of local paths
- **NEW**: Settings for bucket-to-provider mapping

## Impact

- **Affected specs**: Creates new `file-storage` capability
- **Affected code**:
  - `src/services/image_storage.py` → `src/services/file_storage.py`
  - `src/services/image_extractor.py` - Update imports
  - `src/processors/podcast_creator.py` - Use storage provider
  - `src/delivery/audio_generator_v2.py` - Remove `get_output_path()`
  - `src/api/podcast_routes.py` - Update file serving
  - `src/config/settings.py` - Add bucket configuration
- **Breaking changes**: None (existing image paths remain compatible)
- **Migration**: Existing local files continue working
