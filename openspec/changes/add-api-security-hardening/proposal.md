# Change: Add API security hardening for authentication, CORS, and uploads

## Why
The API currently lacks documented authentication and relies on permissive local CORS defaults, which increases exposure risk when deployed beyond trusted environments. Strengthening authentication, CORS configuration, and upload handling reduces the attack surface and improves production readiness.

## What Changes
- Add authentication requirements for non-public API endpoints in production.
- Make CORS policy environment-configurable with secure production defaults.
- Harden document upload handling with streaming size enforcement, file-type validation, and sanitized error responses.

## Impact
- Affected specs: api-security (new capability)
- Affected code: src/api/app.py, src/api/upload_routes.py, src/config/settings.py, related middleware/utilities

## Related Proposals

### Authentication Alignment

This proposal should align with the **Supabase integration series** which uses a single-user "bring your own backend" model:
- **`add-supabase-cloud-database`**: Single-user model (no multi-tenant auth needed)
- **`content-capture`**: Chrome extension uses API key authentication

Consider:
- Health endpoints (`/health`, `/ready`) from `add-observability` should be publicly accessible
- Metrics endpoint (`/metrics`) may need protection in production
- Single-user model simplifies auth but instance still needs protection

### Dependencies

- Used by: `add-deployment-pipeline` (security checks in CI)
- Related: `add-observability` (health endpoint auth consideration)
- Related: `add-api-versioning` (auth applies across versions)
- Related: `content-capture` (extension authentication)
