## 1. Production Enforcement
- [ ] 1.1 Add production startup validation for security configuration.
  - Verify `ADMIN_API_KEY` is set when `ENVIRONMENT=production` or `staging`; log warning or refuse to start if missing.
  - Verify `ALLOWED_ORIGINS` is not the dev default (`localhost:5173,localhost:3000`) in production; log warning if so.
  - Files: `src/config/settings.py` (add validator), `src/api/app.py` (startup check)
  - Dependencies: none (independent)
- [ ] 1.2 Add environment-aware CORS defaults and enforcement.
  - When `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is unset or uses dev defaults, default to empty list (deny all cross-origin).
  - Retain current permissive defaults for `ENVIRONMENT=development`.
  - Files: `src/config/settings.py` (update `get_allowed_origins_list()`), `src/api/app.py`
  - Dependencies: none (independent)
- [ ] 1.3 Define explicit public endpoint allowlist.
  - Add a `PUBLIC_ENDPOINTS` constant or config listing routes that intentionally skip auth: `/health`, `/ready`, `/api/v1/system/config`, `/api/v1/otel/v1/traces`.
  - Document rationale for each public endpoint.
  - Files: `src/api/dependencies.py` or new `src/api/security.py`
  - Dependencies: none (independent)

## 2. Upload Hardening
- [ ] 2.1 Add file signature (magic bytes) validation for uploads.
  - After reading the first chunk, verify magic bytes match the declared extension (e.g., PDF starts with `%PDF`, ZIP with `PK`, DOCX is ZIP-based).
  - Return `415 Unsupported Media Type` with descriptive message on signature mismatch.
  - Define a mapping of extension → expected magic bytes for supported upload formats.
  - Files: `src/api/upload_routes.py` (add validation after first chunk read)
  - Dependencies: none (independent)
- [ ] 2.2 Add MIME type cross-check for uploads.
  - Validate client-provided `Content-Type` against declared extension.
  - Reject uploads where MIME type contradicts extension (e.g., `.pdf` uploaded as `image/png`).
  - Files: `src/api/upload_routes.py`
  - Dependencies: 2.1 (uses same validation module)

## 3. Testing
- [ ] 3.1 Add tests for production startup validation (1.1).
  - Test that production mode with missing `ADMIN_API_KEY` logs warning / raises.
  - Test that production mode with dev-default CORS origins logs warning.
  - Files: `tests/security/test_production_validation.py`
  - Dependencies: 1.1
- [ ] 3.2 Add tests for CORS environment-aware defaults (1.2).
  - Test that production mode without explicit `ALLOWED_ORIGINS` denies cross-origin.
  - Test that development mode retains permissive defaults.
  - Files: `tests/api/test_cors_security.py`
  - Dependencies: 1.2
- [ ] 3.3 Add tests for file signature validation (2.1, 2.2).
  - Test upload with valid extension but wrong magic bytes returns 415.
  - Test upload with matching extension and magic bytes succeeds.
  - Test upload with mismatched MIME type returns 415.
  - Files: `tests/api/test_upload_security.py` (extend existing)
  - Dependencies: 2.1, 2.2

## 4. Documentation
- [ ] 4.1 Document production security configuration requirements.
  - Add section to CLAUDE.md or docs/SETUP.md covering required env vars for production.
  - Document public endpoint allowlist and rationale.
  - Files: `CLAUDE.md` or `docs/SETUP.md`
  - Dependencies: 1.1, 1.2, 1.3
