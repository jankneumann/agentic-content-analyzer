# Persisted ingestion run results

> Parent roadmap: `ingestion-reliability`
> Change ID: `persisted-ingestion-run-results`
> Effort: M
> Priority: 2

## Summary

Introduce IngestionRun and SourceRunResult tables written by every pipeline driver, replacing the current behavior of reading only items_ingested and discarding status/errors/warnings (src/pipeline/runner.py:123, src/cli/pipeline_commands.py:136). Surface via CLI/API queries.

## Dependencies

- None

## Acceptance Outcomes

- aca pipeline daily exits non-zero or prints a WARN summary when any source is partial or failed
- Per-source run history is queryable via CLI and API
- A 1-of-N feed failure is visible in the run record, not only in logs

## Rationale

Partial failures (1-of-N dead feeds) are currently invisible above the service layer.
