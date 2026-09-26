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
