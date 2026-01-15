# Change: Add Content Sharing

## Why

Users want to share interesting content, summaries, digests, and audio with others. Currently there's no way to generate a shareable link. By adding content sharing:

1. **Easy sharing**: One-click generation of shareable links
2. **No auth required**: Recipients view content without signing up
3. **Audio included**: Share podcast versions of digests
4. **Social-friendly**: Open Graph tags for rich previews

## Sharing Model

Following the "unlisted" pattern (like YouTube unlisted videos):
- Content is not public by default
- User generates a share token (UUID4)
- Anyone with the link can view
- User can revoke sharing anytime

```
/shared/content/{token}  → View article
/shared/summary/{token}  → View summary
/shared/digest/{token}   → View digest with audio player
/shared/audio/{token}    → Stream/download audio
```

## What Changes

- **NEW**: `is_public` and `share_token` fields on Content, Summary, Digest models
- **NEW**: Share API endpoints: `POST/GET/DELETE /api/v1/{type}/{id}/share`
- **NEW**: Public endpoints: `GET /shared/{type}/{token}`
- **NEW**: Mobile-friendly HTML templates for shared content
- **NEW**: Rate limiting on public endpoints
- **MODIFIED**: Alembic migration for new fields

## Configuration

No new configuration required. Sharing works with both local and Supabase deployments.

## Impact

- **New spec**: `content-sharing` - Public share links
- **Affected code**:
  - `src/models/` - Add sharing fields
  - `src/api/shared_routes.py` - Public endpoints
  - `src/api/*_routes.py` - Share management endpoints
  - `src/templates/` - Shared content templates
- **Dependencies**: `supabase-storage` (for audio URLs)
- **Migration**: Alembic migration adding `is_public`, `share_token` columns

## Related Proposals

This is proposal 3 of 5 in the Supabase integration series:

1. **supabase-database** - Database provider abstraction
2. **supabase-storage** - Storage provider for audio/media
3. **content-sharing** (this proposal) - Public share links
4. **content-capture** - Chrome extension and bookmarklet
5. **mobile-reader** - PWA and mobile-friendly templates

## Dependencies

- Requires: `supabase-storage` (for audio file URLs in shared content)
- Required by: `mobile-reader` (uses shared content templates)
