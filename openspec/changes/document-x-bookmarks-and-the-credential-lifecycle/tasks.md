# Tasks: Document X bookmarks and the credential lifecycle

> Change ID: `document-x-bookmarks-and-the-credential-lifecycle`

## 1. Plan
- [x] 1.1 Read the roadmap proposal, every host-ledger learning, and the shipped commits (`git log 95348cb^..HEAD`)
- [x] 1.2 Verify commands and flags from `--help` (`aca auth session`, `aca auth status`, `aca ingest x-bookmarks`, `aca sources`) and settings from `src/config/settings.py`
- [x] 1.3 Move the spec delta to `developer-workflow` and drop the placeholder capability

## 2. User and setup docs
- [x] 2.1 `docs/USER_GUIDE.md`: Browser Sessions and X Bookmarks sections, source tree, ingest list, troubleshooting; remove `aca ingest substack-sync`
- [x] 2.2 `docs/SETUP.md`: Browser-Session Capture (sinks, OpenBao session roles, argv risk, extension fallback), Substack and X Bookmarks setup, env reference rows; remove the DevTools fallback and `--session-cookie`
- [x] 2.3 `docs/MOBILE_CAPTURE.md`: bookmark on X as the X capture gesture
- [x] 2.4 `sources.d/x_bookmarks.yaml`: comment updates only

## 3. Engineering docs
- [x] 3.1 `docs/GOTCHAS.md`: five entries (frozen settings, KV v2 clobbering, ruff pin, alert codes, public X bearer token)
- [x] 3.2 `docs/DEVELOPMENT.md`: `remediation_command` and credential codes
- [x] 3.3 `CLAUDE.md`: Essential Commands, Sources paragraph, index purposes, two Critical Gotchas rows

## 4. Validate
- [x] 4.1 Every relative Markdown link and anchor added resolves
- [x] 4.2 Docs-related tests pass (`tests/unit/test_capture_consumer_contracts.py`, `tests/test_scripts/test_gx10_tailnet_exposure.py`)
- [x] 4.3 `openspec validate document-x-bookmarks-and-the-credential-lifecycle --type change --strict`
