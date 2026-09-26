# Learning Log

| Item | Status | Summary |
|------|--------|--------|
| ri-02 | implementation | src/cli/secret_sinks.py: RailwaySink, BaoSink, SecretsFileSink; write(mapping) r |
| ri-09 | implementation | strict, kind-only required; max_items 1..10000, full (default false), expand_lin |
| ri-04 | implementation | src/config/credentials.py get_credential_provider(): get(name) reads the OpenBao |
| ri-05 | implementation | 401; 403 without cf-mitigated; redirect to /sign-in or /account/login; 2xx text/ |
| ri-11 | implementation | newest-first pages by cursor-bottom, stop_when(page_ids) hook, page cap, x_bookm |
| ri-10 | implementation | XBookmarksSource always keys as x_bookmarks:account (X_BOOKMARKS_LOCATOR); aca s |
| ri-12 | implementation | XBookmarksIngestionService walks every page before writing; credential failure o |
| ri-01 | implementation | API (systemd aca-api.service, ACA_API_HOST=127.0.0.1) and OpenBao (deploy/gx10/d |
| ri-03 | implementation | newsletter-session-writer grants only patch on secret/data/newsletter; AppRole n |
| ri-13 | implementation | src/queue/follow_up_operations.py: the canonical ingestion handler lends its run |
| ri-06 | implementation | completed_at of the latest success or zero_items run of the gated source (substa |
| ri-16 | implementation | classify_terminal_event classified failed operations from status alone as operat |
| ri-07 | implementation | src/config/browser_profiles.py owns DEFAULT_BROWSER_PROFILES_DIR, browser_profil |
| ri-08 | implementation | src/cli/session_commands.py: Playwright launch_persistent_context on browser_pro |
| ri-17 | implementation | Browser Sessions and X Bookmarks sections in USER_GUIDE; capture, sinks, env/set |
| ri-14 | implementation | PUT /api/v1/browser-sessions/substack {substack_sid} and /x {auth_token, ct0}; S |
| ri-15 | implementation | extension/session_sync.js holds cookie reading, permission origin, https check,  |
| ri-18 | implementation | the library can only authenticate from a cookies file on disk; _fetch_archive an |
