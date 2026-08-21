# Syncing a Backup Down to a Local Database

`aca manage restore-from-cloud` downloads a dump from the configured **backup
target**, decrypts it, and replays it into a local Postgres via `pg_restore`.

> **This is not the disaster-recovery path.** It restores ONE store — Postgres —
> into a scratch database so you can work against realistic data. Full
> multi-store disaster recovery is [BACKUP_RESTORE.md](./BACKUP_RESTORE.md),
> and its runbook starts with recovering the decryption identity.

> **Historical note.** Earlier revisions of this document described a daily
> `pg_dump` run by `pg_cron` and uploaded to MinIO. That job never produced a
> backup — see [GOTCHAS.md](./GOTCHAS.md#the-pg_cron-backup-never-produced-a-backup).
> Backups are now produced by `aca backup run` on the host.

## Overview

```
Backup target (R2 / S3 / MinIO)      Local dev box
┌────────────────────────────┐      ┌──────────────────────────────────┐
│ aca/daily/<stamp>/         │      │                                  │
│ └─ postgres.dump.age       │ ───► │  /tmp/postgres.dump.age          │
└────────────────────────────┘      │            │  age --decrypt      │
                                    │            ▼                     │
                                    │       postgres.dump              │
                                    │            │  pg_restore         │
                                    │            ▼                     │
                                    │  postgresql://localhost/...      │
                                    └──────────────────────────────────┘
```

The CLI orchestrates subprocesses and contains no Python restore logic:

1. `rclone lsjson --recursive <remote>` — discover artifacts by prefix and
   timestamp. Discovery does **not** depend on any filename prefix, so both
   `postgres.dump.age` and legacy `railway-*.dump` are found.
2. `rclone copyto <remote> <local>`
3. `age --decrypt --identity <identity> --output <plain> <ciphertext>`
   (skipped for an unencrypted artifact)
4. `pg_restore --clean --if-exists --no-owner --no-privileges --format=custom
   --dbname <target> <local-dump>`

Every credential travels by environment. None appears in a process argument
list, so nothing leaks through `/proc` to other local users.

### Backup target credentials

The CLI reads the provider-neutral backup settings. The same names address
Cloudflare R2, AWS S3 and MinIO — they differ only in the values.

| Setting                        | Env var                          | Notes                                   |
|--------------------------------|----------------------------------|-----------------------------------------|
| `backup_s3_endpoint`           | `BACKUP_S3_ENDPOINT`             | omit for AWS                            |
| `backup_s3_bucket`             | `BACKUP_S3_BUCKET`               | required                                |
| `backup_s3_region`             | `BACKUP_S3_REGION`               | `auto` for R2                           |
| `backup_s3_prefix`             | `BACKUP_S3_PREFIX`               | default `aca`                           |
| `backup_s3_access_key_id`      | `BACKUP_S3_ACCESS_KEY_ID`        | `SecretStr`                             |
| `backup_s3_secret_access_key`  | `BACKUP_S3_SECRET_ACCESS_KEY`    | `SecretStr`                             |
| `backup_age_identity_path`     | `BACKUP_AGE_IDENTITY_PATH`       | required to decrypt; escrowed, not on the backup host |

The legacy `RAILWAY_MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
and `RAILWAY_BACKUP_BUCKET` still work — they map forward onto these fields with
one deprecation warning naming the replacements.

Artifacts written by `aca backup run` are age-encrypted, so
`BACKUP_AGE_IDENTITY_PATH` must point at the escrowed identity or the command
aborts naming it. See [BACKUP_RESTORE.md](./BACKUP_RESTORE.md#key-escrow-procedure).

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

If multiple dumps exist on the same date, the lexicographically last artifact
key is picked — fine because the key embeds a full ISO-8601 UTC timestamp.

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
  "dump_file": "postgres.dump.age",
  "source": "aca/daily/2026-08-21T030000Z/postgres.dump.age",
  "local_path": "/tmp/postgres.dump",
  "decrypted": true,
  "target_db": "postgresql://aca:***@localhost:5432/newsletters_sync"
}
```

## PII Caveats

**Production dumps contain customer data.**

- **Subscribers, email addresses, API keys (if any persisted), audit logs, and
  OAuth tokens are all in the dump.** Treat any restored local database with
  the same care as the production DB.
- Delete the staged files (`/tmp/postgres.dump` and the `.age` ciphertext it
  came from) when you're done — the CLI prints the path but does NOT
  auto-delete. `rm` them yourself. The decrypted dump is plaintext PII sitting
  in `/tmp`; that is the whole reason the copy on the backup target is
  encrypted.
- Do not commit a restored DB's `pg_dump` or any query outputs to source
  control.
- If you only need schema and not PII, use `pg_dump --schema-only` against the
  restored DB to strip rows before sharing.

## Freshness

Backups run daily at 03:00 UTC via the `aca-backup.timer` systemd unit on the
host. Retention is 7 daily / 4 weekly / 12 monthly, enforced by the backup
target's lifecycle rules. This means:

- The **latest** dump can be up to ~24 hours stale.
- You can restore any of the last 7 days, plus 4 weekly and 12 monthly
  snapshots. Everything else is gone.
- `RAILWAY_BACKUP_SCHEDULE` and `RAILWAY_BACKUP_RETENTION_DAYS` are **inert** —
  they have no Python consumer and never had one. The schedule lives in the
  timer unit; retention lives in the target's lifecycle rules.

Note the gap between the 24-hour cadence and the 48-hour staleness threshold:
one missed run is tolerated before an alert fires, deliberately, because
alerting on a single transient failure trains operators to ignore the channel.

`aca backup list` shows what actually exists; a gap means a run failed. There is
no PITR on gx-10 — Railway's managed point-in-time restore does not come with
you, which is the reason this scheme exists.

## Troubleshooting

### `Backup target credentials are not configured`

`BACKUP_S3_ACCESS_KEY_ID` / `BACKUP_S3_SECRET_ACCESS_KEY` did not resolve.

```bash
aca manage check-profile-secrets
echo $BACKUP_S3_ENDPOINT   # the endpoint is not a secret; the keys are
```

### `No backup dumps found under <bucket>/<prefix>`

The prefix is probably wrong. List what is actually there:

```bash
aca backup list
```

Set `BACKUP_S3_PREFIX` accordingly. Note that each environment writes under its
own manifest path, so a shared bucket with a shared prefix is a configuration
error rather than a convenience.

### `This artifact is age-encrypted but BACKUP_AGE_IDENTITY_PATH is not set`

Every artifact `aca backup run` writes is encrypted. Recover the escrowed
identity — see
[BACKUP_RESTORE.md](./BACKUP_RESTORE.md#key-escrow-procedure) — and point
`BACKUP_AGE_IDENTITY_PATH` at it. If the identity is lost, the artifact is
unrecoverable; there is no other path.

### `Refusing to restore ... addresses the same database as RAILWAY_DATABASE_URL`

The guard compares normalized `(host, port, database)`, so rewriting the URL will
not get past it and should not: `pg_restore --clean --if-exists` drops objects in
the target. Point `--target-db` at a scratch database, or pass
`--allow-remote-target` if overwriting production is genuinely what you want.

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

`tests/integration/test_backup_round_trip.py` exercises the full round trip —
seed, back up, encrypt, upload, download, decrypt, restore, compare — against a
containerized S3-compatible target in `docker-compose.yml`. It proves a backup is
actually restorable rather than merely produced, which is the claim the previous
arrangement could not make.

Unit tests cover the CLI orchestration with mocked subprocesses.

## See Also

- [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) — the disaster-recovery runbook
- [SETUP.md](./SETUP.md) — provider configuration
- [GOTCHAS.md](./GOTCHAS.md) — why the pg_cron backup never produced a backup
- Design doc D5 in `openspec/changes/cloud-db-source-of-truth/design.md`, as
  amended by `openspec/changes/add-gx10-backup-scheme/design.md`
