# Add gx-10 Off-Site Backup Scheme

## Why

The project is migrating off Railway onto a self-hosted **gx-10** host. That
migration removes Railway's managed Postgres PITR, which `docs/SYNC_DOWN.md`
names as the fallback for sub-daily recovery. Nothing replaces it.

Worse, the backup it would fall back *from* does not work either.

### The existing automated backup has never produced a backup

`railway/postgres/init-backup-job.sql` schedules a pg_cron job that pipes
`pg_dump -Fc` into `mc pipe`. It fails at three independent points, any one of
which is fatal:

1. **`MINIO_ENDPOINT` is never set for the Postgres service.** It appears in no
   `railway.toml`, `docker-compose*.yml`, or `railway/` file outside the backup
   scripts themselves. `railway/postgres/00-set-backup-gucs.sh:11-14` therefore
   takes its early exit and writes no GUCs.
2. **The job body then self-skips.** `init-backup-job.sql:55-58` —
   `IF minio_ep IS NULL THEN RAISE NOTICE ... RETURN`.
3. **`mc` is not installed in the image.** `railway/postgres/Dockerfile` has
   zero `RUN` lines; it only `COPY`s config onto `paradedb/paradedb:v0.25.2-pg17`.
   A Postgres image does not ship the MinIO client, so
   `COPY TO PROGRAM 'mc alias set ...'` (`init-backup-job.sql:64,72`) could only
   ever fail.

A fourth blocker is already documented in `CLAUDE.md`: *"pg_cron + Railway
managed PG — `current_setting('app.*')` GUC variables are restricted."* The
chosen GUC mechanism is called out in-repo as unsupported on the target platform.

### The watchdog cannot fire either

`src/api/health_routes.py:185` gates the backup check on
`database_provider == "railway" AND railway_backup_enabled`. On gx-10 the first
conjunct is false, so the check never runs. Even on Railway it inspects
`cron.job_run_details` for a job that never succeeds. And a stale result is
**non-gating** — `all_ok` is mutated only by the database check
(`health_routes.py:118,131,135`), so `backup: stale` produces a WARNING log
(`:193`) and nothing else. There is no alert emission on this path at all.

Two further defects compound it:

- **The check goes dark exactly when the DB layer breaks.** `loop` is bound at
  `:124` inside the database `try` block but used at `:188`. If the import at
  `:122` raises, `:188` raises `NameError`, swallowed at `:194` into
  `checks["backup"] = "unknown"`.
- **The warning text lies.** `:193` hardcodes "2x schedule interval", but the
  real threshold is `railway_backup_staleness_hours` (default 48,
  `settings.py:490`), independent of `railway_backup_schedule`.

Relatedly, `railway_backup_schedule` and `railway_backup_retention_days` have
**no Python consumer whatsoever**. They are shadowed by the shell script's own,
differently-named env vars (`BACKUP_BUCKET`, `BACKUP_RETENTION_DAYS`). They read
as live configuration but are inert — which is how a dead backup stayed
invisible for this long.

### Consequence

This change is not "port a working backup to a new host". It is **the first
working backup this project has had**, and the gx-10 migration is the forcing
function. The plan must therefore prove a backup actually lands *and restores* —
not merely that a job is scheduled.

Scope also covers the stores the pg_cron job never addressed: the graph database,
the image and audio artifact directories, and OpenBao.

### What this change is NOT

The existing sync layer (`src/sync/`, `aca sync export|import|push`) is a
**logical, selective, environment-to-environment copy**. Disaster recovery needs
a **physical, complete, restorable artifact**. Both are kept; the sync layer is
not repurposed as the backup. See `design.md` D8.

## What Changes

- **Provider-neutral backup settings**, in three groups, all declared together in
  one package so no downstream package needs to reach into `src/config/`:
  - *Target* (`BACKUP_S3_ENDPOINT|BUCKET|REGION|ACCESS_KEY_ID|SECRET_ACCESS_KEY|PREFIX`)
    read by both the backup and restore paths, working against Cloudflare R2, AWS
    S3, or MinIO unchanged. The `railway_minio_*` and `railway_backup_bucket` names
    keep working via the repo's established deprecation-mapping pattern
    (`settings.py:1554-1588`).
  - *Encryption* (`BACKUP_AGE_RECIPIENT`, `BACKUP_AGE_IDENTITY_PATH`) — the public
    recipient used by the backup path, and the identity used by `verify` and by
    restore. No new deprecation mapping; these have no legacy predecessor.
  - *Monitoring* (`BACKUP_MONITORING_ENABLED`, `BACKUP_STALENESS_HOURS`) — the
    provider-neutral successors to `railway_backup_enabled` and
    `railway_backup_staleness_hours`, mapped forward by the same validator. A
    freshness check that no longer depends on Railway must not keep reading a
    setting named `railway_*`.
- **A new `aca backup` CLI group** (`run`, `verify`, `list`) that orchestrates
  per-store backup, encryption, upload, and manifest writing.
- **A host-level systemd timer + service** on gx-10 invoking `aca backup run`,
  replacing the in-database pg_cron job. It survives DB container replacement,
  needs no superuser, needs no `mc` inside the DB image, and one unit covers
  every store.
- **Multi-store coverage**: Postgres (`pg_dump -Fc`), graph DB (Neo4j
  `neo4j-admin database dump` / FalkorDB `BGSAVE` + RDB copy), artifact
  directories, and OpenBao (`bao operator raft snapshot save`).
- **Client-side encryption with `age`** before upload, so a bucket-credential
  leak is not a PII leak. Key escrow is documented; a lost key means
  unrecoverable backups.
- **Retention via bucket lifecycle rules** (7 daily / 4 weekly / 12 monthly),
  declared as documented configuration rather than an unattended delete cron.
  Provider-side retention keeps working while gx-10 is down.
- **A generalized, de-gated backup freshness check** based on a bucket-side
  manifest written by the backup run, not on `cron.job_run_details`.
- **A durable freshness alert** via the existing out-of-band workflow-alert path,
  widened to carry a non-operation `system_check` source.
- **An endpoint-agnostic `aca manage restore-from-cloud`**, plus a gx-10
  multi-store restore runbook and the currently-skipped round-trip integration
  test implemented against a containerized S3-compatible stand-in.
- **Three security fixes** to the restore path, unavoidable because this change
  edits exactly those lines: credentials currently passed as `argv`
  (`restore_commands.py:193`), `target_db` emitted with its password unmasked in
  JSON output (`:287-296`), and a prod-database guard using naive string
  equality (`:110-120`).

### Explicitly out of scope

- **`railway/postgres/**` is not touched.** `verify-production-paradedb-langfuse`
  edits those files and treats the current backup as a precondition for its DB
  image cutover. Repointing the backup mid-flight would invalidate that change's
  rollback evidence. The dead-job finding is recorded in `docs/GOTCHAS.md` for
  that change to act on; no ordering dependency is created.
- **No production database, bucket, or secret-store mutation.** Implementation
  makes no live calls to production data stores (see Hard Constraints).
- **WAL archiving / PITR.** Deferred with the RPO trade-off recorded in
  `design.md` D2.

## Impact

### Affected specs

| Capability | Delta | What changes |
|---|---|---|
| `backup-and-restore` | ADDED (new capability) | Backup target/encryption/monitoring settings, multi-store backup run, client-side encryption, run manifest, freshness monitoring, durable freshness alerting, provider-side retention, host scheduling, multi-store restore |
| `cli-interface` | ADDED + MODIFIED | ADDED: `aca backup` command group. MODIFIED: `Restore From Cloud Command` — provider-neutral target, prefix-based discovery, decryption, three credential-safety fixes |
| `database-provider` | MODIFIED | `Railway Backup Strategy` narrowed to a legacy configuration surface; the operative backup and its freshness check move to `backup-and-restore` |

### Affected code

| Area | Files | Owning package |
|---|---|---|
| Contracts | `openspec/contracts/backup/**`, `openspec/contracts/content-workflows/events/**`, `openspec/contracts/README.md` | wp-contracts |
| Settings & secret hygiene | `src/config/settings.py`, `src/config/secrets.py`, `src/config/profiles.py`, `profiles/*.yaml`, `pyproject.toml`, `scripts/check-profile-secrets.sh` | wp-settings |
| Backup engine & CLI | `src/services/backup/**`, `src/cli/backup_commands.py`, `src/cli/app.py` | wp-backup-cli |
| Health & alerting | `src/api/health_routes.py`, `src/contracts/workflow_alert_models.py`, `src/queue/worker.py` | wp-health-alerts |
| Restore | `src/cli/restore_commands.py` | wp-restore-cli |
| Deployment & docs | `deploy/backup/**`, `scripts/backup_retention.py`, `docs/BACKUP_RESTORE.md`, `docs/SYNC_DOWN.md`, `docs/SETUP.md`, `docs/GOTCHAS.md` | wp-deploy-assets |
| Round-trip verification | `docker-compose.yml`, `tests/integration/test_backup_round_trip.py` | wp-integration |

### Not affected

`railway/postgres/**` (see D1) and `src/sync/**` (see D3).

### Retracted: "no migration"

An earlier revision of this proposal claimed this change adds no migration,
on the reasoning that backup state lives in the backup target so it survives
loss of the database (D7). That reasoning still holds for backup *state* — no
backup data is stored in Postgres.

It does not hold for backup *alerting*. PLAN_REVIEW established that the durable
alert path is anchored on `workflow_terminal_events`, whose three CHECK
constraints reject a `system_check` row outright. The alert could have been
constructed in Pydantic and never persisted or delivered. The operator was
offered the real cost and chose to accept it, so **this change does add an
Alembic migration** relaxing those constraints. See design amendment A1.

Consequence worth stating plainly: `has_db_migration` is now **true**, where the
GATEKEEPER assessed this change as `false`. The risk profile changed after the
gate ran, and that is recorded rather than absorbed silently.

## Hard Constraints

Carried from the autopilot GATEKEEPER risk finding; these are testable
requirements, not advice:

1. Implementation SHALL make no live calls to production databases, storage
   buckets, or secret stores. All new destructive or network behavior is
   exercised with mocks/fakes or a local container fixture.
2. Any retention or deletion capability SHALL default to dry-run and require an
   explicit opt-in flag to delete. No unattended automatic delete path.
3. Backup credentials and bucket URLs containing keys SHALL NOT be logged,
   committed, or emitted in CLI output.
4. Restore SHALL retain the existing loud safeguards around
   `pg_restore --clean --if-exists`, which drops objects in the target.

## Approaches Considered

### Approach A — Host shell script + systemd timer

A self-contained `bash` script on gx-10 doing `pg_dump | age | rclone rcat`,
driven by a systemd timer. The application is not involved.

**Pros**
- No Python dependency; keeps working even if the app environment is broken.
- Simplest possible operational story; a reviewer can read it end to end.
- No `boto3` needed (`boto3` is lazy-imported and undeclared in `pyproject.toml`,
  `file_storage.py:381`).

**Cons**
- **Violates Hard Constraint 1 in practice** — shell is poorly unit-testable, so
  the destructive and network paths would ship unverified.
- Re-implements settings/profile/OpenBao resolution in bash, so backup config
  drifts from application config.
- No access to `Settings`, so the deprecation mapping and secret masking cannot
  be reused.

**Effort**: S

### Approach B — Pure Python backup service

An `aca backup run` command doing everything in-process: `boto3` for upload,
Python-side dump orchestration, native encryption bindings.

**Pros**
- Fully unit-testable; reuses `Settings`, profiles, OpenBao, and existing masking.
- Consistent with the `cli-interface` CLI/API parity requirement.

**Cons**
- Requires declaring `boto3` (and an encryption binding) as real dependencies,
  enlarging the runtime image for a once-a-day job.
- Streaming a multi-GB `pg_dump` through Python adds memory and failure modes
  that `pg_dump | age | rclone` avoids entirely.
- Re-implements what `pg_dump`, `neo4j-admin`, and `bao` already do correctly.

**Effort**: L

### Approach C — Python-orchestrated, native-tool execution *(Recommended)*

`aca backup run` owns orchestration: it resolves settings, decides what to back
up, shells out to the correct native tool per store (`pg_dump`, `neo4j-admin`,
`redis-cli`/`BGSAVE`, `bao`, `age`, `rclone`), writes the bucket-side manifest,
and reports outcomes. A systemd timer invokes that one command.

**Pros**
- **Matches the repo's existing idiom exactly.** `src/cli/restore_commands.py`
  already orchestrates `mc`/`pg_restore` via `subprocess.run`, and
  `tests/cli/test_restore_from_cloud.py` already tests it by patching
  `subprocess.run` — so Hard Constraint 1 is satisfied by an established,
  proven pattern rather than a new one.
- Reuses `Settings`, profile resolution, OpenBao, and secret masking; backup
  config cannot drift from application config.
- Native tools do the heavy lifting, so no multi-GB stream through the
  interpreter — dumps go `pg_dump | age | rclone`, never through Python.
- One command is the single entry point for the timer, for a manual run, and for
  the integration test — the scheduled path and the tested path are identical.

**Cons**
- Requires host binaries on gx-10 (`rclone`, `age`, `pg_dump`, `bao`). Mitigated
  by an explicit preflight check in `aca backup verify` that names each missing
  binary rather than failing mid-run.
- The *reader* side still needs an in-process S3 client for the one small manifest
  object the freshness check retrieves, so `boto3` is declared as a dependency
  (design D14). This does not reintroduce Approach B's cost — that objection was
  about streaming multi-GB dumps through the interpreter, which this change still
  does not do — and it closes an existing latent defect, since `boto3` is already
  imported lazily by the S3 storage provider while appearing nowhere in
  `pyproject.toml`.
- Subprocess orchestration must handle partial failure per store; a single
  store's failure must not silently pass the whole run.

**Effort**: M

### Selected Approach

**Approach C — Python-orchestrated, native-tool execution.** Confirmed at Gate 1
with no modifications.

The deciding factor is Hard Constraint 1. Approach A cannot
satisfy it — shell scripts resist unit testing, and shipping unverified
destructive paths is precisely the risk the gatekeeper flagged. Approach B
satisfies it but pays for that with dependency weight and by reimplementing
tools that already work, and streaming large dumps through Python introduces
failure modes the pipe form does not have.

Approach C gets Approach B's testability using machinery the repo already
proves: `restore_commands.py` orchestrates subprocesses today and its tests mock
`subprocess.run` today. The scheduled path, the manual path, and the tested path
are one command, so "the backup works" is a claim the test suite can actually
make.


The operator additionally confirmed four scope decisions at the discovery gate,
each recorded as a design decision in `design.md`:

| Decision | Choice | Design ref |
|---|---|---|
| Treatment of the dead pg_cron job | gx-10 host-side only; `railway/postgres/**` untouched | D1 |
| Recovery point objective | Daily dumps, 24h RPO; WAL archiving deferred | D2 |
| Freshness alerting path | Widen Path B (durable out-of-band alerts) | D5 |
| Backup encryption | `age`, client-side before upload | D4 |

Approaches A and B were considered and rejected; their full pros/cons are
retained above. A was rejected because shell resists the unit testing that Hard
Constraint 1 requires; B because it pays dependency weight and re-implements
tools that already work.
