## ADDED Requirements

### Requirement: Browser-Session Credential Lifecycle Is Documented

The project documentation SHALL describe how to capture, check, and refresh the
Substack and X browser sessions and how to enable and run the X bookmarks
source, using only commands and settings that exist in the code. It SHALL NOT
instruct the operator to copy cookies out of DevTools or to pass a cookie value
as a command-line argument.

#### Scenario: Operator sets up a browser session
- **WHEN** an operator reads `docs/SETUP.md`
- **THEN** it SHALL document `aca auth session substack|x` with its `--to bao|railway|secrets-file` sinks and the OpenBao session roles seeded by `scripts/bao_seed_newsletter.py --with-session-roles`
- **AND** it SHALL list `X_AUTH_TOKEN`, `X_CT0`, `BROWSER_PROFILES_DIR`, `SUBSTACK_REQUEST_DELAY_S`, `X_BOOKMARKS_PAGE_DELAY_S`, `X_BOOKMARKS_MAX_EXPANDED_LINKS`, `ACA_API_HOST`, `ACA_FORWARDED_ALLOW_IPS` and `ACA_BAO_BIND_ADDR`
- **AND** it SHALL NOT contain a `--session-cookie` argument example

#### Scenario: Operator enables X bookmarks
- **WHEN** an operator reads `docs/USER_GUIDE.md`
- **THEN** it SHALL state that the source ships disabled, show `aca sources enable x_bookmarks:account` and `aca ingest x-bookmarks` with `--full`, `--max-items` and `--expand-links`, and describe the backfill cursor and the `credentials_missing` / `session_expired` codes

#### Scenario: Operator captures X content from a phone
- **WHEN** an operator reads `docs/MOBILE_CAPTURE.md`
- **THEN** it SHALL state that bookmarking a post on X is the capture gesture for X content once the source is enabled, and that the phone holds no credential

#### Scenario: Contributor looks for credential pitfalls
- **WHEN** a contributor reads `docs/GOTCHAS.md`
- **THEN** it SHALL contain entries for frozen `settings` versus the live credential provider and for KV v2 `create_or_update` clobbering sibling keys
