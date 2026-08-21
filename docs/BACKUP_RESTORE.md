# Backup and Restore (gx-10)

Disaster-recovery backup and restore for the self-hosted gx-10 host.

> **Read this first if you are in an incident.** Jump to
> [Restore runbook](#restore-runbook). Step 0 is recovering the decryption
> identity, and without it nothing else in this document will help you.

---

## Start here: the decryption identity

Every backup artifact is encrypted with [`age`](https://age-encryption.org) on the
host, before upload. The bucket never holds plaintext, so a leaked bucket
credential is not a PII leak.

The corollary is unforgiving and there is no way around it:

> **If the age identity is lost, every backup is permanently unrecoverable.**
> There is no vendor to call, no reset link, and no partial recovery. The
> ciphertext is intact and useless.

So the identity is escrowed **outside** anything the backups protect.

### Key escrow procedure

1. Generate the keypair once, on a trusted workstation — never on gx-10:

   ```bash
   age-keygen -o backup-identity.txt
   # Public key: age1qqq...        <- the RECIPIENT
   ```

2. The **recipient** (public key) is not a secret. It goes in
   `/etc/aca/backup.env` as `BACKUP_AGE_RECIPIENT`, and it may be committed to a
   runbook. It only lets you *create* backups you cannot read.

3. The **identity** (`backup-identity.txt`, private key) is escrowed in at least
   **two** locations that do not depend on this system:

   - a password manager entry shared with at least one other person, and
   - an offline copy (printed or on encrypted removable media) in a different
     physical location.

   Two locations, because one is a single point of failure and the failure is
   total. A different person, because a key only you can reach is lost when you
   are unavailable — which correlates with incidents.

4. **The identity never goes on gx-10.** `aca-backup.service` ships the recipient
   and deliberately not the identity, so compromising the backup host does not
   yield the plaintext of every backup that host ever wrote. `aca backup verify`
   and `aca manage restore-from-cloud` are operator-initiated and supply the
   identity themselves.

5. Verify escrow quarterly by decrypting the canary from a machine that has only
   the escrowed copy:

   ```bash
   BACKUP_AGE_IDENTITY_PATH=/path/to/escrowed-identity.txt aca backup verify
   ```

   An escrow you have never restored from is a hypothesis, not a backup.

---

## What is backed up

| Store | Tool | Notes |
|---|---|---|
| PostgreSQL | `pg_dump --format=custom` | The only **required** store. A failure here means no manifest is written. |
| Graph database | `neo4j-admin database dump` / `redis-cli --rdb` | Branches on `(graphdb_provider, graphdb_mode)`. See below. |
| Artifact directories | `tar` | images, podcasts, audio digests — including files no database row references, since those are still the only copy. |
| OpenBao | `bao operator raft snapshot save` | Skipped with a named reason when not configured. |

Everything streams: `<dump> | age | rclone rcat`. No artifact is staged on disk
and none passes through the Python interpreter, so a multi-GB dump costs no
proportional memory.

### Graph database, by configuration

| `graphdb_provider` | `graphdb_mode` | Behavior |
|---|---|---|
| `neo4j` | `local`, `embedded` | Dumped with `neo4j-admin database dump`. |
| `neo4j` | `cloud` (AuraDB) | **Skipped**, reason `managed_provider_no_filesystem_access`. `neo4j-admin` cannot reach a managed instance. Use AuraDB's own scheduled snapshots, and record in your DR plan that this store is covered by the provider rather than by this job. |
| `falkordb` | any | `redis-cli --rdb` snapshot. This is the single **declared write exception** to the read-only rule: it writes a snapshot file and mutates no application data. |

---

## Setup

### 1. Host prerequisites

```bash
sudo apt install age rclone postgresql-client-17 tar coreutils
# plus neo4j-admin or redis-tools, and bao, if those stores are configured
```

`aca backup verify` names each missing binary individually rather than failing
generically; `aca backup run` performs the same binary check **before** contacting
any store, so a missing tool is never discovered after `pg_dump` has already read
production.

### 2. Bucket and credentials

Create a bucket (Cloudflare R2, AWS S3, or MinIO — the same code path serves all
three) and issue **two** credentials for it:

| Credential | Used by | Permissions |
|---|---|---|
| write | gx-10 backup unit | `PutObject`, `ListBucket` on the prefix. **No delete.** |
| manifest-read | application tier | `GetObject` on `<prefix>/manifests/<env>/latest.json` only |

These are the *same two settings* (`BACKUP_S3_ACCESS_KEY_ID` /
`BACKUP_S3_SECRET_ACCESS_KEY`) holding *different values* per environment — one
credential namespace, not two sets of settings. The application tier needs neither
write access nor the decryption identity: it reads one small unencrypted manifest
and nothing else.

Withholding delete from the write credential is what makes "no unattended
deletion" true at the provider as well as in the code.

### 3. Configuration

```bash
BACKUP_S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
BACKUP_S3_BUCKET=aca-backups
BACKUP_S3_REGION=auto          # "auto" for R2; a real region for AWS
BACKUP_S3_PREFIX=aca
BACKUP_S3_ACCESS_KEY_ID=...
BACKUP_S3_SECRET_ACCESS_KEY=...
BACKUP_AGE_RECIPIENT=age1...   # public; safe on the host
BACKUP_AGE_IDENTITY_PATH=...   # private; NEVER on the backup host
BACKUP_MONITORING_ENABLED=true
BACKUP_STALENESS_HOURS=48
```

The legacy `RAILWAY_MINIO_*`, `RAILWAY_BACKUP_BUCKET`, `RAILWAY_BACKUP_ENABLED`
and `RAILWAY_BACKUP_STALENESS_HOURS` names still resolve — they map forward onto
these with one deprecation warning naming the replacements.

### 4. Scheduling

```bash
sudo useradd --system --home /var/lib/aca-backup --create-home aca-backup
sudo install -m 0644 deploy/backup/aca-backup.{service,timer} /etc/systemd/system/
sudo install -D -m 0600 -o root -g root \
    deploy/backup/aca-backup.env.example /etc/aca/backup.env
sudo "$EDITOR" /etc/aca/backup.env
sudo systemctl daemon-reload
sudo systemctl enable --now aca-backup.timer
systemctl list-timers aca-backup.timer
```

Daily at 03:00 UTC with a randomized delay, `Persistent=true` so a host that was
off at 03:00 catches up rather than silently skipping the day.

### 5. Retention

```bash
python scripts/backup_retention.py                 # dry run — prints, changes nothing
python scripts/backup_retention.py --apply         # sets the lifecycle rules
python scripts/backup_retention.py --dialect aws --apply
```

7 daily / 4 weekly / 12 monthly, declared in `deploy/backup/retention.yaml` and
enforced by the **backup target's own lifecycle rules**. No scheduled process in
this repository deletes a backup object. Two reasons, and the second is the one
that matters: provider-side expiry keeps working while gx-10 is down, and an
unattended process with delete rights over the backup target is the single most
dangerous component such a system can have — a bug in it destroys the backups
instead of the data.

The tier is a **key segment** chosen at write time, not a tag: lifecycle rules
expire by age under a prefix and R2 supports no tag filters, so a tag-based scheme
would collapse to "keep everything N days, then nothing".

---

## Monitoring

Freshness comes from the run manifest at
`<prefix>/manifests/<environment>/latest.json` — the one object on the target that
is not encrypted, so a reader holding no identity can evaluate it.

| Status | Meaning |
|---|---|
| `ok` | Recent **and** every store succeeded. |
| `stale` | Older than `BACKUP_STALENESS_HOURS`. |
| `partial` | Recent, but a store failed or was skipped. Not healthy. |
| `no_history` | No manifest. No backup has ever succeeded here. |
| `unknown` | The target could not be read. Distinct from `no_history`. |
| `environment_mismatch` | The manifest belongs to a different environment. |

`GET /ready` reports this under `checks.backup` and **never** fails readiness on
it: pulling an instance out of the load balancer over a stale backup converts a
backup problem into a serving outage. The actionable signal is the durable alert
emitted by worker maintenance — at most one per staleness window, so a sustained
outage re-alerts once per period rather than once per tick.

A 24-hour cadence against a 48-hour threshold means one missed run is tolerated
before alerting. That is deliberate: alerting on a single transient failure trains
operators to ignore the channel.

---

## Restore runbook

Ordered. Do not skip step 0.

### 0. Recover the decryption identity

Retrieve `backup-identity.txt` from escrow and place it somewhere readable only by
you:

```bash
install -m 0600 /path/from/escrow/backup-identity.txt ~/.config/aca/identity.txt
export BACKUP_AGE_IDENTITY_PATH=~/.config/aca/identity.txt
```

Confirm before going further — an identity that does not open the canary will not
open the dumps either:

```bash
aca backup verify
```

### 1. Find what you have

```bash
aca backup list
```

Keys are `<prefix>/<tier>/<ISO-8601 stamp>/<store>.<ext>.age`.

### 2. PostgreSQL

```bash
aca manage restore-from-cloud --backup-date 2026-08-21 --target-db postgresql://localhost/scratch
```

This downloads, decrypts, and replays with `pg_restore --clean --if-exists`.

**`--clean --if-exists` drops objects in the target.** Restore into a *scratch*
database first and promote it, rather than restoring over anything you still need.
The command refuses a target that addresses the same database as
`RAILWAY_DATABASE_URL` — comparing normalized `(host, port, database)`, so a
trailing slash, an explicit `:5432` or an added `?sslmode=require` will not slip
past it. `--allow-remote-target` is the explicit override and means what it says.

### 3. Graph database

```bash
rclone copyto backup:$BUCKET/<key> ./neo4j.dump.age
age --decrypt --identity "$BACKUP_AGE_IDENTITY_PATH" --output neo4j.dump neo4j.dump.age

# Neo4j — the database must be stopped
neo4j-admin database load neo4j --from-path=. --overwrite-destination=true

# FalkorDB — stop the server, replace the RDB, start it
systemctl stop falkordb
install -m 0644 -o falkordb -g falkordb dump.rdb /var/lib/falkordb/dump.rdb
systemctl start falkordb
```

For AuraDB (`graphdb_mode: cloud`) there is no artifact here — restore from the
provider's own snapshot console.

### 4. Artifact directories

```bash
rclone copyto backup:$BUCKET/<key> ./artifacts.tar.age
age --decrypt --identity "$BACKUP_AGE_IDENTITY_PATH" --output artifacts.tar artifacts.tar.age
tar --extract --file artifacts.tar --directory /opt/aca
```

Extracts `data/images`, `data/podcasts`, `data/audio-digests` with their original
relative paths.

### 5. OpenBao

```bash
rclone copyto backup:$BUCKET/<key> ./openbao.snap.age
age --decrypt --identity "$BACKUP_AGE_IDENTITY_PATH" --output openbao.snap openbao.snap.age
bao operator raft snapshot restore openbao.snap
```

Restoring a raft snapshot replaces the cluster's entire state. Unseal afterwards
with the unseal keys, which are escrowed separately (see [OpenBao](./OPENBAO.md)).

### 6. Verify

```bash
psql "$TARGET_DB" -c "SELECT count(*) FROM contents;"
aca operations list
curl -s localhost:8000/ready | jq .checks
```

---

## Recovery objectives

| | Target | Determined by |
|---|---|---|
| RPO | ≤ 24 h | Daily dump cadence. Up to a day of writes is lost. |
| RTO | ≤ 2 h | Download + decrypt + `pg_restore` for a database of this size. |

WAL archiving (pgBackRest / wal-g) would cut RPO to minutes and is deferred to a
follow-up. The trade-off is recorded rather than assumed: 24 hours is acceptable
because this system re-ingests from upstream sources, so a lost day is a re-run
rather than lost information.

---

## Troubleshooting

**`aca backup verify` reports an absent canary.** No backup run has ever
succeeded. This is *not* a key problem — the two are reported separately for
exactly this reason. Run `aca backup run` and read the per-store outcomes.

**`aca backup verify` reports a decryption failure.** The canary exists and your
identity does not open it. The recipient configured on the host does not match the
identity you hold. Check `BACKUP_AGE_RECIPIENT` against `age-keygen -y` of your
identity.

**A store is `failed` with `uploaded_size_mismatch`.** The upload exited zero but
the stored object is a different size than what was streamed. Treat the artifact
as unusable. Usually a truncated stream or a target-side limit.

**A store is `failed` with `pipeline_stage_exit_nonzero`.** Some stage of
`dump | age | rclone` exited non-zero. Run the unit manually and read stderr:
`sudo -u aca-backup /opt/aca/.venv/bin/aca backup run`. Stage stderr is
deliberately kept out of the manifest and the CLI output, because it can echo a
connection string.

**`/ready` reports `environment_mismatch`.** Two environments share a prefix and
one overwrote the other's manifest, or `ENVIRONMENT` differs from what wrote it.
Give each environment its own `BACKUP_S3_PREFIX` or its own bucket.

**`/ready` reports `unknown` persistently.** The application tier cannot read the
manifest. Check the manifest-read credential and that
`<prefix>/manifests/<env>/latest.json` is within its scope.

---

## Related

- [SYNC_DOWN.md](./SYNC_DOWN.md) — the *logical* environment-to-environment copy. A different tool for a different job; see `design.md` D3 of `add-gx10-backup-scheme`.
- [SETUP.md](./SETUP.md) — provider configuration.
- [OPENBAO.md](./OPENBAO.md) — unseal-key escrow.
- [GOTCHAS.md](./GOTCHAS.md) — why the previous pg_cron backup never produced a backup.
