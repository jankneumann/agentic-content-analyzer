# Change Context: unify-content-workflows-agentic-surfaces

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|-------------|-------------|--------------|-----------------|---------------|---------|----------|
| agentic-operations.1 | `specs/agentic-operations/spec.md` | Canonical operation handle | `contracts/openapi/v1.yaml#/components/schemas/OperationHandle` | D6, D8 | --- | `tests/contract/test_canonical_workflow_contracts.py`, `tests/queue/test_operation_service.py` | --- |
| agentic-operations.2 | `specs/agentic-operations/spec.md` | Universal queue execution | `contracts/db/schema.sql` | D6 | --- | `tests/queue/test_workflow_handlers.py`, `tests/contract/test_cross_interface_workflows.py` | --- |
| agentic-operations.3 | `specs/agentic-operations/spec.md` | Idempotency and operation control | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1operations~1{id}` | D6 | --- | `tests/queue/test_operation_controls.py`, `tests/api/test_operation_routes.py` | --- |
| agentic-operations.4 | `specs/agentic-operations/spec.md` | Agent-usable structured interfaces | `contracts/openapi/v1.yaml#/components/schemas/Problem` | D8 | --- | `tests/contract/test_cross_interface_workflows.py` | --- |
| audio-digest.1 | `specs/audio-digest/spec.md` | Public queued audio digest workflow | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1audio-digests` | D5, D6, D10 | --- | `tests/workflows/test_audio_digest_workflow.py`, `tests/services/test_public_audio_services.py` | --- |
| cli-interface.1 | `specs/cli-interface/spec.md` | CLI and API parity | `contracts/openapi/v1.yaml` | D8 | --- | `tests/cli/test_workflow_conformance.py` | --- |
| cli-interface.2 | `specs/cli-interface/spec.md` | Backward compatibility | --- | D12 | --- | `tests/cli/test_workflow_conformance.py` | --- |
| cli-interface.3 | `specs/cli-interface/spec.md` | Durable CLI workflow behavior | `contracts/openapi/v1.yaml#/components/schemas/OperationHandle` | D6, D8 | --- | `tests/cli/test_workflow_conformance.py` | --- |
| cli-interface.4 | `specs/cli-interface/spec.md` | CLI capability discovery | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1capabilities` | D9 | --- | `tests/cli/test_workflow_conformance.py` | --- |
| content-provenance.1 | `specs/content-provenance/spec.md` | Canonical summary-backed content set | `contracts/openapi/v1.yaml#/components/schemas/ContentQuery` | D2, D3 | --- | `tests/services/test_content_set_resolver.py` | --- |
| content-provenance.2 | `specs/content-provenance/spec.md` | Explicit half-open date policy | `contracts/openapi/v1.yaml#/components/schemas/ContentQuery` | D3 | --- | `tests/services/test_content_set_resolver.py` | --- |
| content-provenance.3 | `specs/content-provenance/spec.md` | End-to-end provenance invariants | `contracts/db/schema.sql` | D3, D4 | --- | `tests/processors/test_workflow_provenance.py`, `tests/contract/test_source_workflow_matrix.py` | --- |
| content-provenance.4 | `specs/content-provenance/spec.md` | Persisted selection snapshot | `contracts/db/schema.sql` | D4 | --- | `tests/migrations/test_workflow_provenance.py`, `tests/processors/test_workflow_provenance.py` | --- |
| content-query.1 | `specs/content-query/spec.md` | Structured content selection model | `contracts/openapi/v1.yaml#/components/schemas/ContentQuery` | D3 | --- | `tests/services/test_content_set_resolver.py` | --- |
| content-query.2 | `specs/content-query/spec.md` | ContentSetResolver workflow execution | `contracts/openapi/v1.yaml#/components/schemas/ContentQuery` | D3 | --- | `tests/services/test_content_set_resolver.py` | --- |
| e2e-testing.1 | `specs/e2e-testing/spec.md` | Registry-generated vertical source coverage | `contracts/openapi/v1.yaml#/components/schemas/IngestCommand` | D11 | --- | `tests/contract/test_source_workflow_matrix.py` | --- |
| e2e-testing.2 | `specs/e2e-testing/spec.md` | Mixed-source provenance coverage | `contracts/db/seed.sql` | D11 | --- | `tests/contract/test_source_workflow_matrix.py` | --- |
| e2e-testing.3 | `specs/e2e-testing/spec.md` | Cross-interface conformance coverage | `contracts/openapi/v1.yaml` | D8, D11 | --- | `tests/contract/test_cross_interface_workflows.py` | --- |
| e2e-testing.4 | `specs/e2e-testing/spec.md` | Workflow edge-case coverage | `contracts/db/seed.sql` | D11, D12 | --- | `tests/contract/test_source_workflow_matrix.py`, `tests/contract/test_cross_interface_workflows.py` | --- |
| job-management.1 | `specs/job-management/spec.md` | Job records project canonical operations | `contracts/db/schema.sql` | D6 | --- | `tests/queue/test_operation_service.py` | --- |
| job-management.2 | `specs/job-management/spec.md` | Complete workflow handler registry | `contracts/openapi/v1.yaml#/components/schemas/OperationHandle` | D6 | --- | `tests/queue/test_workflow_handler_registry.py` | --- |
| job-management.3 | `specs/job-management/spec.md` | Operation cancellation state | `contracts/events/operation.progress.schema.json` | D6 | --- | `tests/queue/test_operation_controls.py` | --- |
| llm-provider-routing.1 | `specs/llm-provider-routing/spec.md` | Complete pipeline routing through LLMRouter | --- | D10 | --- | `tests/processors/test_provider_boundaries.py` | --- |
| mcp-http-client.1 | `specs/mcp-http-client/spec.md` | MCP tools use configured HTTP mode | `contracts/openapi/v1.yaml` | D8 | --- | `tests/mcp/test_workflow_conformance.py` | --- |
| mcp-http-client.2 | `specs/mcp-http-client/spec.md` | MCP workflow tools use canonical operations | `contracts/openapi/v1.yaml#/components/schemas/OperationHandle` | D6, D8 | --- | `tests/mcp/test_workflow_conformance.py` | --- |
| mcp-http-client.3 | `specs/mcp-http-client/spec.md` | MCP structured results and errors | `contracts/openapi/v1.yaml#/components/schemas/Problem` | D8 | --- | `tests/mcp/test_workflow_conformance.py` | --- |
| mcp-http-client.4 | `specs/mcp-http-client/spec.md` | MCP capability discovery | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1capabilities` | D9 | --- | `tests/mcp/test_workflow_conformance.py` | --- |
| pipeline.1 | `specs/pipeline/spec.md` | Parallel registry source ingestion | `contracts/openapi/v1.yaml#/components/schemas/IngestCommand` | D1, D7 | --- | `tests/workflows/test_pipeline_workflow.py` | --- |
| pipeline.2 | `specs/pipeline/spec.md` | Single durable pipeline workflow | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1pipeline-runs` | D6, D7 | --- | `tests/workflows/test_pipeline_workflow.py` | --- |
| pipeline.3 | `specs/pipeline/spec.md` | Pipeline selection is preserved | `contracts/db/schema.sql` | D3, D7 | --- | `tests/workflows/test_pipeline_workflow.py` | --- |
| podcast-generation.1 | `specs/podcast-generation/spec.md` | Digest-bound podcast provenance | `contracts/db/schema.sql` | D4 | --- | `tests/processors/test_workflow_provenance.py`, `tests/workflows/test_podcast_script_workflow.py` | --- |
| podcast-generation.2 | `specs/podcast-generation/spec.md` | Durable podcast workflows | `contracts/openapi/v1.yaml#/paths/~1api~1v1~1podcast-scripts` | D5, D6 | --- | `tests/workflows/test_podcast_script_workflow.py`, `tests/workflows/test_podcast_audio_workflow.py` | --- |
| source-capability-registry.1 | `specs/source-capability-registry/spec.md` | Executable source registry | `contracts/openapi/v1.yaml#/components/schemas/IngestCommand` | D1 | --- | `tests/ingestion/test_source_registry.py` | --- |
| source-capability-registry.2 | `specs/source-capability-registry/spec.md` | Typed ingestion service dispatch | `contracts/openapi/v1.yaml#/components/schemas/IngestCommand` | D1 | --- | `tests/ingestion/test_ingestion_service.py` | --- |
| source-capability-registry.3 | `specs/source-capability-registry/spec.md` | Registry-derived capability parity | `contracts/openapi/v1.yaml#/components/schemas/CapabilityDocument` | D1, D9 | --- | `tests/services/test_capability_service.py`, `tests/contract/test_source_workflow_matrix.py` | --- |
| source-configuration.1 | `specs/source-configuration/spec.md` | Heterogeneous source discovery | `contracts/openapi/v1.yaml#/components/schemas/SourceCapability` | D1 | --- | `tests/ingestion/test_source_registry.py`, `tests/services/test_capability_service.py` | --- |
| theme-analysis.1 | `specs/theme-analysis/spec.md` | Theme analysis consumes resolved content | `contracts/db/schema.sql` | D3, D4 | --- | `tests/workflows/test_theme_analysis_workflow.py`, `tests/processors/test_workflow_provenance.py` | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Make source metadata executable | --- | One descriptor prevents source-key drift across dispatch and discovery. |
| D2 | Resolve canonical identity before eligibility | --- | Alias rows cannot independently enter downstream analysis. |
| D3 | Resolve immutable, fingerprinted content selections | --- | Preview and execution consume the same deterministic set. |
| D4 | Persist digest and podcast provenance | --- | Downstream generation never broadens the original selection. |
| D5 | Put persistence inside workflows | --- | Every successful operation has a stable resource result. |
| D6 | Reuse `pgqueuer_jobs` as the operation ledger | --- | One queue supplies status, retry, idempotency, and cancellation. |
| D7 | Use one parent-child pipeline workflow | --- | All interfaces observe the same stage semantics. |
| D8 | Replace external contracts in one coordinated cutover | --- | Controlled clients can converge without permanent adapters. |
| D9 | Generate interface types and capability metadata | --- | Drift becomes a build failure instead of a runtime mismatch. |
| D10 | Enforce router and media service boundaries | --- | Provider details stay out of workflows and transports. |
| D11 | Generate vertical and invariant-focused coverage | --- | Broad source coverage remains deterministic and scalable. |
| D12 | Use shadow validation before the breaking cutover | --- | Existing data and queued work are checked before legacy removal. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|

## Coverage Summary

- **Requirements traced**: 37/37
- **Tests mapped**: 37 requirements have at least one test
- **Evidence collected**: 0/37 requirements have pass/fail evidence
- **Gaps identified**: Implementation files and validation evidence are pending.
- **Deferred items**: None.
