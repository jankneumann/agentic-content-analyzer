## Context
The API already has foundational security: API key authentication on settings endpoints (`X-Admin-Key` header via `verify_admin_key()` in `dependencies.py`), configurable CORS origins (`ALLOWED_ORIGINS`), streaming upload size enforcement (1MB chunks), and global error sanitization middleware. However, production deployments rely on manual configuration — there is no automatic enforcement of secure defaults, no file content validation (only extension-based), and no centralized public endpoint allowlist.

## Goals / Non-Goals
- Goals:
  - Automatically enforce secure defaults in production (CORS, auth key presence).
  - Add file signature (magic bytes) validation to complement extension-based format checks.
  - Define an explicit public endpoint allowlist so unauthenticated routes are intentional.
  - Validate production security configuration at startup.
- Non-Goals:
  - Redesigning authentication (API key mechanism is established and working).
  - Adding rate limiting or DDoS protection (separate concern).
  - Protecting content API endpoints (single-user model — instance is the security boundary).
  - Malware/virus scanning of uploaded files.

## Decisions
- Decision: Use API key authentication via `X-Admin-Key` header (already implemented).
  - Rationale: Established in codebase, sufficient for single-user model, used by Chrome extension and admin UI.
  - Alternatives considered: Bearer tokens (unnecessary complexity for single-user), OAuth (overkill).
- Decision: Enforce CORS by environment — restrictive defaults in production, permissive in development.
  - Rationale: Prevents accidental exposure when deploying without explicit CORS config.
  - Alternatives considered: Always require explicit config (too strict for dev), wildcard default (insecure).
- Decision: Validate file uploads by magic bytes in addition to extension.
  - Rationale: Extension-only validation allows spoofed file types. Magic bytes catch files with wrong extensions (e.g., executable renamed to `.pdf`).
  - Alternatives considered: Full MIME sniffing library (heavyweight), extension-only (current, insufficient).
- Decision: Log warnings (not hard failures) for production misconfigurations at startup.
  - Rationale: Hard failures could break existing deployments that work correctly despite non-ideal config. Warnings surface issues without causing downtime.
  - Alternatives considered: Hard failure (too disruptive), silent pass (defeats purpose).

## Risks / Trade-offs
- **CORS behavior change in production**: `get_allowed_origins_list()` returning empty list for unconfigured production deployments will block cross-origin requests. This is a deliberate security default, but will break existing production deployments that relied on dev defaults silently passing through. Mitigate via: startup warning log, clear documentation of required `ALLOWED_ORIGINS` for production.
- **Startup warnings are advisory only**: Production misconfigurations (missing `ADMIN_API_KEY`, dev CORS defaults) produce log warnings but do NOT prevent startup. This is intentional — hard failures could cause downtime for deployments that work correctly despite non-ideal config.
- Magic bytes validation adds a small check on every upload; negligible performance impact since first chunk is already in memory.
- Public endpoint allowlist is documentation-only (not enforcement middleware). In the single-user model, most endpoints are intentionally unauthenticated. Enforcement can be added later if multi-user support is needed.

## Migration Plan
1. Add production startup validators to `settings.py` — warn on missing `ADMIN_API_KEY` and dev-default CORS.
2. Update `get_allowed_origins_list()` to return empty list for production when no explicit origins configured.
3. Add magic bytes validation in `upload_routes.py` after first chunk read (before format routing).
4. Add MIME cross-check against declared extension.
5. Define `PUBLIC_ENDPOINTS` constant documenting intentionally unauthenticated routes.
6. Add tests for all new behaviors.
7. Document production security requirements in setup docs.
