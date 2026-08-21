# Tasks — add-gx10-backup-scheme

Task order is test-first within each phase: every implementation task depends on
the test task that pins its behavior.

Size key: XS ≤30min · S 30min–2hr · M 2hr–1day · L 1–3 days.

## Phase 1 — Backup target settings (wp-settings)

- [ ] 1.1 Write tests for provider-neutral `backup_s3_*` settings resolution — presence, `SecretStr` typing, `backup_s3_prefix` default, R2 endpoint accepted unchanged (S)
  **Spec scenarios**: backup-and-restore.1 (Backup target settings are available; Cloudflare R2 endpoint requires no protocol change)
  **Design decisions**: D9
  **Dependencies**: None
- [ ] 1.2 Add `backup_s3_*` fields to `Settings` with `SecretStr` credentials (S)
  **Dependencies**: 1.1
- [ ] 1.3 Write tests for deprecation mapping — legacy-only maps forward, new wins when both set, exactly one warning logged (S)
  **Spec scenarios**: backup-and-restore.1 (Deprecated MinIO settings still resolve; New settings win over deprecated ones), database-provider.1 (Legacy MinIO settings map to the provider-neutral namespace)
  **Design decisions**: D9
  **Dependencies**: None
- [ ] 1.4 Implement the `@model_validator(mode="after")` deprecation mapper mirroring `_apply_deprecated_neo4j_aliases` (S)
  **Dependencies**: 1.3
- [ ] 1.5 Checkpoint: run tests, review diff, verify scope
- [ ] 1.6 Write tests for credential masking of identifier-suffixed names (`*_ACCESS_KEY_ID`) (XS)
  **Spec scenarios**: backup-and-restore.1 (Backup credentials are masked in diagnostics)
  **Design decisions**: D9
  **Dependencies**: None
- [ ] 1.7 Extend `SECRET_KEY_PATTERNS` to cover identifier-suffixed credential names (XS)
  **Dependencies**: 1.6
- [ ] 1.8 Extend `scripts/check-profile-secrets.sh` to detect hardcoded S3-shaped credentials (XS)
  **Dependencies**: 1.6
- [ ] 1.9 Declare backup settings in profile config, `.secrets.yaml.example`, and `StorageSettings` (S)
  **Dependencies**: 1.2
- [ ] 1.10 Checkpoint: run tests, review diff, verify scope

## Phase 2 — Backup engine and CLI (wp-backup-cli)

- [ ] 2.1 Write tests for per-store backup outcome reporting — success, failure, skipped; non-zero exit when a required store fails (M)
  **Spec scenarios**: backup-and-restore.2 (A failing store does not silently pass; OpenBao is captured when configured)
  **Design decisions**: D3
  **Dependencies**: 1.2
- [ ] 2.2 Implement the store-outcome model and run orchestrator (M)
  **Dependencies**: 2.1
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
- [ ] 2.14 Implement `aca backup run` and `aca backup list` command surface and register the group (S)
  **Dependencies**: 2.13, 2.2
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
- [ ] 3.3 Rewrite `_check_backup_recency` against the manifest, de-gate the provider condition, and hoist the event-loop binding out of the database `try` block (M)
  **Dependencies**: 3.1, 3.2
- [ ] 3.4 Correct the staleness warning text to describe the configured threshold (XS)
  **Spec scenarios**: database-provider.1 (Backup health check)
  **Design decisions**: D8
  **Dependencies**: 3.3
- [ ] 3.5 Checkpoint: run tests, review diff, verify scope
- [ ] 3.6 Write tests for the widened alert envelope — `system_check` source, key grammar, optional operation fields, resolvable diagnostic URL, rejection of credential-bearing payloads (M)
  **Spec scenarios**: backup-and-restore.6 (System-check alerts carry no operation identity; Alerts never carry credentials)
  **Design decisions**: D5
  **Dependencies**: None
- [ ] 3.7 Widen `WorkflowAlertEnvelopeV1` — source kind, event-key grammar, workflow type, diagnostic-URL validator, diagnostic codes (M)
  **Dependencies**: 3.6
- [ ] 3.8 Write tests for worker-loop emission — one alert per check window, no emission from the readiness path (S)
  **Spec scenarios**: backup-and-restore.6 (Stale backup raises a durable alert; Readiness polling does not multiply alerts)
  **Design decisions**: D6
  **Dependencies**: 3.6
- [ ] 3.9 Implement idempotent freshness-alert emission in periodic worker maintenance (M)
  **Dependencies**: 3.8, 3.7, 3.3
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
- [ ] 4.8 Compare databases by normalized identity rather than raw string equality in the live-database guard (S)
  **Dependencies**: 4.5
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
- [ ] 5.4 Author the systemd service and timer units invoking the backup command (S)
  **Spec scenarios**: backup-and-restore.8 (Scheduling units are provided; Scheduling requires no database privileges)
  **Dependencies**: 2.14
- [ ] 5.5 Checkpoint: run tests, review diff, verify scope
- [ ] 5.6 Write the gx-10 multi-store restore runbook, leading with decryption-identity recovery (M)
  **Spec scenarios**: backup-and-restore.9 (Restore is possible for each backed-up store)
  **Design decisions**: D4
  **Dependencies**: 4.10
- [ ] 5.7 Document the `age` key-escrow procedure and the lost-key consequence (S)
  **Design decisions**: D4
  **Dependencies**: 5.6
- [ ] 5.8 Update `docs/SYNC_DOWN.md` and `docs/SETUP.md` for the provider-neutral target (S)
  **Dependencies**: 4.3
- [ ] 5.9 Record the three-point pg_cron backup failure in `docs/GOTCHAS.md` (XS)
  **Design decisions**: D1
  **Dependencies**: None
- [ ] 5.10 Checkpoint: run tests, review diff, verify scope

## Phase 6 — Round-trip verification (wp-integration)

- [ ] 6.1 Provision a containerized S3-compatible backup target fixture in the compose stack (M)
  **Spec scenarios**: backup-and-restore.9 (Round-trip restore is verified by test)
  **Dependencies**: 2.14
- [ ] 6.2 Implement the round-trip integration test in the integration suite — seed → backup → encrypt → upload → download → decrypt → restore → compare — replacing the placeholder removed in 4.1b (M)
  **Spec scenarios**: backup-and-restore.9 (Round-trip restore is verified by test)
  **Dependencies**: 6.1, 4.10
- [ ] 6.3 Merge work-package branches and run the full suite (M)
  **Dependencies**: 6.2, 3.9, 5.8
- [ ] 6.4 Final checkpoint: full suite green, diff reviewed, every task's scope verified

## Note on task 2.4 sizing

2.4 is the single L-sized task. Decomposition into four M tasks (one per store
adapter) was attempted and rejected: the four adapters share one `StoreAdapter`
interface, and splitting them produces four packages that each redefine or wait
on that interface, which raises coordination risk more than it lowers
implementation risk. It is kept as one L task with a checkpoint immediately
after (2.5), and its test task (2.3) covers each adapter independently so
partial progress is still verifiable.
