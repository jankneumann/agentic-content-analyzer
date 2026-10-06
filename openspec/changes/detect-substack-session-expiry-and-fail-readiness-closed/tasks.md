# Tasks: Detect Substack session expiry and fail readiness closed

> Change ID: `detect-substack-session-expiry-and-fail-readiness-closed`

## 1. Plan

- [x] 1.1 Trace where `substack.sid` is sent (httpx subscriptions + archive fallback only; the substack-api library path is unauthenticated)
- [x] 1.2 Trace how readiness and typed failures surface (`ConfiguredSourceReadiness`, `CapabilityService`, workflow handler, `result_sanitizer`)
- [x] 1.3 Enumerate closed code lists; decide which belong here and which to ri-16
- [x] 1.4 Move the spec delta to `browser-session-credentials` and `source-capability-registry`

## 2. Implement

- [x] 2.1 `src/ingestion/credential_failures.py`: codes, `CredentialFailureError`, `SessionExpiredError`
- [x] 2.2 `CredentialProvider.mark_rejected()` and `CredentialMetadata.rejected_at`
- [x] 2.3 `is_dead_session_response()`, `_get_with_session()` with one refresh and one retry, `verify_session()`
- [x] 2.4 `ingest_content()` probes, fetches everything, then persists; `SessionExpiredError` returns a zero-row `session_expired` error envelope
- [x] 2.5 Cookie-less run adds a `credentials_missing` warning; subscriptions raise instead of returning `[]`
- [x] 2.6 `_substack_readiness` on the `substack` descriptor, read through the provider
- [x] 2.7 Add both codes to the sanitizer's closed vocabulary

## 3. Test

- [x] 3.1 Predicate table (401, 403, Cloudflare 403, sign-in redirects, HTML 200, 404/429/5xx)
- [x] 3.2 Login redirect, HTML login page, 401: refresh once, retry with the refreshed cookie, still dead, `session_expired`, `get_db` never opened
- [x] 3.3 Unchanged cookie after refresh fails without a second request; explicit override is not refreshed or recorded
- [x] 3.4 A session dying mid-run (archive redirect after an inconclusive probe) still persists zero rows
- [x] 3.5 Refreshed cookie recovers the run, rows are persisted, `mark_verified` recorded; public archive success does not verify
- [x] 3.6 Readiness: `credentials_missing` without a cookie, `session_expired` after a rejection, ready again after a fresh cookie is patched (fake provider and real `bao_secrets` cache)
- [x] 3.7 No cookie value in any response, exception, or captured log record
- [x] 3.8 Durable projection keeps `session_expired` / `credentials_missing`
- [x] 3.9 Existing Substack, credential, orchestrator, sanitizer, capability, contract suites pass

## 4. Follow-ups (not in this change)

- [ ] 4.1 ri-16: add `session_expired` (and `credentials_missing`) to `WorkflowAlertDiagnosticCode` and the alert schema enum together
- [ ] 4.2 Route the substack-api library path through the authenticated client, then revisit failing closed without a cookie
- [ ] 4.3 Remove the legacy `session_cookie` operation-payload override
