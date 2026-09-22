# Change Context: closeout-db-source-overrides-evidence

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|-------------|-------------|--------------|-----------------|---------------|---------|----------|
| source-configuration.1 | `specs/source-configuration/spec.md` | Source override management API uses authenticated public management keys and keeps disabled shadows management-visible. | --- | D2, D4, D5 | --- | `tests/api/test_source_write_api.py`; `tests/api/test_sources_api.py` | --- |
| source-configuration.2 | `specs/source-configuration/spec.md` | CLI lifecycle commands use public management keys and redact Obsidian locators. | --- | D2, D5 | --- | `tests/cli/test_source_commands.py` | --- |
| source-override-closeout-evidence.1 | `specs/source-override-closeout-evidence/spec.md` | OpenAPI, runtime, and transports share nested `config.type`, PATCH, response, and legacy error semantics. | --- | D1, D2, D3 | --- | `tests/contract/test_canonical_workflow_contracts.py`; `tests/api/test_source_write_api.py`; `tests/cli/test_source_commands.py`; `web/src/lib/api/__tests__/sources.test.ts` | --- |
| source-override-closeout-evidence.2 | `specs/source-override-closeout-evidence/spec.md` | Authentication and opaque Obsidian identity include application/audit-log redaction. | --- | D4, D5 | --- | `tests/api/test_source_write_api.py`; `tests/api/test_audit_middleware.py`; `tests/cli/test_source_commands.py` | --- |
| source-override-closeout-evidence.3 | `specs/source-override-closeout-evidence/spec.md` | Browser quick-add supports Readwise while existing Obsidian rows remain opaque and not browser-configurable. | --- | D6 | --- | `web/src/components/settings/__tests__/SourcesConfigurator.test.tsx`; `web/tests/e2e/settings/sources.spec.ts` | --- |
| source-override-closeout-evidence.4 | `specs/source-override-closeout-evidence/spec.md` | A disposable PostgreSQL database proves predecessor-to-head migration behavior and incompatible-table diagnostics. | --- | D7 | --- | `tests/migrations/test_source_overrides.py` | --- |
| source-override-closeout-evidence.5 | `specs/source-override-closeout-evidence/spec.md` | Current setup and architecture docs make source override operations and recovery reproducible. | --- | D8, D9 | --- | deterministic documentation checks in `tasks.md`; strict OpenSpec validation | --- |

The change-local `contracts/` directory contains only explanatory Markdown, so
no machine-readable change contract is available for hand-populated contract
references. The implementation extends the durable content-workflows OpenAPI;
its paths and generated artifacts are asserted directly by the mapped tests.

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Keep `config.type` as the sole meaningful discriminator while preserving ignored sibling compatibility. | Durable OpenAPI schemas plus runtime/transport parity tests. | Avoids archive-driven API breakage. |
| D2 | PATCH only changes enabled state. | Typed PATCH contract and source mutation tests. | Preserves existing version and shadow behavior. |
| D3 | Extend the durable content-workflows contract. | Additive OpenAPI paths and regenerated Python/TypeScript models. | Prevents a second competing contract domain. |
| D4 | Model owner-session and admin-key authentication. | Security schemes and 401/403 no-mutation tests. | Matches middleware and route defense in depth. |
| D5 | Keep Obsidian public identity opaque. | Public projection/error/log redaction and negative tests. | Prevents worker-local locator disclosure. |
| D6 | Make browser management intentionally asymmetric. | Readwise quick-add; opaque existing Obsidian management; generic override-removal copy. | The browser cannot validate worker mounts or infer YAML baselines. |
| D7 | Prove the shipped migration in a disposable database. | Predecessor-to-head PostgreSQL test with scoped teardown. | A temporary schema is unsafe because the migration inspects `public`. |
| D8 | Retain complete-catalog GET. | No pagination contract change; existing grouped count query remains. | This is a bounded operator configuration catalog. |
| D9 | Keep current docs authoritative. | Update `docs/SETUP.md` and `docs/ARCHITECTURE.md`; leave the archive untouched. | Operators need live guidance rather than corrected history. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|
| plan-1 | plan | consistency/security/testability | high | fixed | Three refinement rounds resolved discriminator, auth, privacy, UI provenance, migration isolation, and durable-spec conflicts. |
| plan-final | plan | structured review | low | accepted | No blocking finding; external vendor quorum was policy-blocked and recorded as single-reviewer fallback. |

## Coverage Summary

- **Requirements traced**: 7/7
- **Tests mapped**: 7 requirements have at least one planned test/check
- **Evidence collected**: 0/7 requirements have pass/fail evidence
- **Gaps identified**: implementation and validation pending
- **Deferred items**: none
