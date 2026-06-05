# Tasks: `aca deploy sync-secrets`

## 1. Shared Railway helper
- [x] 1.1 Create `src/cli/railway.py` with `run_railway(args) -> CompletedProcess`,
  `get_variables(service, environment) -> dict[str, str]` (parses
  `railway variables --json`), `set_variables(pairs, service, environment)`
  (batched `--set`), and `resolve_target(service, environment) -> (service, env)`
  (uses `railway status --json` defaults).
- [x] 1.2 Pre-flight check: detect missing `railway` CLI / unlinked project and
  raise a `typer.Exit` with actionable guidance (link dir or `RAILWAY_TOKEN`).
- [x] 1.3 Refactor `src/cli/auth_commands.py` to use the shared helper; remove or
  thinly wrap `_railway_set_env` / `_railway_status`. Verify Gmail push unchanged.

## 2. Mapping config + loader
- [x] 2.1 Add `settings/deploy/railway_secrets.yaml` with the `services.<name>.secrets`
  schema (`local`, optional `railway`, optional `extends`).
- [x] 2.2 Create `src/config/deploy_secrets.py`: load + validate the mapping
  (resolve `extends`, reject unknown keys, duplicate Railway target names,
  non-string locals). Return a typed structure per service.
- [x] 2.3 Resolve local values: env var > `.secrets.yaml` entry; report missing
  as `skipped`, never push.

## 3. `aca deploy sync-secrets` command
- [x] 3.1 Create `src/cli/deploy_commands.py` with `deploy_app` Typer group and
  the `sync-secrets` command (`--service`, `--env`, `--apply`, `--only`
  repeatable, `--yes`, plus global `--json`).
- [x] 3.2 Implement classify (`new`/`changed`/`unchanged`) against live remote vars
  and collect `unmanaged` remote-only keys.
- [x] 3.3 Implement `mask()` redaction and the human-readable diff renderer
  (guard `typer.echo` with `not is_json_mode()`; errors stay unguarded).
- [x] 3.4 Implement `--json` summary payload
  (`{service, environment, new[], changed[], unchanged[], unmanaged[], applied}`).
- [x] 3.5 Apply path: batched `set_variables` for `new`+`changed` only when
  `--apply`; confirm prompt unless `--yes` or `--json`.
- [x] 3.6 Register `app.add_typer(deploy_app, name="deploy")` in `src/cli/app.py`.

## 4. Tests
- [x] 4.1 `tests/config/test_deploy_secrets.py`: loader validation + `extends`.
- [x] 4.2 `tests/cli/test_deploy_commands.py` (CliRunner, mock `run_railway`):
  dry-run writes nothing; `--apply` sets only mapped new/changed; `--only`
  filter; missing-CLI error; `--json` shape.
- [x] 4.3 Redaction tests for `mask()` (short, long, empty values); assert no raw
  secret appears in captured output.
- [x] 4.4 Regression: `aca auth` Gmail credential push still succeeds via shared
  helper.

## 5. Docs
- [x] 5.1 Document the command + mapping file in `docs/MOBILE_DEPLOYMENT.md` (or a
  new `docs/DEPLOY_SECRETS.md`) and link from `CLAUDE.md` deployment section.
- [x] 5.2 Add a one-line gotcha if `railway variables --json` is version-gated.

## 6. Verify
- [x] 6.1 `pytest tests/cli/test_deploy_commands.py tests/config/test_deploy_secrets.py -v` (27/27 pass, incl. `tests/cli/test_railway.py`)
- [x] 6.2 `ruff check` + `mypy` clean on new modules.
- [x] 6.3 Verified wiring via `aca deploy sync-secrets --help` + unit-level dry-run/apply
  gating tests. Real-service dry-run deferred to the user (requires `railway login`).

## Notes / out of scope

- **Pre-existing failures (NOT touched):** `tests/test_cli/test_auth_commands.py::test_gmail_deploy_*`
  expect exactly 2 `railway` subprocess calls but the deploy flow's `_warn_deploy_target`
  makes a 3rd (`railway status --json`). Confirmed failing on `main` before this change
  (stash-isolated check), so it is unrelated test/code drift in the auth deploy path.
  Filed as a follow-up; not fixed here per scope discipline.
- `railway variables --json` shape is assumed flat (`{NAME: VALUE}`); see design.md open
  question. `get_variables()` degrades to `{}` on any parse failure, so a shape change
  cannot corrupt a sync — it just yields an all-`new` diff.
