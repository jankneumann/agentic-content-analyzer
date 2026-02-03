# Change: Add Client-Side DOM Capture for Paywall & Image Support

## Why

The current content capture flow sends only the URL to the server, which fetches the page anonymously. This fails for:

1. **Paywall-gated content** — the server has no auth cookies, so paid articles return login walls
2. **Login-required content** — private dashboards, internal tools, authenticated feeds
3. **JS-rendered SPAs** — server-side fetch gets empty shells
4. **Images** — currently ignored entirely; no images are extracted or stored from captured pages

The Chrome extension already has access to the fully rendered, authenticated DOM. By capturing and sending the rendered HTML from the browser, we get exactly what the user sees — including content they've paid for.

## What Changes

- **MODIFIED**: Chrome extension captures rendered DOM (`document.documentElement.outerHTML`) in addition to URL/title/excerpt
- **NEW**: `POST /api/v1/content/save-page` API endpoint accepting HTML content + metadata
- **NEW**: `src/services/html_processor.py` module parses client-supplied HTML through trafilatura, extracts images via `ImageExtractor`, stores images via `FileStorageProvider`, and rewrites markdown image references to local storage URLs
- **MODIFIED**: Extension popup adds a "Capture full page" toggle (URL-only vs. full page capture)
- **UNCHANGED**: Existing `POST /api/v1/content/save-url` remains for bookmarklet and non-extension clients
- **UNCHANGED**: Server-side URL fetch remains as fallback
- **UNCHANGED**: `src/services/url_extractor.py` is not modified (HTML processing is a separate pipeline)

## Design Constraints

- HTML payload limit: 5 MB (covers 99%+ of web pages without embedded data URIs)
- Image download: server-side from URLs extracted from the HTML (not sent inline from extension)
- Image size limit: 5 MB per image, 20 images max per page (matches existing `ImageExtractor` defaults)
- No new extension permissions required — `activeTab` + `scripting` already allow DOM capture

## Impact

- **Modified spec**: `content-capture` — new endpoint, modified extension behavior
- **Modified code**:
  - `extension/popup.js` — DOM capture logic, capture mode toggle
  - `extension/popup.html` — capture mode UI
  - `src/api/save_routes.py` — new `save-page` endpoint
- **New code**:
  - `src/services/html_processor.py` — client HTML processing pipeline (uses existing `ImageExtractor` + `FileStorageProvider`)
- **Dependencies**: None new (uses existing trafilatura, ImageExtractor, FileStorageProvider)
