# Change: Add Mobile Content Capture (iOS Focus)

## Why

Users discover interesting content while browsing on their iPhones. The existing `content-capture` proposal covers Chrome extensions and bookmarklets, but **iOS has no browser extension support**. Mobile users need:

1. **Native iOS integration** via Share Sheet and Shortcuts app
2. **Cross-device sync** - capture on phone, process on server
3. **Database-agnostic capture** - works with both Supabase and Neon backends

## What's Included

### iOS Shortcuts Integration
- Pre-built Shortcut that calls the Save URL API
- Appears in iOS Share Sheet for any URL
- Supports adding notes/tags during capture
- Works offline (queues URLs for later sync)

### Save URL API Enhancement
- `POST /api/v1/content/save-url` - Queue URL for processing
- Optional API key authentication (for mobile use)
- Rate limiting per API key
- Returns content ID for status polling

### Web Capture Page (Mobile-Optimized)
- `GET /save` - Mobile-friendly save form
- Pre-fills from URL parameters (for bookmarklet/shortcut)
- Touch-optimized UI (44px tap targets)
- Works as fallback for any mobile browser

## Database Backend Considerations

### How Capture Works with Supabase vs Neon

Both backends are PostgreSQL, so the **Content model and API are identical**. The difference is in **operational characteristics**:

| Aspect | Supabase | Neon |
|--------|----------|------|
| **Connection** | Pooled via Supavisor | Pooled via `-pooler` endpoint |
| **Cold Start** | Always warm (dedicated compute) | May have 2-5s wake time (scale-to-zero) |
| **Best For** | Production with consistent traffic | Development, CI, cost-sensitive workloads |
| **Mobile Capture** | Instant response | First capture may be slower |

### Architecture Flow

```
iPhone Share Sheet
       ↓
iOS Shortcut (HTTP POST)
       ↓
Save URL API (/api/v1/content/save-url)
       ↓
Database Provider Factory (auto-detects Supabase/Neon/Local)
       ↓
PostgreSQL (Content record created with status=PENDING)
       ↓
Background Task (extract content via Crawl4AI or existing parsers)
       ↓
PostgreSQL (Content updated with markdown, status=PARSED)
```

The **same API endpoint** works regardless of database backend. The provider abstraction (`src/database/providers/`) handles connection pooling and SSL configuration per-provider.

## What Changes

- **ENHANCED**: `content-capture` spec to include iOS Shortcuts
- **NEW**: iOS Shortcut file (.shortcut) for distribution
- **NEW**: Mobile-optimized save page template
- **NEW**: Optional API key authentication for mobile clients
- **MODIFIED**: Save URL endpoint with rate limiting

## Impact

- **Affected specs**: `content-capture` (enhanced)
- **New code**:
  - `shortcuts/Save to Newsletter.shortcut` - iOS Shortcut
  - `src/templates/save_mobile.html` - Mobile save page
  - `src/api/auth/api_keys.py` - Simple API key auth (optional)
- **Dependencies**: None (uses existing database provider abstraction)

## Related Proposals

- **content-capture** - Base Chrome extension/bookmarklet (this extends it)
- **add-crawl4ai-integration** - Enhanced content extraction
- **add-user-authentication** - Full auth system (this uses lightweight API keys)
- **mobile-reader** - PWA for reading captured content

## User Journey

### Capturing from iPhone

1. **Install Shortcut**: User adds pre-built Shortcut to their device
2. **Configure API URL**: Enter their server URL and optional API key
3. **Share Any URL**: From Safari, tap Share → "Save to Newsletter"
4. **Optional Notes**: Add tags or notes before saving
5. **Confirmation**: Shortcut shows success/failure toast

### Viewing Captured Content

1. Content appears in the web UI under "Recent Content"
2. Status shows: Pending → Parsing → Parsed → Summarized
3. Use `mobile-reader` PWA for mobile-optimized reading
