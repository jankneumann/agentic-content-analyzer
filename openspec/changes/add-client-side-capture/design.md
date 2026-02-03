# Design: Client-Side DOM Capture

## Context

The Chrome extension currently sends only URL metadata to `POST /api/v1/content/save-url`, which triggers server-side fetching. This fails for authenticated/paywall content because the server has no browser session. The extension already has `activeTab` + `scripting` permissions, which allow capturing the rendered DOM.

## Goals

1. Capture the full rendered DOM from the extension and send it to the backend
2. Extract and store images from captured pages using existing infrastructure
3. Rewrite image references in stored markdown to point to local storage
4. Keep backward compatibility — URL-only save and bookmarklet continue to work

## Non-Goals

1. Sending images inline from the extension (too large, slow uploads)
2. Capturing CSS, fonts, or full-page screenshots
3. Capturing content from pages the user doesn't have access to
4. Offline capture or queuing (requires service worker, future scope)
5. Storing raw HTML for archival (see Decision 6)

## Decisions

### Decision 1: Extension captures outerHTML, server downloads images

**What**: The extension captures `document.documentElement.outerHTML` and sends it as a string. The server extracts image URLs from the HTML, downloads them server-side, and stores them.

**Why**: This keeps the upload payload small (HTML is typically 50-500 KB) while still capturing all content the user sees. Images are downloaded server-side because:
- The extension popup has limited lifetime (closes on blur)
- Downloading images in the extension would require background service worker
- Server-side download is simpler and more reliable
- Existing `ImageExtractor.extract_from_html()` already handles this flow

**Trade-off**: Server-side image download may fail for images behind auth. This is acceptable because most article images are served from CDNs without auth. For auth-gated images, the markdown content itself (the primary value) is still captured.

### Decision 2: New endpoint `POST /api/v1/content/save-page` alongside existing `save-url`

**What**: Add a new endpoint rather than modifying the existing one.

**Why**:
- Different payload shape (HTML body vs. URL-only)
- Different processing flow (parse HTML directly vs. fetch-then-parse)
- Bookmarklet and non-extension clients continue using `save-url` unchanged
- Clear separation of concerns

**Alternative considered**: Adding an optional `html` field to `save-url`. Rejected because it muddies the endpoint semantics — callers wouldn't know which processing path would be taken.

```python
# New endpoint
POST /api/v1/content/save-page
Body: {
  "url": "https://...",           # Source URL (for dedup + metadata)
  "title": "...",                 # Page title
  "html": "<html>...</html>",    # Rendered DOM from extension
  "excerpt": "...",               # Optional selected text
  "tags": [...],                  # Optional tags
  "source": "chrome_extension"    # Capture source
}
Response: { "content_id": 123, "status": "queued", "message": "Content queued for processing", "duplicate": false }
```

### Decision 3: Capture mode toggle in extension popup

**What**: Add a checkbox in the popup for "Capture full page" (default: on). Persisted via `chrome.storage.sync`.

**Why**: Users may sometimes want URL-only save (faster, smaller payload) — e.g., for YouTube videos or pages where server-side extraction works fine. The toggle gives control without removing the original flow.

**Default**: Full page capture ON — this is the primary value proposition.

**Alternative considered**: Adding a default setting to `options.html`. Rejected to keep scope minimal — the popup toggle with `chrome.storage.sync` persistence is sufficient. The setting persists across popup opens, achieving the same goal without a second configuration surface.

### Decision 4: Parse HTML with trafilatura, extract images with ImageExtractor

**What**: Reuse existing infrastructure rather than building new parsers.

**Why**:
- `trafilatura.extract(html, output_format="markdown")` already accepts raw HTML strings
- `ImageExtractor.extract_from_html(html, base_url)` already extracts `<img>` tags and data URIs
- `ImageExtractor.save_extracted_images()` already handles storage and DB records
- `FileStorageProvider` already supports local/S3/Supabase/Railway

**Flow**:
```
Extension captures outerHTML
  → POST /api/v1/content/save-page
  → Create Content record (status=PENDING)
  → Background task (html_processor.process_client_html):
    1. Parse HTML → markdown (trafilatura)
    2. If markdown is empty → status=FAILED, error_message
    3. Extract images from HTML (ImageExtractor)
    4. Download images server-side (ImageExtractor)
    5. Store images (FileStorageProvider → "images" bucket)
    6. Rewrite markdown image refs → storage URLs
    7. Update Content record (status=PARSED)
```

### Decision 5: Image reference rewriting

**What**: After extracting and storing images, replace the original image URLs in the markdown with local storage paths.

**Why**: Ensures images persist even if the source page removes them. Uses the existing file serving endpoint `GET /api/v1/files/images/{path}`.

**How**: After `ImageExtractor.save_extracted_images()` returns `ImageCreate` objects with `storage_path`, iterate markdown content and replace each original URL with the corresponding storage URL. For images that failed to download, the original URL is preserved unchanged.

### Decision 6: Metadata flag instead of raw HTML storage

**What**: Store `{"capture_method": "client_html"}` in `metadata_json` instead of the full raw HTML.

**Why**: Storing up to 5 MB of HTML in a PostgreSQL JSONB column is a performance anti-pattern — JSONB must parse and store the entire value, and large JSONB values degrade query performance for all rows in the Content table.

**Alternative considered**: Storing raw HTML in FileStorageProvider and referencing the path in metadata. Rejected for now — the primary value is the extracted markdown, not the raw HTML. If HTML archival becomes needed, it can be added as a follow-up without schema changes (just add an `html_storage_path` key to metadata).

### Decision 7: Separate processing module (`html_processor.py`)

**What**: Create `src/services/html_processor.py` for the client HTML processing pipeline instead of adding it to `save_routes.py` or `url_extractor.py`.

**Why**:
- `save_routes.py` is the API layer — should dispatch to services, not contain processing logic
- `url_extractor.py` is focused on URL fetching + parsing — adding an HTML-input path would conflate two different ingestion strategies
- A separate module enables parallel implementation (API endpoint and processing logic can be developed independently)
- Cleaner testability — `html_processor` can be unit-tested without API overhead

**Alternative considered**: Adding an `extract_from_html(html, url)` method to `URLExtractor`. Rejected because it would make `URLExtractor` responsible for two unrelated concerns (fetching URLs and processing pre-fetched HTML).

## Concurrency and Race Conditions

**Concurrent duplicate submissions**: If two `save-page` requests arrive simultaneously with the same URL, the existing `UNIQUE (source_type, source_id)` database constraint prevents duplicate Content records. The second insert will fail with an IntegrityError, which the endpoint handles by returning the existing content ID — the same pattern used by `save-url`.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Large HTML payloads (>5 MB) | Enforce 5 MB limit server-side; reject with 413 |
| Extension popup closes during save | Show progress, but save is async — once POST returns, processing continues server-side |
| Some images behind auth fail to download | Graceful fallback — keep original URL in markdown, log warning |
| CORS for large POST from extension | Extension fetch() to own configured API URL is not subject to CORS |
| Rate limiting for expensive capture | Reuse existing rate limiting; full-page capture is ~1 req/click |
| Empty/malformed HTML from extension | Processing sets status=FAILED with descriptive error; user sees failure via status poll |
| Concurrent duplicate URL submissions | Handled by existing DB unique constraint on (source_type, source_id) |
