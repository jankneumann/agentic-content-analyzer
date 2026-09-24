# Tasks: Add admin endpoint for browser-session sync

> Change ID: `add-admin-endpoint-for-browser-session-sync`

## 1. Plan
- [x] 1.1 Refine proposal, design and the `browser-session-credentials` spec delta against `BaoSink`, the credential provider, the CLI validators, audit/auth middleware and the contract precedent

## 2. Implementation
- [x] 2.1 Move the Substack/X validators to `src/ingestion/browser_session_validation.py` (value-free `SessionValidationError` with `reason`/`status_code`); CLI imports them
- [x] 2.2 `BaoSink(echo=...)` so the server can silence the stdout success line
- [x] 2.3 `src/services/browser_session_sync.py`: OpenBao requirement check, sink check, one validation request, one `BaoSink.write()`, `apply_local_write` with the same `saved_at`
- [x] 2.4 `src/api/browser_session_routes.py`: strict `SecretStr` bodies, header-only admin guard, body cap, rate limit, typed problem responses, `@audited`
- [x] 2.5 Register the router in `src/api/app.py`; add the prefix to `_PROBLEM_PATH_PREFIXES`; document it in `ENDPOINT_AUTH_MAP`
- [x] 2.6 Exclude the routes from mutating fuzz tests

## 3. Tests (`tests/api/test_browser_session_routes.py`, network-free)
- [x] 3.1 401 without a key and 403 with a bad key, each with an audit row (`admin_key_fp`, `auth_failure`)
- [x] 3.2 Web-UI session cookie and the dev no-key bypass are refused
- [x] 3.3 Happy path (x, substack): one validation request, one merge-PATCH on a fake KV v2 adapter, siblings byte-identical, cache updated with the same `saved_at`, audit operation/notes
- [x] 3.4 Invalid session (401, redirect, login page, wrong JSON) is 422 `session_invalid`; site 429/503 and transport errors are 502; nothing written
- [x] 3.5 OpenBao unconfigured is 503 `openbao_not_configured` with no outbound request; OpenBao refusal is 502 with a value-free hint
- [x] 3.6 Extra/missing fields, bad cookie characters, empty and oversized values are 422 without echoing input; body over 16 KiB is 413; rate limit is 429
- [x] 3.7 No sentinel value in responses, logs, audit rows or OpenAPI; cookie fields are `writeOnly` with no examples

## 4. Documentation
- [x] 4.1 `docs/TAILNET.md` "Browser-session sync endpoint"; link from `docs/OPENBAO.md`

## 5. Validation
- [x] 5.1 `uvx ruff@0.15.15 check/format`, `mypy`, targeted pytest (routes, CLI, sinks, audit, contract drift, fuzz), `openspec validate --strict`
- [ ] 5.2 Live check on gx-10: a real OpenBao PATCH through the API with the `newsletter-app` AppRole (needs the host)
