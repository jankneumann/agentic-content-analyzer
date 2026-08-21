# Design — gx-10 Off-Site Backup Scheme

## Context

Migration from Railway to the self-hosted gx-10 host removes managed Postgres
PITR. Investigation during planning established that the in-repo pg_cron backup
has never produced a backup (see `proposal.md` § Why), so this change delivers
the project's first working disaster-recovery capability rather than porting an
existing one.

Four scope decisions were confirmed by the operator at the discovery gate and
are recorded below as D1, D2, D4, D5.

## Decisions

### D1 — Host-side only; `railway/postgres/**` is not touched

**Decision.** The new scheme is built entirely as host-side machinery invoked on
gx-10. The dead pg_cron job, its GUC seeding script, and the `railway_backup_*`
settings are left in place and untouched.

**Rationale.** `verify-production-paradedb-langfuse` edits `railway/postgres/**`
and treats the current backup arrangement as a precondition for its DB image
cutover. Repointing or deleting the backup mid-flight would invalidate that
change's rollback evidence and force a sequencing dependency between two
otherwise independent changes.

**Consequences.** Two backup mechanisms coexist temporarily — one working, one
inert. That is acceptable only because the inert one is documented: this change
records the three-point failure in `docs/GOTCHAS.md` so the finding is not lost
and the other change can retire the job on its own schedule. Retiring the
pg_cron job is explicitly a follow-up, not orphaned work.

**Alternatives rejected.** Retiring the job here (head-on conflict, forced
sequencing). Repairing the job here (doubles the surface, still blocked by the
documented Railway GUC restriction, and the whole point is to leave Railway).

### D2 — Daily dumps, 24h RPO; WAL archiving deferred

**Decision.** Target **RPO ≤ 24 hours** and **RTO ≤ 2 hours** using scheduled
`pg_dump -Fc` snapshots. WAL archiving (pgBackRest / wal-g) is deferred to a
follow-up proposal.

**Rationale.** The corpus is re-derivable: content is ingested from external
sources (Gmail, RSS, YouTube, web search) that remain available, so a lost day is
recoverable by re-ingestion rather than being permanently destroyed. A single
portable dump format also keeps the restore runbook short, which matters more for
RTO than RPO does here — an untested complex restore is worse than a tested
simple one.

**Consequences.** Up to 24 hours of ingested content, digests, and agent state can
be lost. Derived artifacts (summaries, digests, embeddings) are regenerable at LLM
cost. Human-authored data — review decisions, approvals, prompt overrides, source
overrides — is **not** re-derivable and is the real exposure. This is the accepted
trade-off, and the follow-up must be revisited if human-authored volume grows.

**Alternatives rejected.** WAL archiving now: near-zero RPO, but adds a stateful
daemon with its own retention model and a much longer restore runbook, on a host
whose first backup does not yet exist. Walk before running.

### D3 — Backup ≠ sync; both are kept

**Decision.** `src/sync/` and `aca sync export|import|push` remain a logical,
selective, environment-to-environment copy. The backup path produces physical,
complete, restorable artifacts. Neither is reimplemented in terms of the other.

**Rationale.** They answer different questions. Sync answers *"give me
production-like data in my dev database"* and deliberately excludes tables
(`EXCLUDED_TABLES = {pgqueuer_jobs, alembic_version}`, `sync/constants.py:59`).
Disaster recovery answers *"reconstruct the system as it was"* and must include
exactly those — queue state and migration version are part of the system.

**Consequences.** Some conceptual overlap in file-copying code is accepted rather
than factored out, because the two have opposite completeness requirements.

**Note on artifact backup specifically.** `FileSyncer` discovers files by querying
DB reference columns (`FILE_PATH_COLUMNS`, `sync/constants.py:101-105`). That is
correct for sync and **wrong for DR**: any file not referenced by a live DB row is
invisible to it, so orphans and files whose rows are mid-transaction are silently
omitted. The backup path therefore syncs the artifact **directories** wholesale
via `rclone`, accepting that it copies some orphans — over-inclusion is the safe
error direction for a backup.

### D4 — Client-side encryption with `age`

**Decision.** Every artifact is encrypted with `age` before upload:
`pg_dump -Fc | age -r <recipient> | rclone rcat`. The bucket never receives
plaintext.

**Rationale.** `docs/SYNC_DOWN.md` documents that dumps contain subscriber email
addresses, OAuth tokens, and audit logs. Once those leave the host for a
third-party bucket, provider-side encryption (SSE) protects against disk theft but
not against anyone holding bucket credentials — including the provider. Client-side
encryption makes a credential leak a denial-of-access problem rather than a data
breach. `age` is chosen over GPG for a single static binary, no keyring daemon,
and one-line key generation.

**Consequences.** **A lost identity key makes every backup permanently
unrecoverable.** This is the single largest operational risk introduced by this
change and is treated as such:

- The recipient (public) key is safe to commit and lives in the profile config.
- The identity (private) key is **never** stored on gx-10 alone. It is escrowed in
  OpenBao and in one offline location outside the gx-10 blast radius.
- `aca backup verify` asserts the identity key is present and can decrypt a
  known-good canary object; a backup scheme that cannot decrypt is not a backup.
- The restore runbook opens with key recovery, not with `pg_restore`.

**Alternatives rejected.** SSE-only (provider and any credential holder read PII).
GPG (heavier key handling for no additional guarantee here).

### D5 — Widen the durable alert path (Path B) for freshness alerts

**Decision.** Extend `WorkflowAlertEnvelopeV1` with a `system_check` source rather
than routing backup alerts through the in-app notification path.

**Rationale.** The two alerting paths differ in guarantees, not just plumbing.
Path A (`notification_service.py`) is in-app, has no retries, and
`_is_delivery_enabled` **fails open** (`:135-139`) — a silent-failure mode that is
unacceptable for a durability signal, because the failure of the alert looks
identical to the absence of a problem. Path B has HMAC signing, SSRF policy,
leases, retry classification, and exactly-once delivery.

**Consequences.** This is a **contract change to a recently-landed spec**, not a
drop-in. `WorkflowAlertEnvelopeV1` is an allowlist and each of the following must
be widened together, or the envelope rejects the alert at construction:

| Element | Location | Change |
|---|---|---|
| `source_kind` | `workflow_alert_models.py:32` | add `"system_check"` |
| `event_key` grammar | `workflow_alert_models.py:141-176` | add a key regex for the new kind |
| `workflow_type` | `workflow_alert_models.py:51` | admit a non-`OperationType` literal |
| `diagnostic_url` | `workflow_alert_models.py:253-276` | permit the readiness/backup diagnostic route |
| diagnostic codes | `WorkflowAlertDiagnosticCode` | add `backup_stale`, `backup_no_history`, `backup_verify_failed` |

`operation_id` and `attempt` are operation-shaped and meaningless for a system
check; the widening must make them optional for the new kind rather than
synthesizing fake values, since a fake operation id would produce a diagnostic URL
that 404s.

### D6 — Emit from the worker's periodic loop, never from `/ready`

**Decision.** `readiness_check()` continues to only *report* `checks["backup"]`.
Alert emission lives in the worker's periodic maintenance loop, alongside
`_drain_workflow_alert_deliveries` (`queue/worker.py:570`).

**Rationale.** `/ready` is polled at probe frequency. Emitting from there would
produce one alert per probe — an alert storm that trains operators to ignore the
channel. Emission must also be idempotent per check window so a flapping probe
cannot multiply alerts.

**Consequences.** Freshness alerting requires a running worker. That is correct:
if the worker is down the system has a larger problem, and the dead-man's-switch
consideration in D7 covers total host loss.

### D7 — Freshness derives from a bucket-side manifest, not `cron.job_run_details`

**Decision.** Each successful `aca backup run` writes
`<prefix>/manifest/latest.json` to the bucket, recording run timestamp, per-store
outcomes, artifact keys, sizes, and checksums. The freshness check reads that
object. The `database_provider == "railway"` gate is removed.

**Rationale.** The current check asks the *source* host whether it believes it ran
a backup. The question that matters is whether an artifact actually **arrived at
the destination**. A manifest in the bucket answers the real question, works
regardless of database provider, and survives the source host being destroyed —
which is the scenario backups exist for.

**Consequences.** The check performs a network read, so it must stay off-thread
and time-bounded exactly as the current implementation does
(`health_routes.py:187-190`), and must degrade to a status string rather than
raising. `checks["backup"]` remains **non-gating**: a stale backup must not flip
`/ready` to 503, because taking the API out of rotation over a backup problem
converts a durability incident into an availability incident.

### D8 — Two pre-existing defects in the freshness check are fixed here

**Decision.** Fix both while rewriting the check:

1. **Unbound `loop`.** `loop` is bound at `health_routes.py:124` inside the
   database `try` block but used at `:188`. If the import at `:122` raises,
   `:188` raises `NameError`, swallowed at `:194` into `"unknown"` — the backup
   signal goes dark precisely when the DB layer breaks.
2. **Misleading warning text.** `:193` hardcodes "2x schedule interval" while the
   real threshold is `railway_backup_staleness_hours` (default 48), independent
   of the schedule.

**Rationale.** Both sit on lines this change already rewrites. Leaving a
known-false log message next to new code is how the current situation arose.

### D9 — Deprecation mapping follows the established `graphdb` pattern

**Decision.** New `backup_s3_*` settings; the `railway_minio_*` and
`railway_backup_bucket` names keep working via a `@model_validator(mode="after")`
that mirrors `_apply_deprecated_neo4j_aliases` (`settings.py:1554-1588`):
`model_fields_set` to distinguish explicit values from defaults, new field wins
when both are set, `object.__setattr__` for in-validator mutation, one
`logger.warning` per mapped group.

**Consequences.** Two settings-hygiene gaps must be closed alongside, or the new
credentials are less protected than the ones they replace:

- `SECRET_KEY_PATTERNS` (`secrets.py:25-31`) matches `*_KEY`, `*_SECRET`,
  `*_PASSWORD`, `*_TOKEN`, `*_CREDENTIAL*`. `BACKUP_S3_ACCESS_KEY_ID` ends in
  `_ID` and would **not** be masked. The pattern list must be extended.
- `scripts/check-profile-secrets.sh` greps only for Anthropic/OpenAI-shaped keys,
  so a hardcoded S3 secret in a profile passes today. Extend it.
- Existing credential fields are plain `str | None`, not `SecretStr`
  (`settings.py:498,696`). New backup credentials use `SecretStr`; converting the
  existing ones is out of scope but noted.

### D10 — Retention is provider-side; the CLI never deletes unattended

**Decision.** Retention (7 daily / 4 weekly / 12 monthly) is expressed as bucket
lifecycle rules, committed as documented configuration under `deploy/backup/`
with an applier that is **dry-run by default** and requires an explicit
`--apply` flag. The backup run itself never deletes.

**Rationale.** Provider-side retention keeps working when gx-10 is down — the
exact condition under which the old `mc rm --older-than` cleanup cron would stop
running, leaving retention silently unenforced. It also satisfies Hard Constraint
2 structurally: there is no unattended delete path to misconfigure.

**Consequences.** Lifecycle syntax differs between R2 and S3, so the applier is
provider-aware, and the committed rules are the source of truth that the runbook
points at. Object Lock / versioning is recommended for S3 and noted for R2 but
not required by this change.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Lost `age` identity key ⇒ all backups unrecoverable | **Critical** | Dual escrow (OpenBao + offline); `aca backup verify` decrypts a canary; runbook leads with key recovery |
| Backups run but never restore-tested | High | Round-trip integration test against a containerized S3-compatible stand-in; runbook prescribes periodic test restores |
| Path B widening breaks the just-landed alert contract | Medium | All five envelope elements widened together with tests; `operation_id`/`attempt` made optional rather than faked |
| Host binaries missing on gx-10 | Medium | `aca backup verify` preflight names each missing binary before any run |
| Partial multi-store failure reported as success | Medium | Per-store outcomes in the manifest; run exits non-zero if any required store fails |
| Test fixture is a `MagicMock`, so new settings silently return truthy Mocks | Low | Replace with an explicit fake exposing only declared fields (see below) |

## Testing Notes

Two traps in the existing test file that the tasks must account for:

- `tests/cli/test_restore_from_cloud.py:29-39` builds `fake_settings` as a
  `MagicMock`. Any *new* setting the command reads returns a truthy `Mock`
  instead of failing, so a missing-config test would pass for the wrong reason.
  Replace with an explicit fake.
- Several tests assert on `mock_run.call_args_list[N]` by **positional index**
  (`:47`, `:325`). Adding or reordering any subprocess step silently breaks them.
  Tests must match on the invoked argv rather than on call position.
