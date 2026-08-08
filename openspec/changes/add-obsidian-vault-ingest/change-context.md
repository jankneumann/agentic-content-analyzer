# Change Context: add-obsidian-vault-ingest

The legacy change has no change-local `contracts/` directory, so Phase 1 contract-file
validation is skipped and Contract Ref uses `---`. P5 will modify the canonical OpenAPI
contract and generated bindings atomically; those files will be recorded in Phase 2.

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|------------|-------------|-------------|----------------|---------------|---------|----------|
| obsidian-vault-ingest.1 | `specs/obsidian-vault-ingest/spec.md` | Worker-local bounded vault scan | --- | D1, D2, D6, D9 | `src/ingestion/obsidian_scanner.py`; `src/ingestion/obsidian_adapter.py`; `src/queue/execution_claim.py`; scanner/adapter/claim tests | scanner bounds/readiness; real cancellation between committed notes; exact adapter outcomes | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.2 | `specs/obsidian-vault-ingest/spec.md` | Strict bounded clip metadata contract | --- | D5 | `src/ingestion/obsidian_parser.py`; `tests/ingestion/test_obsidian_parser.py` | parser valid/default/invalid/adversarial YAML tests | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.3 | `specs/obsidian-vault-ingest/spec.md` | Race-safe filesystem containment | --- | D2, D6 | `src/ingestion/obsidian_scanner.py`; `tests/ingestion/test_obsidian_scanner.py` | symlink/TOCTOU/stability/embed scanner tests | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.4 | `specs/obsidian-vault-ingest/spec.md` | Deterministic inert Markdown normalization | --- | D5, D6 | `src/ingestion/obsidian_parser.py`; `tests/ingestion/test_obsidian_parser.py` | normalization goldens and renderer regression tests | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.5 | `specs/obsidian-vault-ingest/spec.md` | Incremental state and concurrent claims | --- | D7 | state/generation migrations; `src/models/obsidian_ingest.py`; `src/repositories/obsidian_ingest.py`; `src/ingestion/obsidian_adapter.py`; state/adapter tests | barrier-backed claims; retry exhaustion; crash reconciliation; observation-generation CAS | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.6 | `specs/obsidian-vault-ingest/spec.md` | Canonical identity preserves note context | --- | D5, D8 | parser; `src/ingestion/obsidian_adapter.py`; `src/models/content.py`; content-source migrations; adapter integration tests | URL canonicalization; duplicate annotations; advisory-lock canonical race | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.7 | `specs/obsidian-vault-ingest/spec.md` | Read-only ingress/export ownership boundary | --- | D10 | scanner/adapter; `tests/architecture/test_obsidian_ownership.py`; scanner/adapter tests | byte-for-byte mutation snapshots; generated-note loop guard; import boundary | 134-test P1-P4 PostgreSQL gate passed |
| obsidian-vault-ingest.8 | `specs/obsidian-vault-ingest/spec.md` | Private diagnostics and path-free replay | --- | D3, D7, D9 | state migrations/model/repository; adapter/execution-claim code; redaction/retry tests | bounded parse/persistence/mount diagnostics; commit rollback; retry exhaustion | 134-test P1-P4 PostgreSQL gate passed |
| source-capability-registry.1 | `specs/source-capability-registry/spec.md` | Registry-derived parity with private filesystem configuration | canonical OpenAPI v1 | D1, D3, D4, D9 | generated contracts; config/settings; registry/service; CLI/HTTP/MCP/capability/UI/source-management surfaces | contract, registry, worker, transport, capability, UI build/render, opaque management, custom config-location, and privacy tests | 555-test focused P5 suite, 55 web tests/build, contract drift, mypy/Ruff passed |
| real-ingestion-ci.1 | `specs/real-ingestion-ci/spec.md` | Every registry source maps to deterministic fixture/live policy | --- | D4 | `tests/fixtures/sources/obsidian.py`; fixture registry; real-ingestion policy/harness/tier tests | exact fixture/policy equality, path-free missing-mount behavior, external-network prohibition | 17 registry/live-policy tests and 3 pure Obsidian fixture tests passed |
| real-ingestion-ci.2 | `specs/real-ingestion-ci/spec.md` | Offline durable results match Content/state deltas | --- | D7, D8, D9 | real-ingestion harness and PR-tier incremental Obsidian test | independent before/after Content IDs; state/event status and attempt deltas; typed result counters | implementation and collection/compile/style evidence complete; PostgreSQL execution pending P6 environment-capable gate |

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
| impl-p4.1 | wp-adapter | concurrency | high | fixed | Canonical URL identity is serialized by transaction advisory lock and a barrier-backed two-session test. |
| impl-p4.2 | wp-adapter | outcomes | high | fixed | Durable `retry_exhausted` state is reported as failed with a bounded diagnostic. |
| impl-p4.3 | wp-adapter | transactions | high | fixed | Content references publish only after the per-note transaction commits. |
| impl-p4.4 | wp-adapter | recovery | medium | fixed | Monotonic observation generation provides CAS protection against stale missing scans. |
| impl-p4.5 | wp-adapter | evidence | medium | fixed | Real barriers/failpoints force claim, crash-gap, cancellation, and canonical races. |
| impl-p4.6 | wp-adapter | migration | medium | fixed | Generation zero remains valid for pre-upgrade rows while negatives and booleans fail closed. |
| impl-p5.1 | wp-source-vertical | configuration | high | fixed | HTTP, MCP, direct CLI, and worker reloads consistently use deployment-configured source locations. |
| impl-p5.2 | wp-source-vertical | frontend | high | fixed | Persisted Obsidian content has exhaustive query/filter/badge mappings and a render regression. |
| impl-p5.3 | wp-source-vertical | privacy | medium | fixed | Configured-source discovery returns no Obsidian server policy or private locator fields. |
| impl-p5.4 | wp-source-vertical | privacy | medium | fixed | Source config models/loaders hide invalid private input values from errors and protocol surfaces. |
| impl-p5.5 | wp-source-vertical | contract | medium | fixed | `ContentQuery.source_types` is generated from a contract enum that includes every persisted content source. |
| impl-p5.6 | wp-source-vertical | management | medium | fixed | Obsidian source mutations require opaque public keys while internal natural-key merge/upsert remains private. |
| impl-p5.7 | wp-source-vertical | evidence | medium | fixed | Real-ingestion evidence snapshots Content independently of result claims and tracks state/event status and attempts. |

## Coverage Summary

- **Requirements traced**: 11/11
- **Tests mapped**: 11 requirements have at least one planned test
- **Evidence collected**: 10/11 requirements have P1-P5 pass/fail evidence
- **Gaps identified**: P6 PostgreSQL durable-delta execution, reliability/security regressions, and documentation pending
- **Deferred items**: watcher, device bridge, attachments, write/move behavior, custom templates
