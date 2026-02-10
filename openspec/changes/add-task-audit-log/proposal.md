# Add Task Audit Log

## Summary

Add a "Task History" view for audit and operational visibility — a filterable table showing all historical job executions across the pipeline (ingestion, summarization, digests, theme analysis, scripts, podcasts, audio digests). Available in both the web UI (new tab under Management) and the CLI (`aca jobs history`).

## Problem

Currently, the system provides:
- A **Review Queue** under Management for pending digests/scripts
- A `aca jobs list` CLI command for raw job queue inspection
- An API endpoint `GET /api/v1/jobs` for job data

However, there is no unified audit view that:
1. Shows **all historical task executions** with human-readable context (content titles, friendly task names)
2. Provides **time-based filtering** (last day, last week) for operational review
3. Is accessible from the **web UI** for non-CLI users
4. Enriches raw job data with **content metadata** (titles) for meaningful audit trails

## Objectives

1. Add a **"Task History" page** under the Management nav group in the web UI with a filterable, sortable table
2. Add an `aca jobs history` CLI command with equivalent filtering capabilities
3. Create an enriched API endpoint that joins job records with content titles
4. Support filters: time range (last day, last week, custom), entry count (last N), task type, and status

## Scope

### In Scope
- New web route `/task-history` with Management nav entry
- New API endpoint `GET /api/v1/jobs/history` with content-enriched responses
- New CLI command `aca jobs history` with `--since`, `--last`, `--type`, `--status` flags
- Time-based filtering (1d, 7d, 30d, custom)
- Task type friendly names mapping (entrypoint → human label)

### Out of Scope
- Real-time SSE streaming for the audit view (existing SSE covers active tasks)
- Job log/output capture (raw logs stay in container/worker output)
- Export to CSV/PDF
- Archival or retention policy changes (existing `aca jobs cleanup` handles this)

## Dependencies

- Existing `pgqueuer_jobs` table and `list_jobs()` function in `src/queue/setup.py`
- Existing `Content` model with `id` and `title` fields
- Existing `job-management` spec (will add requirements)
- Existing `cli-interface` spec (will add requirements)
