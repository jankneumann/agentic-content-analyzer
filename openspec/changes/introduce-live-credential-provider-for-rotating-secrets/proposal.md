# Introduce live credential provider for rotating secrets

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-04`)
> Change ID: `introduce-live-credential-provider-for-rotating-secrets`
> Effort: M · Priority: 2 · Depends on: `ri-02`

## Why

`settings` (`src/config/settings.py` `get_settings()`) is built once behind
`lru_cache`. `src/ingestion/substack.py` read `settings.substack_session_cookie`,
so a running worker kept the boot-time `substack.sid` forever, even though
`src/config/bao_secrets.py` already swaps its in-memory OpenBao cache when the
AppRole token manager re-fetches at 75% TTL. With plain token auth nothing ever
re-read OpenBao. Browser-session cookies (`substack.sid`, X `auth_token`/`ct0`)
rotate far more often than workers restart, and ri-05, ri-06 and ri-11 need one
place that resolves them live, reports `saved_at`, and accepts a write-back.

## What Changes

- New `src/config/credentials.py`:
  - `CredentialProvider.get(name)` resolves at call time: the OpenBao cache
    first (memory only, no network per call), then `Settings`.
  - An explicit registry `BROWSER_SESSION_CREDENTIALS` maps
    `SUBSTACK_SESSION_COOKIE` / `X_AUTH_TOKEN` / `X_CT0` to the `Settings`
    fields `substack_session_cookie` / `x_auth_token` / `x_ct0` and the labels
    `substack.sid` / `x.auth_token` / `x.ct0`. Unknown names are refused.
  - `metadata(name)` returns `CredentialMetadata` (`present`, `source`,
    `saved_at` parsed from the `<NAME>_SAVED_AT` sibling, `last_verified_at`),
    never the value.
  - `mark_verified(name)` records an in-process `last_verified_at` bound to the
    current value (a rotation clears it); nothing is written to OpenBao.
  - `refresh(min_interval_s=60)` asks OpenBao for fresh values, bounded
    process-wide.
  - `apply_local_write(mapping)` makes values this process just PATCHed through
    `BaoSink` visible immediately, stamping `<NAME>_SAVED_AT`.
  - `get_credential_provider()` returns the process-wide instance.
- `src/config/bao_secrets.py`: keeps the authenticated client and location
  after the first load; adds `get_bao_secrets()` (read-only snapshot view),
  `refresh_bao_secrets(min_interval_s=...)` (thread-safe, throttled, reuses the
  client, one re-auth on failure, works for token and AppRole auth) and
  `apply_bao_local_write(mapping)` (copy-merge-swap under the lock). The token
  manager now fetches and swaps under the same lock.
- `src/config/settings.py`: `x_auth_token` and `x_ct0` fields; all three
  browser-session fields are `repr=False`. `profiles/base.yaml` wires
  `${X_AUTH_TOKEN:-}` and `${X_CT0:-}`.
- `src/config/secrets.py`: `is_secret_key()` also matches `*_COOKIE` and
  `X_CT0`, so `aca profile show` masks them.
- `src/ingestion/substack.py`: `SubstackClient` resolves `substack.sid` through
  the provider before every HTTP request (explicit `session_cookie` overrides
  still win) and logs exception types instead of exception text on the HTTP
  fallbacks. It no longer references `settings.substack_session_cookie`.

## Impact

- Affected specs: `browser-session-credentials` (new), `openbao-secrets`.
- Affected code: `src/config/credentials.py` (new), `src/config/bao_secrets.py`,
  `src/config/settings.py`, `src/config/secrets.py`, `profiles/base.yaml`,
  `src/ingestion/substack.py`.
- `src/ingestion/orchestrator.py` needs no change: it only forwards an explicit
  override, and nothing else outside settings/profile plumbing read the cookie.
- No schema, contract, or migration change. No new dependency.
