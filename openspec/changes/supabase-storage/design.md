# Design: Supabase Storage Support

## Context

Audio files (podcasts, TTS output) are currently stored locally. This limits mobile access and sharing capabilities. We need a storage abstraction that supports both local development and cloud deployment.

## Goals

1. Abstract file storage behind a provider interface
2. Support Supabase Storage for cloud deployments
3. Maintain local storage for development
4. Enable public URLs for shared audio content

## Non-Goals

1. S3 support (can be added later following same pattern)
2. Image optimization or processing
3. Video storage

## Decisions

### Decision 1: Storage Provider Protocol

**What**: Create a `StorageProvider` protocol for file operations.

```python
class StorageProvider(Protocol):
    @property
    def name(self) -> str: ...

    def upload(
        self,
        path: str,
        data: bytes,
        content_type: str,
        public: bool = False
    ) -> str:
        """Upload file, return URL."""
        ...

    def get_url(self, path: str, expires_in: int | None = None) -> str:
        """Get URL. If expires_in is None, return permanent URL."""
        ...

    def delete(self, path: str) -> bool: ...
    def exists(self, path: str) -> bool: ...
```

### Decision 2: Local Storage Implementation

**What**: Store files in configurable directory, serve via FastAPI.

```python
class LocalStorageProvider:
    def __init__(self, base_path: str, base_url: str):
        self.base_path = Path(base_path)
        self.base_url = base_url  # e.g., "/api/files"

    def upload(self, path: str, data: bytes, ...) -> str:
        file_path = self.base_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        return f"{self.base_url}/{path}"
```

### Decision 3: Supabase Storage Implementation

**What**: Use `supabase-py` SDK for storage operations.

```python
from supabase import create_client

class SupabaseStorageProvider:
    def __init__(self, url: str, key: str, bucket: str):
        self.client = create_client(url, key)
        self.bucket = bucket

    def upload(self, path: str, data: bytes, content_type: str, public: bool) -> str:
        self.client.storage.from_(self.bucket).upload(
            path, data, {"content-type": content_type}
        )
        if public:
            return self.client.storage.from_(self.bucket).get_public_url(path)
        return self.get_url(path, expires_in=3600)
```

### Decision 4: File Serving Endpoint

**What**: Add FastAPI endpoint for serving local files with proper headers.

```python
@router.get("/api/files/{path:path}")
async def serve_file(path: str):
    file_path = settings.storage_path / path
    if not file_path.exists():
        raise HTTPException(404)
    return FileResponse(
        file_path,
        media_type=mimetypes.guess_type(path)[0],
        headers={"Accept-Ranges": "bytes"}
    )
```

### Decision 5: Audio URL Storage

**What**: Store full URLs (not paths) in database for audio files.

**Why**: Enables seamless switching between providers without data migration.

```python
# Before: local path
audio_path = "data/podcasts/digest-123.mp3"

# After: full URL
audio_url = "https://xxx.supabase.co/storage/v1/object/public/audio/digest-123.mp3"
# or
audio_url = "/api/files/podcasts/digest-123.mp3"
```

## File Structure

```
src/storage/
├── file_providers/
│   ├── __init__.py
│   ├── base.py                 # StorageProvider protocol
│   ├── local.py                # LocalStorageProvider
│   ├── supabase_storage.py     # SupabaseStorageProvider
│   └── factory.py              # get_storage_provider()
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Supabase storage limits (1GB free) | Document limits, audio is small (~1MB/10min) |
| Bandwidth costs | Use public bucket for shared content, signed URLs for private |
| Migration of existing files | Support both local paths and URLs in audio_url field |
