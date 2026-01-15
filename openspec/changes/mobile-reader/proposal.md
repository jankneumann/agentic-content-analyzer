# Change: Add Mobile Reader & Audio Playback

## Why

Users want to read summaries and listen to podcast digests on mobile devices. The current web UI is not optimized for mobile. By adding mobile reader support:

1. **Read anywhere**: Mobile-friendly digest and summary views
2. **Listen on the go**: Audio player for podcast digests
3. **Add to home screen**: PWA support for app-like experience
4. **Offline access**: Service worker for cached content (future)

## What's Included

### Mobile-Optimized Templates
- Responsive layouts for content, summaries, digests
- Touch-friendly navigation
- Readable typography without zooming
- Dark mode support

### Audio Player
- Embedded player for podcast digests
- Play/pause, seek, speed controls
- Background playback on mobile
- Progress tracking

### PWA Support
- Web app manifest for "Add to Home Screen"
- App icons and splash screens
- Standalone display mode

## What Changes

- **NEW**: PWA manifest and icons
- **NEW**: Mobile-optimized CSS/layouts
- **NEW**: Audio player component
- **MODIFIED**: Existing templates for responsiveness
- **MODIFIED**: Shared content templates (from `content-sharing`)

## Configuration

```bash
# Optional: Custom app name for PWA
APP_NAME="My Newsletter Digest"
APP_SHORT_NAME="Digests"
```

## Impact

- **New spec**: `mobile-reader` - Mobile UI and PWA
- **New files**:
  - `src/static/manifest.json` - PWA manifest
  - `src/static/icons/` - App icons
  - `src/static/css/mobile.css` - Mobile styles
  - `src/templates/components/audio-player.html` - Player component
- **Modified**:
  - All content templates for responsiveness
  - Base template to include manifest link

## Related Proposals

This is proposal 5 of 5 in the Supabase integration series:

1. **supabase-database** - Database provider abstraction
2. **supabase-storage** - Storage provider for audio/media
3. **content-sharing** - Public share links for content
4. **content-capture** - Chrome extension and bookmarklet
5. **mobile-reader** (this proposal) - PWA and mobile-friendly templates

## Dependencies

- Requires: `content-sharing` (builds on shared content templates)
- Requires: `supabase-storage` (for audio file URLs)
