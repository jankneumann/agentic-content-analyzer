# Implementation Tasks

## Phase 1: Database Provider Abstraction

### 1.1 Create Provider Module
- [ ] Create `src/storage/providers/__init__.py` with provider exports
- [ ] Create `src/storage/providers/base.py` with `DatabaseProvider` protocol
- [ ] Create `src/storage/providers/local.py` for local PostgreSQL provider
- [ ] Create `src/storage/providers/supabase.py` for Supabase provider
- [ ] Create `src/storage/providers/factory.py` with provider detection and factory

### 1.2 Update Configuration
- [ ] Add Supabase database settings to `src/config/settings.py`:
  - `supabase_project_ref: str | None`
  - `supabase_db_password: str | None`
  - `supabase_region: str = "us-east-1"`
  - `supabase_pooler_mode: Literal["transaction", "session"] = "transaction"`
  - `database_provider: Literal["local", "supabase"] | None` (explicit override)
- [ ] Add `get_database_url()` method to construct URLs from Supabase config
- [ ] Add provider auto-detection logic

### 1.3 Refactor Database Module
- [ ] Update `src/storage/database.py` to use provider factory
- [ ] Configure engine with provider-specific options (pool size, SSL, timeouts)
- [ ] Add connection health check endpoint
- [ ] Handle Supabase-specific connection errors gracefully

### 1.4 Testing
- [ ] Create unit tests for provider factory detection logic
- [ ] Create unit tests for Supabase URL construction
- [ ] Create integration test fixtures with mock Supabase config
- [ ] Test local PostgreSQL still works (regression)

---

## Phase 2: Storage Provider Abstraction

### 2.1 Create Storage Provider Module
- [ ] Create `src/storage/file_providers/__init__.py` with exports
- [ ] Create `src/storage/file_providers/base.py` with `StorageProvider` protocol
- [ ] Create `src/storage/file_providers/local.py` for local filesystem
- [ ] Create `src/storage/file_providers/supabase_storage.py` for Supabase Storage
- [ ] Create `src/storage/file_providers/factory.py` with provider factory

### 2.2 Update Configuration
- [ ] Add storage settings to `src/config/settings.py`:
  - `storage_provider: Literal["local", "supabase"] = "local"`
  - `storage_path: str = "data/uploads"`
  - `supabase_url: str | None`
  - `supabase_anon_key: str | None`
  - `supabase_storage_bucket: str = "audio-files"`

### 2.3 Add File Serving Endpoint
- [ ] Create `GET /api/files/{path:path}` endpoint for local file serving
- [ ] Add proper `Content-Type` detection
- [ ] Add range request support for audio streaming
- [ ] Add caching headers

### 2.4 Integrate with TTS/Podcast Generation
- [ ] Update `src/tts/` to use storage provider for audio uploads
- [ ] Update audio URL generation in digest/podcast models
- [ ] Handle both local paths and cloud URLs in existing records

### 2.5 Testing
- [ ] Unit tests for storage provider factory
- [ ] Unit tests for local storage operations
- [ ] Integration tests with Supabase Storage (mock or real)
- [ ] Test audio file upload and retrieval flow

---

## Phase 3: Content Sharing

### 3.1 Database Schema Changes
- [ ] Create Alembic migration adding to `contents` table:
  - `is_public: Boolean = False`
  - `share_token: String(36), nullable, unique index`
- [ ] Create Alembic migration adding same fields to `newsletter_summaries`
- [ ] Create Alembic migration adding same fields to `digests`
- [ ] Run migrations and test rollback

### 3.2 Update Models
- [ ] Add sharing fields to `Content` model
- [ ] Add sharing fields to `NewsletterSummary` model
- [ ] Add sharing fields to `Digest` model
- [ ] Add Pydantic schemas for share requests/responses

### 3.3 Share API Endpoints
- [ ] Create `POST /api/v1/content/{id}/share` - enable sharing
- [ ] Create `GET /api/v1/content/{id}/share` - get share status
- [ ] Create `DELETE /api/v1/content/{id}/share` - disable sharing
- [ ] Duplicate endpoints for summaries and digests

### 3.4 Public Share Endpoints
- [ ] Create `src/api/shared_routes.py` for public endpoints
- [ ] Implement `GET /shared/content/{token}` with HTML/JSON response
- [ ] Implement `GET /shared/summary/{token}`
- [ ] Implement `GET /shared/digest/{token}`
- [ ] Implement `GET /shared/audio/{token}` with redirect/streaming

### 3.5 Shared Content Templates
- [ ] Create base HTML template for shared content
- [ ] Create content-specific template with markdown rendering
- [ ] Create summary template with structured sections
- [ ] Create digest template with all sections
- [ ] Add audio player component
- [ ] Add Open Graph meta tags
- [ ] Ensure mobile responsiveness

### 3.6 Rate Limiting
- [ ] Add rate limiting middleware for `/shared/*` endpoints
- [ ] Configure limits (100/min per IP, 1000/hour per token)
- [ ] Add `Retry-After` header on 429 responses

### 3.7 Testing
- [ ] Unit tests for share token generation
- [ ] API tests for share endpoints
- [ ] Integration tests for public access
- [ ] Test 404 for disabled/non-existent shares
- [ ] Test HTML and JSON response formats

---

## Phase 4: Chrome Extension / Bookmarklet

### 4.1 Create Chrome Extension
- [ ] Create `extension/manifest.json` (Manifest V3)
- [ ] Create `extension/popup.html` - configuration UI
- [ ] Create `extension/popup.js` - save functionality
- [ ] Create `extension/content.js` - page content extraction
- [ ] Create `extension/config.js` - user settings storage
- [ ] Add extension icons (16, 48, 128px)

### 4.2 Extension Features
- [ ] One-click save current page URL
- [ ] Capture selected text as excerpt
- [ ] Show save confirmation/status
- [ ] Settings page for API URL and key configuration
- [ ] Error handling with user-friendly messages

### 4.3 Create Bookmarklet
- [ ] Create `bookmarklet/bookmarklet.js` with save logic
- [ ] Create bookmarklet generator page in web UI
- [ ] Support URL and title capture
- [ ] Redirect to app save page

### 4.4 Save URL API Endpoint
- [ ] Create `POST /api/v1/content/save-url` endpoint
- [ ] Implement URL validation
- [ ] Implement duplicate detection by URL
- [ ] Queue content extraction via background task
- [ ] Return content ID for status polling
- [ ] Create `GET /api/v1/content/{id}/status` for polling

### 4.5 Content Extraction
- [ ] Integrate with existing `ParserRouter` for URL content extraction
- [ ] Add Readability-style extraction for web pages
- [ ] Handle extraction failures gracefully
- [ ] Store extracted content as `Content` record

### 4.6 Testing
- [ ] Manual extension testing in Chrome
- [ ] API tests for save-url endpoint
- [ ] Test duplicate URL detection
- [ ] Test extraction for various page types

---

## Phase 5: Documentation

### 5.1 Setup Documentation
- [ ] Add Supabase setup section to `docs/SETUP.md`
- [ ] Document database provider configuration
- [ ] Document storage provider configuration
- [ ] Add "Bring Your Own Supabase" quick start guide

### 5.2 User Documentation
- [ ] Document sharing feature usage
- [ ] Document Chrome extension installation
- [ ] Document bookmarklet setup
- [ ] Add troubleshooting section

### 5.3 Architecture Documentation
- [ ] Update `docs/ARCHITECTURE.md` with provider diagrams
- [ ] Document storage flow for audio files
- [ ] Document sharing URL structure

---

## Phase 6: Validation

### 6.1 Local Setup Regression
- [ ] Verify local PostgreSQL still works unchanged
- [ ] Verify local file storage still works
- [ ] Verify all existing features work

### 6.2 Supabase Integration
- [ ] Test with real Supabase free tier project
- [ ] Verify Alembic migrations work
- [ ] Verify connection pooling behavior
- [ ] Test storage upload and retrieval
- [ ] Test shared content access

### 6.3 Mobile Testing
- [ ] Test shared content pages on mobile browsers
- [ ] Test audio playback on mobile
- [ ] Verify touch interactions work

### 6.4 Extension Testing
- [ ] Test extension in Chrome
- [ ] Test bookmarklet in Safari/Firefox
- [ ] Test save flow end-to-end
