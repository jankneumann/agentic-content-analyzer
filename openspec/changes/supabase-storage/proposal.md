# Change: Add Supabase Storage Support

## Why

The current implementation stores audio files (podcasts, TTS output) locally at `data/podcasts/`. This creates problems for:

1. **Mobile access**: Local files can't be served to mobile devices without complex setup
2. **Sharing**: Can't generate public URLs for shared audio content
3. **Scalability**: Local storage doesn't scale for cloud deployments
4. **CDN delivery**: No fast, global delivery for audio streaming

By adding Supabase Storage as a cloud option:

1. **Mobile-ready audio**: Files accessible from any device via HTTPS
2. **Shareable links**: Public URLs for shared content (see `content-sharing` proposal)
3. **CDN-backed**: Supabase provides global CDN for fast delivery
4. **Free tier**: 1GB storage, 2GB bandwidth/month on free plan

## What Changes

- **NEW**: Storage provider abstraction in `src/storage/file_providers/`
- **NEW**: Supabase Storage provider using `supabase-py` SDK
- **NEW**: Local storage provider with FastAPI file serving
- **NEW**: API endpoint for serving local files: `GET /api/files/{path}`
- **MODIFIED**: TTS generation to use storage provider
- **MODIFIED**: `src/config/settings.py` for storage configuration
- **MODIFIED**: Audio URL handling in digest/podcast models

## Configuration Examples

**Local Storage (unchanged default)**:
```bash
STORAGE_PROVIDER=local
STORAGE_PATH=data/uploads
```

**Supabase Storage**:
```bash
STORAGE_PROVIDER=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_STORAGE_BUCKET=audio-files
```

## Impact

- **New spec**: `storage-provider` - File storage abstraction
- **Affected code**:
  - `src/storage/file_providers/` - New provider implementations
  - `src/config/settings.py` - Storage settings
  - `src/tts/` - Use storage provider for uploads
  - `src/api/` - File serving endpoint
- **Dependencies**: `supabase-database` proposal (shares Supabase config)
- **Migration**: None required (existing local files continue working)

## Related Proposals

This is proposal 2 of 5 in the Supabase integration series:

1. **supabase-database** - Database provider abstraction
2. **supabase-storage** (this proposal) - Storage provider for audio/media
3. **content-sharing** - Public share links for content
4. **content-capture** - Chrome extension and bookmarklet
5. **mobile-reader** - PWA and mobile-friendly templates

## Dependencies

- Requires: `supabase-database` (for shared Supabase configuration)
- Required by: `content-sharing` (for audio sharing URLs)
