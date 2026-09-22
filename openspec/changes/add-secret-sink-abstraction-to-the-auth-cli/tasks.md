# Tasks: Add secret sink abstraction to the auth CLI

> Change ID: `add-secret-sink-abstraction-to-the-auth-cli`

## 1. Plan

- [x] 1.1 Verify the current `--deploy` path (`src/cli/auth_commands.py`, `src/cli/railway.py`) and the OpenBao client (`src/config/bao_secrets.py`)
- [x] 1.2 Confirm that hvac's `kv.v2.patch()` is client-side read + `create_or_update_secret` (hvac 2.4.0 source), and choose a raw server-side PATCH instead (design D1)
- [x] 1.3 Move the spec delta to `openbao-secrets`, `cli-interface`, and `railway-secrets-sync`

## 2. Implement

- [x] 2.1 Add `src/cli/secret_sinks.py`: the `SecretSink` protocol, `SinkName`, `SecretSinkError`, and `build_sink`
- [x] 2.2 `RailwaySink`: `ensure_railway_cli` and the linked-target notice in `check()`, one `set_variables` call per `write()`, key-name-only echo
- [x] 2.3 `BaoSink`: env-driven mount and path, fail-fast client auth, merge-patch PATCH, `<KEY>_SAVED_AT` siblings, 404/403/401/405 mapped to actionable errors, no create
- [x] 2.4 `SecretsFileSink`: in-place upsert that keeps comments, round-trip verification with a full-dump fallback, atomic 0600 write, refuses malformed files
- [x] 2.5 Add `saved_at_key()` / `SAVED_AT_SUFFIX` to `src/config/secrets.py`
- [x] 2.6 `aca auth gmail|youtube --to railway|bao|secrets-file`; `--deploy` as a deprecated alias with a stderr warning; conflicting-flag and `--service` validation; sink checked before OAuth
- [x] 2.7 Add `SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, `X_CT0` to `settings/deploy/railway_secrets.yaml`

## 3. Test

- [x] 3.1 A fake KV v2 client proves that sibling keys stay byte-identical and that `kv.v2.patch`, `create_or_update_secret`, and `read_secret_version` are never called
- [x] 3.2 The OpenBao sink covers a missing path, 403, a missing `BAO_ADDR`, missing credentials, a missing hvac, and failed authentication
- [x] 3.3 Secrets-file sink: other keys, comments, block scalars, awkward values, the 0600 mode, no temp leftovers, the fallback, and a malformed file
- [x] 3.4 The Railway sink calls `set_variables` exactly once per write; `--deploy` and `--to railway` produce identical argv
- [x] 3.5 CLI parsing: `--to bao` for Gmail and YouTube, an unknown sink, conflicting flags, `--service` misuse, the local-only default, and no value in the output or logs
- [x] 3.6 The shipped allowlist includes the three session credentials for `api` and `worker`
- [x] 3.7 The existing `tests/test_cli/test_auth_commands.py`, `tests/cli/test_auth_commands.py`, and `tests/cli/test_manage_commands.py` pass unchanged

## 4. Document

- [x] 4.1 `docs/OPENBAO.md`, `docs/SETUP.md`, `docs/USER_GUIDE.md`, `docs/DEPLOY_SECRETS.md`
- [x] 4.2 Validate with `openspec validate add-secret-sink-abstraction-to-the-auth-cli --type change --strict`
