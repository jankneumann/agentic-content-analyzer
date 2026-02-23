# Security Review Report

## Run Context

- Change ID: `add-voice-input`
- Commit SHA: `b53cc15046422bcb6f75c573d517eb276e25de38`
- Timestamp: 2026-02-23T01:18:51+00:00
- Profile: `mixed`
- Confidence: `high`

## Gate Summary

- Decision: **PASS**
- Fail threshold: `high`
- Triggered findings: `0`

## Scanner Results

| Scanner | Status | Notes |
|---|---|---|
| dependency-check | error | native dependency-check failed (exit 13); docker fallback failed (exit 13) |
| zap | unavailable | DAST profile requires --zap-target for ZAP execution |
| manual-code-review | complete | Full review of all changed files (25 files across backend + frontend) |

## Severity Summary

- Total findings: `3` (all Low/Info)
- Critical: `0`
- High: `0`
- Medium: `0`
- Low: `2`
- Info: `1`

## Gate Reasons

- Degraded automated execution (dependency-check + ZAP unavailable)
- Manual code review covers all new endpoints and frontend components
- No high/critical findings — gate passes

## Manual Code Review Findings

### Finding 1: No endpoint-specific rate limiting on LLM cleanup (Low)

- **File**: `src/api/voice_cleanup_routes.py:48-87`
- **Severity**: Low
- **Description**: The `/api/v1/voice/cleanup` endpoint calls an LLM on every request. While protected by AuthMiddleware (session or API key), there is no per-endpoint rate limit. A compromised session could trigger excessive LLM costs.
- **Mitigation**: Auth is required (dual-auth: middleware + dependency). Single-owner deployment model limits exposure. Max input is 10,000 chars.
- **Recommendation**: Consider adding a simple in-memory rate limiter (similar to `LoginRateLimiter`) if abuse becomes a concern.

### Finding 2: `os.environ.get()` instead of `get_settings()` in voice settings (Low)

- **File**: `src/api/voice_settings_routes.py:123-124`
- **Severity**: Low
- **Description**: `_resolve_voice_setting()` uses `os.environ.get()` to check if env vars are set, bypassing the Settings/profile precedence chain. This is intentional (checking if env var is explicitly set to block DB overrides), but inconsistent with the integration test fixture convention.
- **Mitigation**: The check is specifically about "is the env var physically set?" which `os.environ.get()` correctly answers. This doesn't leak data or bypass auth.
- **Recommendation**: Document the intentional use of `os.environ.get()` with a code comment.

### Finding 3: Voice transcript forwarded to LLM without sanitization (Info)

- **File**: `src/api/voice_cleanup_routes.py:67-69`
- **Severity**: Info
- **Description**: User-provided text is passed directly to `LLMRouter.generate()` as `user_prompt`. This is technically an LLM prompt injection surface — a crafted input could attempt to override the system prompt.
- **Mitigation**: The system prompt is hardcoded (not user-configurable), the response is rendered as plain text in a textarea (no HTML/JS execution), and the endpoint requires authentication. The attack surface is text-in/text-out with no side effects beyond the response content.
- **Recommendation**: Acceptable as-is. Standard practice for LLM text processing endpoints.

## Authentication & Authorization Review

| Endpoint | Auth Middleware | Route Dependency | Status |
|---|---|---|---|
| `POST /api/v1/voice/cleanup` | AuthMiddleware (not exempt) | `verify_admin_key` | Protected (dual auth) |
| `GET /api/v1/settings/voice` | AuthMiddleware (not exempt) | `verify_admin_key` | Protected (dual auth) |
| `PUT /api/v1/settings/voice/{field}` | AuthMiddleware (not exempt) | `verify_admin_key` | Protected (dual auth) |
| `DELETE /api/v1/settings/voice/{field}` | AuthMiddleware (not exempt) | `verify_admin_key` | Protected (dual auth) |

- `ENDPOINT_AUTH_MAP` updated at `dependencies.py:42` to document voice routes
- No routes are in `AUTH_EXEMPT_PREFIXES` — all require authentication

## Input Validation Review

| Input | Validation | Location |
|---|---|---|
| `CleanupRequest.text` | `min_length=1, max_length=10000` | `voice_cleanup_routes.py:39` |
| `VoiceUpdateRequest.value` | `min_length=1` | `voice_settings_routes.py:62` |
| `update_voice_setting(field)` | Allowlist check against `_VOICE_SETTINGS` keys | `voice_settings_routes.py:194` |
| Provider value | Allowlist: `["openai", "elevenlabs"]` | `voice_settings_routes.py:210` |
| Speed value | Float range: `0.5 <= speed <= 2.0` | `voice_settings_routes.py:216-226` |
| Language value | Allowlist: 7 BCP-47 tags | `voice_settings_routes.py:228` |
| Boolean fields | Allowlist: `["true", "false"]` | `voice_settings_routes.py:234` |

## Frontend Security Review

- Web Speech API runs entirely in browser — no audio sent to backend
- Only final transcript text sent to cleanup endpoint via authenticated `apiClient`
- No `dangerouslySetInnerHTML` or innerHTML usage — all text rendered safely
- Synthetic `onChange` events in `search-input.tsx:26-29` are safe (typed as `React.ChangeEvent`)
- Voice settings fetched via authenticated API — no local storage of credentials

## Dependency Review

- **No new packages added** to `pyproject.toml`
- `ModelStep.VOICE_CLEANUP` added to existing `StrEnum` — no DB migration needed (config-only, not a PG enum)
- Frontend uses existing `lucide-react` icons and `sonner` toasts — no new npm dependencies

## Error Handling Review

- LLM failures return `502` with generic message: `"Voice cleanup service is temporarily unavailable"` — no stack traces or API keys leaked
- Empty/None LLM responses fall back to original text (safe default)
- Pydantic validation errors return standard `422` with field-level details (no sensitive info)
- `logger.exception()` logs full error server-side for debugging

## Test Coverage

- `tests/api/test_voice_cleanup_api.py`: 6 tests (success, empty input, missing field, model step, LLM error, empty response, None response)
- `tests/api/test_voice_settings_api.py`: 17 tests (GET defaults, DB override, PUT all fields, invalid values, env var blocking, DELETE/reset)
- `web/tests/e2e/settings/voice.spec.ts`: 9 E2E tests (UI rendering, presets, badges, error state, voice input section)
