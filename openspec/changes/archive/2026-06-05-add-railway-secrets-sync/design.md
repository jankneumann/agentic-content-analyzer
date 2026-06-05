# Design: `aca deploy sync-secrets`

## Context

- **Existing precedent**: `src/cli/auth_commands.py`
  - `_railway_set_env(key, value, service=None)` → `railway variables --set KEY=VALUE`
    (requires a linked Railway project dir or `RAILWAY_TOKEN`).
  - `_railway_status()` → parses `railway status --json` for project/env/service.
- **`railway` CLI** is installed (`/opt/homebrew/bin/railway`) and is the
  transport — we shell out rather than reimplement the Railway API.
- **Local secret source**: `.secrets.yaml` is a flat `KEY: value` YAML store
  (the same file profile `${VAR}` interpolation reads). Env vars override it.
- **Conservative-mutation convention** in this repo: dry-run/proposal-first,
  human-gated, additive/reversible (see `aca curate`, `substack-sync`).

## Goals

- One reusable Railway helper module; no duplicated subprocess logic.
- Make the local→deployed secret sync explicit, auditable, and safe by default.
- Never leak secret values; never push local-only values to prod.

## Non-Goals

- Reverse sync (Railway → local), variable deletion, redeploy orchestration,
  non-Railway targets.

## Architecture

### Module layout

```
src/cli/railway.py            # shared: run_railway(), get_variables(), set_variable(), resolve_target()
src/cli/deploy_commands.py    # `aca deploy` Typer group + sync-secrets command
src/config/deploy_secrets.py  # load + validate settings/deploy/railway_secrets.yaml
settings/deploy/railway_secrets.yaml   # the allowlist/mapping
```

`src/cli/app.py` registers `app.add_typer(deploy_app, name="deploy")`.
`auth_commands.py` is updated to import `set_variable` / `resolve_target` from
`src/cli/railway.py` (the old private functions become thin wrappers or are
removed).

### Mapping config — `settings/deploy/railway_secrets.yaml`

```yaml
# Which local secret keys may be pushed to which Railway service, and under
# what Railway variable name. Keys NOT listed here are never synced.
services:
  api:
    secrets:
      - local: ANTHROPIC_API_KEY        # railway name defaults to local name
      - local: OPENAI_API_KEY
      - local: ADMIN_API_KEY
      - local: APP_SECRET_KEY
      - local: NEON_DATABASE_URL
        railway: DATABASE_URL           # rename on push
      - local: NEO4J_AURADB_URI
        railway: NEO4J_URI
      - local: NEO4J_AURADB_PASSWORD
        railway: NEO4J_PASSWORD
  worker:
    extends: api                        # optional: inherit api's list
```

Notes:
- `railway` defaults to `local` when omitted.
- `extends` lets a worker service reuse the api list without duplication.
- Loader validates: no unknown top-level keys, every `local` is a string,
  duplicate Railway target names within a service are rejected.

### Sync algorithm (per `sync-secrets`)

1. **Resolve target**: `--service` + `--env` (fall back to `railway status
   --json` defaults; error if ambiguous and not specified).
2. **Load mapping** for the service from `railway_secrets.yaml`.
3. **Resolve local values**: for each mapped `local` key, value =
   `os.environ.get(key)` or `.secrets.yaml[key]`. Missing → reported as
   `skipped (no local value)`, never pushed.
4. **Fetch remote**: `railway variables --json --service <s> --environment <e>`.
5. **Classify** each mapped key by Railway target name:
   - `new` — absent remotely
   - `changed` — present but value differs
   - `unchanged` — identical
6. **Render diff** (redacted). Also list `unmanaged` (remote vars not in the
   mapping) for awareness — never modified.
7. **Apply** (only if `--apply`): call `set_variable()` for each `new` +
   `changed`. Batch into a single `railway variables --set K=V --set K2=V2 …`
   call where possible to minimize redeploys. Report counts.

### Redaction

```python
def mask(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}…{value[-4:]}"
```

Diff lines show `KEY  [new]  → ab3…f9c1`. The `--json` payload contains
`masked` previews and never the raw value.

### Safety / guardrails

| Risk | Mitigation |
|------|------------|
| Push local-only dev value to prod | Allowlist mapping is the *only* eligibility source; defaults push nothing not listed |
| Secret leak in output | `mask()` applied to every value; raw values never logged |
| Accidental write | Dry-run default; `--apply` required; `--yes` to skip confirm in CI |
| Destructive overwrite of remote-only vars | Additive only; `unmanaged` vars listed, never touched/deleted |
| `railway` not installed / not linked | Pre-flight check with actionable message (link dir or set `RAILWAY_TOKEN`) |
| Wrong environment | `--env` required to apply to a non-default env; status default only used for dry-run |

## Testing strategy

- **Unit**: mapping loader (extends resolution, validation errors), classify
  (`new`/`changed`/`unchanged`), `mask()` edge cases, target resolution.
- **CLI** (`CliRunner`): dry-run prints diff and calls `set_variable` zero
  times; `--apply` calls it for mapped new/changed only; `--json` shape;
  missing-`railway`-CLI error path. Mock `run_railway`/subprocess — never shell
  out in tests.
- **Regression**: `aca auth` Gmail push still works through the shared helper.

## Open questions

- Should `railway_secrets.yaml` live under `settings/` (config) or `sources.d/`?
  Proposed `settings/deploy/` since it's deploy config, not a content source.
- Confirm `railway variables --json` is available in the pinned CLI version;
  fall back to parsing plain `railway variables` output if not.
