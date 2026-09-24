# Design: Add admin endpoint for browser-session sync

## Decisions

### Two static routes instead of `{site}`
`PUT /api/v1/browser-sessions/substack` and `/x` each bind their own strict body
model, so OpenAPI shows the exact fields per site, `extra="forbid"` is per site, and
an unknown site is a plain 404. A path parameter would need a discriminated body and
a second validation step.

### Header-only admin auth
`verify_admin_key` also admits a web-UI session cookie and, in development with no
keys configured, anyone on loopback. On gx-10 `tailscale serve` proxies every tailnet
peer from 127.0.0.1, so the dev bypass would admit the whole tailnet. A credential
write therefore requires `verify_admin_key` to have validated the `X-Admin-Key`
header itself; anything else is 401.

### Problem bodies to avoid echoing input
FastAPI's default (legacy-path) 422 body includes each error's `input`, which would
be the cookie value. Registering the path prefix in `_PROBLEM_PATH_PREFIXES` makes
the existing handler emit `path`, `code` and `message` only. The models also set
`hide_input_in_errors=True`.

### Order: configured -> authenticate -> validate -> write -> cache
Checking OpenBao configuration (env only) first means an unconfigured server makes no
request to Substack/X. Authenticating before validating mirrors the CLI's
`sink.check()` so a broken store costs no request to the site. The write is one
`BaoSink.write()` (one merge-PATCH, one `saved_at`), and the local cache update uses
that same `saved_at`; a cache failure is logged and does not fail the request
because OpenBao already holds the value.

### Fresh AppRole login per call
The sink authenticates with `BAO_ROLE_ID`/`BAO_SECRET_ID` per request instead of
reusing `bao_secrets`' cached client, whose token may be near expiry. The endpoint is
manual and rate-limited, and the `newsletter-app` secret-id has no use limit.

### Upstream failure vs invalid session
A 5xx or 429 from the site, or a transport error, is 502: the operator should retry,
not re-capture. Any other non-200, a redirect (not followed), a non-JSON page or JSON
without the expected field is 422 `session_invalid`.

### Rate limit
No admin-wide limiter exists; the login limiter counts failed passwords only. A new
`EndpointRateLimiter` instance (10 per 5 min per IP; `request.client.host` is the real
peer because uvicorn trusts forwarded headers only from 127.0.0.1) bounds how often a
looping client can make the API call Substack/X on the operator's account.

## Non-goals
- The extension UI and manifest permissions (ri-15).
- Declaring the routes in the canonical workflow contract (admin routes are not there).
- A streaming body limit. The Content-Length check and field limits bound what the
  route parses; `AuthMiddleware` rejects unauthenticated requests before the route
  reads the body, and the outer NUL-byte guard already reads at most 1 MiB.
