# Change Context: production-telemetry-and-out-of-band-alerting

## Roadmap and architecture context

RI-09 consumes RI-07 typed persisted outcomes and RI-08 append-only
reconciliation action evidence. Operation lifecycle plus strict V2 result
projection remains canonical; this change does not create another workflow
state machine.

The 2026-08-01 architecture refresh regenerated the Python inventory, but the
TypeScript analyzer failed under Node 25 and the database analyzer did not
understand Python Alembic migrations. The graph therefore reported no
cross-layer flows and was not sufficient evidence. Package boundaries below
were derived directly from queue, contract, settings, telemetry, notification,
and reconciliation implementations and tests.

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|-------------|-------------|--------------|-----------------|---------------|---------|----------|
| PWA.1 | `production-workflow-alerting` | Closed committed-state outcome classification and routing | `contracts/workflow-alert-envelope.schema.json#/properties/outcome` | D3 | --- | `tests/services/test_workflow_terminal_event_service.py` | --- |
| PWA.2 | `production-workflow-alerting` | Closed bounded allowlist-first external envelope | `contracts/workflow-alert-envelope.schema.json` | D4 | --- | `tests/contract/test_workflow_alert_contracts.py`; `tests/property/test_workflow_alert_redaction.py` | --- |
| PWA.3 | `production-workflow-alerting` | Trusted same-origin diagnostic URL construction | `contracts/workflow-alert-envelope.schema.json#/properties/diagnostic_url` | D4 | --- | `tests/services/test_workflow_terminal_event_service.py`; `tests/config/test_settings.py` | --- |
| PWA.4 | `production-workflow-alerting` | Durable attempt-aware leased webhook delivery | `contracts/db/schema.sql`; `contracts/workflow-alert-envelope.schema.json` | D6 | --- | `tests/services/test_workflow_alert_delivery.py`; `tests/integration/test_workflow_alert_delivery.py` | --- |
| PWA.5 | `production-workflow-alerting` | Default-off fail-closed webhook configuration and transport | `contracts/workflow-alert-envelope.schema.json` | D5, D8 | --- | `tests/config/test_settings.py`; `tests/services/test_alert_sinks.py` | --- |
| PWA.6 | `production-workflow-alerting` | Pipeline graph aggregation and attempt-aware identity | `contracts/db/schema.sql` | D1, D3 | --- | `tests/services/test_workflow_terminal_event_service.py`; `tests/integration/test_workflow_alert_end_to_end.py` | --- |
| PWA.7 | `production-workflow-alerting` | Sanitized correlated staging verification | `contracts/staging-evidence.schema.json` | D10 | --- | `tests/scripts/test_verify_workflow_alerting.py` | --- |
| AO.1 | `agentic-operations` | Atomic canonical terminal-event intent | `contracts/db/schema.sql` | D1 | --- | `tests/migrations/test_workflow_alert_persistence.py`; `tests/integration/test_workflow_alert_persistence.py` | --- |
| AO.2 | `agentic-operations` | Fresh committed-state projection with workflow independence | `contracts/workflow-alert-envelope.schema.json` | D3, D7 | --- | `tests/queue/test_worker_extended.py`; `tests/integration/test_workflow_alert_end_to_end.py` | --- |
| OBS.1 | `observability` | Bounded low-cardinality terminal logs and OTel telemetry | --- | D7 | --- | `tests/telemetry/test_workflow_events.py` | --- |
| CSR.1 | `content-state-reconciliation` | Reconciliation events follow committed immutable action evidence | `contracts/db/schema.sql` | D2 | --- | `tests/services/test_content_reconciliation_service.py`; `tests/integration/test_content_reconciliation.py` | --- |
| NE.1 | `notification-events` | External alert boundary is isolated from generic SSE notifications | `contracts/workflow-alert-envelope.schema.json` | D4 | --- | `tests/services/test_notification_service.py`; `tests/integration/test_workflow_alert_end_to_end.py` | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Cover every canonical terminal path and crash window | Minimal event trigger plus unique attempt/status key | Application post-commit hooks are bypassable and lossy |
| D2 | Preserve reconciliation atomicity and dry-run purity | Action trigger plus post-rollback bounded failure intent | Page summaries can be lost after committed item actions |
| D3 | Keep persisted lifecycle/result authority | One pure classifier and pipeline root routing policy | Handler snapshots and legacy payload inference are stale/unsafe |
| D4 | Prove external payload safety | Strict versioned model, allowlisted projection, constructed URL | Recursive denylist redaction cannot bound future fields |
| D5 | Provide one testable idempotent v1 sink | Constrained HTTPS webhook with optional HMAC | Existing SendGrid dependency lacks sender/recipient/idempotency contracts |
| D6 | Recover safely without long transactions | Leased `SKIP LOCKED` delivery and stable idempotency key | Transactions cannot span external I/O or solve ambiguous responses |
| D7 | Keep observability non-authoritative | Safe structured log/OTel projection after commit | Exporter failure must never change workflow state |
| D8 | Protect secrets and current behavior | Default-off typed settings outside DB override registry | Generic settings persistence exposes plaintext values |
| D9 | Retain evidence independently | Copied IDs, no destructive FK, bounded terminal-only cleanup | Operation retention must not delete pending/exhausted alert state |
| D10 | Prove staging delivery without leaking payloads | Schema-validated correlation manifest with hashed receipt | Captured requests/responses can expose secrets or user content |

## Existing boundaries consumed

- `pgqueuer_jobs` generation-fenced terminal transitions and retry semantics
- strict `IngestionResultV2` / `PipelineResultV2` outcome projection
- opaque `src_<digest>` source keys and bounded diagnostic codes
- immutable content-reconciliation action IDs and per-item transactions
- shared OTel resource/export configuration
- environment/profile/OpenBao/Railway secret resolution

## Boundaries intentionally not reused

- generic `NotificationDispatcher` payloads and process-local SSE delivery
- `DeviceRegistration`, which has no APNs/FCM delivery implementation
- database-backed settings overrides for endpoint or signing secrets
- raw worker errors or `record_pipeline_stage_failed(error=...)` attributes
- Langfuse generation traces as an alert sink

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|
| plan.sink | plan | architecture | high | resolved | Selected HTTPS webhook plus receiver idempotency contract |
| plan.atomicity | persistence | resilience | high | resolved | Trigger-backed minimal intent in terminal/action transactions |
| plan.redaction | classifier | security | high | resolved | Closed allowlist-first envelope and diagnostic URL construction |
| plan.fanout | classifier | architecture | high | resolved | Leaf telemetry plus pipeline-root external aggregation |
| plan.delivery | delivery | resilience | high | resolved | Leases, retry classes, exhaustion, stable key, bounded retention |
| plan.staging | verification | spec_gap | high | resolved | Sanitized versioned evidence schema and duplicate failure policy |

## Coverage Summary

- **Requirements traced**: 12/12
- **Tests mapped**: 12 requirements have at least one planned test
- **Evidence collected**: 0/12 requirements have pass/fail evidence
- **Gaps identified**: exact graph-suppression query plan must be measured before retaining an index
- **Deferred items**: email/push adapters and alert-management UI require separate proposals

## Follow-up boundaries

- GitHub issue #481 tracks broader unsafe locator/provider-error logging.
- GitHub issue #484 tracks reconciliation/summarizer failure observability not
  safely addressed by copying raw exceptions into RI-09.
