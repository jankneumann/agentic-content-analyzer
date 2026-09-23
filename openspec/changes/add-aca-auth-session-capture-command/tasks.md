# Tasks: Add aca auth session capture command

> Change ID: `add-aca-auth-session-capture-command`

## 1. Plan
- [x] 1.1 Refine proposal, design and the `browser-session-credentials` spec delta against the real sink, provider and profile modules

## 2. Implementation
- [x] 2.1 `src/ingestion/x_web.py`: X web bearer token, user agent, account-settings URL, cookie names, `x_web_headers()`
- [x] 2.2 `src/cli/session_commands.py`: site specs, per-domain all-or-nothing cookie selection (expired/empty ignored)
- [x] 2.3 Profile directory creation under `browser_profiles_dir()` with mode 0700 (root too), symlink refusal
- [x] 2.4 Lazy Playwright `launch_persistent_context` context manager with a clear missing-install error
- [x] 2.5 Existing-session short-circuit, login page, 1s polling, `--timeout` failure, `--headless`
- [x] 2.6 One httpx validation request per site (no redirects), value-free error messages
- [x] 2.7 Sink check before the browser opens; one `write()`; default sink `bao` if `BAO_ADDR` else `secrets-file`; `apply_local_write` with the sink's `saved_at` after a bao write
- [x] 2.8 Register `aca auth session` with one line in `src/cli/app.py`

## 3. Tests (`tests/cli/test_session_commands.py`, no browser, no network)
- [x] 3.1 Context already holding cookies validates and writes once; no sentinel in output or logs (substack + x via real `BaoSink` over a fake KV v2 adapter)
- [x] 3.2 Never-produced cookies time out non-zero with a fake clock; nothing written
- [x] 3.3 Validation failure (401, login page, wrong JSON, transport error) writes nothing
- [x] 3.4 Profile dir 0700 under `browser_profiles_dir()`; root tightened; symlink refused
- [x] 3.5 X requires both cookies; no cross-domain pairs; x.com preferred over twitter.com
- [x] 3.6 Second run reuses the profile without login; default sink selection; no scheduling code

## 4. Documentation
- [x] 4.1 `docs/SETUP.md` "Substack API Setup": replace DevTools steps with the command, keep them as a fallback

## 5. Validation
- [x] 5.1 `uvx ruff@0.15.15 check/format`, `mypy`, targeted pytest, `openspec validate --strict`
- [ ] 5.2 Operator smoke test with a real headed Chromium login for Substack and X (needs a display and real accounts)
