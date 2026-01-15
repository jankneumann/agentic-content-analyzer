# Change: Add Content Capture (Extension & Bookmarklet)

## Why

Users discover interesting content while browsing the web. Currently, they must manually copy URLs and use the app's ingestion features. By adding content capture tools:

1. **One-click saving**: Save any webpage with a single click
2. **Cross-browser**: Chrome extension + universal bookmarklet
3. **Highlight support**: Save selected text as excerpt
4. **Seamless pipeline**: Captured content flows through existing processing

## What's Included

### Chrome Extension
- One-click save from toolbar
- Capture selected text as highlight/excerpt
- Configuration page for API URL and credentials
- Save status feedback

### Universal Bookmarklet
- Works on any browser (Safari, Firefox, mobile browsers)
- Drag-and-drop installation
- Opens save page with pre-filled URL

### Save URL API
- `POST /api/v1/content/save-url` - Queue URL for processing
- Duplicate detection by URL
- Background content extraction
- Status polling endpoint

## What Changes

- **NEW**: `extension/` directory with Chrome extension
- **NEW**: `bookmarklet/` with bookmarklet code
- **NEW**: Save URL API endpoint
- **NEW**: URL content extraction service
- **MODIFIED**: Content ingestion to support URL source

## Configuration

The extension/bookmarklet connects to user's own instance:
```javascript
// Extension config (stored in chrome.storage)
{
  "apiUrl": "https://your-app.example.com",
  "apiKey": "your-supabase-anon-key"  // or custom API key
}
```

## Impact

- **New spec**: `content-capture` - Extension and save API
- **New code**:
  - `extension/` - Chrome extension
  - `bookmarklet/` - Bookmarklet generator
  - `src/api/` - Save URL endpoint
  - `src/services/url_extractor.py` - Content extraction
- **Dependencies**: None (works with local or Supabase)

## Related Proposals

This is proposal 4 of 5 in the Supabase integration series:

1. **supabase-database** - Database provider abstraction
2. **supabase-storage** - Storage provider for audio/media
3. **content-sharing** - Public share links for content
4. **content-capture** (this proposal) - Chrome extension and bookmarklet
5. **mobile-reader** - PWA and mobile-friendly templates

## Dependencies

- None (standalone feature)
- Enhanced by: `content-sharing` (share captured content)
