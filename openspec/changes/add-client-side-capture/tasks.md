# Implementation Tasks

## 1. Backend: Save Page API Endpoint

**Modifies**: `src/api/save_routes.py`
**Dependencies**: None (can run in parallel with Task 2)

- [ ] 1.1 Add `SavePageRequest` Pydantic model (url, title, html, excerpt, tags, notes, source) with 5 MB html field limit
- [ ] 1.2 Add `SavePageResponse` model (content_id, status, message, duplicate, image_count)
- [ ] 1.3 Implement `POST /api/v1/content/save-page` endpoint in `save_routes.py`
- [ ] 1.4 Add duplicate detection by URL (same logic as `save-url`)
- [ ] 1.5 Create Content record with `source_type=WEBPAGE` and `metadata_json={"capture_method": "client_html"}` flag
- [ ] 1.6 Enqueue background processing via `_process_client_html()` imported from `html_processor.py`
- [ ] 1.7 Return `SavePageResponse` with `image_count=0` initially (updated after processing)

## 2. Backend: Client HTML Processing Pipeline

**Modifies**: NEW `src/services/html_processor.py`
**Dependencies**: None (can run in parallel with Task 1)

- [ ] 2.1 Create `src/services/html_processor.py` with `process_client_html(content_id: int, html: str, source_url: str)` async function
- [ ] 2.2 Parse client-supplied HTML through trafilatura to produce markdown (reuse `URLExtractor._parse_html()` pattern)
- [ ] 2.3 Handle empty/malformed HTML — if trafilatura returns empty markdown, set status=FAILED with descriptive error_message
- [ ] 2.4 Extract images from HTML using `ImageExtractor.extract_from_html(html, base_url=source_url)`
- [ ] 2.5 Download and store images via `ImageExtractor.save_extracted_images()` with `FileStorageProvider`
- [ ] 2.6 Rewrite image URLs in markdown content to point to local storage paths (`/api/v1/files/images/{path}`)
- [ ] 2.7 Update Content record with markdown, content_hash, title (from extraction), image count in metadata, and status=PARSED
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
- [ ] 3.7 Add visual indicator showing capture status (e.g., "Full page captured" or "URL only")
- [ ] 3.8 Show image count in success message when available from `save-page` response

## 4. Testing

**Modifies**: `tests/api/`, `tests/services/`
**Dependencies**: Blocked by Tasks 1, 2, 3

- [ ] 4.1 API tests: `save-page` creates content with HTML payload
- [ ] 4.2 API tests: `save-page` rejects oversized HTML (>5 MB)
- [ ] 4.3 API tests: `save-page` detects duplicate URLs
- [ ] 4.4 API tests: `save-page` returns image_count in response
- [ ] 4.5 API tests: `save-page` with empty/malformed HTML results in FAILED status after processing
- [ ] 4.6 Unit tests: `html_processor.process_client_html()` extracts markdown from HTML string
- [ ] 4.7 Unit tests: `html_processor` image extraction from client HTML with URL rewriting
- [ ] 4.8 Unit tests: `html_processor` graceful handling of image download failures
- [ ] 4.9 Unit tests: `html_processor` handles HTML with no images (markdown unchanged)
- [ ] 4.10 Integration test: POST to save-page with HTML containing image tags → verify Content created, background task processes HTML, images stored in local storage, markdown has rewritten URLs

## 5. Documentation

**Modifies**: `docs/CONTENT_CAPTURE.md`, `extension/README.md`
**Dependencies**: Blocked by Tasks 1, 2, 3

- [ ] 5.1 Update `docs/CONTENT_CAPTURE.md` with save-page endpoint and capture modes
- [ ] 5.2 Update `extension/README.md` with capture mode documentation
- [ ] 5.3 Update CLAUDE.md if new gotchas discovered
