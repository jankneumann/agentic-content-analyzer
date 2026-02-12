# Change: Harden API security with production enforcement, CORS defaults, and upload validation

## Why
The API has a working authentication system (`X-Admin-Key` on settings endpoints), configurable CORS origins, streaming upload size checks, and error sanitization middleware. However, it lacks: (1) automatic enforcement of secure defaults in production, (2) file content validation beyond extension matching, and (3) an explicit public endpoint allowlist. These gaps mean production deployments rely on manual configuration — misconfiguration silently degrades security.

## What Changes
- Add production startup validation that verifies `ADMIN_API_KEY` is set and `ALLOWED_ORIGINS` uses explicit origins (not dev defaults or wildcard).
- Add environment-aware CORS defaults that automatically restrict origins in production when not explicitly configured.
- Add file signature (magic bytes) validation for uploads to complement existing extension-based format checks.
- Define an explicit public endpoint allowlist so unauthenticated routes are intentional and documented.

## Impact
- Affected specs: api-security (new capability)
- Affected code: src/api/app.py, src/api/upload_routes.py, src/config/settings.py, src/api/dependencies.py

## Existing Implementation (baseline)
The following features are already in place and are NOT re-implemented by this proposal:
- **Authentication**: `verify_admin_key()` in `src/api/dependencies.py` — API key auth with dev-mode bypass (commit a101c2b)
- **CORS**: Configurable via `ALLOWED_ORIGINS` env var, parsed in `settings.get_allowed_origins_list()`
- **Upload size enforcement**: Streaming 1MB chunk reads in `upload_routes.py` with configurable `max_upload_size_mb`
- **Error sanitization**: Global middleware in `error_handler.py` + per-route generic errors in `upload_routes.py`
- **Format validation**: Extension-based check against parser `supported_formats`/`fallback_formats`

## Related Proposals

### Authentication Alignment
This proposal builds on the single-user "bring your own backend" model:
- Health endpoints (`/health`, `/ready`) remain publicly accessible
- Settings/prompt endpoints are already protected by `X-Admin-Key`
- Content API endpoints are unauthenticated (single-user model — the instance itself is the security boundary)

### Dependencies
- Related: `add-observability` (health endpoint auth consideration)
- Related: `content-capture` (extension authentication via API key)
