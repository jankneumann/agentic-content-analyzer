# Proposal: `aca deploy sync-secrets` — sync local secrets to Railway

## Summary

Add a CLI command that pushes selected secrets from the local `.secrets.yaml`
(and env overrides) to a target Railway service/environment as variables, so
the deployed app's runtime config can be updated from the same source of truth
developers already maintain locally. Proposal-first: dry-run diff by default,
writes gated behind `--apply`.

## Problem

There are **two independent configuration planes** and no tooling to bridge
them safely:

1. **Local CLI plane** (`PROFILE=railway-cli`): reads `.secrets.yaml` + env on
   the developer's machine. `railway-cli.yaml` only overrides `api_base_url`
   and `admin_api_key`; everything else is inherited from `base.yaml`. Under a
   remote profile, DB-touching commands route over HTTP (`is_remote_backend()`),
   so the CLI needs almost nothing locally.
2. **Deployed Railway plane**: the running container reads its **own** Railway
   Variables (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `ADMIN_API_KEY`, graph/
   storage creds, …). It has **no access** to the developer's `.secrets.yaml`.

Today, keeping the deployed plane in sync is a manual, error-prone dashboard
chore. There is a partial precedent — `src/cli/auth_commands.py` already shells
out to `railway variables --set KEY=VALUE` via `_railway_set_env()` and reads
`railway status --json` via `_railway_status()` — but it is hard-wired to Gmail
OAuth credentials and not reusable.

### Motivating incident (2026-05-30)

Running `PROFILE=railway-cli aca ingest blog` failed with **`403 Forbidden`**
from `POST https://api.aca.rotkohl.ai/api/v1/contents/ingest`. Root cause: the
local `ADMIN_API_KEY` (in `.secrets.yaml`) had drifted out of sync with the
`ADMIN_API_KEY` variable on the deployed Railway service. The server's auth
middleware (`src/api/middleware/auth.py:135`) returns `403` specifically when a
key *is* sent but `secrets.compare_digest` fails — i.e. a silent mismatch
between the two planes, indistinguishable to the user from a permissions bug.

A dry-run of `aca deploy sync-secrets` would have surfaced
`ADMIN_API_KEY [changed]` in its diff *before* the failure, turning an opaque
403 into an obvious one-line drift. This is the concrete motivation for the
command.

Risks of doing this naively (e.g. "push all of `.secrets.yaml`"):

- **Wrong values for prod**: local-only entries such as
  `NEO4J_PASSWORD: newsletter_password` or the localhost `database_url` must
  never be copied to a deployed service.
- **Secret leakage in logs/output**: values must be redacted in all output.
- **Destructive surprises**: blindly overwriting or deleting remote variables.

## Solution

A new `aca deploy` command group with `sync-secrets`, backed by a shared,
reusable Railway helper extracted from `auth_commands.py`.

```
aca deploy sync-secrets --service api --env production        # dry-run diff (default)
aca deploy sync-secrets --service api --env production --apply # write via `railway variables --set`
```

### Key Design Decisions

1. **Explicit allowlist mapping, never wholesale.** A new
   `settings/deploy/railway_secrets.yaml` declares, per service, which local
   secret keys are eligible and their Railway variable name (supports rename,
   e.g. local `NEON_DATABASE_URL` → Railway `DATABASE_URL`). Keys not in the
   mapping are never pushed.
2. **Dry-run by default; `--apply` to write.** Mirrors the established
   conservative-mutation pattern (`aca curate`, `substack-sync`): show a diff,
   require an explicit flag to mutate.
3. **Diff against live Railway vars.** Read current values via
   `railway variables --json --service <s> --environment <e>` and classify each
   mapped key as `new`, `changed`, or `unchanged`.
4. **Redaction everywhere.** Output shows key names + status only; values are
   masked (e.g. `sk-…last4`). Never print full secret values.
5. **Additive only — never delete.** The command only sets/updates variables it
   is told to manage. Remote-only variables are left untouched (and listed as
   "unmanaged" for visibility, not removed).
6. **Reuse, don't duplicate.** Extract `_railway_set_env` / `_railway_status`
   into `src/cli/railway.py`; `auth_commands.py` and the new command both use it.

## Scope

### In Scope

- New `src/cli/railway.py` shared helper (extracted + generalized from
  `auth_commands.py`): set var, get vars (`--json`), resolve status/target.
- New `aca deploy` Typer group (`src/cli/deploy_commands.py`) with
  `sync-secrets`.
- New `settings/deploy/railway_secrets.yaml` allowlist/mapping config + loader.
- Dry-run diff renderer (human + `--json` modes, value redaction).
- `--service`, `--env`/`--environment`, `--apply`, `--only KEY` (repeatable),
  `--yes` flags.
- Tests: mapping load, diff classification, redaction, dry-run vs apply,
  CliRunner coverage of the new group.
- `auth_commands.py` refactored to use the shared helper (behavior preserved).

### Out of Scope

- Reading secrets **from** Railway back into `.secrets.yaml` (reverse sync).
- Deleting/pruning remote variables.
- Non-Railway targets (Neon/Supabase dashboards, OpenBao seeding — OpenBao has
  its own flow).
- Managing non-secret config (`MODEL_*`, feature flags) — could reuse the
  mechanism later but is not part of this change.
- Triggering a redeploy after variables change (Railway handles this per its
  own settings).

## Success Criteria

1. `aca deploy sync-secrets --service api --env production` prints a redacted
   diff and writes **nothing**.
2. Adding `--apply` sets exactly the mapped `new`/`changed` variables via the
   `railway` CLI and reports counts; `unchanged` keys are skipped.
3. A local-only key absent from `railway_secrets.yaml` is never pushed.
4. No secret value appears unmasked in stdout, stderr, or `--json` output.
5. `--json` emits a machine-readable summary (`{service, environment, new[],
   changed[], unchanged[], unmanaged[], applied: bool}`).
6. `aca auth` Gmail-credential push still works (shared helper, no regression).
7. Missing `railway` CLI or unauthenticated session fails with a clear,
   actionable error (not a stack trace).
