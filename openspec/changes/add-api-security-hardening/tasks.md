## 1. Production Enforcement
- [ ] 1.1 Add production startup validation and environment-aware CORS defaults.
  - Add Pydantic validator or `@model_validator` that logs security warnings at startup when `ENVIRONMENT=production`:
    - Warn if `ADMIN_API_KEY` is not set.
    - Warn if `ALLOWED_ORIGINS` still uses dev defaults (contains only `localhost` origins).
  - Update `get_allowed_origins_list()` to return empty list when `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is unset or uses dev defaults (deny all cross-origin by default in production).
  - Retain current permissive defaults for `ENVIRONMENT=development`.
  - Files: `src/config/settings.py` (add validator + update `get_allowed_origins_list()`)
  - Dependencies: none (independent)
- [ ] 1.2 Define explicit public endpoint allowlist (documentation constant).
  - Add a `PUBLIC_ENDPOINTS` or `ENDPOINT_AUTH_MAP` constant documenting which routes are intentionally unauthenticated and why:
    - System endpoints: `/health`, `/ready`, `/api/v1/system/config`, `/api/v1/otel/v1/traces` (infrastructure)
    - Application endpoints: `/api/v1/content/*`, `/api/v1/digests/*`, etc. (single-user model — instance is security boundary)
    - Protected endpoints: `/api/v1/settings/*` (admin API key required)
  - This is documentation-only (no enforcement middleware). Enforcement can be added later if multi-user support is needed.
  - Files: `src/api/dependencies.py` (add constant with docstring)
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
- [ ] 3.1 Add tests for production startup validation and CORS defaults (1.1).
  - Test that production mode with missing `ADMIN_API_KEY` logs warning.
  - Test that production mode with dev-default CORS origins logs warning.
  - Test that production mode without explicit `ALLOWED_ORIGINS` returns empty origins list.
  - Test that development mode retains permissive localhost defaults.
  - Test that production mode with explicit `ALLOWED_ORIGINS` returns configured list.
  - Files: `tests/security/test_production_validation.py`
  - Dependencies: 1.1
- [ ] 3.2 Add tests for file signature and MIME validation (2.1, 2.2).
  - Test upload with valid extension but wrong magic bytes returns 415.
  - Test upload with matching extension and magic bytes succeeds.
  - Test upload with unknown extension (no magic bytes mapping) succeeds.
  - Test upload with mismatched MIME type returns 415.
  - Test upload with `application/octet-stream` MIME type bypasses MIME check.
  - Files: `tests/api/test_upload_security.py` (extend existing)
  - Dependencies: 2.1, 2.2

## 4. Documentation
- [ ] 4.1 Document production security configuration requirements.
  - Add section to CLAUDE.md or docs/SETUP.md covering required env vars for production.
  - Document public endpoint allowlist and rationale.
  - Files: `CLAUDE.md` or `docs/SETUP.md`
  - Dependencies: 1.1, 1.2
