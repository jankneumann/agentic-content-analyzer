# Add secret sink abstraction to the auth CLI

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-02`)
> Change ID: `add-secret-sink-abstraction-to-the-auth-cli`
> Effort: M · Priority: 1 · Depends on: none

## Why

`aca auth gmail|youtube --deploy` can only push a freshly minted OAuth token to
Railway. The project is moving to OpenBao on gx-10, whose background token manager
re-fetches exactly one KV v2 path (`secret/newsletter`). A credential written anywhere
else, or written with a full-document `create_or_update`, either never reaches a
running worker or clobbers the LLM keys stored alongside it. Every later credential
write in this roadmap (Substack `substack.sid`, the X `auth_token`/`ct0` pair,
adapter write-back of rotated `ct0`) needs the same write path, so it belongs behind
one small abstraction rather than per-command Railway calls.

## What Changes

- New `src/cli/secret_sinks.py` with a `SecretSink` protocol
  (`name`, `target`, `next_step_hint`, `check()`, `write(mapping) -> key names`) and
  three implementations:
  - `RailwaySink` wraps `src/cli/railway.py` (`set_variables`, `linked_target`) and
    prints the linked-target notice that `--deploy` printed.
  - `BaoSink` sends one server-side KV v2 `PATCH` (`application/merge-patch+json`)
    to `BAO_MOUNT_PATH`/`BAO_SECRET_PATH` (default `secret/newsletter`), adding a
    `<KEY>_SAVED_AT` ISO-8601 UTC sibling per key. It never calls
    `create_or_update_secret`, never reads the path, and fails with a clear message
    when the path does not exist rather than creating it.
  - `SecretsFileSink` upserts keys into `.secrets.yaml` (`SECRETS_FILE`) in place,
    preserving other keys and comments, and writes atomically with mode 0600.
- `aca auth gmail|youtube` gain `--to railway|bao|secrets-file`. `--deploy` stays
  for one release as a deprecated alias for `--to railway` and prints a
  deprecation warning to stderr. With neither flag, behaviour is unchanged: the
  token is saved locally and nothing is pushed.
- The sink is checked before the OAuth flow starts, so a bad OpenBao configuration
  or a missing `railway` CLI fails before the operator clicks through consent.
- `saved_at_key()` / `SAVED_AT_SUFFIX` in `src/config/secrets.py` name the
  `saved_at` sibling for the later credential provider (ri-04).
- `settings/deploy/railway_secrets.yaml` lists `SUBSTACK_SESSION_COOKIE`,
  `X_AUTH_TOKEN`, and `X_CT0` for the interim (worker inherits via `extends`).
- Docs: `docs/OPENBAO.md`, `docs/SETUP.md`, `docs/USER_GUIDE.md`,
  `docs/DEPLOY_SECRETS.md`.

Out of scope: AppRole policies (ri-03), the live credential provider (ri-04), and
browser-session capture (ri-06).

## Impact

- Affected specs: `openbao-secrets`, `cli-interface`, `railway-secrets-sync`
  (all ADDED requirements).
- Affected code: `src/cli/secret_sinks.py` (new), `src/cli/auth_commands.py`,
  `src/config/secrets.py`, `src/cli/manage_commands.py` (docstring),
  `settings/deploy/railway_secrets.yaml`, `tests/cli/test_secret_sinks.py` (new).
- Compatibility: existing `--deploy` invocations keep working and issue the same
  `railway variables --set` calls. The Railway target notice now prints before the
  OAuth flow instead of after it.

## Acceptance Outcomes

- `aca auth gmail --to bao` writes only `GMAIL_OAUTH_TOKEN_JSON` (plus its
  `_SAVED_AT` sibling) and leaves every other key at `secret/newsletter`
  byte-identical, proven by a test against a fake KV v2 client.
- The railway sink behaves exactly as `--deploy` did, and `--deploy` remains as a
  deprecated alias that emits a deprecation warning for one release.
- Gmail and YouTube OAuth flows accept `--to bao` with no provider-specific code.
- `settings/deploy/railway_secrets.yaml` lists `SUBSTACK_SESSION_COOKIE`,
  `X_AUTH_TOKEN`, and `X_CT0`.
