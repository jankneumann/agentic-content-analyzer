## Context

The codebase has image storage with provider abstraction but podcast audio
writes directly to local disk. This blocks cloud deployment for audio content.

## Goals

- Unified storage abstraction for all file types
- Multi-bucket support for content type separation
- Cloud-ready audio/podcast delivery
- Backward compatibility with existing image paths

## Non-Goals

- Direct digest-to-audio generation (separate proposal: `add-audio-digest-generation`)
- Video storage support
- CDN integration (future work)

## Decisions

### Decision 1: Rename vs. Create New

**Choice**: Rename existing image storage classes
**Rationale**: The image storage implementation is solid and complete.
Renaming preserves the code and avoids duplication.

### Decision 2: Bucket Configuration

**Choice**: Settings-based bucket→provider mapping

```python
# settings.py
storage_buckets = {
    "images": "local",      # or "s3", "supabase"
    "podcasts": "supabase",
    "audio-digests": "local"
}
```

**Rationale**: Allows different providers per content type without code changes.

### Decision 3: File Serving Strategy

**Choice**:
- Local: Serve via FastAPI with range request support
- Cloud: Redirect to signed URL (let CDN handle streaming)

**Rationale**: Leverages cloud CDN for performance, keeps local dev simple.

## Risks / Trade-offs

- **Risk**: Breaking existing image extraction
  - Mitigation: Keep `get_image_storage()` as alias during transition

- **Risk**: Large audio files in memory
  - Mitigation: Use streaming upload/download for files >10MB

## Migration Plan

1. Phase 1-2: Refactor with backward-compatible aliases
2. Phase 3-4: Integrate podcasts
3. Phase 5-6: Test and document
4. Remove deprecated aliases after one release cycle
