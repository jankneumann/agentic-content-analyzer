# Document X bookmarks and the credential lifecycle

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-17`)
> Change ID: `document-x-bookmarks-and-the-credential-lifecycle`

## Why

Items ri-01 through ri-16 and ri-18 shipped a new source (`x_bookmarks`), a
capture command (`aca auth session substack|x`), session rows in
`aca auth status`, an extension **Sync session** button, a live credential
provider, paid-Substack fetching with the cookie, and a `remediation_command`
on credential alerts. The operator-facing docs still pointed at the manual
DevTools cookie copy and at `aca ingest substack-sync --session-cookie`, a
command that no longer exists and that put the cookie on argv. Without
accurate docs the operator falls back to the manual path the roadmap removes,
and the pitfalls the implementers hit (frozen `settings`, KV v2 clobbering,
the ruff pin) get rediscovered.

## What Changes

- `docs/USER_GUIDE.md`: new **Browser Sessions (Substack and X)** section
  (capture, sinks, `aca auth status [--json]`, refresh via the CLI or the
  extension, fail-closed codes, paid Substack behaviour) and **X Bookmarks**
  section (ships disabled, `aca sources enable x_bookmarks:account`,
  `aca ingest x-bookmarks` options, incremental walk, backfill cursor, Grok
  search dedup, link expansion and its cap, quiet-hour scheduling); the
  non-existent `aca ingest substack-sync` example is replaced.
- `docs/SETUP.md`: **Browser-Session Capture** replaces the DevTools fallback
  and the `--session-cookie` argv example; OpenBao session roles
  (`scripts/bao_seed_newsletter.py --with-session-roles`); the Substack
  section drops `substack-sync`; new **X Bookmarks Setup**; env reference rows
  for `SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, `X_CT0`,
  `BROWSER_PROFILES_DIR`, `SUBSTACK_REQUEST_DELAY_S`,
  `X_BOOKMARKS_PAGE_DELAY_S`, `X_BOOKMARKS_MAX_EXPANDED_LINKS`,
  `ACA_API_HOST`, `ACA_FORWARDED_ALLOW_IPS`, `ACA_BAO_BIND_ADDR`.
- `docs/MOBILE_CAPTURE.md`: bookmarking a post on X is the capture gesture
  for X content; the phone holds no credential.
- `docs/GOTCHAS.md`: frozen `settings` vs the live `CredentialProvider`; KV v2
  `create_or_update` clobbering and hvac `kv.v2.patch()`; the CI ruff pin and
  RUF102; failed-operation alert codes needing the classifier and sanitizer;
  the allowlisted public X bearer token.
- `docs/DEVELOPMENT.md`: the alert `remediation_command` field and the two
  credential codes.
- `CLAUDE.md`: Essential Commands (`aca auth session`, `aca auth status`,
  `aca ingest x-bookmarks`), `x_bookmarks.yaml` in the Sources paragraph, two
  Critical Gotchas rows (KV v2 clobbering, ruff pin), index purposes.
- `sources.d/x_bookmarks.yaml`: comments only (extension refresh, scheduling,
  link-expansion cap).

## Impact

- Documentation only; no code, contract, or migration changes.
- Spec delta: one ADDED requirement under `developer-workflow`.
- `X_BOOKMARKS_MAX_EXPANDED_LINKS` documents the setting that ri-13
  (`expand-linked-articles-from-bookmarked-posts`) adds; it must land with or
  before this change.
