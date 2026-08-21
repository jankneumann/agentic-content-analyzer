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

> **Partially superseded.** D6's rationale stands. Its key sketch does not — see
> A2 for the grammar and A10 for the check-window definition.

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

---

# Amendments from PLAN_REVIEW (round 1)

Twelve critical findings. Each was verified against the tree before being
accepted — the three that reshape the alerting design were confirmed by reading
the constraints themselves, not by trusting the review. These amendments
supersede the named parts of D4–D14.

### A1 — D5 now requires a database migration (supersedes D5 and the proposal's "no migration" claim)

**Finding.** The durable alert path is anchored on `workflow_terminal_events`,
which enforces three CHECK constraints that a `system_check` row violates:
`ck_workflow_terminal_events_source_kind` (`source_kind IN
('operation','reconciliation_action','reconciliation_failure')`),
`ck_workflow_terminal_events_event_identity` (an XOR over three exact
`event_key` formulas), and `ck_workflow_terminal_events_source_shape` (per-kind
nullability of `operation_id` / `claim_generation` / `terminal_status`). The
same DDL is duplicated in `src/queue/setup.py`, and `WorkflowTerminalSourceKind`
is a `StrEnum` in `src/models/workflow_alert.py`.

**Amendment.** The operator was told at the discovery gate that widening Path B
was a Pydantic contract change; it is not. Presented with the real cost, the
operator chose to accept the migration. Therefore:

- An Alembic migration relaxes all three CHECK constraints to admit
  `system_check`, with the new event-key literal form (A2) added to the
  event-identity CHECK and `operation_id` / `claim_generation` /
  `terminal_status` permitted NULL for the new kind.
- The duplicated DDL in `src/queue/setup.py`, the `StrEnum` in
  `src/models/workflow_alert.py`, and the insert path in
  `src/services/workflow_terminal_event_service.py` all move into
  `wp-health-alerts`'s write scope.
- `proposal.md`'s "no migration, deliberately" claim is retracted.
- `has_db_migration` becomes **true**. This is a material change to the risk
  profile the GATEKEEPER assessed under `has_db_migration: false`, and is
  recorded as such rather than absorbed silently.
- Envelope construction is not evidence of delivery. A task proves an
  end-to-end enqueue **and drain** of a `system_check` alert against a migrated
  database.

**Alternative rejected.** Routing over a path needing no terminal-event row —
offered to the operator alongside the migration and declined.

### A2 — One lowercase event-key grammar (supersedes D5's key sketch)

`WorkflowEventKey` is `^[a-z0-9:_-]+$`. Both previously proposed grammars
contained uppercase `T`/`Z` from an ISO-8601 stamp, so **every** emitted alert
would have failed validation at construction — and the two grammars disagreed
with each other on the middle segment.

One grammar now, stated identically in the contract, this design, and the
widened annotation: `system_check:backup_freshness:<epoch-seconds>`, where the
suffix is the check-window start. The condition (stale, no-history, partial)
travels in `codes`, not in the key, so one grammar covers every case and
idempotency-per-window is preserved. The literal form is added to the
event-identity CHECK in the A1 migration.

### A3 — Reuse the existing diagnostic route (supersedes the `/api/v1/health/backup` proposal)

`/api/v1/health/backup` does not exist, is not in `validate_diagnostic_route`'s
allowlist, and no task created it — while `contracts/README.md` simultaneously
claimed no endpoint was added. Rather than add a route, an OpenAPI delta, and an
owning package, the alert points at
`/api/v1/workflow-terminal-events/{event_id}`, which already exists and is
already allowlisted. The contract's type is corrected to absolute, matching the
`AnyUrl` the model actually declares.

### A4 — Graph backup branches on mode, and the snapshot write is declared (supersedes D3's graph note)

`neo4j-admin database dump` needs a stopped database and is impossible against
AuraDB, which `graphdb_mode: cloud` supports. FalkorDB `BGSAVE` is a write, which
contradicted the read-only requirement as originally written.

The requirement now branches on `(graphdb_provider, graphdb_mode)`. The managed
path records a skip with a named reason, following the OpenBao precedent, and the
runbook names the provider-native snapshot that covers it. The read-only scenario
is narrowed to forbid *application-data* mutation, with the provider snapshot as
a single declared exception — precise rather than aspirational.

### A5 — Retention tiers are decided at write time (supersedes D10)

Lifecycle rules expire by age under a prefix; R2 does not support tag filters.
Age-based expiry over one flat prefix keeps everything for N days and then
nothing, so the 4 weekly and 12 monthly tiers **could not exist**. Artifacts are
now written under a tier segment chosen at write time by a documented promotion
rule, and lifecycle rules are expressed per tier prefix. D10's provider-awareness
gains a defined scope: the applier must account for R2 lacking tag filters.

### A6 — Silent-success defences (new; closes the change's own failure mode)

Four gaps each reproduced the exact failure this change exists to eliminate — a
backup that reports success and is not restorable:

1. **Pipeline exit status.** A shell pipeline reports the *last* stage's status.
   `pg_dump` failing halfway still yields zero from `rclone` and uploads a
   truncated ciphertext the manifest records as succeeded. Every stage's status
   is now checked, and a size read-back compares the stored object against the
   bytes streamed.
2. **Partial reads as healthy.** Freshness derived from timestamp alone meant a
   manifest with `overall_outcome: "partial"` reported `ok` — precisely what D11
   rejected when it dismissed reading freshness from a HEAD on the newest
   artifact. Status now reflects outcomes as well as age.
3. **Cross-environment overwrite.** A fixed manifest key under a prefix
   defaulting to a shared constant meant a staging run overwrote the production
   freshness signal: production backups could stop entirely while `/ready`
   reported `ok`. The manifest records its environment and the reader rejects a
   mismatch.
4. **Preflight never ran unattended.** The missing-binary preflight was attached
   to `verify`, which D13 deliberately does not wire to the timer. `run` — the
   only path that ever executes unattended — had none. `run` now preflights the
   binaries it will invoke, before touching any store; it is a subset of
   `verify`'s check (binaries only, no identity).

### A7 — Digest computation named (supersedes the manifest contract's optional fields)

`bytes` and `checksum_sha256` were mandatory in the spec but optional in the
contract, so a manifest omitting both validated — leaving an empty upload
indistinguishable from a good one. They are now conditionally required whenever a
store's outcome is `succeeded`, enforced by `if/then` in the schema.

The digest is produced by teeing into `sha256sum` **inside the same pipeline**, so
no artifact passes through the interpreter — preserving Approach C's property that
multi-GB dumps never enter Python.

### A8 — The shared manifest reader gets an owner (supersedes D14)

D14 required the readiness check and the worker to read through one cached
helper, but `wp-health-alerts` had no service module in scope and explicitly
denied `src/services/backup/**`, which belongs to a package it did not depend on.
The only in-scope options were duplicating the reader (two caches, two timeout
policies) or importing an API module from the queue worker, inverting the
layering.

`src/services/backup/manifest_reader.py` is owned by **`wp-backup-cli`**, which
already owns that tree and already needs a client to write the manifest.
`wp-health-alerts` gains a dependency on `wp-backup-cli` and read-only access to
it, narrowing its deny list. The serialization cost is accepted: one owner for one
cache is worth more than the lost parallelism.

---

# Amendments from PLAN_REVIEW (round 2)

Findings 26 → 12, criticals 12 → 5. All round-1 criticals verified resolved
against the artifacts that had to change, not against the prose claiming they
changed. The remaining five were one surface: the alert contract still did not
match the model.

### A9 — The envelope has six widening points, not five (supersedes D5's table)

**Finding.** A2 fixed the `event_key` grammar in one location. The same class of
defect survived in a second: `_validate_identity_and_collections`
(`workflow_alert_models.py:295`) branches on `source_kind == "operation"` and
falls through to `if self.operation_id is not None or self.workflow_type !=
"content.reconciliation": raise` (`:321-323`). A `system_check` alert with
`workflow_type = "system.backup_freshness"` raises there **after** all five
previously-named elements are widened. D5's table pointed "event_key grammar" at
`:141-176`, which belongs to `WorkflowTerminalEventV1` — a different class
entirely.

**Amendment.** The widening has six points, and reading the model rather than the
table produced a **seventh** the review did not catch:

| # | Element | Location |
|---|---|---|
| 1 | `source_kind` literal | `workflow_alert_models.py:32` |
| 2 | `workflow_type` literal | `:51` |
| 3 | `diagnostic_url` validator | `:253-276` |
| 4 | `WorkflowAlertDiagnosticCode` | code enum |
| 5 | `WorkflowEventKey` grammar | `:48` |
| 6 | **`_validate_identity_and_collections` needs a `system_check` branch** | **`:295-323`** |
| 7 | **`WorkflowAlertCounts` needs the four backup tally fields** | **`:194-201`** |

Point 7 was found by reading the model, not from the review. `WorkflowAlertCounts`
is itself a `StrictModel` with `extra="forbid"` and seven closed fields, none
backup-related — so `counts.manifest_age_seconds` and the per-store tallies are
rejected at construction unless that model is widened too. This is the third time
the same lesson has appeared: **the closed model is authoritative, the table
describing it is not.** Every widening point is now pinned by a test that
constructs a real envelope, never by asserting a regex in isolation.

The `system_check` branch must assert what the other branches assert for their
kinds: `operation_id is None`, `attempt == 1`, `event_key` matching the A2
grammar, and `diagnostic_url` path equal to
`/api/v1/workflow-terminal-events/{event_id}`.

### A10 — "Check window" defined; D6's keying rationale reconciled

**Finding.** A2's epoch-seconds suffix contradicted D6's stated "keyed, not timed
by wall clock" rationale, D6 was left standing as normative, and "check window"
was defined in no artifact — leaving alert volume during a sustained outage
unspecified.

**Amendment.** D6's rationale is upheld and A2's key is corrected in meaning, not
in form. The suffix is **not** a wall-clock read at emission time. It is the start
of the fixed-length window containing the evaluation, computed by truncating the
evaluation time to a multiple of the window length — a pure function of the
window, so every evaluation inside one window derives the identical key regardless
of when the worker happens to run.

The window length equals the configured staleness threshold. Consequence, stated
so it is not discovered in production: during a sustained outage exactly one alert
is emitted per staleness period — not one per worker tick, and not one only.
Re-alerting is what distinguishes an ongoing outage from a transient blip, and the
identical-key property is what makes the durable path deduplicate within a window.

### A11 — The alert schema is authoritative for the diagnostic-code set

The code set drifted across two rounds and *widened* each time (3 → 4 → 6) because
it was enumerated in the design, the contract, and the task list independently.
Patching the count a third time would repeat the failure.

`contracts/events/backup-freshness-alert.schema.json` is now the single source of
truth. Design prose and tasks reference it; they do not restate it. The conformance
test asserts `WorkflowAlertDiagnosticCode` admits exactly the schema's enum — so
the two cannot drift again without a test failing.

### A12 — Schema now mirrors the model field-for-field

Four further mismatches, each of which would have failed the conformance test by
construction: the schema omitted `attempt`, `resource_refs`, `source_keys` and
`counts` (all required by the model); typed `attempt` as `null` where the model
requires `int >= 1`; declared `claim_generation` and `terminal_status`, which are
not envelope fields at all and are rejected by `extra="forbid"`; and admitted
`http://` where the model is https-only and the producer hardcodes https
(`workflow_terminal_event_service.py:568`).

The schema is now checked field-for-field against the model: no missing fields, no
invented fields, identical required sets. That check is mechanical and belongs in
CI, not in a reviewer's attention — task 3.7b asserts it.

---

# Amendments from PLAN_REVIEW (round 3)

Findings 12; criticals 5 → 1. All five round-2 criticals verified closed. The one
remaining critical is new, and it is the most consequential finding of the whole
review.

### A13 — The emitting service is authoritative, not the envelope model (supersedes A9's scope)

**Finding.** A9 concluded that the closed model is authoritative and the table
describing it is not — then applied that conclusion one layer too shallow. All
seven widening points in A9 live in `workflow_alert_models.py`. **That model does
not emit the alert.** `WorkflowTerminalEventService.process_pending_event`
(`workflow_terminal_event_service.py:132`) does, and a `system_check` row hits
three further gates before an envelope is ever constructed:

1. `_validate_event_identity` (`:802-807`) raises for any non-operation kind
   whose `reconciliation_run_id` or `reconciliation_content_id` is NULL. A system
   check has neither.
2. The same function then constructs a `WorkflowTerminalEventV1` (`:810`) — the
   class A9's table dismissed as "a different class entirely." It is on the
   emission path precisely because this function instantiates it.
3. `classify_terminal_event` (`:472`) calls that validator first and then branches
   only on `reconciliation_failure`, falling through to `_operation_type(None)`,
   which raises.

**Why this is the worst possible failure mode.** All three raise `ValueError`, and
`process_pending_event` catches it at `:167`, writing
`classification_status='rejected'` with `envelope=None`. **Nothing raises to the
caller. No delivery is enqueued. No error is logged as a failure.** The
orphan-cleanup query in `src/queue/worker.py:70-86` then DELETEs the row.

Built as planned, *the alert reporting that backups are dead would itself be
silently dropped* — the exact silent-success failure this change exists to
eliminate, reproduced inside the change's own alerting path. Verified by reading
all three call sites, not inferred.

Task 3.7f covered persisting the row. Persisting is not classifying, and
classifying is not projecting. Existing task 3.9b would have caught it — but only
after `wp-health-alerts` was built, which is the wrong time to discover that
`classify_terminal_event` needs a branch nobody designed.

**Amendment.** The widening extends into the service:

| # | Element | Location |
|---|---|---|
| 8 | `_validate_event_identity` needs a `system_check` arm admitting null reconciliation identity | `:802-807` |
| 9 | `WorkflowTerminalEventV1.validate_source_identity` must admit the A2 key grammar | `workflow_alert_models.py:141-176` |
| 10 | `classify_terminal_event` needs a `system_check` branch returning a classification | `:472` |

Point 9 retracts A9's dismissal of `WorkflowTerminalEventV1` as irrelevant. It was
wrong: the service instantiates that class on the emission path.

**Generalised lesson, now stated once instead of rediscovered each round.** Three
rounds produced the same class of defect in five locations — `event_key` grammar,
`_validate_identity_and_collections`, `WorkflowAlertCounts`, then these three.
Each time a *document describing* a constraint stood in for the *code enforcing*
it. The durable fix is not another table: it is that **every widening point is
proven by a test that drives the real emission path end to end** — enqueue a
`system_check` event, drain it, and assert a delivery was actually created.
Envelope construction, classification, and persistence are each necessary and
none is sufficient. Task 3.9b is upgraded accordingly and is the acceptance
criterion for the alerting slice.

### A14 — Round-2 residue and cross-artifact drift

Eight nits, none architectural, all cheap. Recorded rather than deferred, because
three of them are round-2 items that were agreed and then simply not applied —
which is its own lesson about amendment rounds:

- `wp-contracts`'s lock path still named a stale contracts location.
- The manifest key still lacked the environment segment A6.3 required — the
  *reader* check landed, the *key* did not, leaving the cross-environment
  overwrite half-fixed.
- **A8 inverted its own intent**: it granted `wp-health-alerts` read access to
  `manifest_reader.py`, but the yaml *denied* exactly that file, and deny beats
  `read_allow`. The package could not read the reader it was designed to consume.
- Task 3.9 still described D6's superseded "manifest generation" keying while task
  3.7m specified window truncation; D6's superseded sketch still stood as
  normative prose.
- The schema left `release_revision` / `release_revision_source` unconstrained
  where the model pins a pattern, an enum, and a present-together rule.
- Task 3.7k's "agree field-for-field" is not literally satisfiable: the schema is
  *correctly* a narrowed variant in six places (constants and subsets). The
  assertion is restated as narrowing-compatibility — every schema constraint must
  be at least as strict as the model's, and no schema field may be absent from
  the model.

The 48h-vs-24h staleness default is **accepted as-is**: a 24h backup cadence with
a 48h staleness threshold means one missed run is tolerated before alerting,
which is deliberate — alerting on a single transient failure trains operators to
ignore the channel.
