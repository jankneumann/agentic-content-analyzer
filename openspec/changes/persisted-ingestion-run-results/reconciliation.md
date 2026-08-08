# Persisted ingestion result reconciliation

The original ingestion-reliability proposal asked for separate
`IngestionRun` and `SourceRunResult` tables. RI-07 keeps `pgqueuer_jobs` as the
single workflow authority instead. The missing behavior is supplied by typed,
bounded projections over the existing operation graph; it does not require a
second run state machine.

## Original acceptance cases

| Original acceptance case | Existing durable authority | New projection or behavior | Non-recoverable legacy gap |
|---|---|---|---|
| `aca pipeline daily` exits non-zero or prints a WARN summary when any source is partial or failed. | The `pipeline.run` parent lifecycle, its `continue_on_source_error` input, and child operation IDs/checkpoints remain in `pgqueuer_jobs`. | `PipelineResultV2.ingestion_summary` records the aggregate outcome and bounded child summaries. Pipeline waiting uses that shared classification: strict partial/failure is non-zero; tolerated partial warns without corrupting JSON output. | Old pipeline rows that did not retain child domain outcomes can only classify missing evidence as `unknown`; a dropped partial signal cannot be reconstructed. |
| Per-source run history is queryable through CLI and API. | `operation_type`, lifecycle status/timestamps, `parent_job_id`, `retry_count`, payload input, result, and terminal problem remain on the operation record. | `GET /api/v1/ingestions` and `aca ingest history` project terminal `IngestionHistoryItem` rows with command, opaque configured-source, outcome, lifecycle, parent, and creation-window filters. Exact operation GET remains the full-result read. | Legacy rows may lack configured-source identity and skipped/failed counts. Missing counts remain `null`, command identity follows the documented legacy precedence, and unclassifiable outcomes are `unknown`. |
| A 1-of-N feed failure is visible in the run record, not only in logs. | The ingestion child remains the authoritative operation and retains its exact content provenance once in `payload.result.content_ids`. | Strict `IngestionResultV2` retains aggregate `partial`, bounded diagnostic codes/messages, omitted counts, and bounded `source_outcomes` keyed by stable opaque configured-source IDs. Compact history exposes only opaque keys, counts, and diagnostic codes. | V1 results never stored configured-source failures or the discarded partial/error detail. History must report `unknown` rather than infer success from a completed lifecycle. |

## Authority-to-projection matrix

| Concern | Authoritative operation field | Public projection |
|---|---|---|
| Lifecycle | `pgqueuer_jobs.status` and lifecycle timestamps | `OperationStatus`; terminal history narrows this to `TerminalOperationStatus` |
| Typed ingestion outcome | `payload.result` | Untagged reader union `IngestionResultV1 \| IngestionResultV2`; new writers use V2 |
| Pipeline aggregation | Parent `payload.result` plus authoritative child operations | `PipelineResultV2.ingestion_summary` via the `pipeline.run` result-schema registry entry |
| Parent/child identity | `parent_job_id` | `parent_operation_id` and per-source `operation_id` |
| Retry identity | The same operation row and `retry_count` | `retry_count`; no parallel retry record |
| Checkpoint/resume | Existing operation checkpoint fields | Excluded from list/history pages; used only by workflow execution and exact reads |
| Idempotency | `idempotency_key` on the operation | No duplicate history identity; not copied into compact public rows |
| Exact provenance | `payload.result.content_ids` | Present once on exact V2 ingestion results; excluded from summaries/history |
| Terminal diagnosis | `payload.problem` and bounded V2 diagnostics | Exact reads retain RFC 7807 problem detail; history retains only bounded `problem_code` and diagnostic codes |
| Resource identity | `payload.resource` | Exact operation reads only; generic `OperationSummary` deliberately omits resource metadata |
| Retention | Existing operation graph and terminal timestamps | Graph-aware maintenance applies finite completed/failed horizons without detaching children |

## Compatibility and bounds

- `IngestionResultV1` preserves the current strict stored shape and permits
  arbitrary legacy values only inside its existing `details` object. Its
  optional `schema_version` defaults to `1` for untagged stored rows.
- V2 result metadata outside the exact `content_ids` array has a 64 KiB
  serialized budget. Diagnostics, source outcomes, history rows, cursors,
  command keys, problem codes, and lifecycle messages have explicit count or
  string bounds in the canonical OpenAPI contract.
- Generic operation list rows use `OperationSummary`, whose emitted keys are a
  subset of the old strict `OperationHandle`. Raw input, checkpoint, result,
  resource, and problem bodies remain absent from lists.
- Active ingestion remains visible through generic operations. The dedicated
  ingestion history is terminal-only and never invents outcome counts for
  queued or in-progress work.

No new run table, source-result table, or workflow lifecycle authority is
introduced by this change.
