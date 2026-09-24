# Add admin endpoint for browser-session sync

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-14`)
> Change ID: `add-admin-endpoint-for-browser-session-sync`
> Depends on: `ri-01` (tailnet baseline), `ri-02` (`BaoSink`), `ri-03` (API AppRole `patch`), `ri-04` (credential provider), `ri-08` (session validators)

## Why

When a session-expiry alert fires and the operator is at a laptop, the only way to
refresh `substack.sid` or the X `auth_token`/`ct0` pair today is
`aca auth session` on the workstation. The Chrome extension (ri-15) can read those
cookies from the operator's own browser, but it has nowhere safe to send them. It
needs one admin-only, tailnet-reachable write path that proves the session works
and writes it to OpenBao the same way the CLI does, without ever echoing a value.

## What Changes

- New admin routes `PUT /api/v1/browser-sessions/substack` (body `{substack_sid}`)
  and `PUT /api/v1/browser-sessions/x` (body `{auth_token, ct0}`) in
  `src/api/browser_session_routes.py`. Bodies are `SecretStr` fields with
  `repr=False`, `extra="forbid"`, RFC 6265 cookie-octet values of 1..4096 chars and
  a 16 KiB body cap (413).
- Auth: `verify_admin_key` plus a guard that accepts only a valid `X-Admin-Key`
  header. The web-UI session cookie and the unconfigured-dev bypass get 401. Routes
  are tagged `@audited(operation="browser_sessions.sync")`; handler notes carry site,
  outcome and key names only. `admin_key_fp` behaviour comes from the unchanged
  `AuditMiddleware` (outside `AuthMiddleware`).
- `/api/v1/browser-sessions/` joins `_PROBLEM_PATH_PREFIXES`, so every error is
  `application/problem+json` and 422 validation bodies never echo the input.
- `src/services/browser_session_sync.py`: refuse (503 `openbao_not_configured`,
  listing what is missing) before any I/O unless OpenBao is configured; authenticate
  the sink; validate with ONE request; write ONE `BaoSink` merge-PATCH with one
  `saved_at`; then `get_credential_provider().apply_local_write(values, saved_at=…)`.
  Refused session is 422 `session_invalid`; site outage/throttle/transport error is
  502 `session_validation_unavailable`; OpenBao failure is 502 `openbao_write_failed`.
- The CLI's per-site validators move to `src/ingestion/browser_session_validation.py`
  (value-free `SessionValidationError` with a stable `reason`) and
  `src/cli/session_commands.py` imports them, so the CLI and API judge a session by
  the same request.
- `BaoSink` gains an optional `echo` callback (default `typer.echo`, unchanged CLI
  output) so the server can silence the stdout line.
- In-process rate limit: 10 calls per 5 minutes per client IP (`EndpointRateLimiter`).
- `tests/contract/test_fuzz.py` excludes the routes (they call Substack/X and OpenBao).
- Docs: `docs/TAILNET.md` section "Browser-session sync endpoint"; link from
  `docs/OPENBAO.md`.

## Impact

- Capability: `browser-session-credentials` (ADDED requirements).
- Contract: not added to `openspec/contracts/content-workflows/openapi/v1.yaml`. That
  contract declares only the durable-workflow surface; admin routes such as
  `/api/v1/sources` writes and `/api/v1/auth` are documented by FastAPI's OpenAPI
  only, and no drift test enumerates them. No generated file changes.
- No migration, no new dependency, no new setting. Railway (no OpenBao) answers 503.
