## 1. Contract Enforcement

- [x] 1.1 [S] Write contract validation tests
  **Spec scenarios**: source-capability-registry.5-6, agentic-operations.8-9
  **Contracts**: `contracts/openapi/v1.yaml`, `contracts/events/operation.progress.schema.json`, `contracts/generated/models.py`, `contracts/generated/types.ts`
  **Design decisions**: D8, D9
  **Dependencies**: None

- [x] 1.2 [M] Add contract generation commands
  Add reproducible OpenAPI validation, Pydantic generation, TypeScript generation, event-schema validation, and drift checks to the build without editing generated output manually.
  **Dependencies**: 1.1

- [x] 1.3 [XS] Checkpoint: run contract tests, review diff, verify scope
  **Dependencies**: 1.2

## 2. Canonical Content Provenance

- [x] 2.1 [M] Write provenance migration tests
  **Spec scenarios**: content-provenance.7-8, job-management.2
  **Contracts**: `contracts/db/schema.sql`, `contracts/db/seed.sql`
  **Design decisions**: D4, D12
  **Dependencies**: 1.3

- [x] 2.2 [M] Add provenance schema migration
  Add digest selection fields and additive podcast content fields, backfill legacy rows, update ORM models, then make current provenance fields non-null where contracted.
  **Dependencies**: 2.1

- [x] 2.3 [XS] Checkpoint: run migration tests, review diff, verify scope
  **Dependencies**: 2.2

- [x] 2.4 [M] Write content resolver tests
  **Spec scenarios**: content-provenance.1-4, content-query.1-10
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/ContentQuery`, `contracts/db/seed.sql`
  **Design decisions**: D2, D3
  **Dependencies**: 1.3

- [x] 2.5 [M] Implement ContentSetResolver
  Add immutable policy, item, exclusion, and resolved-set models; implement canonical identity, summary joins, half-open date bases, deterministic ordering, preview diagnostics, and fingerprints.
  **Dependencies**: 2.4, 2.2

- [x] 2.6 [XS] Checkpoint: run resolver tests, review diff, verify scope
  **Dependencies**: 2.5

- [x] 2.7 [M] Write processor provenance tests
  **Spec scenarios**: content-provenance.5-8, theme-analysis.1-2, podcast-generation.1-2
  **Contracts**: `contracts/db/schema.sql`
  **Design decisions**: D3, D4
  **Dependencies**: 2.5

- [x] 2.8 [M] Constrain theme analysis selection
  Replace period re-querying with supplied resolved content and persist analyzed IDs plus fingerprint.
  **Dependencies**: 2.7

- [x] 2.9 [M] Persist digest selection snapshot
  Make digest generation consume the supplied resolved set and persist exact content IDs, summary IDs, policy, fingerprint, and canonical count.
  **Dependencies**: 2.7, 2.8

- [x] 2.10 [M] Constrain podcast content tools
  Load podcast availability from digest provenance, enforce fetch and citation membership, persist content-named fields, and reject incomplete legacy provenance.
  **Dependencies**: 2.7, 2.9

- [x] 2.11 [XS] Checkpoint: run processor tests, review diff, verify scope
  **Dependencies**: 2.8, 2.9, 2.10

## 3. Source Registry

- [x] 3.1 [M] Write source registry tests
  **Spec scenarios**: source-capability-registry.1-4, source-configuration.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/IngestCommand`
  **Design decisions**: D1
  **Dependencies**: 1.3

- [x] 3.2 [M] Implement SourceRegistry
  Add descriptors for all eighteen canonical commands, startup validation, emitted source metadata, config accessors, scheduling flags, and removed-key diagnostics.
  **Dependencies**: 3.1

- [x] 3.3 [XS] Checkpoint: run registry tests, review diff, verify scope
  **Dependencies**: 3.2

- [x] 3.4 [M] Write ingestion dispatch tests
  **Spec scenarios**: source-capability-registry.3-4, cli-interface.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/IngestCommand`
  **Design decisions**: D1
  **Dependencies**: 3.2

- [x] 3.5 [M] Implement IngestionService
  Dispatch typed commands through registry descriptors, preserve every source-specific option, return canonical ingestion responses, and migrate adapter entry points to the service.
  **Dependencies**: 3.4

- [x] 3.6 [XS] Checkpoint: run ingestion tests, review diff, verify scope
  **Dependencies**: 3.5

- [x] 3.7 [M] Write capability parity tests
  **Spec scenarios**: source-capability-registry.5-6, cli-interface.6, mcp-http-client.9
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/CapabilityDocument`
  **Design decisions**: D9
  **Dependencies**: 3.2, 1.2

- [x] 3.8 [M] Implement CapabilityService
  Project registry descriptors into the canonical capability document with stable contract version, fields, transports, operations, and resources.
  **Dependencies**: 3.7

- [x] 3.9 [S] Write upload reference tests
  **Spec scenarios**: source-capability-registry.3-6
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1uploads`, `contracts/openapi/v1.yaml#/components/schemas/FilesIngestCommand`
  **Design decisions**: D1, D8
  **Dependencies**: 1.3

- [x] 3.10 [M] Implement durable upload references
  Store uploaded documents through the configured storage provider and resolve `upload_ids` inside files ingestion so CLI, HTTP, MCP, and frontend share one server-visible contract.
  **Dependencies**: 3.9, 3.5

- [x] 3.11 [XS] Checkpoint: run capability tests, review diff, verify scope
  **Dependencies**: 3.8, 3.10

## 4. Operation Core

- [x] 4.1 [M] Write operation projection tests
  **Spec scenarios**: agentic-operations.1-2, job-management.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/OperationHandle`, `contracts/events/operation.progress.schema.json`
  **Design decisions**: D5, D6
  **Dependencies**: 1.3

- [x] 4.2 [M] Implement OperationService
  Add versioned job payload models, operation projection, resource attachment, result attachment, progress events, bounded waiting, and cursor listing over `pgqueuer_jobs`.
  **Dependencies**: 4.1

- [x] 4.3 [XS] Checkpoint: run operation model tests, review diff, verify scope
  **Dependencies**: 4.2

- [x] 4.4 [M] Write handler registry contract tests
  **Spec scenarios**: agentic-operations.3, job-management.3
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/OperationHandle`
  **Design decisions**: D5, D6
  **Dependencies**: 4.2

- [x] 4.5 [M] Implement handler registry contract
  Add typed handler registration, operation-type completeness validation, worker-startup failure, and resource-attachment enforcement using test handlers.
  **Dependencies**: 4.4

- [x] 4.6 [XS] Checkpoint: run handler tests, review diff, verify scope
  **Dependencies**: 4.5

- [x] 4.7 [M] Write operation control tests
  **Spec scenarios**: agentic-operations.4-7, job-management.4-5
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1operations~1{operation_id}~1retry`, `contracts/openapi/v1.yaml#/paths/~1api~1v1~1operations~1{operation_id}~1cancel`
  **Design decisions**: D6, D12
  **Dependencies**: 4.2

- [x] 4.8 [M] Implement operation controls
  Add idempotent submission, retry rules, queued cancellation, running cancellation requests, cancellation checkpoints, and version 1 payload compatibility.
  **Dependencies**: 4.7

- [x] 4.9 [XS] Checkpoint: run operation control tests, review diff, verify scope
  **Dependencies**: 4.8

## 5. Durable Workflows

- [x] 5.1 [M] Write summarization workflow tests
  **Spec scenarios**: agentic-operations.2-4
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/SummarizationRequest`
  **Design decisions**: D5, D6
  **Dependencies**: 4.2

- [x] 5.2 [M] Implement SummarizationWorkflow
  Normalize selection defaults, enqueue item children, aggregate canonical results, and attach a durable summary-batch result.
  **Dependencies**: 5.1, 2.5

- [x] 5.3 [M] Write theme workflow tests
  **Spec scenarios**: theme-analysis.1-2, agentic-operations.1-3
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/ThemeAnalysisRequest`
  **Design decisions**: D3, D5
  **Dependencies**: 2.8, 4.2

- [x] 5.4 [M] Implement ThemeAnalysisWorkflow
  Resolve once, create a persisted analysis lifecycle, call the constrained analyzer, and attach the analysis resource.
  **Dependencies**: 5.3

- [x] 5.5 [XS] Checkpoint: run summary/theme workflow tests, review diff, verify scope
  **Dependencies**: 5.2, 5.4

- [x] 5.6 [M] Write digest workflow tests
  **Spec scenarios**: content-provenance.5-8, agentic-operations.2, cli-interface.4
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/DigestCreateRequest`, `contracts/db/schema.sql`
  **Design decisions**: D4, D5
  **Dependencies**: 2.9, 4.2

- [x] 5.7 [M] Implement DigestWorkflow
  Reserve one digest record, resolve or verify its content set, run theme analysis, persist generated data, and attach the digest resource idempotently.
  **Dependencies**: 5.6, 5.4

- [x] 5.8 [M] Write podcast script workflow tests
  **Spec scenarios**: podcast-generation.1-3
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/PodcastScriptRequest`, `contracts/db/schema.sql`
  **Design decisions**: D4, D5
  **Dependencies**: 2.10, 4.2

- [x] 5.9 [M] Implement PodcastScriptWorkflow
  Reserve one script record, verify digest provenance, generate against the constrained context, persist metadata, and attach the script resource.
  **Dependencies**: 5.8

- [x] 5.10 [XS] Checkpoint: run digest/script workflow tests, review diff, verify scope
  **Dependencies**: 5.7, 5.9

- [x] 5.11 [M] Write podcast audio workflow tests
  **Spec scenarios**: podcast-generation.4-5
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/PodcastAudioRequest`
  **Design decisions**: D5, D10
  **Dependencies**: 4.2

- [x] 5.12 [M] Implement PodcastAudioWorkflow
  Enforce script approval, reserve one podcast record, invoke the public audio service, store output, and attach the podcast resource idempotently.
  **Dependencies**: 5.11, 5.9

- [x] 5.13 [M] Write audio digest workflow tests
  **Spec scenarios**: audio-digest.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/AudioDigestRequest`
  **Design decisions**: D5, D10
  **Dependencies**: 4.2

- [x] 5.14 [M] Implement AudioDigestWorkflow
  Reserve one audio digest record, invoke only the public generator API, persist storage output, and attach the resource idempotently.
  **Dependencies**: 5.13

- [x] 5.15 [XS] Checkpoint: run audio workflow tests, review diff, verify scope
  **Dependencies**: 5.12, 5.14

- [x] 5.16 [M] Write pipeline workflow tests
  **Spec scenarios**: pipeline.1-8
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/PipelineRequest`
  **Design decisions**: D7
  **Dependencies**: 3.5, 5.2, 5.7
  Cover durable defer/resume at worker concurrency one, parent-scoped child reuse,
  descriptor-owned immutable scheduled command planning across multiple Gmail and YouTube subtypes,
  raw and ORM deduplication receipts, cross-source canonical IDs, strict completion repair, and
  exact selection propagation.

- [x] 5.17 [M] Implement PipelineWorkflow
  Create parent-child source jobs from registry descriptors, apply source filters,
  preserve partial failures, defer without occupying a worker while children run,
  resume from persisted checkpoints, resolve once, and return the persisted digest.
  Scheduled commands retain absolute lower bounds and resolved source snapshots, deduplicated
  ingestion receipts retain encountered canonical IDs across ORM and raw SQL paths including
  academic cross-source duplicates, retries target only failed or cancelled checkpoint children,
  and final projection is atomic and child-verified.
  **Dependencies**: 5.16, 5.4

- [x] 5.18 [XS] Checkpoint: run pipeline tests, review diff, verify scope
  **Dependencies**: 5.17

- [x] 5.19 [M] Write worker handler integration tests
  Prove at worker concurrency one that deferred workflows demote and requeue their parent so
  child operations run without starvation. Prove ingestion handlers apply descriptor-owned retry
  policy to HTTP 429 responses and retain diagnostics when retries are exhausted. Prove the digest
  handler reconstructs and passes a serialized `resolved_set`, and prove `force_reprocess` reaches
  summarization execution rather than being ignored.
  **Spec scenarios**: agentic-operations.3, job-management.3
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/OperationHandle`
  **Design decisions**: D5, D6, D7
  **Dependencies**: 4.5, 5.17

- [x] 5.20 [M] Register durable workflow handlers
  Register ingestion, summarization, theme, digest, pipeline, podcast script, podcast audio, and audio digest handlers against the application workflows.
  A handler returning a deferred outcome MUST release and requeue the parent operation. The
  ingestion handler MUST enforce `SourceRetryPolicy` for retryable responses and preserve terminal
  failure diagnostics. The summarization handler MUST honor `force_reprocess` for completed
  content, and the digest handler MUST validate and pass the pipeline's serialized exact selection.
  **Dependencies**: 5.19, 5.2, 5.4, 5.7, 5.9, 5.12, 5.14, 5.17

- [x] 5.21 [XS] Checkpoint: run worker integration tests, review diff, verify scope
  **Dependencies**: 5.20

## 6. Provider Boundaries

- [x] 6.1 [M] Write provider boundary tests
  **Spec scenarios**: llm-provider-routing.1-3
  **Contracts**: None
  **Design decisions**: D10
  **Dependencies**: 1.3

- [x] 6.2 [M] Migrate digest processors to LLMRouter
  Route generation and tool use through provider-neutral router APIs while preserving token, cost, model, and telemetry metadata.
  **Dependencies**: 6.1, 2.9

- [x] 6.3 [M] Migrate podcast processors to LLMRouter
  Replace bespoke Anthropic and Gemini loops with router tool contracts while preserving constrained content tools.
  **Dependencies**: 6.1, 2.10

- [x] 6.4 [M] Migrate revision processors to LLMRouter
  Move digest revision, podcast revision, and historical context calls behind the router.
  **Dependencies**: 6.1

- [x] 6.5 [XS] Checkpoint: run LLM routing tests, review diff, verify scope
  **Dependencies**: 6.2, 6.3, 6.4

- [x] 6.6 [M] Write public audio service tests
  **Spec scenarios**: audio-digest.1-2, podcast-generation.4
  **Contracts**: None
  **Design decisions**: D10
  **Dependencies**: 1.3

- [x] 6.7 [M] Consolidate public audio services
  Make podcast and audio digest generation use public TTS plus storage methods; remove transport calls to legacy generators and private synthesis methods.
  **Dependencies**: 6.6

- [x] 6.8 [XS] Checkpoint: run audio service tests, review diff, verify scope
  **Dependencies**: 6.7

## 7. HTTP Surface

- [x] 7.1 [M] Write operation API contract tests
  **Spec scenarios**: agentic-operations.1-9, job-management.1-5
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1operations~1{operation_id}`, `contracts/events/operation.progress.schema.json`
  **Design decisions**: D6, D8
  **Dependencies**: 1.2, 4.2

- [x] 7.2 [M] Implement operation API routes
  Add status, bounded wait, cursor listing, SSE, retry, cancellation, RFC 7807 projection, and capability discovery routes.
  **Dependencies**: 7.1, 3.8, 4.8

- [x] 7.3 [XS] Checkpoint: run operation API tests, review diff, verify scope
  **Dependencies**: 7.2

- [x] 7.4 [M] Write ingestion API contract tests
  **Spec scenarios**: source-capability-registry.3-4, cli-interface.1-2, source-configuration.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1ingestions`, `contracts/openapi/v1.yaml#/paths/~1api~1v1~1uploads`
  **Design decisions**: D1, D8
  **Dependencies**: 1.2, 3.10

- [x] 7.5 [M] Implement upload API route
  Accept multipart files, store them through the upload service, return durable upload references, and enforce size plus media limits.
  **Dependencies**: 7.4

- [x] 7.6 [M] Implement ingestion API route
  Validate the discriminated union, reject extra fields, submit `ingestion.execute`, and preserve the canonical ingestion result in the completed operation.
  **Dependencies**: 7.4, 7.5, 5.20

- [x] 7.7 [XS] Checkpoint: run ingestion API tests, review diff, verify scope
  **Dependencies**: 7.5, 7.6

- [x] 7.8 [M] Write workflow API contract tests
  **Spec scenarios**: theme-analysis.2, podcast-generation.3-5, audio-digest.1, pipeline.6
  **Contracts**: `contracts/openapi/v1.yaml`
  **Design decisions**: D5, D8
  **Dependencies**: 1.2

- [x] 7.9 [M] Implement workflow API routes
  Replace summarization, theme, digest, pipeline, podcast script, podcast audio, and audio digest mutation routes with canonical operation submission.
  **Dependencies**: 7.8, 5.20

- [x] 7.10 [S] Retire legacy HTTP mutation routes
  Remove workflow-specific background tasks, status endpoints, flat ingestion request parsing, and direct audio generator calls at the coordinated cutover.
  **Dependencies**: 7.9

- [x] 7.11 [XS] Checkpoint: run HTTP tests, review diff, verify scope
  **Dependencies**: 7.9, 7.10

## 8. CLI and MCP Surfaces

- [x] 8.1 [M] Write CLI conformance tests
  **Spec scenarios**: cli-interface.1-6, agentic-operations.1-7
  **Contracts**: `contracts/openapi/v1.yaml`
  **Design decisions**: D8, D9
  **Dependencies**: 1.2, 7.11

- [x] 8.2 [M] Implement canonical CLI workflows
  Generate source arguments from command models, support uploads, submit operations through one client, add JSON output, add waiting, and expose capability discovery.
  **Dependencies**: 8.1

- [x] 8.3 [S] Retire direct CLI workflow paths
  Remove direct ingestion, digest, pipeline, podcast, and audio execution paths plus obsolete legacy aliases.
  **Dependencies**: 8.2

- [x] 8.4 [XS] Checkpoint: run CLI tests, review diff, verify scope
  **Dependencies**: 8.2, 8.3

- [ ] 8.5 [M] Write MCP conformance tests
  **Spec scenarios**: mcp-http-client.1-9, agentic-operations.8-9
  **Contracts**: `contracts/openapi/v1.yaml`
  **Design decisions**: D8, D9
  **Dependencies**: 1.2, 7.11

- [ ] 8.6 [M] Extract bounded MCP tool modules
  Split ingestion, content, workflow, review, operation, and knowledge tools behind a composition root without changing generated tool names unexpectedly.
  **Dependencies**: 8.5

- [ ] 8.7 [M] Route every MCP tool through HTTP mode
  Map all tools to the shared API client, enforce strict HTTP mode globally, and keep in-process mode on canonical application services.
  **Dependencies**: 8.5, 8.6

- [ ] 8.8 [M] Implement MCP operation tools
  Add structured capability, status, wait, retry, and cancellation tools; return native objects; translate RFC 7807 failures to protocol errors.
  **Dependencies**: 8.5, 8.7

- [ ] 8.9 [XS] Checkpoint: run MCP tests, review diff, verify scope
  **Dependencies**: 8.6, 8.7, 8.8

## 9. Frontend Surface

- [x] 9.1 [M] Write frontend contract drift tests
  **Spec scenarios**: source-capability-registry.5-6, agentic-operations.8, cli-interface.6
  **Contracts**: `contracts/generated/types.ts`, `contracts/openapi/v1.yaml`
  **Design decisions**: D9
  **Dependencies**: 1.2

- [x] 9.2 [S] Add frontend type generation
  Generate source command, operation, problem, capability, and resource types from OpenAPI during the frontend build and CI.
  **Dependencies**: 9.1

- [x] 9.3 [M] Implement canonical frontend API client
  Add typed submission, upload, capability, status, SSE, retry, cancellation, and resource lookup methods.
  **Dependencies**: 9.1, 9.2, 7.11

- [x] 9.4 [XS] Checkpoint: run frontend contract tests, review diff, verify scope
  **Dependencies**: 9.2, 9.3

- [ ] 9.5 [M] Write frontend workflow tests
  **Spec scenarios**: agentic-operations.1-7, source-configuration.1, e2e-testing.5-6
  **Contracts**: `contracts/openapi/v1.yaml`
  **Design decisions**: D8, D9
  **Dependencies**: 9.3

- [ ] 9.6 [M] Implement capability-driven ingestion controls
  Render every source command from capability metadata with explicit components for uploads, identifiers, option sets, dates, and booleans.
  **Dependencies**: 9.5

- [ ] 9.7 [M] Implement operation progress views
  Show durable status, SSE progress, errors, safe cancellation, retry actions, and reconnect behavior across all workflow screens.
  **Dependencies**: 9.5

- [ ] 9.8 [M] Implement workflow resource navigation
  Wire completed digest, theme, script, podcast, and audio resources into existing review, detail, and playback views.
  **Dependencies**: 9.5, 9.7

- [ ] 9.9 [XS] Checkpoint: run frontend tests, review diff, verify scope
  **Dependencies**: 9.6, 9.7, 9.8

## 10. End-to-End Validation

- [ ] 10.1 [M] Write vertical fixture registry tests
  **Spec scenarios**: e2e-testing.1-2
  **Contracts**: `contracts/openapi/v1.yaml#/components/schemas/IngestCommand`, `contracts/db/seed.sql`
  **Design decisions**: D11
  **Dependencies**: 3.2, 2.5

- [ ] 10.2 [M] Implement vertical source fixture library
  Add deterministic fixtures for every registry descriptor and a shared harness from ingestion through podcast context assembly.
  **Dependencies**: 10.1, 5.9

- [ ] 10.3 [XS] Checkpoint: run vertical source tests, review diff, verify scope
  **Dependencies**: 10.2

- [ ] 10.4 [M] Add pairwise source matrix tests
  **Spec scenarios**: e2e-testing.3-4, content-provenance.1-6
  **Contracts**: `contracts/db/seed.sql`
  **Design decisions**: D11
  **Dependencies**: 10.2

- [ ] 10.5 [M] Add cross-interface parity tests
  **Spec scenarios**: e2e-testing.5-6, source-capability-registry.6, mcp-http-client.1-8
  **Contracts**: `contracts/openapi/v1.yaml`
  **Design decisions**: D8, D9, D11
  **Dependencies**: 7.11, 8.4, 8.9, 9.9

- [ ] 10.6 [XS] Checkpoint: run combination tests, review diff, verify scope
  **Dependencies**: 10.4, 10.5

- [ ] 10.7 [M] Add workflow edge-case tests
  **Spec scenarios**: e2e-testing.7-8, agentic-operations.4-7, job-management.2-5
  **Contracts**: `contracts/db/schema.sql`, `contracts/events/operation.progress.schema.json`
  **Design decisions**: D2, D3, D6, D12
  **Dependencies**: 10.2, 4.8

- [ ] 10.8 [S] Update architecture documentation
  Document registry extension, selection provenance, queue operations, external contracts, source testing, migration order, and removed legacy paths in project documentation.
  **Dependencies**: 10.7

- [ ] 10.9 [M] Checkpoint: run full gates, review migration, verify cutover
  Run unit, integration, contract, frontend, E2E, lint, type checks, OpenSpec validation, architecture validation, and schema upgrade/downgrade rehearsal.
  **Dependencies**: 10.3, 10.6, 10.7, 10.8
