# Tasks — add-gx10-backup-scheme

Task order is test-first within each phase: every implementation task depends on
the test task that pins its behavior.

Size key: XS ≤30min · S 30min–2hr · M 2hr–1day · L 1–3 days.

## Phase 0 — Contracts (wp-contracts)

- [x] 0.1 Land `openspec/contracts/backup/schemas/backup-manifest.schema.json` as the durable manifest contract, including the plaintext-and-credential-free constraints (S)
  **Spec scenarios**: backup-and-restore.4 (Manifest records the run; Manifest contains no credentials; Manifest is readable without the decryption identity)
  **Design decisions**: D7, D11
  **Dependencies**: None
- [x] 0.2 Land the widened alert-envelope event schema beside the existing envelope contracts in `openspec/contracts/content-workflows/events/` (S)
  **Spec scenarios**: backup-and-restore.6 (System-check alerts carry no operation identity)
  **Design decisions**: D5
  **Dependencies**: None
  **Ordering note**: the schema is the coordination boundary, so it lands first. The
  test asserting it agrees with `WorkflowAlertEnvelopeV1` is 3.7b, because the model
  is not widened until 3.7 — asserting agreement here would fail by construction.
- [x] 0.3 Register the `backup` contract domain in `openspec/contracts/README.md` (XS)
  **Dependencies**: 0.1
- [x] 0.4 Checkpoint: contract tests green, diff reviewed, scope verified

## Phase 1 — Backup settings (wp-settings)

- [x] 1.1 Write tests for provider-neutral `backup_s3_*` settings resolution — presence, `SecretStr` typing, `backup_s3_prefix` default, R2 endpoint accepted unchanged (S)
  **Spec scenarios**: backup-and-restore.1 (Backup target settings are available; Cloudflare R2 endpoint requires no protocol change)
  **Design decisions**: D9
  **Dependencies**: None
- [x] 1.2 Add `backup_s3_*` fields to `Settings` with `SecretStr` credentials (S)
  **Dependencies**: 1.1
- [x] 1.3 Write tests for deprecation mapping — legacy-only maps forward, new wins when both set, exactly one warning logged (S)
  **Spec scenarios**: backup-and-restore.1 (Deprecated MinIO settings still resolve; New settings win over deprecated ones), database-provider.1 (Legacy MinIO settings map to the provider-neutral namespace)
  **Design decisions**: D9
  **Dependencies**: None
- [x] 1.4 Implement the `@model_validator(mode="after")` deprecation mapper mirroring `_apply_deprecated_neo4j_aliases` (S)
  **Dependencies**: 1.3
- [x] 1.4b Write tests for the encryption and monitoring settings — presence, `backup_staleness_hours` default parity with the legacy setting, `railway_backup_enabled`/`railway_backup_staleness_hours` mapping forward through the same validator (S)
  **Spec scenarios**: backup-and-restore.1 (Encryption settings are declared in the same surface; Monitoring settings are provider-neutral; Legacy monitoring settings map forward)
  **Design decisions**: D9, D11
  **Dependencies**: 1.3
- [x] 1.4c Add `backup_age_recipient`, `backup_age_identity_path`, `backup_monitoring_enabled`, and `backup_staleness_hours` to `Settings`, and extend the deprecation mapper to cover the two legacy monitoring names (S)
  **Dependencies**: 1.4b, 1.4
- [x] 1.5 Checkpoint: run tests, review diff, verify scope
- [x] 1.6 Write tests for credential masking of identifier-suffixed names (`*_ACCESS_KEY_ID`) (XS)
  **Spec scenarios**: backup-and-restore.1 (Backup credentials are masked in diagnostics)
  **Design decisions**: D9
  **Dependencies**: None
- [x] 1.7 Extend `SECRET_KEY_PATTERNS` to cover identifier-suffixed credential names (XS)
  **Dependencies**: 1.6
- [x] 1.8 Extend `scripts/check-profile-secrets.sh` to detect hardcoded S3-shaped credentials (XS)
  **Dependencies**: 1.6
- [x] 1.9 Declare backup settings in profile config, `.secrets.yaml.example`, and `StorageSettings` — one credential namespace, with the write/read-only split documented as a per-environment value difference per design D11, not as additional settings (S)
  **Design decisions**: D11
  **Dependencies**: 1.2, 1.4c
- [x] 1.9b Declare `boto3` as a runtime dependency in `pyproject.toml`, closing the existing lazy-import gap that the freshness reader would otherwise inherit (XS)
  **Design decisions**: D14
  **Dependencies**: None
- [x] 1.10 Checkpoint: run tests, review diff, verify scope

## Phase 2 — Backup engine and CLI (wp-backup-cli)

- [ ] 2.1 Write tests for per-store backup outcome reporting — success, failure, skipped; non-zero exit when a required store fails (M)
  **Spec scenarios**: backup-and-restore.2 (A failing store does not silently pass; OpenBao is captured when configured)
  **Design decisions**: D3
  **Dependencies**: 1.2
- [ ] 2.2a Implement the store-outcome model (S)
  **Dependencies**: 2.1
- [ ] 2.2b Implement the run orchestrator over that model (S)
  **Dependencies**: 2.2a
- [ ] 2.3 Write tests for each store adapter's invocation, patching `subprocess.run` and asserting on argv rather than call position (M)
  **Spec scenarios**: backup-and-restore.2 (PostgreSQL is captured as a portable dump; Graph database is captured per configured provider; Artifact directories are captured wholesale)
  **Design decisions**: D3
  **Dependencies**: 2.1
- [ ] 2.4 Implement PostgreSQL, graph-database, artifact-directory, and OpenBao store adapters (L — see design note; decomposition attempted below)
  **Dependencies**: 2.3
- [ ] 2.5 Checkpoint: run tests, review diff, verify scope
- [ ] 2.6 Write tests for encryption in the pipe — abort before upload when no recipient configured, encrypted suffix on uploaded key (S)
  **Spec scenarios**: backup-and-restore.3 (Artifacts are encrypted before leaving the host; Missing recipient key aborts before any upload)
  **Design decisions**: D4
  **Dependencies**: 2.1
- [ ] 2.7 Implement `age` encryption in the artifact pipeline (S)
  **Dependencies**: 2.6
- [ ] 2.8 Write tests for manifest contents — timestamps, per-store records, no credentials, not overwritten on failed run (S)
  **Spec scenarios**: backup-and-restore.4 (all scenarios)
  **Design decisions**: D7
  **Dependencies**: 2.1
- [ ] 2.9 Implement manifest writing to the well-known bucket key (S)
  **Dependencies**: 2.8
- [ ] 2.9b Write tests and implementation for canary emission — the run writes an encrypted canary through the same pipeline, and `verify` distinguishes an absent canary from a decryption failure (S)
  **Spec scenarios**: backup-and-restore.3 (The canary is produced by the backup run, not placed by hand)
  **Design decisions**: D4
  **Dependencies**: 2.7, 2.9
- [ ] 2.9c Write a read-only-behavior test asserting the run issues no delete or write operation against source stores and no delete against the backup target (S)
  **Spec scenarios**: backup-and-restore.2 (Backup makes no production mutations), cli-interface.1 (Listing backups does not mutate the target)
  **Dependencies**: 2.1
- [ ] 2.9d Write a failing-mid-pipe test — simulate a non-zero exit from the dump stage and assert the store outcome is `failed`, no manifest is written, and the last stage's zero exit does not mask it (M)
  **Spec scenarios**: backup-and-restore.2 (Every pipeline stage's exit status is checked)
  **Design decisions**: A6.1
  **Dependencies**: 2.1
- [ ] 2.9e Implement per-stage exit-status propagation across the dump/encrypt/upload pipeline (S)
  **Dependencies**: 2.9d
- [ ] 2.9f Write tests for size read-back — assert a stored-object size mismatch against bytes streamed marks the store failed (S)
  **Spec scenarios**: backup-and-restore.2 (Uploaded artifact size is verified against bytes streamed)
  **Design decisions**: A6.1
  **Dependencies**: 2.1
- [ ] 2.9g Implement size read-back verification (S)
  **Dependencies**: 2.9f
- [ ] 2.9h Write tests asserting no credential appears in any constructed subprocess argv across every store adapter (S)
  **Spec scenarios**: backup-and-restore.2 (Credentials are not passed as process arguments)
  **Design decisions**: A6
  **Dependencies**: 2.1
- [ ] 2.9i Pass every credential via process environment or credentials file rather than argv (S)
  **Dependencies**: 2.9h
- [ ] 2.9j Implement in-pipeline SHA-256 via tee so no artifact passes through the interpreter, and record bytes and digest per succeeded store (S)
  **Spec scenarios**: backup-and-restore.4 (Manifest records the run)
  **Design decisions**: A7
  **Dependencies**: 2.8
- [ ] 2.9k Write tests for the retention-tier promotion rule and assert the tier segment appears in the artifact key and the manifest (S)
  **Spec scenarios**: backup-and-restore.2 (Artifacts are written under a retention tier decided at write time)
  **Design decisions**: A5
  **Dependencies**: 2.1
- [ ] 2.9l Implement tier promotion at write time (S)
  **Dependencies**: 2.9k
- [ ] 2.9m Write tests for environment stamping — the manifest records its environment and a foreign-environment manifest is rejected by the reader (S)
  **Spec scenarios**: backup-and-restore.4, backup-and-restore.5 (A manifest from another environment is rejected)
  **Design decisions**: A6.3
  **Dependencies**: 2.8
- [ ] 2.9n Implement `src/services/backup/manifest_reader.py` — the single cached, environment-checked manifest reader consumed by both the readiness check and the worker (M)
  **Design decisions**: A8
  **Dependencies**: 2.9m
- [ ] 2.9o Write tests for graph-database mode branching — local/embedded dumps, cloud records a named skip, FalkorDB snapshot is the declared write exception (M)
  **Spec scenarios**: backup-and-restore.2 (Graph database is captured per configured provider and mode; Managed graph database without filesystem access is skipped explicitly; FalkorDB snapshot is a declared write exception)
  **Design decisions**: A4
  **Dependencies**: 2.3
- [ ] 2.9p Implement graph-database branching on (`graphdb_provider`, `graphdb_mode`) (S)
  **Dependencies**: 2.9o
- [ ] 2.10 Checkpoint: run tests, review diff, verify scope
- [ ] 2.11 Write tests for `aca backup verify` — missing-binary preflight, canary decryption success and failure (S)
  **Spec scenarios**: backup-and-restore.3 (Decryption capability is verified, not assumed), backup-and-restore.8 (Preflight names missing prerequisites)
  **Design decisions**: D4
  **Dependencies**: 2.1
- [ ] 2.12 Implement `aca backup verify` (S)
  **Dependencies**: 2.11
- [ ] 2.13 Write tests for `aca backup list` and the CLI JSON output contract — single JSON document on stdout, no credentials in output (S)
  **Spec scenarios**: cli-interface.1 (all scenarios)
  **Dependencies**: 2.1
- [ ] 2.14a Implement the `aca backup run` command surface (S)
  **Dependencies**: 2.13, 2.2b
- [ ] 2.14b Implement the `aca backup list` command surface (S)
  **Dependencies**: 2.13
- [ ] 2.14c Register the backup command group on the CLI app (XS)
  **Dependencies**: 2.14a, 2.14b
- [ ] 2.14d Write tests asserting `aca backup run` preflights its binaries and aborts naming each missing one before contacting any store (S)
  **Spec scenarios**: backup-and-restore.2 (Scheduled run preflights its binaries before touching any store)
  **Design decisions**: A6.4
  **Dependencies**: 2.11
- [ ] 2.14e Implement the run-side binary preflight as a subset of `verify`'s check — binaries only, no identity (S)
  **Dependencies**: 2.14d
- [ ] 2.15 Checkpoint: run tests, review diff, verify scope

## Phase 3 — Freshness monitoring and alerting (wp-health-alerts)

- [ ] 3.1 Write tests for manifest-derived freshness — ok/stale/no_history/unknown, provider-independence, non-gating readiness (M)
  **Spec scenarios**: backup-and-restore.5 (Freshness is derived from the manifest; Freshness check is provider-independent; Absent manifest is distinguishable from an error; Stale backup does not affect readiness), database-provider.1 (Backup health check)
  **Design decisions**: D7
  **Dependencies**: 1.2
- [ ] 3.2 Write a regression test proving the freshness check still runs when the database health check raises (S)
  **Spec scenarios**: backup-and-restore.5 (Freshness check survives a broken database layer)
  **Design decisions**: D8
  **Dependencies**: None
- [ ] 3.3a Hoist the event-loop binding out of the database `try` block so the freshness check survives a broken database layer (XS)
  **Dependencies**: 3.2
- [ ] 3.3b Rewrite `_check_backup_recency` to derive freshness from the backup target manifest, reading it through the existing S3 client path with the 60-second in-process cache from design D14 (M)
  **Design decisions**: D7, D14
  **Dependencies**: 3.1, 3.3a, 1.9b
- [ ] 3.3c Remove the `database_provider == "railway"` gate from the backup check (XS)
  **Dependencies**: 3.3b
- [ ] 3.3d Write tests for the bounded, non-blocking manifest read and for the disabled path — slow target does not exceed the health-check timeout or block the loop, and `backup_monitoring_enabled=false` reports no status and emits no alert (S)
  **Spec scenarios**: backup-and-restore.5 (Freshness check is bounded and non-blocking; Freshness reader holds no decryption identity), database-provider.1 (Backup disabled)
  **Design decisions**: D7, D11
  **Dependencies**: 3.3b
- [ ] 3.3e Write a guard test asserting no freshness, alerting, or readiness module references a `railway_backup_*` setting name (XS)
  **Spec scenarios**: backup-and-restore.1 (Monitoring settings are provider-neutral)
  **Design decisions**: D9
  **Dependencies**: 3.3c
  **Ordering note**: this guard cannot live in Phase 1. `health_routes.py` still
  reads `railway_backup_enabled` until 3.3c removes the gate, so the assertion is
  only true once the health package has landed.
- [ ] 3.4 Correct the staleness warning text to describe the configured threshold (XS)
  **Spec scenarios**: database-provider.1 (Backup health check)
  **Design decisions**: D8
  **Dependencies**: 3.3b
- [ ] 3.5 Checkpoint: run tests, review diff, verify scope
- [ ] 3.6 Write tests for the widened alert envelope — `system_check` source, key grammar, optional operation fields, resolvable diagnostic URL, rejection of credential-bearing payloads (M)
  **Spec scenarios**: backup-and-restore.6 (System-check alerts carry no operation identity; Alerts never carry credentials)
  **Design decisions**: D5
  **Dependencies**: None
- [ ] 3.7 Widen `WorkflowAlertEnvelopeV1` — source kind, event-key grammar, workflow type, diagnostic-URL validator, diagnostic codes (M)
  **Dependencies**: 3.6
- [ ] 3.7b Update `tests/contract/test_workflow_alert_contracts.py` for the widened envelope — add the `system_check` cases, adjust the closed-allowlist assertions that the widening invalidates, and assert the event schema landed in 0.2 agrees with `WorkflowAlertEnvelopeV1` (S)
  **Spec scenarios**: backup-and-restore.6 (System-check alerts carry no operation identity)
  **Design decisions**: D5
  **Dependencies**: 3.7, 0.2
- [ ] 3.8 Write tests for worker-loop emission — one alert per check window, no emission from the readiness path (S)
  **Spec scenarios**: backup-and-restore.6 (Stale backup raises a durable alert; Readiness polling does not multiply alerts)
  **Design decisions**: D6
  **Dependencies**: 3.6
- [ ] 3.9 Implement idempotent freshness-alert emission in periodic worker maintenance, keyed on the check window per design A10, which supersedes D6's manifest-generation sketch (M)
  **Design decisions**: D6
  **Dependencies**: 3.8, 3.7b, 3.3b
- [ ] 3.7c Write a migration test asserting a `system_check` row is rejected before the migration and accepted after, covering all three CHECK constraints (M)
  **Design decisions**: A1
  **Dependencies**: 3.6
- [ ] 3.7d Author the Alembic migration relaxing `ck_workflow_terminal_events_source_kind`, `ck_workflow_terminal_events_event_identity`, and `ck_workflow_terminal_events_source_shape` to admit `system_check` with null operation-scoped fields (M)
  **Design decisions**: A1
  **Dependencies**: 3.7c
- [ ] 3.7e Mirror the relaxed DDL in `src/queue/setup.py` and add `system_check` to the `WorkflowTerminalSourceKind` StrEnum (S)
  **Design decisions**: A1
  **Dependencies**: 3.7d
- [ ] 3.7f Extend `src/services/workflow_terminal_event_service.py` to persist a system-check event with no operation identity (S)
  **Design decisions**: A1
  **Dependencies**: 3.7e
- [ ] 3.7g Run `alembic heads` and confirm a single head; add a merge revision if the migration introduced a second (XS)
  **Dependencies**: 3.7d
- [ ] 3.7h Write tests that construct a real `WorkflowAlertEnvelopeV1` for a `system_check` alert and assert it survives `_validate_identity_and_collections` — never by asserting a regex in isolation (M)
  **Design decisions**: A9
  **Dependencies**: 3.6
- [ ] 3.7i Add the `system_check` branch to `_validate_identity_and_collections`, asserting null `operation_id`, `attempt == 1`, the A2 event-key grammar, and a diagnostic path equal to the event id (M)
  **Design decisions**: A9
  **Dependencies**: 3.7h
- [ ] 3.7j Widen `WorkflowAlertCounts` with the four backup tally fields — it is a StrictModel with `extra="forbid"`, so backup counts are rejected without this (S)
  **Design decisions**: A9
  **Dependencies**: 3.7h
- [ ] 3.7k Write a mechanical schema-vs-model conformance test asserting narrowing-compatibility between the alert schema and `WorkflowAlertEnvelopeV1` — every schema constraint at least as strict as the model's, and no schema field absent from the model (the schema is correctly a narrowed variant in six places), and that `WorkflowAlertDiagnosticCode` admits exactly the schema's code enum (S)
  **Design decisions**: A11, A12
  **Dependencies**: 3.6
- [ ] 3.7l Write tests for check-window key derivation — every evaluation inside one window derives the identical key, and one alert is emitted per staleness period during a sustained outage (S)
  **Design decisions**: A10
  **Dependencies**: 3.6
- [ ] 3.7m Implement check-window truncation as a pure function of the window length (S)
  **Dependencies**: 3.7l
- [ ] 3.7n Write a test driving the REAL emission path — enqueue a `system_check` terminal event, run `process_pending_event`, and assert a delivery is created; assert the pre-fix behaviour is a silent `classification_status='rejected'` with no delivery and no raise (M)
  **Design decisions**: A13
  **Dependencies**: 3.7f
- [ ] 3.7o Add a `system_check` arm to `_validate_event_identity` admitting null reconciliation identity, and admit the A2 key grammar in `WorkflowTerminalEventV1.validate_source_identity` (M)
  **Design decisions**: A13
  **Dependencies**: 3.7n
- [ ] 3.7p Add a `system_check` branch to `classify_terminal_event` returning a classification instead of falling through to `_operation_type(None)` (M)
  **Design decisions**: A13
  **Dependencies**: 3.7o
- [ ] 3.9b ACCEPTANCE — end-to-end test proving a `system_check` alert is persisted, classified, projected to an envelope, and drained to a delivery against a migrated database. Envelope construction, classification and persistence are each necessary and none is sufficient; assert a delivery row exists and that no path silently sets `classification_status='rejected'` (M)
  **Design decisions**: A1
  **Dependencies**: 3.9, 3.7f
- [ ] 3.9c Write tests asserting a fresh-but-partial manifest is not reported `ok` and raises the partial alert code (S)
  **Spec scenarios**: backup-and-restore.5 (A fresh but partial run does not report healthy)
  **Design decisions**: A6.2
  **Dependencies**: 3.1
- [ ] 3.9d Implement outcome-aware freshness so status reflects `overall_outcome` and per-store outcomes, not age alone (S)
  **Dependencies**: 3.9c, 3.3b
- [ ] 3.10 Checkpoint: run tests, review diff, verify scope

## Phase 4 — Restore path (wp-restore-cli)

- [ ] 4.1 Replace the `MagicMock` settings fixture with an explicit fake exposing only declared fields (S)
  **Design decisions**: D9 (see design § Testing Notes)
  **Dependencies**: None
- [ ] 4.1b Rewrite positional `call_args_list[N]` assertions to match on invoked argv, and remove the skipped round-trip placeholder now owned by the integration package (S)
  **Design decisions**: D9 (see design § Testing Notes)
  **Dependencies**: None
- [ ] 4.2 Write tests for endpoint-agnostic restore and prefix-based artifact discovery independent of the `railway-` filename prefix (M)
  **Spec scenarios**: cli-interface.2 (Restore works against any S3-compatible target; Backup artifacts are discovered independently of legacy naming)
  **Dependencies**: 4.1, 1.2
- [ ] 4.3 Repoint the restore command at the provider-neutral settings and generalize artifact discovery (M)
  **Dependencies**: 4.2
- [ ] 4.4 Checkpoint: run tests, review diff, verify scope
- [ ] 4.5 Write tests for the three security fixes — no credentials in subprocess argv, masked target database in JSON output, live-database guard resisting URL variation (M)
  **Spec scenarios**: cli-interface.2 (Credentials are not passed as process arguments; Command output masks the target database credentials; Live database safeguard resists URL variation)
  **Dependencies**: 4.1
- [ ] 4.6 Pass storage credentials via environment rather than argv (S)
  **Dependencies**: 4.5
- [ ] 4.7 Mask credentials in the emitted target database value (S)
  **Dependencies**: 4.5
- [ ] 4.8 Compare databases by the normalized `(host, effective port, database name)` identity defined in design D12 rather than raw string equality in the live-database guard (S)
  **Design decisions**: D12
  **Dependencies**: 4.5
- [ ] 4.8b Write a regression test proving the existing destructive-restore confirmation safeguard survives the rewrite (S)
  **Spec scenarios**: cli-interface.2 (Destructive restore safeguards are retained)
  **Dependencies**: 4.1
- [ ] 4.9 Write tests for restore-side decryption, including the missing-identity abort (S)
  **Spec scenarios**: cli-interface.2 (Encrypted artifacts are decrypted during restore)
  **Design decisions**: D4
  **Dependencies**: 4.1
- [ ] 4.10 Implement `age` decryption in the restore pipeline (S)
  **Dependencies**: 4.9
- [ ] 4.11 Checkpoint: run tests, review diff, verify scope

## Phase 5 — Deployment assets, retention, documentation (wp-deploy-assets)

- [ ] 5.1 Write tests for the retention applier — dry-run default, explicit flag required to modify, both provider dialects emitted (S)
  **Spec scenarios**: backup-and-restore.7 (all scenarios)
  **Design decisions**: D10
  **Dependencies**: 1.2
- [ ] 5.2 Author the committed tiered retention configuration (7 daily / 4 weekly / 12 monthly) (S)
  **Dependencies**: 5.1
- [ ] 5.3 Implement the dry-run-by-default retention applier (S)
  **Dependencies**: 5.1
- [ ] 5.4 Author the systemd service and timer units invoking the backup command, resolving configuration through the application's own settings path per design D13 — dedicated user, `PROFILE`, root-owned `0600` `EnvironmentFile`, write credential and recipient key only, no identity key, no secret in the unit file (S)
  **Spec scenarios**: backup-and-restore.8 (Scheduling units are provided; Scheduling requires no database privileges), database-provider.1 (Backup job execution)
  **Design decisions**: D13
  **Dependencies**: 2.14c
- [ ] 5.4b Write a test asserting the shipped units contain no literal secret and never invoke a delete operation (XS)
  **Spec scenarios**: backup-and-restore.7 (No unattended deletion path exists), database-provider.1 (Backup retention cleanup)
  **Design decisions**: D10, D13
  **Dependencies**: 5.4
- [ ] 5.5 Checkpoint: run tests, review diff, verify scope
- [ ] 5.6 Write the gx-10 multi-store restore runbook, leading with decryption-identity recovery (M)
  **Spec scenarios**: backup-and-restore.9 (Restore is possible for each backed-up store)
  **Design decisions**: D4
  **Dependencies**: 4.10
- [ ] 5.7 Document the `age` key-escrow procedure, the lost-key consequence, and the issuance of the two separate target credentials — gx-10 write, app-tier manifest read-only (S)
  **Design decisions**: D4, D11
  **Dependencies**: 5.6
- [ ] 5.8 Update `docs/SYNC_DOWN.md` and `docs/SETUP.md` for the provider-neutral target (S)
  **Dependencies**: 4.3
- [ ] 5.9 Record the three-point pg_cron backup failure in `docs/GOTCHAS.md`, and record that `railway_backup_schedule` and `railway_backup_retention_days` are inert (XS)
  **Spec scenarios**: database-provider.1 (Backup settings configuration)
  **Design decisions**: D1
  **Dependencies**: None
- [ ] 5.10 Checkpoint: run tests, review diff, verify scope

## Phase 6 — Round-trip verification (wp-integration)

- [ ] 6.1 Provision a containerized S3-compatible backup target fixture in the compose stack (M)
  **Spec scenarios**: backup-and-restore.9 (Round-trip restore is verified by test)
  **Dependencies**: 2.14c
- [ ] 6.2 Implement the round-trip integration test in the integration suite — seed → backup → encrypt → upload → download → decrypt → restore → compare — replacing the placeholder removed in 4.1b (M)
  **Spec scenarios**: backup-and-restore.9 (Round-trip restore is verified by test)
  **Dependencies**: 6.1, 4.10
- [ ] 6.3 Merge work-package branches and run the full suite (M)
  **Dependencies**: 6.2, 3.9, 5.8
  **Scope note**: this is the integration task, so its diff spans every package's
  files by construction. Package scope enforcement is satisfied by
  `task_type: integrate` on `wp-integration`, not by that package's `write_allow`
  globs; a merge must not be treated as a scope violation.
- [ ] 6.4 Final checkpoint: full suite green, diff reviewed, every task's scope verified

## Note on task 2.4 sizing

2.4 is the single L-sized task. Decomposition into four M tasks (one per store
adapter) was attempted and rejected: the four adapters share one `StoreAdapter`
interface, and splitting them produces four packages that each redefine or wait
on that interface, which raises coordination risk more than it lowers
implementation risk. It is kept as one L task with a checkpoint immediately
after (2.5), and its test task (2.3) covers each adapter independently so
partial progress is still verifiable.


## Note on remaining conjunctive task titles

The "and" splitting heuristic flags five further titles. Each was reviewed and
kept, because the conjunction lists sites or methods for a **single outcome**
rather than joining two outcomes:

| Task | Why it stays one task |
|---|---|
| 1.9 | One outcome — declare the setting — across three declaration sites that must land together or the setting is half-declared. |
| 2.3 | One outcome — write the adapter tests. "patching … and asserting …" describes the method, not a second deliverable. |
| 2.4 | Decomposition attempted and rejected; rationale recorded below. |
| 2.11 | One outcome — the verify test — covering both branches of the same assertion. |
| 2.13 | One outcome — the command's test suite. The JSON contract is a property of that command, not separate work. |
| 5.4 | One outcome — the scheduling units. The clauses after "per design D13" enumerate the constraints the units must satisfy, not additional deliverables. |

Plan iteration 1 added Phase 0 and eleven tasks (1.4b–1.4d, 2.9b, 2.9c, 3.3d,
3.7b, 4.8b, 5.4b) to close settings gaps that structurally blocked downstream
packages, to attach the six spec scenarios that had no owning task, and to bring
the existing alert contract test inside the owning package's scope.

Three titles that *did* join distinct outcomes were split: 2.2 → 2.2a/2.2b,
2.14 → 2.14a/b/c, and 3.3 → 3.3a/b/c. In 3.3 the split matters beyond tidiness:
3.3a is a standalone bug fix (design D8) that is independently valuable and
independently testable, and burying it inside the manifest rewrite would have
hidden it from review.
