# Add aca auth session capture command

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-08`)
> Change ID: `add-aca-auth-session-capture-command`
> Effort: L · Priority: 3 · Depends on: ri-01, ri-02, ri-07

## Why

Substack paid posts need the `substack.sid` cookie and the coming X bookmarks
adapter needs the `auth_token` + `ct0` pair. Today the Substack cookie is copied by
hand out of DevTools into `.secrets.yaml`; nothing checks it works, nothing stamps
`saved_at`, and X has no capture path at all. ri-02 gave the auth CLI a secret sink
(`--to bao|railway|secrets-file`), ri-04 a live credential provider, and ri-07 a
backup-excluded home for browser profiles. This item joins them into one
deterministic, once-per-site login that is also the command an expiry alert names.

## What Changes

- New `src/cli/session_commands.py`, registered as `aca auth session` (one line in
  `src/cli/app.py`), with commands `substack` and `x`, each taking
  `--to bao|railway|secrets-file`, `--timeout SECONDS` (default 300) and `--headless`.
- The command checks the sink first, creates `browser_profiles_dir()/<site>` (and the
  root) with mode 0700, refuses a symlinked profile directory, and launches Chromium
  through Playwright `launch_persistent_context` (headed by default). Playwright is
  imported lazily inside the command; a missing install is a clear error.
- If the profile already holds the target cookies it captures them without opening
  the login page. Otherwise it opens the login page and polls `context.cookies()`
  once a second until the cookies exist or `--timeout` elapses (non-zero exit,
  timeout message).
  - substack: `substack.sid` on `substack.com` -> `SUBSTACK_SESSION_COOKIE`
  - x: `auth_token` and `ct0` on `x.com` -> `X_AUTH_TOKEN`, `X_CT0`; `twitter.com` is
    used only when `x.com` does not hold the pair, and a pair is never mixed across
    domains. Expired and empty cookies are ignored.
- Validation: one httpx request per site, never through the browser —
  `GET https://substack.com/api/v1/subscriptions` (the endpoint `SubstackClient`
  already calls) and `GET https://x.com/i/api/1.1/account/settings.json` with the
  public web bearer token, `x-csrf-token: <ct0>` and both cookies. Anything but a 200
  with the expected JSON exits non-zero without writing.
- One `SecretSink.write()` per capture. Default sink when `--to` is omitted: `bao`
  when `BAO_ADDR` is set, else `secrets-file` (never Railway implicitly). After a
  `bao` write the command calls `get_credential_provider().apply_local_write(...)`
  with the exact `saved_at` the sink wrote.
- New `src/ingestion/x_web.py`: the X web bearer token, user agent, account-settings
  URL, cookie names and `x_web_headers()` in one place for ri-11 to import.
- `docs/SETUP.md` "Substack API Setup": the command replaces the DevTools steps,
  which remain as a manual fallback.
- No timer, cron entry or scheduled job is created.

## Impact

- Affected specs: `browser-session-credentials` (ADDED).
- Code: `src/cli/session_commands.py` (new), `src/ingestion/x_web.py` (new),
  `src/cli/app.py` (one registration line), `docs/SETUP.md` (one section).
- Tests: `tests/cli/test_session_commands.py` (fake browser context, MockTransport,
  fake sinks / fake KV v2 adapter; no browser, no network).
- Runtime dependency: Playwright is only needed on the machine that runs the
  capture (the workstation); the worker image is unchanged.
