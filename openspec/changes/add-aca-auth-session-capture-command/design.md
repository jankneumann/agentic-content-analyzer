# Design: Add aca auth session capture command

## Context

ri-02 (`src/cli/secret_sinks.py`), ri-04 (`src/config/credentials.py`) and ri-07
(`src/config/browser_profiles.py`) supply the sink, the live provider and the
profile root. This change is the thin interactive layer on top.

## Decisions

1. **Seams, not mocks of Playwright.** `capture_session()` resolves its browser,
   sink factory, HTTP client and clock at call time from module-level defaults
   (`playwright_persistent_context`, `default_sink_factory`, `new_http_client`,
   `time`). Tests replace those attributes; Playwright is never imported in tests.
2. **Cookie selection is per domain, all-or-nothing.** For X the first domain in
   `("x.com", "twitter.com")` that holds *both* live cookies wins. A pair assembled
   from two domains could be two different sessions, so it is refused. Domains are
   compared after stripping the leading dot, exactly; `foo.substack.com` or a
   look-alike host never matches.
3. **Existing session short-circuits.** Cookies are read before any navigation; if
   they are present the login page is never opened, which is what makes the second
   run non-interactive. With `--headless` and no session, the command still waits
   (visiting the page can mint a fresh `ct0`) and the timeout message says a login
   needs the window.
4. **Validation over httpx, redirects off.** One request, `follow_redirects=False`,
   so a redirect to a login page is a non-200 failure. Error messages carry the
   method, URL (query stripped) and status only.
5. **Same `saved_at` in OpenBao and the in-process cache.** The default sink factory
   builds `BaoSink(clock=_PinnedClock())`; the clock pins its first reading, which
   `BaoSink.write()` takes for `<KEY>_SAVED_AT`, and the command passes that same
   instant to `CredentialProvider.apply_local_write()`. A cache update failure is a
   warning only: the durable write already succeeded.
6. **Default sink.** `bao` when `BAO_ADDR` is set, else `secrets-file`. Railway is
   never implicit because it redeploys a service.
7. **X web bearer token lives in `src/ingestion/x_web.py`.** It is the public token
   embedded in x.com's JavaScript (identical for all users, copied from the upstream
   exporter's `src/api.ts`), not an account credential. ri-11 imports
   `X_WEB_BEARER_TOKEN` and `x_web_headers()` from there.
8. **Registration.** `src/cli/app.py` gets one line,
   `auth_app.add_typer(importlib.import_module("src.cli.session_commands").app, name="session")`,
   so `src/cli/auth_commands.py` (being edited by ri-06) is untouched.

## Non-goals

- No refresh timer, cron entry or scheduled job; the adapter's write-back handles
  routine `ct0` rotation and this command is re-run on an expiry alert.
- No reading of Chrome's own cookie database, no DevTools automation.
- No `--service` flag for the Railway sink (the default service is used); add it if
  a multi-service Railway project needs session cookies before Railway is retired.
- Installing Playwright/Chromium: the command only reports how to install it.
