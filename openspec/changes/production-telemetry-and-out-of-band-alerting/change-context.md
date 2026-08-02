# Change context: production telemetry and out-of-band alerting

## Roadmap traceability

RI-09 depends on RI-07 typed persisted outcomes and RI-08 append-only
reconciliation action evidence. It does not introduce another workflow state
machine. Operation lifecycle plus strict V2 result projection remains canonical.

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

## Architecture refresh constraint

The 2026-08-01 architecture refresh regenerated the Python inventory but the
TypeScript analyzer failed under Node 25 and the database analyzer did not
understand Python Alembic migrations. The generated graph therefore reported no
cross-layer flows and is not sufficient evidence for this plan. File ownership
and dependencies were derived directly from the queue, contract, settings,
telemetry, notification, and reconciliation implementations and tests.

## Follow-up boundaries

- GitHub issue #481 tracks broader unsafe locator/provider-error logging.
- GitHub issue #484 tracks reconciliation/summarizer failure observability not
  safely addressed by copying raw exceptions into RI-09.
- Future email/push adapters and operator alert-management UI require separate
  proposals after the sink contract has production evidence.
