## Context

ACA currently has a unified `Content` model and a reusable `ContentQueryService`, but workflow ownership is split across source-specific orchestrators, CLI adapters, API routes, queue handlers, three pipeline drivers, and a monolithic MCP server. These paths do not agree on source names, supported parameters, persistence, date semantics, provider routing, or which content belongs to a digest and podcast.

The highest-risk behavior is selection drift. Theme analysis selects completed content using published-or-ingested dates, digest generation applies a separate published-date query, and podcast script generation re-queries all completed content in a digest period instead of using `Digest.source_content_ids`. Duplicate alias rows are also marked completed, so count and provenance errors can propagate even when ingestion itself succeeds.

The implementation must coordinate changes across backend application services, PostgreSQL queue workers, data models, CLI, HTTP, MCP, and the React frontend. Existing foundations to reuse are `ContentQuery`, PostgreSQL `pgqueuer_jobs`, `Digest.source_content_ids`, persisted podcast records, `LLMRouter`, storage services, the canonical `IngestionResponse`, and the source configuration models.

## Goals / Non-Goals

**Goals:**

- Make one registry authoritative for source keys, command schemas, dispatch, scheduling, discovery, and surface coverage.
- Select canonical summarized content once and preserve that exact provenance through themes, digests, scripts, citations, and audio.
- Make every long-running mutation a durable PostgreSQL job with the same operation contract.
- Make workflow persistence independent of transport.
- Make CLI, HTTP, MCP, pipeline, and frontend expose equivalent capabilities and structured results.
- Remove direct provider and private generator calls from transport and workflow code.
- Provide scalable end-to-end confidence for every source and representative mixed-source workflows.

**Non-Goals:**

- Exhaustively test the power set of registered sources.
- Introduce a second operation or workflow ledger alongside `pgqueuer_jobs`.
- Implement dynamic LLM model evaluation or routing policy from `llm-router-evaluation`.
- Preserve legacy workflow request or response shapes after the coordinated cutover.
- Rework content extraction algorithms inside individual source adapters except where canonical duplicate output is required.
- Add event-bus infrastructure or persist every intermediate stage as a new manifest table.

## Target Flow

```text
CLI / HTTP / MCP / Frontend
          |
          v
typed command contract + idempotency key
          |
          v
Application Workflow -> pgqueuer_jobs -> Worker Handler
          |                                  |
          |                                  +-> IngestionService -> SourceRegistry
          |                                  +-> ContentSetResolver
          |                                  +-> Theme / Digest / Podcast workflows
          |                                  +-> LLMRouter / TTS service / Storage service
          v
OperationHandle <---------------- progress + persisted resource reference
```

For digest-to-podcast processing:

```text
ContentQuery
    -> ResolvedContentSet(content_ids, summary_ids, policy, exclusions, fingerprint)
    -> ThemeAnalyzer(resolved_set)
    -> DigestWorkflow(resolved_set, themes)
    -> Digest(source_content_ids, source_summary_ids, selection_fingerprint, policy)
    -> PodcastScriptWorkflow(digest_id)
    -> PodcastScriptRecord(source_content_ids_available, source_content_ids_cited,
                           selection_fingerprint)
    -> PodcastAudioWorkflow(script_id)
```

## Decisions

### D1. Source descriptors form one executable registry

Create a registry module under `src/ingestion/` whose descriptors contain:

- canonical machine key and removed/accepted migration aliases;
- source-specific Pydantic command model and JSON discriminator;
- orchestrator callable returning canonical `IngestionResponse`;
- emitted `ContentSource` value;
- optional config model and config collection accessor;
- capabilities such as `scheduled`, `supports_force`, `supports_date_range`, `supports_preview`, and `requires_identifier`;
- display metadata suitable for capability discovery and frontend rendering.

The canonical ingestion keys are `gmail`, `rss`, `blog`, `substack`, `youtube_playlist`, `youtube_rss`, `podcast`, `x_search`, `perplexity_search`, `files`, `url`, `scholar_search`, `scholar_paper`, `scholar_references`, `arxiv_search`, `arxiv_paper`, `huggingface_papers`, and `readwise`. The combined legacy `youtube` dispatcher is removed; callers choose playlist or RSS explicitly.

`IngestionService.execute(command)` is the only dispatch entry point. Registry validation fails at startup for duplicate keys, aliases, or incomplete descriptors. This was selected over decorators spread across adapter modules because an explicit registry is inspectable, deterministic, and easy to compare with generated contracts.

### D2. Canonical identity is resolved before workflow eligibility

For workflow selection, canonical identity is `content.canonical_id` when present, otherwise `content.id`. Only the canonical record is eligible. It must have an associated persisted `Summary` and an allowed workflow status. Alias records remain queryable for audit and duplicate UI, but never contribute an independent count, summary, theme, digest source, or podcast source.

The resolver reports exclusions grouped by reason: `duplicate_alias`, `missing_summary`, `filtered_out`, `failed`, `outside_period`, and `unsupported_status`. It does not silently repair aliases or move summaries during resolution. Cleanup/backfill belongs to a separate migration step.

### D3. Content selection is immutable and fingerprinted

Introduce immutable models `SelectionPolicy`, `ResolvedContentItem`, `SelectionExclusion`, and `ResolvedContentSet`. Workflow defaults are:

- `date_basis=published_date`;
- `start <= published_date < end`;
- unique canonical content only;
- persisted summary required;
- deterministic ordering by date then content ID;
- no implicit inclusion of null publication dates.

`date_basis=ingested_at` is available only when explicitly supplied. A SHA-256 fingerprint is computed from the schema version, normalized policy, ordered canonical content IDs, and ordered summary IDs. The fingerprint is diagnostic and idempotency input, not an authorization boundary.

This extends `ContentQueryService`; it does not replace the general content-list query behavior. List/search endpoints can still inspect aliases and unsummarized rows, while workflow operations use `ContentSetResolver`.

### D4. Provenance is persisted at the digest boundary

`Digest` remains the durable boundary between content analysis and podcast production. Add `source_summary_ids`, `selection_fingerprint`, and `selection_policy` while retaining `source_content_ids`. Existing digests are backfilled with a `legacy-v0` policy and a deterministic fingerprint of available source IDs.

Rename podcast script provenance columns from newsletter terminology to content terminology and add the digest fingerprint. Script generation loads only the digest's stored content IDs, verifies the current summaries match the persisted digest selection, and constrains content-fetch tools and citations to that set.

Required invariants are:

```text
theme content IDs are a subset of digest source content IDs
podcast available content IDs equal digest source content IDs
podcast cited content IDs are a subset of podcast available content IDs
digest newsletter_count equals unique canonical summarized content count
digest selection fingerprint equals the podcast script selection fingerprint
```

### D5. Workflow services own resource persistence

Create application services for ingestion submission, summarization submission, theme analysis, digest creation, pipeline execution, podcast script creation, podcast audio creation, and audio digest creation. A worker handler calls a workflow service; the workflow creates or updates the durable resource in one transaction boundary and records its reference in the job payload before marking the job complete.

Processors return generation data and never decide transport response shapes. API routes and CLI/MCP adapters never instantiate provider clients, generators, or ORM records for workflow mutations.

### D6. `pgqueuer_jobs` is the universal operation store

Extend the existing job payload contract instead of adding an operations table:

```json
{
  "schema_version": 2,
  "operation_type": "digest.create",
  "input": {},
  "progress": 0,
  "message": "Queued",
  "resource": null,
  "result": null,
  "cancel_requested": false
}
```

The public `OperationHandle` projects the queue record into stable fields: operation ID, type, status, progress, timestamps, retry count, status URL, events URL, optional resource reference, optional result, and RFC 7807 problem details. The external lifecycle is `queued -> in_progress -> completed|failed|cancelled`.

Idempotency uses the existing `idempotency_key` column. Keys are derived from normalized commands unless a caller supplies `Idempotency-Key`. Retrying creates or requeues according to the existing job policy while preserving the logical operation type. Queued work can be cancelled immediately; running work sets `cancel_requested` and handlers stop only at declared checkpoints. Unsafe operations advertise `cancellable=false`.

HTTP polling supports a bounded `wait_seconds`; CLI and MCP expose a higher-level wait helper. Frontend progress uses a shared operation SSE endpoint. This avoids workflow-specific background tasks and status endpoints.

### D7. One pipeline workflow builds a parent-child job graph

`PipelineWorkflow` obtains scheduled descriptors from `SourceRegistry`, applies the requested source filter, and creates child ingestion jobs linked by `parent_job_id`. It then runs summarization, resolves one content set, performs theme analysis, and creates the digest through the same workflow services used independently.

Partial ingestion failures are preserved in child operations and the pipeline result. The pipeline continues only according to an explicit policy and never silently ignores a requested or unknown source. Direct CLI and MCP pipeline implementations are removed.

### D8. External contracts are intentionally replaced together

The cutover replaces workflow mutation shapes in place under `/api/v1` because all controlled clients deploy together. HTTP uses resource-oriented submission endpoints and returns `202 OperationHandle`. Source-specific ingestion is an OpenAPI discriminated union with `additionalProperties: false`. Problems use RFC 7807.

CLI commands compile the same typed requests and provide Rich output by default, `--json` for exact contract output, and `--wait/--no-wait`. MCP tools expose structured objects rather than serialized JSON strings, raise MCP protocol errors for failures, and use the shared HTTP client for every tool when HTTP mode is configured. In-process MCP mode calls the same application services and must pass conformance tests against HTTP mode.

The MCP server is split into bounded tool modules during migration so ingestion, content, workflow, review, and knowledge tools do not continue accumulating in `src/mcp_server.py`.

### D9. Capabilities and generated types prevent surface drift

`GET /api/v1/capabilities`, `aca capabilities`, and MCP `get_capabilities` expose the same registry-derived document. It identifies contract version, source commands and fields, scheduled support, operation types, resource types, and enabled transports.

Backend Pydantic and frontend TypeScript contract stubs are generated from OpenAPI during implementation. The frontend renders source selection and source-specific forms from capability metadata while retaining explicit components for complex fields. CI compares the registry key set with OpenAPI discriminators, CLI commands, MCP tools, test fixtures, and frontend capability handling.

### D10. Providers remain behind router and media service boundaries

Digest generation, podcast generation, revision loops, and historical-context generation use `LLMRouter`, including provider-neutral tool definitions. Workflow services select a `ModelStep`; they do not select SDK clients.

Podcast and audio-digest workflows use public TTS generation and storage service methods. HTTP routes must not call old audio generators or private `_synthesize_*` methods. Provider-specific configuration remains inside existing provider adapters.

### D11. Generated vertical tests plus invariants cover combinations

Each registry descriptor supplies or references a deterministic ingestion fixture. A generated contract test executes fixture ingestion, canonical persistence, summarization, digest selection, and podcast context assembly for every registered source.

Mixed-source coverage uses all pairwise combinations, plus high-risk triples for `gmail/rss/substack` and `scholar_search/arxiv_search/huggingface_papers`. Property-style provenance assertions run for every case. Additional cases cover duplicate aliases, null dates, explicit ingested-date selection, filtered and failed rows, missing summaries, force reprocessing, partial ingestion failure, idempotent resubmission, cancellation, and retry.

Cross-interface tests submit the same command via application service, CLI JSON mode, HTTP, MCP HTTP mode, MCP in-process mode, and frontend API client, then compare the operation and final resource contracts.

### D12. Coordinated migration uses shadow validation before cutover

Implementation lands in dependency order: contracts, data provenance, registry/ingestion, workflow queue, processors/pipeline, HTTP, CLI/MCP, frontend, then integration. Before removing old paths, test-only shadow assertions compare old and new source results and content selections against fixtures.

At cutover, deploy database migrations first, then workers, API, MCP, CLI package, and frontend as one release. Queue workers accept payload schema versions 1 and 2 during the deployment window, but interfaces emit only version 2. After old jobs drain, legacy handlers, direct dispatchers, background tasks, and response adapters are removed.

Rollback restores the previous application release while retaining additive digest provenance columns and accepting version 1 jobs. Destructive column renames are implemented as add/backfill/read-switch/drop across releases, even though the external API cutover is breaking.

## Risks / Trade-offs

- **[Registry becomes another static list]** -> CI derives and compares every external surface and fixture set from the registry; transport-owned source maps are forbidden.
- **[A coordinated cutover strands queued version 1 work]** -> workers support both payload versions during deployment and removal waits for drain verification.
- **[Canonicalization hides useful duplicate metadata]** -> aliases remain visible to audit/search APIs and exclusions are returned in selection previews.
- **[Summary edits make old digest provenance unverifiable]** -> digests store summary IDs and a selection fingerprint; script generation detects mismatch instead of silently reselecting.
- **[Universal queue adds latency to local CLI use]** -> CLI `--wait` provides synchronous ergonomics while preserving the same durable execution path.
- **[Cancellation leaves partial resources]** -> handlers declare cancellation checkpoints and persist failed/cancelled resource state consistently.
- **[OpenAPI generation cannot express every frontend control]** -> generated types define data contracts; domain-specific UI components remain handwritten against capability metadata.
- **[Large cross-cutting migration causes merge contention]** -> contract-first work packages use non-overlapping source scopes, with serialized integration for shared registries and app wiring.

## Migration Plan

1. Freeze canonical contracts and generated stubs.
2. Add digest and podcast provenance columns with backfills; extend job payload parsing and status projection.
3. Implement `ContentSetResolver` and provenance invariant tests.
4. Implement `SourceRegistry` and `IngestionService`; migrate source adapters and worker dispatch.
5. Implement job-backed workflow services and queue handlers.
6. Migrate theme, digest, podcast, audio, and pipeline processors to resolved selections, router, and media services.
7. Replace HTTP mutation endpoints and add capability/operation APIs.
8. Replace CLI and MCP adapters, then migrate frontend types and workflows.
9. Run generated vertical, pairwise, high-risk triple, parity, migration, and rollback tests.
10. Deploy migrations, workers, API, interface clients, and frontend in the coordinated order; drain version 1 jobs and remove legacy paths.

## Open Questions

- The exact release number and maintenance window for the coordinated external cutover will be chosen during implementation.
- Cancellation checkpoints for provider calls depend on provider SDK behavior and will be documented per handler.
- Existing legacy digests without complete `source_content_ids` can be marked `legacy-v0`, but their original source provenance cannot be reconstructed perfectly.
