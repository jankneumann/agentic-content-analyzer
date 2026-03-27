# Change: Add Mobile Content Capture (iOS Focus)

## Status

**Partially implemented** — Core API endpoints, Chrome extension, bookmarklet, and web save page are all live. This proposal covers the **remaining work** to complete the mobile capture experience.

## Why

Users discover interesting content while browsing on their iPhones. The existing `content-capture` spec covers Chrome extensions and bookmarklets, but **iOS has no browser extension support**. Mobile users need:

1. **Native iOS integration** via Share Sheet and Shortcuts app
2. **Rate limiting** on save endpoints to protect against abuse
3. **Mobile-optimized save page** UX audit and improvements
4. **Documentation** for mobile capture workflows

## What's Already Implemented

| Component | Status | Location |
|-----------|--------|----------|
| Save URL API (`POST /save-url`) | Done | `src/api/save_routes.py` |
| Save Page API (`POST /save-page`) | Done | `src/api/save_routes.py` |
| Content Status API (`GET /{id}/status`) | Done | `src/api/save_routes.py` |
| URL Extractor (background) | Done | `src/services/url_extractor.py` |
| HTML Processor (client capture) | Done | `src/services/html_processor.py` |
| Chrome Extension | Done | `extension/` |
| Bookmarklet page | Done | `src/templates/bookmarklet.html` |
| Web save form | Done | `src/templates/save.html` |
| Auth middleware (session + admin key) | Done | `src/api/middleware/auth.py` |
| Frontend save URL hook | Done | `web/src/hooks/use-contents.ts` |
| API tests | Done | `tests/api/test_save_api.py` |
| Shortcuts README | Done | `shortcuts/README.md` |

## What Remains

### 1. Save Endpoint Rate Limiting
- No rate limiter exists on `save-url` or `save-page` endpoints
- Other endpoints (login, share, chat, otel) all have rate limiters
- Need `SaveRateLimiter` following the `EndpointRateLimiter` pattern
- Default: 30 requests/minute per IP (mobile use is bursty but bounded)

### 2. iOS Shortcut Distribution
- Only a README with manual creation steps exists
- Need a downloadable `.shortcut` file or iCloud link
- Need server-rendered installation page at `/api/v1/content/shortcut`
- Shortcut should support: URL capture, optional tags, API key auth

### 3. Mobile Save Page UX
- Current `save.html` template works but needs mobile UX audit
- Touch targets (44px minimum), viewport meta, safe area insets
- Success/error state animations
- "Recent saves" list for quick reference

### 4. Documentation
- Create `docs/MOBILE_CAPTURE.md` comprehensive user guide
- Update `CLAUDE.md` with mobile capture commands
- Update `CONTENT_CAPTURE.md` to cross-reference mobile guide

## Impact

- **Modified code**: `src/api/save_routes.py` (add rate limiter dependency)
- **New code**: `src/api/save_rate_limiter.py`, shortcut installation endpoint
- **New files**: `docs/MOBILE_CAPTURE.md`, updated `src/templates/save.html`
- **Tests**: Rate limiter unit tests, shortcut endpoint tests
- **Dependencies**: None (all infrastructure already exists)

## Related Proposals

- **content-capture** spec — Base capability this extends
- **add-crawl4ai-integration** — Enhanced content extraction (already merged)
- **mobile-reader** spec — PWA for reading captured content

## Architecture Flow

```
iPhone Share Sheet
       |
iOS Shortcut (HTTP POST)
       |
Save URL API (/api/v1/content/save-url)
       |
Rate Limiter (30 req/min per IP) --- 429 if exceeded
       |
Auth Middleware (session cookie OR X-Admin-Key)
       |
Database Provider Factory (auto-detects Supabase/Neon/Local)
       |
PostgreSQL (Content record created with status=PENDING)
       |
Background Task (extract content via Crawl4AI or Trafilatura)
       |
PostgreSQL (Content updated with markdown, status=PARSED)
```

## User Journey

### Capturing from iPhone

1. **Install Shortcut**: User adds pre-built Shortcut via iCloud link or download page
2. **Configure API URL**: Enter their server URL and optional API key
3. **Share Any URL**: From Safari, tap Share -> "Save to Newsletter"
4. **Optional Notes**: Add tags or notes before saving
5. **Confirmation**: Shortcut shows success/failure toast

### Viewing Captured Content

1. Content appears in the web UI under "Recent Content"
2. Status shows: Pending -> Parsing -> Parsed -> Summarized
3. Use mobile-reader PWA for mobile-optimized reading
