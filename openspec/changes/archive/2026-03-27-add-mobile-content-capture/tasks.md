# Implementation Tasks

> **Note**: Core API endpoints (save-url, save-page, status), URL extraction,
> HTML processing, Chrome extension, bookmarklet, web save form, and auth
> are already implemented. Remaining tasks focus on completing the mobile experience.

## 1. Save Endpoint Rate Limiting

- [ ] 1.1 Create `src/api/save_rate_limiter.py` with `EndpointRateLimiter(30, 60)`
- [ ] 1.2 Add rate limiter check to `save_url` endpoint (return 429 with retry_after)
- [ ] 1.3 Add rate limiter check to `save_page` endpoint
- [ ] 1.4 Add `X-RateLimit-Remaining` and `X-RateLimit-Reset` response headers
- [ ] 1.5 Write unit tests for save rate limiter
- [ ] 1.6 Write integration test: rate limit triggers on burst requests

## 2. iOS Shortcut Distribution

- [ ] 2.1 Create iOS Shortcut in Apple Shortcuts app with full flow
- [ ] 2.2 Export `.shortcut` file to `shortcuts/Save to Newsletter.shortcut`
- [ ] 2.3 Create `GET /api/v1/content/shortcut` installation page endpoint
- [ ] 2.4 Create `src/templates/shortcut.html` with download link and QR code
- [ ] 2.5 Add iCloud sharing link as alternative distribution method
- [ ] 2.6 Write test for shortcut installation endpoint

## 3. Mobile Save Page UX Improvements

- [ ] 3.1 Audit `src/templates/save.html` for mobile touch targets (44px min)
- [ ] 3.2 Add viewport meta tag and safe area insets for iOS
- [ ] 3.3 Add success/error state animations (CSS transitions)
- [ ] 3.4 Add "Recent saves" section (localStorage-backed, last 10)
- [ ] 3.5 Add dark mode support matching system preference
- [ ] 3.6 Test on iOS Safari, Chrome, and Android Chrome

## 4. Documentation

- [ ] 4.1 Create `docs/MOBILE_CAPTURE.md` with setup guide
- [ ] 4.2 Document iOS Shortcut installation (with screenshots placeholder)
- [ ] 4.3 Document rate limiting behavior and limits
- [ ] 4.4 Add troubleshooting section for mobile-specific issues
- [ ] 4.5 Update `docs/CONTENT_CAPTURE.md` to cross-reference mobile guide
- [ ] 4.6 Update CLAUDE.md with mobile capture section

## 5. Tests

- [ ] 5.1 Unit tests for rate limiter module
- [ ] 5.2 API tests for rate-limited save endpoints (429 responses)
- [ ] 5.3 API test for shortcut installation page rendering
- [ ] 5.4 E2E test for mobile save page form submission (Playwright)
- [ ] 5.5 E2E test for bookmarklet page rendering
