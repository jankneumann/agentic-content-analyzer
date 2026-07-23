# Change Context: reconcile-openspec-inventory

## Requirement Traceability Matrix

| Req ID | Description | Design | Planned evidence |
|---|---|---|---|
| openspec-inventory-governance.1 | Evidence-backed disposition | D1, D2, D3 | `evidence/inventory-reconciliation.md`, focused tests |
| openspec-inventory-governance.2 | Superseded contracts remain historical | D4 | MCP contract tests and archive record |
| openspec-inventory-governance.3 | Active inventory is actionable | D5, D6 | disposition manifest and inventory validator |
| openspec-inventory-governance.4 | Extracted gaps are traceable | D3, D6 | focused follow-up proposals and specs |

## Review Findings

| Finding | Criticality | Disposition | Resolution |
|---|---|---|---|
| PR-01 Retained roadmap changes were not strict-valid | blocker | fixed | Added `wp-retained-normalization` with exact scopes and six individual validations. |
| PR-02 Parallel archive/follow-up scopes overlapped | blocker | fixed | Narrowed archive scope, made successor creation a dependency of archival, and passed scope/lock overlap checks. |
| PR-03 Package task ownership was duplicated | blocker | fixed | Rewrote tasks and package inputs so verification, successor creation, normalization, archival, integration, and self-archive each have one owner. |
| PR-04 Spec synchronization could overclaim or replace newer scenarios | blocker | fixed | Required a per-change manual sync matrix, `--skip-specs` for reduced/manual merges, and touched-spec diff validation. |
| PR-05 Verification did not cover every disposition or active change | blocker | fixed | Added filtering, source override, HuggingFace, LLM, profile/MCP, RI-01/RI-02 gates plus exact retained/successor/touched-spec validation. |
| PR-06 Manifest lifecycle and self-archive were undefined | blocker | fixed | Defined an evidence snapshot, explicit transitional/final modes, and `wp-self-archive`. |
| PR-07 Archive precondition was nondeterministic | should-fix | fixed | Changed `MAY` to conditional `SHALL`. |
| PR-08 Follow-up count wording was stale | should-fix | fixed | Replaced the obsolete wording while restructuring tasks. |
| PR-09 Proposal impact omitted governance tooling | should-fix | fixed | Added the inventory validator/test impact while preserving the no-runtime-change boundary. |

Independent re-review returned a clean sign-off after all findings were
resolved. Strict OpenSpec, package schema/DAG/keys, scope overlap, lock overlap,
and parallel-zone validation pass with `parallel_pairs=[]`.

## Coverage

- Requirements planned: 4/4
- Automated inventory guard planned: yes
- External state mutated by RI-03: none
- Focused follow-ups retained: filtering runtime contract, source-override
  evidence, LLM evaluation/routing operationalization, and production
  ParadeDB/Langfuse verification
