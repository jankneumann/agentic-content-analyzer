# Implementation Tasks

## 1. Backend: Save Page API Endpoint

**Modifies**: `src/api/save_routes.py`
**Dependencies**: None (can run in parallel with Task 2)

- [ ] 1.1 Add `SavePageRequest` Pydantic model: `url` (HttpUrl, required), `html` (str, required, max 5 MB), `title` (str, optional, max 1000), `excerpt` (str, optional, max 5000), `tags` (list[str], optional, max 20), `notes` (str, optional, max 10000), `source` (str, optional)
- [ ] 1.2 Add `SavePageResponse` model (content_id, status, message, duplicate) — same shape as existing `SaveURLResponse`
- [ ] 1.3 Implement `POST /api/v1/content/save-page` endpoint in `save_routes.py`
- [ ] 1.4 Add duplicate detection by URL (same logic as `save-url`)
- [ ] 1.5 Create Content record with `source_type=WEBPAGE` and `metadata_json={"capture_method": "client_html"}` flag
- [ ] 1.6 Enqueue background processing via `process_client_html()` imported from `html_processor.py`

## 2. Backend: Client HTML Processing Pipeline

**Modifies**: NEW `src/services/html_processor.py`
**Dependencies**: None (can run in parallel with Task 1)

- [ ] 2.1 Create `src/services/html_processor.py` with `process_client_html(content_id: int, html: str, source_url: str)` async function
- [ ] 2.2 Parse client-supplied HTML through trafilatura to produce markdown (call `trafilatura.extract()` with `output_format="markdown"` and `trafilatura.extract_metadata()` for title — same approach as URLExtractor but independent implementation)
- [ ] 2.3 Handle empty/malformed HTML — if trafilatura returns empty markdown, set status=FAILED with descriptive error_message
- [ ] 2.4 Extract images from HTML using `ImageExtractor.extract_from_html(html, base_url=source_url)`
- [ ] 2.5 Download and store images via `ImageExtractor.save_extracted_images()` with `FileStorageProvider`
- [ ] 2.6 Rewrite image URLs in markdown content to point to local storage paths (`/api/v1/files/images/{path}`)
- [ ] 2.7 Update Content record with markdown, content_hash, title (from extraction), `metadata_json["image_count"]`, and status=PARSED
- [ ] 2.8 Handle processing failures — set status=FAILED with error_message

## 3. Extension: DOM Capture and UI

**Modifies**: `extension/popup.js`, `extension/popup.html`
**Dependencies**: None (can run in parallel with Tasks 1 and 2)

- [ ] 3.1 Add `captureDOM()` function using `chrome.scripting.executeScript` to get `document.documentElement.outerHTML`
- [ ] 3.2 Call `captureDOM()` during `init()` alongside existing selected-text capture
- [ ] 3.3 Add capture mode toggle to `popup.html` below the tags input (checkbox: "Capture full page", default: on)
- [ ] 3.4 Store capture preference in `chrome.storage.sync`
- [ ] 3.5 Update `saveUrl()` to POST to `/save-page` when full capture mode is on, or `/save-url` when off
- [ ] 3.6 Handle DOM capture failures gracefully — fall back to URL-only save with user notification
- [ ] 3.7 Add visual indicator showing capture status (e.g., "Full page captured ✓" or "URL only")

## 4a. API Tests for Save Page Endpoint

**Modifies**: `tests/api/test_save_routes.py`
**Dependencies**: Blocked by Task 1

- [ ] 4a.1 API test: `save-page` creates content with HTML payload, returns 201 with content_id
- [ ] 4a.2 API test: `save-page` rejects oversized HTML (>5 MB), returns 413
- [ ] 4a.3 API test: `save-page` rejects missing required fields (url, html), returns 422
- [ ] 4a.4 API test: `save-page` detects duplicate URLs, returns existing content_id with status "exists"

## 4b. Unit Tests for HTML Processor

**Modifies**: `tests/services/test_html_processor.py`
**Dependencies**: Blocked by Task 2

- [ ] 4b.1 Unit test: `process_client_html()` extracts markdown from valid HTML string
- [ ] 4b.2 Unit test: `process_client_html()` sets status=FAILED for empty/malformed HTML (trafilatura returns empty)
- [ ] 4b.3 Unit test: image extraction from client HTML with URL rewriting (mock ImageExtractor)
- [ ] 4b.4 Unit test: graceful handling of image download failures — original URLs preserved, processing continues
- [ ] 4b.5 Unit test: HTML with no images — markdown unchanged, no image extraction attempted
- [ ] 4b.6 Integration test: POST to save-page → call `process_client_html()` synchronously → verify Content status=PARSED, images stored in local storage, markdown has rewritten URLs

## 5. Documentation

**Modifies**: `docs/CONTENT_CAPTURE.md`, `extension/README.md`
**Dependencies**: Blocked by Tasks 1, 2, 3 (needs final API shape and extension behavior)

- [ ] 5.1 Update `docs/CONTENT_CAPTURE.md` with save-page endpoint and capture modes
- [ ] 5.2 Update `extension/README.md` with capture mode documentation
- [ ] 5.3 Update CLAUDE.md if new gotchas discovered
