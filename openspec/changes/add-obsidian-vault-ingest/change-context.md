# Change Context: add-obsidian-vault-ingest

The legacy change has no change-local `contracts/` directory, so Phase 1 contract-file
validation is skipped and Contract Ref uses `---`. P5 will modify the canonical OpenAPI
contract and generated bindings atomically; those files will be recorded in Phase 2.

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|------------|-------------|-------------|----------------|---------------|---------|----------|
| obsidian-vault-ingest.1 | `specs/obsidian-vault-ingest/spec.md` | Worker-local bounded vault scan | --- | D1, D2, D6, D9 | `src/ingestion/obsidian_scanner.py`; `tests/ingestion/test_obsidian_scanner.py` | scanner bounds/readiness; adapter cancellation/outcome; durable surface integration | --- |
| obsidian-vault-ingest.2 | `specs/obsidian-vault-ingest/spec.md` | Strict bounded clip metadata contract | --- | D5 | `src/ingestion/obsidian_parser.py`; `tests/ingestion/test_obsidian_parser.py` | parser valid/default/invalid/adversarial YAML tests | --- |
| obsidian-vault-ingest.3 | `specs/obsidian-vault-ingest/spec.md` | Race-safe filesystem containment | --- | D2, D6 | `src/ingestion/obsidian_scanner.py`; `tests/ingestion/test_obsidian_scanner.py` | symlink/TOCTOU/stability/embed scanner tests | --- |
| obsidian-vault-ingest.4 | `specs/obsidian-vault-ingest/spec.md` | Deterministic inert Markdown normalization | --- | D5, D6 | `src/ingestion/obsidian_parser.py`; `tests/ingestion/test_obsidian_parser.py` | normalization goldens and renderer regression tests | --- |
| obsidian-vault-ingest.5 | `specs/obsidian-vault-ingest/spec.md` | Incremental state and concurrent claims | --- | D7 | --- | migration/repository/two-session/crash tests | --- |
| obsidian-vault-ingest.6 | `specs/obsidian-vault-ingest/spec.md` | Canonical identity preserves note context | --- | D5, D8 | `src/ingestion/obsidian_parser.py`; `tests/ingestion/test_obsidian_parser.py` | URL canonicalization and duplicate annotation integration tests | --- |
| obsidian-vault-ingest.7 | `specs/obsidian-vault-ingest/spec.md` | Read-only ingress/export ownership boundary | --- | D10 | `src/ingestion/obsidian_scanner.py`; `tests/ingestion/test_obsidian_scanner.py` | mutation snapshot and import-boundary tests | --- |
| obsidian-vault-ingest.8 | `specs/obsidian-vault-ingest/spec.md` | Private diagnostics and path-free replay | --- | D3, D7, D9 | --- | state/operation/log/telemetry redaction and retry tests | --- |
| source-capability-registry.1 | `specs/source-capability-registry/spec.md` | Registry-derived parity with private filesystem configuration | --- | D1, D3, D4, D9 | --- | generated contract, config, registry, CLI/HTTP/MCP/UI, fixture parity tests | --- |
| real-ingestion-ci.1 | `specs/real-ingestion-ci/spec.md` | Every registry source maps to deterministic fixture/live policy | --- | D4 | --- | collection completeness and missing-mount policy tests | --- |
| real-ingestion-ci.2 | `specs/real-ingestion-ci/spec.md` | Offline durable results match Content/state deltas | --- | D7, D8, D9 | --- | OperationService incremental/duplicate/failure DB-delta tests | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Durable workflows require bounded terminal operations. | P4 adapter and P5 source vertical | Reuses `ingestion.execute`, cancellation, retry, and scheduling. |
| D2 | Host-local paths cannot route to arbitrary cloud workers. | P3 readiness and P5 capability resolver | Fails closed until a compatible mount is provable. |
| D3 | Vault paths and note names are private server data. | P3 root policy and P5 source configuration | Stable `vault_id` plus opaque HMAC source keys preserve portability and privacy. |
| D4 | Collection checks reject partially registered sources. | Atomic P5 synchronization package | Keeps every commit registry/fixture/contract green. |
| D5 | Captured Markdown must retain annotations without SSRF/refetch drift. | P1 parser/normalizer and P4 persistence | The note bytes remain authoritative. |
| D6 | Synced trees are untrusted and race-prone. | P3 descriptor-relative scanner | No-follow reads and revalidation close traversal and TOCTOU gaps. |
| D7 | Active queue idempotency alone does not cover terminal/crash races. | P2 state/events/claims and P4 reconciliation | Database uniqueness and leases make replay safe. |
| D8 | Same-page notes may contain distinct user context. | P4 canonical linking | Preserves note rows while sharing canonical identity. |
| D9 | RI-09 already owns terminal evidence and alerting. | P4/P5 typed outcomes and redaction | Avoids a second observability model. |
| D10 | Vault ingress and knowledge-base export have different ownership. | P3 loop guards and P4 architecture test | Prevents import cycles and feedback loops. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|
| plan-2.1 | all | topology | critical | fixed | Worker-local mount boundary and fail-closed readiness. |
| plan-2.2 | wp-adapter | durability | critical | fixed | One bounded canonical operation; no poller/watcher. |
| plan-2.3 | wp-source-vertical | contract parity | critical | fixed | Atomic generated/registry/interface/fixture package. |
| plan-2.4 | wp-state | concurrency | high | fixed | Composite digests, immutable events, leases, uniqueness, reconciliation. |
| plan-2.5 | wp-scanner | security | high | fixed | No-follow descriptor access, all symlinks rejected, hard bounds. |
| plan-2.6 | wp-parser | contract | high | fixed | Strict URL/timestamp/YAML and inert normalization. |
| plan-2.7 | all | privacy | high | fixed | Opaque IDs and allowlist-first diagnostics/projections. |

## Coverage Summary

- **Requirements traced**: 11/11
- **Tests mapped**: 11 requirements have at least one planned test
- **Evidence collected**: 0/11 requirements have pass/fail evidence
- **Gaps identified**: Phase 2 implementation files and Phase 3 revision evidence pending
- **Deferred items**: watcher, device bridge, attachments, write/move behavior, custom templates
