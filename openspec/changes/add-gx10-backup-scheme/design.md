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

**Canary provenance.** The canary is not a hand-placed artifact — an artifact
nobody re-creates is an artifact that silently ages out under the lifecycle rules
in D10. Every successful `aca backup run` writes
`<prefix>/canary/latest.age`: a small, fixed, non-sensitive payload encrypted to
`backup_age_recipient` in the same pipeline as every other artifact. `verify`
downloads that object and decrypts it with `backup_age_identity_path`. Because it
is produced by the same code path as the real artifacts, a canary that decrypts is
evidence about the real artifacts and not about a special case. `verify` reports
`no_canary` — distinct from a decryption failure — when the object is absent, so a
never-run backup is not misreported as a broken key.

**Identity availability.** The gx-10 backup host needs only the *recipient*
(public) key to run a backup. `backup_age_identity_path` is required by `verify`
and by restore, not by `run`. This is deliberate: a host compromised through the
backup timer yields no ability to decrypt existing backups.

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

**Definition of "check window".** Idempotency is keyed, not timed by wall clock.
The emitter derives the alert's `event_key` from the condition plus the manifest
generation it observed — `system_check:backup_stale:<manifest_completed_at>` — and
the durable path's existing exactly-once semantics suppress the duplicate. The
consequences are the ones intended: while a backup stays stale the manifest
timestamp does not move, so exactly one alert exists no matter how often
maintenance runs; and when a *new* backup lands and is itself stale, the timestamp
moves and a new alert is emitted rather than being swallowed by the old one. For
`backup_no_history` there is no manifest timestamp, so the key uses the UTC date —
one alert per day until a backup lands.

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

### D11 — The manifest is the one plaintext object, and the app tier gets a read-only credential

**Decision.** `<prefix>/manifest/latest.json` is written **unencrypted**. It is
the single, explicit exception to D4. The API and worker processes read it with a
**read-only, prefix-scoped** backup-target credential and are **never** given
`backup_age_identity_path`.

**Rationale.** D4 and D7 pull in opposite directions and the tension has to be
resolved in one place rather than discovered during implementation. If the
manifest were encrypted, every process that reports backup freshness — the API
serving `/ready`, and the worker emitting alerts — would need the identity key.
That would put the key that decrypts every backup into the two most
network-exposed processes in the system, to answer a question ("when did a backup
last land?") that carries no PII. The blast radius of that trade is much larger
than the information the manifest exposes.

The exception is safe only because the manifest is *constructed* to be safe:
object keys, byte sizes, checksums, timestamps, and per-store outcomes. The
requirement "Manifest contains no credentials" is therefore not a hygiene nicety
but the precondition that makes this decision valid, and it is pinned by test
(task 2.8).

**Consequences.**
- Two credentials exist, not one. gx-10's backup timer holds a write credential;
  the app tier holds a read-only credential scoped to `<prefix>/manifest/*`.
- **This is a deployment split, not a settings split.** Both processes read the
  same `backup_s3_access_key_id` / `backup_s3_secret_access_key` names; the
  *values* differ per environment. No `backup_s3_readonly_*` settings are added.
  Adding a parallel credential namespace would mean every reader had to choose
  between two, and the wrong choice fails open — the app tier would keep working
  with a write credential and nobody would notice. Separation is enforced where it
  is actually enforceable: at the provider, when the runbook issues the keys.
- An attacker with the app tier's credential learns backup *cadence* and object
  names — not backup *contents*. That is the accepted disclosure.
- The canary (D4) stays encrypted, so `verify` — which does hold the identity —
  remains the only path that proves decryptability.

**Alternatives rejected.** Encrypting the manifest and giving the app tier the
identity (largest blast radius, for a status timestamp). Reporting freshness from
`HEAD` on the newest artifact key rather than a manifest (no per-store outcomes,
and a partially-failed run would read as a healthy backup — the exact failure mode
D7 exists to eliminate).

### D12 — The live-database guard compares connection identity, not URL text

**Decision.** `restore_commands.py:110-120` currently compares
`str(local_url).strip() == str(railway_url).strip()`. It is replaced by a
comparison of a normalized tuple parsed from each URL:
`(lowercased host, effective port, database name)`, where the effective port is
the scheme's default (5432) when the URL omits it, and the database name is the
path with its leading slash removed.

**Rationale.** "Normalized identity" would otherwise be an ambiguous instruction
with several defensible readings, and the guard is a safety control — an
implementer guessing at its semantics is exactly the wrong outcome. The listed
components are the ones that determine *which database is written to*.

**Explicitly excluded from the comparison**, each for a reason:
- **Username and password** — the same database reached as two different roles is
  still the same database, and including credentials would let a URL that differs
  only by user slip past the guard.
- **Query parameters** (`?sslmode=`, `?options=`) — connection transport, not
  identity.
- **DNS resolution** — the guard does **not** resolve hostnames. Resolution is a
  network call on a safety path, it varies with split-horizon DNS, and it would
  make the guard's verdict depend on the resolver's mood. Two different hostnames
  that resolve to one server are not caught; that is the accepted limit, and it is
  strictly better than today's exact-string comparison.

**Consequences.** The guard becomes non-trivially testable — the spec scenario
"Live database safeguard resists URL variation" is satisfiable with cases like a
default-port omission and a case-differing host. The `--allow-remote-target`
opt-in is unchanged and remains the only override.

### D13 — The scheduled unit receives its configuration the same way the app does

**Decision.** `deploy/backup/aca-backup.service` runs `aca backup run` as a
dedicated non-login `aca-backup` user with `PROFILE` set and an
`EnvironmentFile=` pointing at a root-owned, `0600` env file holding the backup
target's write credential and `BACKUP_AGE_RECIPIENT`. It does **not** re-implement
configuration resolution, and it does **not** carry the age identity.

**Rationale.** The whole argument for Approach C over Approach A is that backup
configuration cannot drift from application configuration. A systemd unit that
sourced its own separate settings would reintroduce exactly the drift the approach
was chosen to prevent — and the failure it produces is silent, because a backup
pointed at the wrong bucket still exits zero.

**Consequences.**
- Where the deployment already uses OpenBao, the unit may instead resolve secrets
  through the app's existing OpenBao path; the env file is the floor, not the
  ceiling. Either way the secret never appears in the unit file, which is
  world-readable.
- `aca backup verify` is **not** wired to the timer, because it needs the identity
  key and `run` deliberately does not have it. Verify is an operator-invoked
  command, and the runbook schedules it as a periodic manual restore drill.
- The unit's failure path matters as much as its success path: `run` exiting
  non-zero must be visible. Freshness alerting (D5/D6) covers this without any
  systemd-side notification, because a failed run writes no manifest (D7) and the
  manifest therefore goes stale.

### D14 — The app tier reads the manifest through the existing S3 client, and `boto3` becomes a declared dependency

**Decision.** The freshness reader retrieves `<prefix>/manifest/latest.json`
through the S3 client path that `src/services/file_storage.py` already uses, and
caches the parsed result in-process for 60 seconds. `boto3` is added to
`pyproject.toml` as a declared runtime dependency.

**Rationale.** D7 makes the freshness signal a network read, and the design has
to say *with what* — leaving it open would hand an implementer three choices with
very different consequences:

| Mechanism | Why not |
|---|---|
| Shell out to `rclone` per check | `/ready` is polled at probe frequency; a process spawn per probe is a real cost, and it puts a subprocess on the liveness path |
| Hand-rolled SigV4 over `httpx` | Avoids a dependency by writing signing code by hand, on the path that reports whether the backups are alive |
| Existing `boto3` client path | Already in the tree, already used for the S3 storage provider, already tested |

The third is the only one that adds nothing new. The tension with Approach C's
"no `boto3` requirement" is real but narrow, and worth naming: that argument was
about **streaming multi-GB dumps** through the interpreter, which this change
still does not do — dumps go `pg_dump | age | rclone`. A one-object JSON GET is a
different problem with different costs.

Declaring `boto3` also closes a latent defect rather than creating one. It is
imported lazily at `file_storage.py:381` and appears nowhere in
`pyproject.toml`, so the S3 storage provider today fails at first use on any
deployment that did not happen to install it. The freshness check would inherit
exactly that failure — and inherit it *silently*, degrading to
`checks["backup"] = "unknown"` forever, which is the precise failure mode this
whole change exists to eliminate.

**Consequences.**
- The 60-second cache bounds network reads regardless of probe frequency, and is
  far shorter than any staleness threshold, so it cannot mask a real transition.
- The cache is per-process and in-memory; the worker's alert emission (D6) reads
  through the same helper and inherits the same bound.
- The dependency lands in Phase 1 (task 1.9b), before any package consumes it.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Lost `age` identity key ⇒ all backups unrecoverable | **Critical** | Dual escrow (OpenBao + offline); `aca backup verify` decrypts a canary; runbook leads with key recovery |
| Backups run but never restore-tested | High | Round-trip integration test against a containerized S3-compatible stand-in; runbook prescribes periodic test restores |
| Path B widening breaks the just-landed alert contract | Medium | All five envelope elements widened together with tests; `operation_id`/`attempt` made optional rather than faked |
| Host binaries missing on gx-10 | Medium | `aca backup verify` preflight names each missing binary before any run |
| Partial multi-store failure reported as success | Medium | Per-store outcomes in the manifest; run exits non-zero if any required store fails |
| Test fixture is a `MagicMock`, so new settings silently return truthy Mocks | Low | Replace with an explicit fake exposing only declared fields (see below) |
| App-tier bucket credential is over-privileged, or is granted the age identity | High | D11 — read-only manifest-scoped credential; identity never leaves gx-10/escrow; pinned by the credential-scope scenario |
| Widening `WorkflowAlertEnvelopeV1` breaks `tests/contract/test_workflow_alert_contracts.py`, which is outside the owning package's write scope | Medium | File added to `wp-health-alerts` write scope and to its verification steps (task 3.7b) |
| Hand-maintained alert JSON Schema drifts from the Pydantic envelope, which has no generator | Medium | Schema lives beside the envelope in `content-workflows/events/`, and a conformance test asserts schema-vs-model agreement (task 3.7b, after the widening lands) |
| `boto3` undeclared, so the freshness check degrades silently to `unknown` | Medium | D14 — declared in `pyproject.toml` in Phase 1, before any consumer |

## Testing Notes

Two traps in the existing test file that the tasks must account for:

- `tests/cli/test_restore_from_cloud.py:29-39` builds `fake_settings` as a
  `MagicMock`. Any *new* setting the command reads returns a truthy `Mock`
  instead of failing, so a missing-config test would pass for the wrong reason.
  Replace with an explicit fake.
- Several tests assert on `mock_run.call_args_list[N]` by **positional index**
  (`:47`, `:325`). Adding or reordering any subprocess step silently breaks them.
  Tests must match on the invoked argv rather than on call position.
