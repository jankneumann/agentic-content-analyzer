# Design: X GraphQL client with query ID discovery and ct0 write-back

## Context

Port of `src/api.ts` from github.com/displace-agency/x-bookmarks-exporter (MIT)
to httpx, inside the worker, reusing ri-02 (`BaoSink`), ri-04
(`CredentialProvider`), ri-05 (`credential_failures`) and ri-08 (`x_web`).

## Decisions

### Query ID cache lives in `settings_overrides`

The ID is a public identifier from X's bundle, not a secret. `SettingsService`
already stores namespaced key/value overrides with versioning, and the
settings override API lets an operator pin an ID by hand if discovery breaks.
A new table would add a migration for one row. The store fails open: a
database error costs one bundle scrape. After an invalidation the client never
re-reads the cache in the same run, so a failed delete cannot hand back the
stale ID.

### Write the pair, not ct0 alone

The roadmap acceptance line says "single-key patch"; ri-02's learning and the
item brief say to write `X_AUTH_TOKEN` and `X_CT0` in one `BaoSink.write()`.
The pair wins: `ct0` is bound to the session, and a ct0-only patch racing a
fresh `aca auth session x` capture could leave a new `auth_token` next to an
old session's `ct0`. It is still one atomic server-side merge-patch. Cost:
`X_AUTH_TOKEN_SAVED_AT` moves to the rotation time, so `saved_at` in
`aca auth status` means "last written", not "first captured".

### Refresh, retry, and rotation state

A dead answer triggers one throttled `provider.refresh()` and one retry only
when the pair changed (ri-05's rule). The rotated `ct0` is applied to the
provider's local cache, which the client reads per request; a small in-client
override covers the case where even the local apply fails. `mark_verified` is
only called when the pair that succeeded is the pair the provider serves.

### Rate limits end the walk instead of blocking the worker

X's windows are 15 minutes. A wait longer than `max_rate_limit_wait_s`
(900 s), or a third 429 on one page, stops the walk with `rate_limited` and
`rate_limit_reset_at`; the caller (ri-12) decides how to surface the partial
read.

### BaoSink stdout

`BaoSink.write()` reports on stdout for the CLI. The write-back redirects
stdout to stderr around the call so a worker (or an inline CLI run) keeps a
clean stdout. If `BaoSink` grows a way to silence that line, use it instead.

## Non-goals

- Persistence, dedup, markdown rendering, `--full` semantics (ri-12).
- Link expansion into URL ingestions (ri-13).
- `auth_token` rotation through `Set-Cookie`: X does not rotate it routinely;
  its expiry is the human-in-the-loop event.
- Hoverfly simulations: the tests use `httpx.MockTransport`, which is
  network-free and needs no proxy.
