## Why

The system has useful source-specific ingestors and processors, but it does not preserve one canonical content selection or one workflow contract across ingestion, summarization, theme analysis, digest creation, podcast generation, CLI, HTTP, MCP, and the frontend. As a result, valid filters and source parameters can be lost, duplicate aliases can enter downstream analysis, podcasts can use content excluded from their digest, persistent resource IDs depend on the calling interface, and newly added sources require edits to many drifting registries.

This change establishes a single application architecture for source capabilities, canonical content provenance, durable workflows, and agent-facing operations. It is intentionally a coordinated breaking migration so every interface can converge on one contract without retaining competing legacy behavior.

## What Changes

- Add a canonical source capability registry. Each source descriptor owns its stable key, aliases, configuration model, discriminated ingestion command schema, orchestrator, emitted `ContentSource`, scheduling support, and supported options. Pipeline selection, CLI commands, HTTP schemas, MCP tools, frontend source metadata, and capability discovery derive from this registry or its generated contracts.
- Add an `IngestionService.execute(IngestCommand)` application boundary as the only source dispatcher. Remove transport-specific dispatch maps and stale task dispatchers after all callers use the service.
- Extend content querying into a `ContentSetResolver` that returns an immutable resolved set containing unique canonical content IDs, persisted summary IDs, exclusions, explicit date policy, and a stable selection fingerprint.
- **BREAKING**: downstream periods use half-open `[start, end)` bounds on `published_date` by default. `ingested_at` is available only through an explicit date-basis option.
- **BREAKING**: summaries, themes, digests, and podcasts operate on unique canonical content with persisted summaries by default. Duplicate alias rows, failed content, filtered content, and records without summaries are excluded and reported in selection diagnostics.
- Resolve content once per workflow and preserve the exact selection through theme analysis, digest persistence, podcast script generation, citations, and audio generation. Podcast generation uses the persisted digest source IDs instead of re-querying by period.
- Introduce application workflows for digest, podcast script, podcast audio, and audio digest generation. A successful workflow always persists its resource before reporting completion, regardless of caller.
- Use the existing PostgreSQL job queue for every long-running mutation, including ingestion, summarization, theme analysis, digest creation, pipeline execution, podcast scripts, podcast audio, and audio digests. Each surface returns the same operation handle and supports status, progress, result lookup, retry, cancellation where safe, idempotency, and optional waiting.
- Collapse the direct CLI pipeline, shared runner, worker pipeline, and MCP pipeline into one registry-driven pipeline workflow. Source filters are enforced by the registry and all scheduled-capable sources are discoverable.
- Route all digest, podcast, revision, and historical-context LLM calls through `LLMRouter`; route all audio entry points through public workflow/service APIs rather than provider SDKs or generator private methods in transport code.
- **BREAKING**: replace the flat HTTP ingestion request with a discriminated union of source-specific commands. Invalid sources and unsupported option combinations fail synchronously with RFC 7807 errors rather than failing later in a worker.
- **BREAKING**: normalize CLI, HTTP, and MCP mutation results around structured operation and resource envelopes. MCP tools return structured objects, use MCP errors for failures, and honor configured HTTP mode for every tool. CLI supports machine-readable output plus `--wait`, and HTTP exposes stable operation and result URLs.
- Add registry-derived capability discovery to CLI, HTTP, MCP, and the frontend. Capability metadata includes supported sources, options, operations, transport availability, and contract versions.
- Update frontend source types, operation types, ingestion forms, progress handling, and workflow actions from the same machine-readable contracts used by the backend.
- Add generated vertical contract tests for every registered source from fixture ingestion through summarization, digest creation, and podcast context assembly. Add pairwise source combinations, representative high-risk triples, provenance invariants, edge cases, and cross-interface parity tests. Exhaustive source power-set testing is deferred.

## Capabilities

### New Capabilities

- `source-capability-registry`: Canonical source descriptors, typed ingestion commands, aliases, supported operations, scheduling metadata, and registry-derived capability discovery.
- `content-provenance`: Immutable resolved content sets and invariants that preserve canonical content and summary provenance through themes, digests, scripts, citations, and audio.
- `agentic-operations`: Cross-interface operation and resource envelopes, idempotency, progress, waiting, retry, cancellation, structured errors, and result discovery for agent-driven workflows.

### Modified Capabilities

- `source-configuration`: Every configured source type must be representable and discoverable without assuming common fields such as `url`.
- `content-query`: Queries gain canonicalization, summary requirements, explicit date basis, half-open periods, exclusions, and stable resolved-set fingerprints.
- `pipeline`: All interfaces use one registry-driven pipeline implementation and preserve the same resolved content selection between stages.
- `theme-analysis`: Theme analysis consumes a supplied resolved content set instead of independently selecting a broader period.
- `podcast-generation`: Script and audio generation use persisted digest provenance and durable queued workflows.
- `audio-digest`: Audio creation is exposed through one public workflow and storage abstraction across all transports.
- `job-management`: The PostgreSQL job queue becomes the operation mechanism for every long-running mutation and exposes a common operation contract.
- `cli-interface`: Commands, source discovery, structured output, waiting, and resource identifiers align with the canonical application workflows.
- `mcp-http-client`: Every MCP tool honors HTTP mode, returns structured output, exposes operation handles, and reports protocol-level errors consistently.
- `llm-provider-routing`: All pipeline processors and agentic revision loops use `LLMRouter` rather than provider SDKs directly.
- `e2e-testing`: CI validates every registered source vertically, representative combinations, provenance invariants, and CLI/HTTP/MCP/frontend parity.

## Approaches Considered

### Approach 1: Domain Registry and Durable Workflows (Recommended)

Create three explicit application primitives: `SourceRegistry`, `ContentSetResolver`, and job-backed workflow services. Transports become thin adapters over typed commands, resolved selections, operation handles, and persisted resources; frontend types and capability metadata are generated from those contracts.

**Pros**
- Fixes the root causes of all eight findings rather than reconciling output shapes after execution.
- Makes source addition a registry change with generated parity checks.
- Makes provenance an explicit, testable value passed between workflow stages.
- Reuses the existing queue, persistence models, router, and content-query foundation.
- Keeps transport code independent from provider SDKs and processor internals.

**Cons**
- Requires coordinated changes across core services, transports, tests, and frontend.
- Requires careful migration ordering while old dispatchers and background tasks are removed.
- Registry contract design must accommodate heterogeneous and one-off ingestion commands.

**Effort**: L

Approach 1 is recommended because it provides explicit domain boundaries and durable provenance while reusing the current queue and persistence foundations. It achieves the requested end-to-end consistency without introducing a second workflow ledger or concentrating business behavior in a transport-oriented facade.

### Selected Approach

Approach 1 was approved at Gate 1 without modification. The implementation plan SHALL establish `SourceRegistry`, `ContentSetResolver`, and job-backed workflow services before migrating CLI, HTTP, MCP, pipeline, and frontend callers. The cutover is coordinated and breaking; the completed system will not retain legacy dispatchers, background-task paths, or alternate external envelopes.

Alternatives retained for decision history:

- **Approach 2: Transport-Led Application Facade (M)**: faster external convergence, rejected because it centralizes domain behavior in another broad facade and leaves internal bypass paths.
- **Approach 3: Persisted Stage Manifests (L)**: stronger replayability, rejected because it introduces a second workflow ledger and schema lifecycle beyond the current need.

## Impact

- Core application code: `src/ingestion/`, `src/services/content_query.py`, new registry/workflow services, `src/pipeline/`, `src/processors/`, `src/queue/`, and relevant persistence models and migrations.
- Interfaces: `src/cli/`, `src/api/`, `src/mcp_server.py` or its replacement modules, generated OpenAPI/MCP contracts, and `web/src/` source/workflow types and views.
- Tests: ingestion contracts, processor provenance tests, pipeline integration tests, MCP/HTTP conformance tests, CLI regression tests, frontend workflow tests, and generated registry coverage checks.
- Related changes: reuse the canonical ingestion envelope from `unify-mcp-ingest-envelope`, ingestion history from `persisted-ingestion-run-results`, CI tiers from `real-ingestion-test-tiers-in-ci`, and routing behavior from `llm-router-evaluation` without duplicating their scope.
- No new job store is introduced. Existing PostgreSQL queue infrastructure is extended to cover the remaining workflows.
- Existing external workflow contracts may break at the coordinated cutover; no legacy transport compatibility layer is planned.
