# Design: Add browser-session rows to aca auth status

## D1. `last_verified_at` comes from the ingestion history

`CredentialProvider.mark_verified()` (ri-04) keeps `last_verified_at` in the
worker's memory only, bound to a digest of the value, so a separate `aca` process
can never see it. Writing a verification timestamp to OpenBao on every run was
rejected in ri-04 (a secret-store write per ingestion, and `patch` capability on
the worker role).

The durable, cross-process record that already exists is the compact ingestion
history projected from `pgqueuer_jobs` (`OperationService.list_ingestion_history`,
`GET /api/v1/ingestions`). A session's `last_verified_at` is the `completed_at` of
the most recent ingestion of the gated `command_key` whose outcome is `success` or
`zero_items`:

- `success` and `zero_items` both mean the source ran to completion against the
  remote site. Once ri-05 lands, readiness fails closed with a stable code on a
  missing or expired session, so such a run implies the session was accepted.
- `partial`, `failed`, `cancelled` and `unknown` are excluded: some part of the run
  failed, possibly on the session.
- Two `limit=1` queries (one per outcome) and the later `completed_at` wins. The
  history is ordered by `created_at`, so a run that started earlier but finished
  later than another could in theory be missed; for one scheduled source this is
  immaterial.
- `x_bookmarks` does not exist yet as a source kind. The history filter accepts any
  command key, so the lookup simply finds nothing and reports "never".

Caveat, surfaced in the text output: the timestamp proves the session that was
current at that run worked. When `saved_at` is later, the current value has not
been verified yet.

## D2. Route like other read commands; never fail

`is_remote_backend() and not is_direct_mode()` -> HTTP (`WorkflowApiClient`,
admin key from settings); otherwise the local queue database through
`OperationService`, the same split `kb` read commands use. `--direct` under a
remote profile without `--remote-db` is refused for this lookup (reported as
unknown) instead of silently reading local data. The database path uses a
throwaway cursor-signing key, because cursors never leave the process and a local
profile may have no `OPERATION_CURSOR_SIGNING_KEY`.

Every failure (connection refused, bad password, 5s timeout, HTTP problem) becomes
`last_verified_status: "unknown"` with the exception type only as the reason, on
stderr. The rest of the status still prints and the command exits 0.

## D3. Source labels

Provider metadata reports `openbao` or `settings`. The row refines `settings` to
`env` when the variable is set in the process environment (environment variables
win inside `Settings`), so operators can tell a shell export from a profile or
`.secrets.yaml` value. A pair from different sources is `mixed`; per-credential
sources are in `credentials[]`.

## D4. JSON shape and value safety

`{"oauth": [...], "browser_sessions": [...], "last_verified_lookup": {...}}` on one
line. Rows are built from metadata objects that never hold a value; the Railway
listing (which contains values) is reduced to booleans before it reaches a row.
Tests plant sentinel values in OpenBao and in the Railway listing and assert none
of them reaches stdout or stderr in either mode, including the DB-down path.

## Non-goals

- Probing the remote sites from `aca auth status` (that would make status a
  network client of Substack/X and could itself trip rate limits).
- Persisting `last_verified_at` anywhere new.
- The `aca auth session` command itself (ri-08).
