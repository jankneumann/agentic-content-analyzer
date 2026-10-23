# GX-10 observability operations

This runbook covers correlated-operation diagnostics and the GX-10 observability
services. It does not authorize a production cutover.

> **Acceptance status:** the deterministic verifier and offline fixture rehearsal
> are implemented, but the six-hour acceptance soak, native encrypted restore
> drill, and clean-stack cold restart are **not complete**. Tasks 8.5, 8.10, 9.5,
> 10.2, and 10.3 remain held. Do not activate GX-10 mutation ownership from this
> runbook and do not represent fixture output as live Langfuse, restart, restore,
> or soak evidence.

## Trace lookup workflow

Use the durable operation ID as the first lookup key. Keep credentials in the
environment; never put their values in command arguments, shell history,
evidence files, or issue comments.

```bash
export ACA_ORIGIN=https://gx10.example.com
export ADMIN_API_KEY='...'
export OPERATOR_API_KEY='...'
export OPERATION_ID=42

curl --fail-with-body --silent --show-error \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -H "X-Operator-Key: ${OPERATOR_API_KEY}" \
  "${ACA_ORIGIN}/api/v1/operations/${OPERATION_ID}" | jq '{operation_id,status,observability}'

curl --fail-with-body --silent --show-error \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -H "X-Operator-Key: ${OPERATOR_API_KEY}" \
  "${ACA_ORIGIN}/api/v1/operations/${OPERATION_ID}/attempts?limit=50" \
  | jq '{operation_id,root_operation_id,attempts,attempts_omitted,next_after_claim_generation}'
```

The exact-operation response supplies the root operation ID, trace ID, latest
attempt, telemetry-delivery state, and—only for the distinct operator
capability—a server-generated Langfuse URL. Follow that URL; never construct a
Langfuse link from a request value or an internal container hostname. Attempt
pages are ordered by ascending claim generation. Continue with
`after_claim_generation=<next_after_claim_generation>` until the cursor is null.

For an HTTP request, capture the `X-Trace-Id` response header and confirm it
equals the durable trace ID:

```bash
headers_file="$(mktemp)"
trap 'rm -f -- "$headers_file"' EXIT
curl --dump-header "$headers_file" --output /dev/null --fail-with-body \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" "${ACA_ORIGIN}/api/v1/operations/${OPERATION_ID}"
awk 'tolower($1)=="x-trace-id:" {print $2}' "$headers_file" | tr -d '\r'
```

### Deterministic smoke verifier

`scripts/gx10/verify_observability.py` has deliberately separate modes:

- fixture mode rehearses the evidence contract offline and is never live proof;
- live mode executes one absolute submit adapter exactly once, carries only its
  returned operation/root/trace identity, and polls an absolute collection
  adapter. A snapshot for any other identity fails with
  `submission_identity_mismatch`.

Both adapters receive bounded JSON on stdin and return one bounded JSON object on
stdout. They are launched as argument arrays without a shell. Credential values
are inherited only for names explicitly supplied by `--adapter-env-name`; live
canaries are read only from names supplied by `--canary-env-name`. Adapter stderr,
raw evidence, exception text, and canary values are never copied into the report.

The submit request fixes scenario
`gx10-observability-retry-restart-v1`: a queued `summarization.run`, a forced
retryable first-attempt failure, persisted context before restart, and restart
before retry. A conforming submit adapter returns only `operation_id`,
`root_operation_id`, and `trace_id`. The collect adapter uses those IDs to return
the API response/header, PostgreSQL attempts, correlated API/worker logs,
Langfuse observations/generation metadata, and export-health fields.

After installing reviewed deployment-specific adapters at root-owned absolute
paths, run:

```bash
export GX10_SMOKE_CANARY="gx10-smoke-$(openssl rand -hex 16)"
uv run python scripts/gx10/verify_observability.py \
  --live-submit-command /opt/aca/bin/gx10-observability-submit \
  --live-collect-command /opt/aca/bin/gx10-observability-collect \
  --adapter-env-name ACA_ORIGIN \
  --adapter-env-name ADMIN_API_KEY \
  --adapter-env-name OPERATOR_API_KEY \
  --adapter-env-name DATABASE_URL \
  --adapter-env-name LANGFUSE_PUBLIC_KEY \
  --adapter-env-name LANGFUSE_SECRET_KEY \
  --canary-env-name GX10_SMOKE_CANARY \
  --timeout-seconds 30 \
  --output /var/lib/aca/gx10/observability-smoke.json
```

Exit zero and `ready:true` mean this one bounded smoke passed. They do not satisfy
the six-hour task 9.5 gate. The report is created mode `0600`; a pre-existing
temporary file or symlink causes a safe refusal.

Offline fixture rehearsal is explicit:

```bash
uv run python scripts/gx10/verify_observability.py \
  --fixture /path/to/reviewed-evidence-fixture.json \
  --canary gx10-secret-canary-do-not-export \
  --output /tmp/gx10-fixture-report.json
```

## Stage and error catalog

The frozen stages are:

| Area | Stages |
|---|---|
| Admission | `submit`, `queue_wait`, `claim` |
| Acquisition | `fetch`, `discover`, `metadata`, `transcript`, `extract`, `parse` |
| Decision | `filter`, `deduplicate`, `model`, `fallback` |
| Commit | `persist`, `index`, `graph`, `deliver` |
| Operations | `backup`, `restore`, `alert`, `cleanup`, `flush` |

Canonical outcomes are `succeeded`, `partial`, `skipped_policy`,
`skipped_duplicate`, `filtered`, `retryable_failure`, `permanent_failure`, and
`cancelled`. Telemetry delivery is `pending`, `delivered`, `degraded`, `dropped`,
or `disabled`.

Diagnostic and error codes are stable, lowercase machine codes—not exception
messages. An attempt carries at most 20 codes and 2 KiB total code text; omitted
items increment `diagnostics_omitted`. Treat these patterns as follows:

| Signal | Operator action |
|---|---|
| `retryable_failure` | Inspect the next claim generation; verify the stale generation did not finalize it. |
| `permanent_failure` | Locate the terminal stage and safe diagnostic codes; fix the cause before manual retry. |
| `partial` | Identify which stage/resource completed and which failed; do not call the operation successful. |
| `degraded` / `dropped` | Follow exporter troubleshooting below. PostgreSQL evidence remains authoritative. |
| `diagnostics_omitted > 0` | Use correlated service logs and Langfuse; do not expand the bounded API response. |

## Exporter troubleshooting

Start with the operator-only aggregated status:

```bash
curl --fail-with-body --silent --show-error \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -H "X-Operator-Key: ${OPERATOR_API_KEY}" \
  "${ACA_ORIGIN}/api/v1/status/observability" | jq .
```

For a timeout, record only the verifier's `last_successful_export_at`,
`affected_service`, and fixed failure codes. Never paste raw adapter stderr or
trace payloads. Then check the role and collector units:

```bash
sudo systemctl status aca-gx10.service --no-pager
sudo journalctl -u aca-gx10.service --since '-15 minutes' --no-pager
sudo systemctl status aca-gx10-storage.timer aca-gx10-backup.timer \
  aca-gx10-restore-drill.timer --no-pager
```

Confirm each process has its unique configured `OTEL_SERVICE_NAME`, environment,
release revision, loopback OTLP endpoint, masking policy, and export target.
Missing required export configuration is a readiness failure. Do not bypass it
by disabling required observability, enabling prompt capture, or copying secrets
into diagnostics. After correction, restart only the affected role, wait for a
fresh successful export, and rerun one live smoke.

## Disk and retention policy

Successful and partial detailed traces target 30 days; failed traces and failed
PostgreSQL attempt evidence target 90 days. All meaningful operations begin
unsampled. Failure, partial, security, backup, restore, and telemetry-health
evidence must never be sampled away.

The GX-10 storage monitor runs every minute:

```bash
systemctl list-timers aca-gx10-storage.timer
sudo systemctl start aca-gx10-storage.service
sudo journalctl -u aca-gx10-storage.service -n 100 --no-pager
sudo jq . /var/lib/aca/gx10/storage-controller.json
```

The configured watermark policy preserves the `75 < 80 < 85 < 90` hysteresis.
At sustained high pressure, omit optional successful excerpts/metadata first.
At critical pressure, pause nonessential ingestion; never silently delete failure
evidence or modify Langfuse-owned ClickHouse/PostgreSQL schemas. If native
outcome-specific Langfuse deletion is unavailable, retain all traces up to 90
days while the 1 TiB budget permits. Task 10.2 will record measured volume,
growth, latency/drop rate, cost, and final alert thresholds only after task 9.5.

## Backup and restore

GX-10 schedules an encrypted complete backup daily within the 24-hour RPO and an
isolated restore drill weekly:

```bash
systemctl list-timers aca-gx10-backup.timer aca-gx10-restore-drill.timer
sudo systemctl start aca-gx10-backup.service
sudo journalctl -u aca-gx10-backup.service -n 100 --no-pager
sudo systemctl start aca-gx10-restore-drill.service
sudo journalctl -u aca-gx10-restore-drill.service -n 100 --no-pager
```

The frozen inventory covers application PostgreSQL, Neo4j, Langfuse PostgreSQL,
ClickHouse, MinIO, and non-secret configuration. `/etc/aca/gx10/backup-plan.json`
and `restore-plan.json` must be installed by
`deploy/gx10/install-maintenance-plans.sh` before timers are enabled. Backup age
material comes from the dedicated least-privilege OpenBao AppRole. A missing or
invalid recipient fails before any artifact leaves component-local storage; no
plaintext fallback is allowed. Restore identities are separate from the backup
recipient-only file.

Restore only into `/run/aca/gx10/restore-drill` isolated targets. Do not point a
drill at production volumes. Acceptance requires application queue/PostgreSQL RPO
at most 24 hours, component RTO at most 2 hours, full-stack RTO at most 4 hours,
and a passing correlated synthetic operation afterward. The native encrypted
six-component drill has not run in this environment, so task 8.10 remains open.
See [Backup and Restore](../BACKUP_RESTORE.md) for age escrow and provider-neutral
off-site procedures.

## Environment fencing

GX-10 is a passive candidate in this change. Check the shared authority before
any validation:

```bash
curl --fail-with-body --silent --show-error \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -H "X-Operator-Key: ${OPERATOR_API_KEY}" \
  "${ACA_ORIGIN}/api/v1/status/environment-ownership?dry_run_target=gx10" | jq .
```

The configured authority fingerprint must match the one authoritative queue
database, and the configured epoch must match the stored epoch. Independent
database-local epochs are not authority. A mismatch, stale epoch, unavailable
authority, or independent database must keep schedulers/workers passive. A
synthetic smoke may run while passive but must not claim production work.

## Rollback boundaries

Before any separately approved cutover, rollback is one revert/disable boundary:
disable correlation writes and detailed export while leaving additive columns
readable. Do not remove additive schema during an incident.

After a future cutover, ordering is mandatory:

1. fence the current owner in the shared PostgreSQL authority;
2. verify the passive target against that same authority and current epoch;
3. enable target mutations only after verification passes.

DNS, ingress, configuration, or a local epoch change alone never transfers
ownership. The separate Railway-to-GX-10 proposal is held until the soak and
restore evidence exist; this change does not perform traffic or data cutover.

## Langfuse edition capabilities

Use the supported public/API surfaces of the deployed Langfuse edition. Never
query or modify Langfuse-owned PostgreSQL, ClickHouse, or MinIO schemas to force
retention, repair, or verification. The operator lookup URL is generated from
trusted `LANGFUSE_PUBLIC_URL` plus an opaque trace ID.

Capability-detect native outcome-specific retention. When the deployed edition
cannot delete successful and failed traces on different schedules, keep all
traces for up to the 90-day failure-evidence window while budgets permit and use
the storage-pressure policy above. Absence of a native capability is not license
to fabricate evidence: a fixture hierarchy is not a live Langfuse hierarchy,
and the six-hour soak remains not complete until the real backend is observed.
