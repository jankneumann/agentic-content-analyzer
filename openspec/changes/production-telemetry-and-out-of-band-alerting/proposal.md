# Production telemetry and out-of-band alerting

> Parent roadmap: `ingestion-reliability`
> Change ID: `production-telemetry-and-out-of-band-alerting`
> Effort: M
> Priority: 3

## Summary

Call record_ingestion / record_pipeline_stage_* from src/tasks/content.py and the worker (today only the CLI path is instrumented). Add one out-of-band channel (email via existing SendGrid dep, or webhook) to notification_service.emit() for severity >= warning, covering job_failure and zero-item runs; current delivery is SSE to an open browser only (notification_service.py:141-154).

## Dependencies

- `ingestion-run-persistence`

## Acceptance Outcomes

- Scheduled runs emit per-source ingestion counters
- A failed or empty overnight run produces an email/push notification by morning

## Rationale

A 3 a.m. failed or empty run currently alerts nobody.
