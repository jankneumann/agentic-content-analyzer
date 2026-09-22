# Tasks: Introduce live credential provider for rotating secrets

> Change ID: `introduce-live-credential-provider-for-rotating-secrets`

## 1. Plan

- [x] 1.1 Trace the frozen read (`get_settings()` lru_cache -> `settings.substack_session_cookie`) and the OpenBao cache lifecycle (`_load_bao_secrets`, `_BaoTokenManager`)
- [x] 1.2 Grep every reader of `substack_session_cookie` outside settings/profile plumbing (only `src/ingestion/substack.py`; the orchestrator forwards an explicit override)
- [x] 1.3 Move the spec delta to `browser-session-credentials` (new) and `openbao-secrets`

## 2. Implement

- [x] 2.1 `bao_secrets`: keep client + location after load; `get_bao_secrets()`, `refresh_bao_secrets(min_interval_s)`, `apply_bao_local_write(mapping)`; token manager fetches and swaps under `_bao_lock`
- [x] 2.2 `src/config/credentials.py`: explicit registry, `CredentialProvider.get/metadata/mark_verified/refresh/apply_local_write`, `get_credential_provider()`
- [x] 2.3 `Settings.x_auth_token` / `x_ct0`; `repr=False` on all three browser-session fields; wire `profiles/base.yaml`
- [x] 2.4 `is_secret_key()` masks `*_COOKIE` and `X_CT0`
- [x] 2.5 `SubstackClient` / `SubstackContentIngestionService` resolve `substack.sid` through the provider before each HTTP request; exception text no longer logged on the HTTP fallbacks

## 3. Test

- [x] 3.1 A token-manager refresh against a fake hvac client makes a long-lived provider return the rotated cookie and its new `saved_at`, with no new `Settings`
- [x] 3.2 `refresh()` works for token and AppRole auth, reuses the client, re-authenticates once on failure, recovers from a failed boot load, and is rate limited (including failed attempts and 10 concurrent callers)
- [x] 3.3 `apply_local_write()` is visible without an OpenBao read, stamps `saved_at`, keeps sibling keys, leaves older snapshots untouched, and refuses unregistered keys
- [x] 3.4 Settings fallback when OpenBao is unconfigured or unreadable; empty profile values are absent
- [x] 3.5 `metadata()` for `substack.sid`, `x.auth_token`, `x.ct0`; `last_verified_at` clears on rotation and is never written to OpenBao
- [x] 3.6 `SubstackClient` sends the rotated cookie on the next request (httpx `MockTransport`); explicit override and settings fallback still work
- [x] 3.7 No credential value appears in any captured log record in the provider and adapter tests
- [x] 3.8 Existing `tests/test_config/test_bao_secrets.py`, `test_bao_settings_integration.py`, `tests/cli/test_secret_sinks.py`, orchestrator, CLI and config suites pass unchanged
