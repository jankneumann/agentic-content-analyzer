# Implementation Tasks

## 1. Create Chrome Extension

- [ ] 1.1 Create `extension/manifest.json` (Manifest V3)
- [ ] 1.2 Create `extension/popup.html` with save UI
- [ ] 1.3 Create `extension/popup.js` with save logic
- [ ] 1.4 Create `extension/options.html` for configuration
- [ ] 1.5 Create `extension/options.js` for config storage
- [ ] 1.6 Create extension icons (16, 48, 128px)
- [ ] 1.7 Add `extension/README.md` with installation instructions

## 2. Extension Features

- [ ] 2.1 Implement one-click save current page
- [ ] 2.2 Implement capture selected text as excerpt
- [ ] 2.3 Add save status feedback (success/error)
- [ ] 2.4 Add loading indicator during save
- [ ] 2.5 Handle API errors with user-friendly messages
- [ ] 2.6 Store configuration in chrome.storage.sync

## 3. Create Bookmarklet

- [ ] 3.1 Create `bookmarklet/bookmarklet.js`
- [ ] 3.2 Minify bookmarklet code
- [ ] 3.3 Create bookmarklet generator page in web UI
- [ ] 3.4 Add drag-and-drop installation instructions

## 4. Save URL API

- [ ] 4.1 Create `src/api/save_routes.py`
- [ ] 4.2 Implement `POST /api/v1/content/save-url`
- [ ] 4.3 Add URL validation
- [ ] 4.4 Add duplicate detection by URL
- [ ] 4.5 Implement `GET /api/v1/content/{id}/status`
- [ ] 4.6 Configure CORS for extension

## 5. URL Content Extraction

- [ ] 5.1 Create `src/services/url_extractor.py`
- [ ] 5.2 Integrate with existing `ParserRouter`
- [ ] 5.3 Add Readability-style extraction for articles
- [ ] 5.4 Handle extraction failures gracefully
- [ ] 5.5 Add timeout handling for slow sites
- [ ] 5.6 Respect rate limiting (add delays)

## 6. Bookmarklet Save Page

- [ ] 6.1 Create `GET /save` endpoint
- [ ] 6.2 Create `src/templates/save.html` template
- [ ] 6.3 Pre-fill form with URL params
- [ ] 6.4 Add save button that calls API
- [ ] 6.5 Show success/redirect after save

## 7. Testing

- [ ] 7.1 Manual extension testing in Chrome
- [ ] 7.2 API tests for save-url endpoint
- [ ] 7.3 Test duplicate URL detection
- [ ] 7.4 Test extraction for various page types
- [ ] 7.5 Test bookmarklet in multiple browsers

## 8. Documentation

- [ ] 8.1 Document extension installation (load unpacked)
- [ ] 8.2 Document bookmarklet setup
- [ ] 8.3 Document configuration options
- [ ] 8.4 Add troubleshooting guide
