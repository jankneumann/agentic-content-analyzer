# Validation Report: add-notification-events

**Date**: 2026-02-25 03:00:00
**Commit**: 0110a50
**Branch**: openspec/add-notification-events
**PR**: #221

## Phase Results

### ✓ Deploy: Services started successfully
- PostgreSQL (pgvector/pgvector:pg17) — healthy
- Neo4j 5 — healthy
- API (uvicorn from worktree) — running on port 8000
- Alembic migrations applied: `da8203070ef9` (notification tables)
- Health: 200, Ready: 200

### ✓ Smoke Tests: 33/39 passed, 4 expected failures, 2 skipped

**Notification-specific tests (16/16 PASS):**
- Event list: returns 200, correct shape (events array, total, pagination)
- Event list: accepts pagination and type filter params
- Unread count: returns 200, correct shape (count integer >= 0)
- Mark all read: returns 200
- Mark nonexistent event read: returns 404 (not 500)
- Device registration lifecycle: create → list (found) → delete (200)
- Device missing fields: returns 422
- Delete nonexistent device: returns 404
- Preferences list: returns 200, 7 event types configured
- Preferences shape: event_type, enabled, source fields present
- Update/reset preference: 200, source returns to "default"
- Invalid event type: rejected (not 500)
- SSE stream: connects, returns text/event-stream content-type
- SSE no auth: does not return 500

**Generic smoke tests:**
- Health/Ready: PASS (3/3)
- CORS: PASS (5/5)
- Error sanitization: PASS (4/4)
- Security headers: PASS (2/3, 1 skipped)
- Auth enforcement: FAIL (4/4) — **Expected in dev mode** (`ENVIRONMENT=development` bypasses auth)

### ⚠ E2E Tests: 1104 passed, 149 failed, 37 skipped (17.7 min)

**No notification-specific test failures.** All 149 failures are pre-existing:
- Accessibility (axe-core): ~38 failures (30s timeouts)
- Theme toggle: ~24 failures (UI timing)
- Auth/login: ~21 failures (route mocking)
- Job resume: ~17 failures (API mocking)
- Review layouts: ~16 failures (two-pane rendering)
- Telemetry: ~12 failures (30s timeouts)
- Other: ~21 failures (scripts, contents, settings, PWA)

### ○ Architecture: SKIPPED
Architecture graph (`architecture.graph.json`) and validation script (`validate_flows.py`) not present. Manual architecture review performed via code exploration.

### ⚠ Spec Compliance: 31/38 passed, 1 failed, 6 N/A

**Failed scenario:**
- **`pipeline_completion` event never emitted** — The event type is defined in `NotificationEventType` and available in preferences, but `src/cli/pipeline_commands.py` does not import or use the notification dispatcher. Individual pipeline steps (digest_creation, batch_summary, etc.) emit their own events, but the composite pipeline-level event is missing.

**N/A scenarios (6):** Frontend UI scenarios (bell rendering, dropdown, navigation) — not testable via API. Backend data endpoints confirmed working.

**Note:** Auth enforcement scenarios cannot be fully verified against dev-mode instance (auth bypass by design in `ENVIRONMENT=development`).

### ✓ Log Analysis: Clean
- 1198 log lines collected
- 10 warnings (4 collation mismatch, 1 WatchFiles reload, 5 deprecation)
- 0 errors, 0 criticals, 0 tracebacks
- Deprecation warnings are pre-existing (`datetime.utcnow()` in theme_routes.py, digest_routes.py, and dependencies)
- No notification-specific warnings or errors

### ⚠ CI/CD: Core checks passing, non-blocking failures

| Check | Status | Notes |
|-------|--------|-------|
| lint | PASS | |
| test | PASS | 1m 45s |
| validate-profiles | PASS | |
| contract-test | FAIL | Timed out (6h) — known systemic issue |
| SonarCloud | FAIL | Needs dashboard investigation |
| Railway preview | FAIL | Non-blocking (expected for PR previews) |
| Neon PR branch | SKIPPING | Expected — Neon workflow skipped |

### ✓ Unit/Integration Tests: 61/61 passed (1.70s)

| Test File | Tests | Result |
|-----------|-------|--------|
| test_notification_service.py | 20 | PASS |
| test_notification_cleanup.py | 4 | PASS |
| test_notification_api.py | 21 | PASS |
| test_notification_preferences_api.py | 16 | PASS |

## Findings Summary

### Must Fix (1)
1. **`pipeline_completion` event not emitted** — Add notification emission to `src/cli/pipeline_commands.py` after full pipeline run completes. The event type and infrastructure exist; only the emission call is missing.

### Non-Blocking (Pre-existing)
- Auth smoke tests fail in dev mode (by design)
- 149 E2E test failures are all pre-existing (not notification-related)
- `contract-test` CI timeout is a known systemic issue
- SonarCloud and Railway preview failures are non-blocking
- `datetime.utcnow()` deprecation warnings in theme_routes.py, digest_routes.py

## New Test Assets
- `test_notifications.py` added to `.claude/skills/validate-feature/scripts/smoke_tests/` — 16 reusable notification endpoint tests

## Result

**PASS WITH CAVEAT** — All notification endpoints, SSE streaming, device registration, preferences, cleanup, and unit tests verified. One spec gap found: `pipeline_completion` event emission missing from pipeline CLI.

### Recommended Next Steps
1. Fix `pipeline_completion` emission in `src/cli/pipeline_commands.py` (quick fix)
2. Investigate SonarCloud findings for PR #221
3. Proceed to `/cleanup-feature add-notification-events` after fixing

---
_Generated by `/validate-feature add-notification-events` at 2026-02-25_
