# Deploy Secrets Sync

`aca deploy sync-secrets` pushes selected secrets from your local
`.secrets.yaml` (or env overrides) to a deployed **Railway** service/environment.

## Why this exists — the two config planes

There are two independent configuration planes:

- **Local CLI plane** (`PROFILE=railway-cli`): reads `.secrets.yaml` + env on your
  machine. Used to point the CLI at the deployed API.
- **Deployed Railway plane**: the running container reads its **own** Railway
  Variables. It has no access to your local `.secrets.yaml`.

When a secret drifts between the two, things break in confusing ways — e.g. an
`ADMIN_API_KEY` mismatch surfaces as a `403 Forbidden` on `aca ingest`, not as
an obvious "wrong key" message. `sync-secrets` makes the drift visible (and
fixable) from one command.

## Safety model

Mirrors `aca curate` / `substack-sync`:

- **Allowlist-gated** — only keys declared in
  `settings/deploy/railway_secrets.yaml` for the target service are eligible.
  Local-only dev values can never leak to prod.
- **Dry-run by default** — writes happen only with `--apply`.
- **Additive** — variables are created/updated, never deleted. Remote-only
  variables are listed as `unmanaged` and left untouched.
- **Redacted** — secret values are always masked in output (`abc…wxyz`).

## The mapping file

`settings/deploy/railway_secrets.yaml` declares which local keys map to which
Railway service and variable name:

```yaml
services:
  api:
    secrets:
      - ANTHROPIC_API_KEY            # Railway name == local name
      - local: NEON_DATABASE_URL     # rename on push
        railway: DATABASE_URL
  worker:
    extends: api                     # inherit api's list
    secrets: []
```

- A bare string maps a key to the same name on Railway.
- `local`/`railway` lets you rename (local `NEON_DATABASE_URL` → Railway
  `DATABASE_URL`).
- `extends` lets a service inherit another's secret list.

## Usage

```bash
# Dry-run: show a redacted diff, write nothing
aca deploy sync-secrets --service api --env production

# Apply: write the new/changed variables (requires explicit --env)
aca deploy sync-secrets --service api --env production --apply

# Limit to specific keys
aca deploy sync-secrets --service api --env production --only ADMIN_API_KEY --apply

# Machine-readable summary (masked values only)
aca deploy sync-secrets --service api --json
```

The diff classifies each managed key as `new`, `changed`, or `unchanged`, and
lists `skipped` keys (no local value) and `unmanaged` remote variables.

## Prerequisites

- The `railway` CLI installed and authenticated (`railway login`), with the
  project linked (`railway link`) **or** `RAILWAY_TOKEN` set in the environment.
- `--apply` requires an explicit `--env` (refuses to write to an implicit
  environment).

## Related

- `aca auth gmail --deploy` pushes OAuth tokens to Railway via the same shared
  helper (`src/cli/railway.py`).
- See [docs/MOBILE_DEPLOYMENT.md](MOBILE_DEPLOYMENT.md) for the Railway
  deployment overview.
