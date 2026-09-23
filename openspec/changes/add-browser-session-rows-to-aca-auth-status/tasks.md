# Tasks: Add browser-session rows to aca auth status

> Change ID: `add-browser-session-rows-to-aca-auth-status`

## 1. Plan
- [x] 1.1 Confirm ri-04 provider metadata (`present`, `source`, `saved_at`) and that `last_verified_at` is in-process only
- [x] 1.2 Choose the durable `last_verified_at` source (ingestion history in `pgqueuer_jobs`) and record it in design.md
- [x] 1.3 Move the spec delta to `cli-interface`

## 2. Implement
- [x] 2.1 `src/cli/browser_session_status.py`: session specs (substack, x), row builder, text renderer
- [x] 2.2 Durable lookup: HTTP `/api/v1/ingestions` under a remote profile, `OperationService` otherwise, 5s bound, never raises
- [x] 2.3 `aca auth status`: split OAuth rows from rendering, add browser-session section, add `--json` (also honors global `--json`), diagnostics on stderr

## 3. Test
- [x] 3.1 Rows render with sentinel secrets never printed (text and JSON, incl. Railway listing)
- [x] 3.2 X row requires both keys; mixed sources; env vs settings source
- [x] 3.3 `saved_at` parsing (Z, offset, naive, garbage, empty)
- [x] 3.4 DB-down, timeout, and remote-profile `--direct` paths report unknown and exit 0
- [x] 3.5 JSON shape: one document, expected keys; global `--json`
- [x] 3.6 HTTP lookup via `httpx.MockTransport` (absent filters omitted from the URL)
- [x] 3.7 Real-Postgres integration test of the history lookup (rolled back)
- [x] 3.8 Keep the existing auth CLI tests hermetic (stub the lookup)

## 4. Validate
- [x] 4.1 `uvx ruff@0.15.15 check` / `format` on changed files
- [x] 4.2 `mypy` on changed src files
- [x] 4.3 Targeted pytest
- [x] 4.4 `openspec validate add-browser-session-rows-to-aca-auth-status --type change --strict`
