## Context
The API is intended for internal use but may be deployed in environments where unauthenticated access and permissive CORS are unacceptable. File upload endpoints also need stronger guardrails against abuse and sensitive error disclosure.

## Goals / Non-Goals
- Goals:
  - Require authentication for non-public endpoints in production.
  - Make CORS policy configurable and secure-by-default for production.
  - Harden upload processing against memory exhaustion and file spoofing.
  - Avoid leaking internal exception details in API responses.
- Non-Goals:
  - Redesign of the ingestion pipeline or parser architecture.
  - Replacing existing auth providers or identity systems.

## Decisions
- Decision: Introduce a pluggable authentication dependency (API key or bearer token) with an explicit allowlist for public routes.
  - Alternatives considered: Global middleware only, or per-route decorators without centralized config.
- Decision: Move CORS origins to settings and enforce stricter defaults when ENVIRONMENT=production.
  - Alternatives considered: Hardcoded origin lists, or disabling CORS entirely in production.
- Decision: Enforce upload size limits before full buffering and validate file type using MIME/signature checks in addition to extensions.
  - Alternatives considered: Extension-only validation and full in-memory buffering.

## Risks / Trade-offs
- Adding auth may require client updates; mitigate via clear docs and staged rollout.
- Streaming validation may complicate parser integration; mitigate with a small adapter layer.

## Migration Plan
1. Add auth configuration and allowlist for public routes.
2. Update CORS configuration and verify frontend access.
3. Update upload endpoint to validate size/type early and sanitize errors.
4. Document and test changes.

## Open Questions
- Which authentication mechanism should be the initial default (API key vs. bearer token)?
- Which endpoints must remain public (e.g., health check, system config)?
