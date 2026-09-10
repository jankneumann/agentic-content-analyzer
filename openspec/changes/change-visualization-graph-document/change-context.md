# Change Context: change-visualization-graph-document

Phase 1 (pre-implementation) complete. Files Changed and Evidence are filled in
Phase 2 and Phase 3 respectively.

Contract Ref is hand-filled: `packages/gen-eval/scripts/generate_contract_refs.py`
is absent from this repository, so the documented fallback applies. The two
machine-readable contracts under `contracts/` are the vendored graph document
schema and the corrections schema; requirements that no contract validates carry
`---`.

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|------------|-------------|-------------|----------------|---------------|---------|----------|
| change-visualization.1 | specs/change-visualization/spec.md | Every change visualization SHALL be expressed as one JSON document that validates against the vendored graph d | contracts/graph-doc.schema.json | D1 | --- | tests/contract/test_change_graph_contract.py | --- |
| change-visualization.2 | specs/change-visualization/spec.md | The projector SHALL derive the document only from the architecture graph, the architecture diff, the cross-lay | contracts/graph-doc.schema.json | D2 | --- | scripts/tests/test_project_change_graph.py | --- |
| change-visualization.3 | specs/change-visualization/spec.md | Lanes SHALL be the container classification the architecture views already use (frontend, backend, database, e | contracts/graph-doc.schema.json | D3 | --- | scripts/tests/test_project_change_graph.py | --- |
| change-visualization.4 | specs/change-visualization/spec.md | A narration step MAY fill the document's title, summary, node summaries, stat chips and walkthrough headings a | --- | D4 | --- | scripts/tests/test_narrate_change_graph.py | --- |
| change-visualization.5 | specs/change-visualization/spec.md | An optional overlay file SHALL support `rename`, `exclude`, `lane` and `group` corrections addressed by exact  | contracts/corrections.schema.json | D7 | --- | scripts/tests/test_change_graph_corrections.py | --- |
| change-visualization.6 | specs/change-visualization/spec.md | Each view SHALL render to one light and one dark SVG containing no script, external stylesheet, external image | --- | D5 | --- | web/scripts/render-change-graph.test.ts | --- |
| change-visualization.7 | specs/change-visualization/spec.md | CI SHALL post exactly one comment per pull request, identified by a hidden marker, and SHALL update that comme | --- | D8 | --- | web/scripts/comment.test.ts | --- |
| change-visualization.8 | specs/change-visualization/spec.md | The projector SHALL count changed files that the architecture graph does not cover and SHALL write that count  | --- | D2 | --- | scripts/tests/test_project_change_graph.py | --- |
| codebase-atlas.1 | specs/codebase-atlas/spec.md | The atlas SHALL render the architecture graph into a single HTML file that makes no network request, needs no  | --- | D6 | --- | scripts/tests/test_atlas_determinism.py | --- |
| codebase-atlas.2 | specs/codebase-atlas/spec.md | The page SHALL open with a banner reporting, per language, the fraction of on-disk files the graph covers, the | --- | D6 | --- | web/tests/e2e/atlas.spec.ts | --- |
| codebase-atlas.3 | specs/codebase-atlas/spec.md | Selection, hop depth, filter text, disabled language and edge-type filters, the loaded change document and the | --- | D6 | --- | web/tests/e2e/atlas.spec.ts | --- |
| codebase-atlas.4 | specs/codebase-atlas/spec.md | When the page is given a change graph document that validates against the vendored contract, it SHALL colour n | contracts/graph-doc.schema.json | D6 | --- | scripts/tests/test_atlas_delta.py | --- |
| codebase-atlas.5 | specs/codebase-atlas/spec.md | When the loaded document carries a walkthrough, the page SHALL show a step rail with each step's heading and b | contracts/graph-doc.schema.json | D6 | --- | web/tests/e2e/atlas.spec.ts | --- |
| codebase-atlas.6 | specs/codebase-atlas/spec.md | In this repository the Makefile SHALL provide `atlas` (write the page), `atlas-check` (read-only drift check w | --- | D9 | --- | scripts/tests/test_skill_doc_paths.py | --- |
| codebase-atlas.7 | specs/codebase-atlas/spec.md | The page SHALL offer `coverage` as a third colour mode alongside `language` and `delta`, and SHALL persist the | --- | D10 | --- | scripts/tests/test_atlas_coverage.py | --- |
| codebase-atlas.8 | specs/codebase-atlas/spec.md | Beyond a zoom threshold a module node SHALL expand in place into its symbols, each carrying its own colour und | --- | D10 | --- | web/tests/e2e/atlas.spec.ts | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Adopt the pr-lens graph document, vendored and pinned | --- | see design.md D1 |
| D2 | The projector is a `refresh-architecture` script and derives every delta | --- | see design.md D2 |
| D3 | Lanes, views and flows reuse the existing zoom levels | --- | see design.md D3 |
| D4 | Narration is a separate step under the model router | --- | see design.md D4 |
| D5 | Render with the pinned pr-lens renderer from a Node script | --- | see design.md D5 |
| D6 | The atlas consumes the same document; a walkthrough is a list of hash states | --- | see design.md D6 |
| D7 | Corrections live in `settings/change-graph.yaml` | --- | see design.md D7 |
| D8 | CI posts one marked comment and publishes assets to a branch | --- | see design.md D8 |
| D9 | Governance and documentation drift | --- | see design.md D9 |
| D10 | Coverage is a node property with semantic zoom, not a second graph | --- | see design.md D10 |
| D11 | The Obsidian canvas export is a timeboxed spike, not a deliverable | --- | see design.md D11 |

## Coverage Summary

- **Requirements traced**: 16/16
- **Tests mapped**: 16 requirements have at least one planned test
- **Evidence collected**: 0/16 requirements have pass/fail evidence
- **Gaps identified**: ---
- **Deferred items**: ---
