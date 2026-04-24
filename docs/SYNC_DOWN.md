# Syncing a Railway Backup Down to a Local Database

The Railway production Postgres runs a daily `pg_dump` via `pg_cron`, uploads
the result to MinIO, and retains N days of history (see
[SETUP.md §"Automated Backups"](./SETUP.md#automated-backups-pg_cron--minio)).
The `aca manage restore-from-cloud` command is a thin wrapper that downloads
one of those dumps and replays it into a local Postgres via `pg_restore`.

## Overview

```
Railway MinIO                 Local dev box
┌──────────────────┐         ┌──────────────────────────────────┐
│ backups/         │         │                                  │
│ ├─ railway-...   │  mc cp  │   /tmp/railway-YYYY-MM-DD-*.dump │
│ └─ railway-...   │ ──────► │                │                 │
└──────────────────┘         │           pg_restore             │
                             │                ▼                 │
                             │    postgresql://localhost/...    │
                             └──────────────────────────────────┘
```

The CLI orchestrates three subprocesses and no Python restore logic:

1. `mc alias set <alias> <endpoint> <user> <pass>`
2. `mc ls <alias>/<bucket>/` (pick the dump, either latest or a specific date)
3. `mc cp <remote> <local>`
4. `pg_restore --clean --if-exists --no-owner --no-privileges --format=custom
   --dbname <target> <local-dump>`

Any nonzero exit from a subprocess aborts the CLI with the subprocess's stderr
appended to the error message.

## Prerequisites

### Tools

Both must be available on your `PATH`:

- **`mc`** — MinIO client. Install via `brew install minio/stable/mc` or see
  [MinIO docs](https://min.io/docs/minio/linux/reference/minio-mc.html).
- **`pg_restore`** — part of `postgresql-client`. The client version should be
  **>=** the server version that produced the dump (currently PG17). On macOS:
  `brew install postgresql@17`.

Verify:

```bash
mc --version
pg_restore --version   # must show 17.x for PG17 backups
```

### Target database (IMPORTANT)

**Never point `--target-db` at a database you care about.** The command runs
`pg_restore --clean --if-exists`, which drops and recreates all schema objects
in the target. The intended pattern is:

```bash
# Create a scratch DB next to your dev DB
createdb newsletters_sync
export DATABASE_URL=postgresql://localhost:5432/newsletters_sync
```

Then either rely on `DATABASE_URL` or pass `--target-db` explicitly.

### MinIO credentials

The CLI reads three settings from the active profile:

| Setting                   | Env var                      | Source                |
|---------------------------|------------------------------|-----------------------|
| `railway_minio_endpoint`  | `RAILWAY_MINIO_ENDPOINT`     | Railway project vars  |
| `minio_root_user`         | `MINIO_ROOT_USER`            | Railway project vars  |
| `minio_root_password`     | `MINIO_ROOT_PASSWORD`        | Railway project vars  |
| `railway_backup_bucket`   | `RAILWAY_BACKUP_BUCKET`      | default `backups`     |

Pull them from the Railway dashboard (or `railway variables`) and set them in
your `.env` / `.secrets.yaml` under the `railway-cli` profile.

## Usage

### Restore the latest dump

```bash
export PROFILE=railway-cli
export DATABASE_URL=postgresql://localhost:5432/newsletters_sync
aca manage restore-from-cloud --yes
```

### Restore a specific date

```bash
aca manage restore-from-cloud --backup-date 2026-04-20 --yes
```

If multiple dumps exist on the same date (e.g., schedule changed), the
lexicographically last filename is picked — fine because the backup filename
embeds `HHMM`.

### Override the target DB without touching `DATABASE_URL`

```bash
aca manage restore-from-cloud \
  --target-db postgresql://localhost:5432/scratch_db \
  --yes
```

### JSON output (for automation)

```bash
aca --json manage restore-from-cloud --yes | jq .
```

```json
{
  "success": true,
  "dump_file": "railway-2026-04-20-0300.dump",
  "source": "aca-backups/backups/railway-2026-04-20-0300.dump",
  "local_path": "/tmp/railway-2026-04-20-0300.dump",
  "target_db": "postgresql://localhost:5432/newsletters_sync"
}
```

## PII Caveats

**Production dumps contain customer data.**

- **Subscribers, email addresses, API keys (if any persisted), audit logs, and
  OAuth tokens are all in the dump.** Treat any restored local database with
  the same care as the production DB.
- Delete the local dump file (`/tmp/railway-YYYY-MM-DD-*.dump`) when you're
  done — the CLI prints its path but does NOT auto-delete. `rm` it yourself.
- Do not commit a restored DB's `pg_dump` or any query outputs to source
  control.
- If you only need schema and not PII, use `pg_dump --schema-only` against the
  restored DB to strip rows before sharing.

## Freshness

Dumps run daily (default `0 3 * * *` UTC, see `RAILWAY_BACKUP_SCHEDULE`).
Retention defaults to 7 days (`RAILWAY_BACKUP_RETENTION_DAYS`). This means:

- The **latest** dump can be up to ~24 hours stale.
- You can restore any snapshot from the last ~7 days; older data is gone.
- For more granular recovery, use Railway's Postgres PITR (point-in-time
  restore) feature instead of the MinIO dumps.

If the daily job failed, `mc ls` will show a gap — pick the most recent
successful dump by date.

## Troubleshooting

### `mc: authentication failed`

Credentials didn't propagate. Double-check your profile:

```bash
aca manage check-profile-secrets
echo $RAILWAY_MINIO_ENDPOINT
echo $MINIO_ROOT_USER
```

### `mc: No such object` / empty `mc ls`

The bucket name probably differs from `backups`. Inspect:

```bash
mc ls aca-backups/          # lists top-level buckets
mc ls aca-backups/backups/  # lists dump files
```

Set `RAILWAY_BACKUP_BUCKET` accordingly.

### `pg_restore: error: server version mismatch`

Your local `pg_restore` is older than PG17. Upgrade:

```bash
brew install postgresql@17
brew link --force postgresql@17
```

### `pg_restore: connection to server ... failed`

Your `--target-db` URL is unreachable or the database doesn't exist. Create
it first:

```bash
createdb newsletters_sync
```

### `No backup found for date YYYY-MM-DD`

The CLI prints the list of dates it saw. Pick one of those; if your desired
date is missing, either the backup job didn't run that day or retention has
expired it.

## Integration Test

An integration test fixture exercising the full round-trip against a local
MinIO container is planned (`tests/cli/test_restore_from_cloud.py` has a
`@pytest.mark.skip` placeholder). Provisioning a `minio/minio` service in
`docker-compose.yml` plus a seeded dump is the blocker. Unit tests cover the
CLI orchestration with mocked subprocesses today.

## See Also

- [SETUP.md — Automated Backups](./SETUP.md#automated-backups-pg_cron--minio)
- [MOBILE_DEPLOYMENT.md](./MOBILE_DEPLOYMENT.md) — Railway deployment guide
- Design doc D5 in `openspec/changes/cloud-db-source-of-truth/design.md`
