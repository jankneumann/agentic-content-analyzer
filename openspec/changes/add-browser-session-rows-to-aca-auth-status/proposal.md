# Add browser-session rows to aca auth status

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-06`, effort S, priority 5)
> Depends on: `ri-04` (`introduce-live-credential-provider-for-rotating-secrets`)

## Why

Browser-session cookies (`substack.sid`, X `auth_token` + `ct0`) expire on the
remote site's schedule, not ours. Until the terminal-event outbox exists,
`aca auth status` is the one place an operator can see that a session is missing
or stale and which command refreshes it. Today it only reports Gmail/YouTube OAuth
files, and it has no machine-readable output.

## What Changes

- `aca auth status` gains a "Browser session status" section with one row per
  session: `substack` (`SUBSTACK_SESSION_COOKIE`) and `x` (`X_AUTH_TOKEN` +
  `X_CT0`, present only when both are). Each row shows present/missing, source
  (`openbao` / `env` / `settings`, `mixed` for a split pair), `saved_at` (from
  `<KEY>_SAVED_AT` via `CredentialProvider.metadata()`), `last_verified_at`, and the
  refresh command `aca auth session substack|x`.
- `last_verified_at` is derived from the durable ingestion history
  (`pgqueuer_jobs`, via `OperationService.list_ingestion_history` or
  `GET /api/v1/ingestions` under a remote profile): the completion time of the
  latest `success`/`zero_items` ingestion of the gated source (`substack`,
  `x_bookmarks`). Unreachable history yields `unknown`; the command still exits 0.
- `aca auth status --json` (and the global `aca --json auth status`) prints one
  JSON document (`oauth`, `browser_sessions`, `last_verified_lookup`) on stdout;
  diagnostics go to stderr. No credential value or Railway variable value is ever
  emitted.

## Impact

- Code: new `src/cli/browser_session_status.py`; `auth status` in
  `src/cli/auth_commands.py` split into row builders plus text/JSON renderers
  (existing text output unchanged).
- Specs: `cli-interface` (ADDED requirements).
- Tests: `tests/cli/test_auth_status_sessions.py`,
  `tests/integration/test_auth_status_last_verified.py`; the existing
  `tests/test_cli/test_auth_commands.py` stubs the history lookup to stay hermetic.
- No schema, contract, or migration change. No new secret access: the command
  reads the same OpenBao/settings sources the worker does.
