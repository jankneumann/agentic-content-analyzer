# Change Context: repair-canonical-cli-transport-behavior

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|------------|-------------|-------------|----------------|---------------|---------|----------|
| cli-interface.1 | `specs/cli-interface/spec.md` | JSON mode emits exactly one document on stdout and sends diagnostics to stderr. | `openspec/contracts/content-workflows/openapi/v1.yaml` | D3 | `src/cli/workflow_commands.py`, `src/cli/graph_commands.py`, `src/utils/logging.py` | `tests/cli/test_canonical_workflows.py`, `tests/cli/test_graph_commands.py` | --- |
| cli-interface.2 | `specs/cli-interface/spec.md` | Discovery commands expose canonical cursor pages and omit absent optional query parameters. | `openspec/contracts/content-workflows/openapi/v1.yaml` | D1, D2 | `src/clients/workflow_api_client.py`, `src/cli/workflow_commands.py` | `tests/clients/test_workflow_api_client.py`, `tests/cli/test_canonical_workflows.py` | --- |
| test-infrastructure.1 | `specs/test-infrastructure/spec.md` | CLI unit tests select transports explicitly and consume async boundaries. | --- | D4 | `tests/cli/test_curate_commands.py`, `tests/cli/test_graph_commands.py` | `tests/cli/test_curate_commands.py`, `tests/cli/test_graph_commands.py` | --- |
| test-infrastructure.2 | `specs/test-infrastructure/spec.md` | Optional dependencies and tracked profile keys avoid known startup warnings. | --- | D5 | `pyproject.toml`, `uv.lock`, `profiles/local.yaml` | `tests/config/test_cli_runtime_hygiene.py` | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Repair malformed requests at the canonical caller boundary. | Filter only absent optional parameters in `WorkflowApiClient`. | Preserves strict API cursor validation and explicit falsey values. |
| D2 | Keep documented discovery command spelling compatible. | Mirror command-local JSON handling at `configured-sources`. | Supports operators without removing root JSON mode. |
| D3 | Separate payload and diagnostic streams. | Send logs to stderr and suppress human graph text in JSON mode. | Makes stdout reliably machine-readable without hiding diagnostics. |
| D4 | Unit tests must not consult ambient credentials or leak coroutines. | Force RSS transport and execute the real coroutine consumer with async mocks. | Tests the actual boundary deterministically. |
| D5 | Remove warning causes rather than suppressing them globally. | Constrain the optional detector and migrate tracked profile keys. | Keeps genuine future compatibility warnings visible. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|

## Coverage Summary

- **Requirements traced**: 4/4
- **Tests mapped**: 4 requirements have at least one planned test
- **Evidence collected**: 0/4 requirements have pass/fail evidence
- **Gaps identified**: ---
- **Deferred items**: Production deployment evidence belongs to roadmap item `ri-04`.
