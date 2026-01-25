# Implementation Tasks

## 1. Save URL API Endpoint

- [ ] 1.1 Create `src/api/save_routes.py` with router
- [ ] 1.2 Implement `POST /api/v1/content/save-url` endpoint
- [ ] 1.3 Add URL validation (valid URL format, https preferred)
- [ ] 1.4 Add duplicate detection by source_url
- [ ] 1.5 Implement `GET /api/v1/content/{id}/status` endpoint
- [ ] 1.6 Configure CORS for mobile clients (allow all origins for API key auth)
- [ ] 1.7 Register router in `src/api/app.py`

## 2. Optional API Key Authentication

- [ ] 2.1 Create `src/api/auth/api_keys.py` module
- [ ] 2.2 Create APIKey model (id, hashed_key, name, rate_limit, created_at)
- [ ] 2.3 Implement `verify_api_key()` dependency
- [ ] 2.4 Add rate limiting per API key (60 req/min default)
- [ ] 2.5 Create Alembic migration for api_keys table
- [ ] 2.6 Add API key management CLI commands

## 3. URL Content Extraction

- [ ] 3.1 Create `src/services/url_extractor.py`
- [ ] 3.2 Integrate with existing `ParserRouter` for HTML parsing
- [ ] 3.3 Add fallback extraction (title, meta description) if parsing fails
- [ ] 3.4 Implement async extraction as background task
- [ ] 3.5 Add timeout handling (30s max per URL)
- [ ] 3.6 Handle common errors (404, timeout, blocked)

## 4. Mobile Save Page

- [ ] 4.1 Create `GET /save` endpoint in save_routes.py
- [ ] 4.2 Create `src/templates/save.html` (mobile-optimized)
- [ ] 4.3 Pre-fill form from URL query parameters
- [ ] 4.4 Add JavaScript for async form submission
- [ ] 4.5 Show success/error states with clear messaging
- [ ] 4.6 Add responsive design (works on phone and desktop)

## 5. iOS Shortcut

- [ ] 5.1 Create Shortcut in Apple Shortcuts app
- [ ] 5.2 Configure to receive URLs from Share Sheet
- [ ] 5.3 Add input fields for API URL and API key
- [ ] 5.4 Implement HTTP POST action to save-url endpoint
- [ ] 5.5 Add success/error notifications
- [ ] 5.6 Export as .shortcut file to `shortcuts/` directory
- [ ] 5.7 Create `shortcuts/README.md` with installation guide

## 6. Database Provider Testing

- [ ] 6.1 Write integration tests for save-url with local PostgreSQL
- [ ] 6.2 Write integration tests for save-url with Supabase
- [ ] 6.3 Write integration tests for save-url with Neon
- [ ] 6.4 Verify cold start handling with Neon (test after idle period)
- [ ] 6.5 Test duplicate detection across providers

## 7. Unit Tests

- [ ] 7.1 Test save_routes.py endpoint logic
- [ ] 7.2 Test URL validation edge cases
- [ ] 7.3 Test duplicate detection logic
- [ ] 7.4 Test API key authentication
- [ ] 7.5 Test rate limiting behavior
- [ ] 7.6 Test url_extractor.py with mock responses

## 8. Documentation

- [ ] 8.1 Create `docs/MOBILE_CAPTURE.md` user guide
- [ ] 8.2 Document iOS Shortcut installation
- [ ] 8.3 Document API key setup
- [ ] 8.4 Add troubleshooting section
- [ ] 8.5 Update CLAUDE.md with new endpoint
