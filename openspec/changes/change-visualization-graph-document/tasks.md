# Tasks: Change visualization from a graph document

> Change ID: `change-visualization-graph-document`
> Execution tier: local-parallel
> Selected approach: artifact-derived projection onto the vendored pr-lens graph document, rendered by the pinned renderer and by the atlas

## Status

- [ ] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## 1. Contract and governance

- [ ] 1.1 [S] Write a contract test asserting the vendored `contracts/graph-doc.schema.json` `version` equals the contract version of the pinned `@coldtea/pr-lens-schema`, and that both example documents from upstream validate under Python `jsonschema` draft 2020-12; verify with `pytest tests/contract/test_change_graph_contract.py`
  **Spec scenarios**: Contract version mismatch is refused; Document validates before any rendering
  **Contracts**: `contracts/graph-doc.schema.json`, `contracts/corrections.schema.json`
  **Design decisions**: D1
  **Dependencies**: None
- [ ] 1.2 [S] Add `@coldtea/pr-lens-schema` and `@coldtea/pr-lens-renderer` as pinned `devDependencies` in `web/package.json`; verify `pnpm install --frozen-lockfile` succeeds and 1.1 passes
  **Dependencies**: 1.1
- [ ] 1.3 [S] Add a Python validation helper in `refresh-architecture/scripts/arch_utils/change_graph.py` that loads the vendored schema, validates a document, and writes `*.rejected.json` with errors on failure; verify with unit tests for a valid, an unknown-field, and a wrong-version document
  **Spec scenarios**: Document validates before any rendering; Contract version mismatch is refused
  **Design decisions**: D1
  **Dependencies**: 1.1
- [ ] 1.4 [S] Add `atlas`, `atlas-check` and `change-graph` Makefile targets wrapping the existing and new scripts; verify `make atlas-check` exits 2 on a stale page and 0 after `make atlas`
  **Spec scenarios**: Documented targets exist
  **Design decisions**: D9
  **Dependencies**: None
- [ ] 1.5 [S] Fix the atlas skill document: remove the missing proposal reference, describe the new targets and flags, and add a test that every repository path named in `codebase-atlas/SKILL.md` and `refresh-architecture/SKILL.md` exists; verify the test passes
  **Spec scenarios**: Skill document references resolve
  **Design decisions**: D9
  **Dependencies**: 1.4

- [ ] Checkpoint: run contract tests, `pnpm install`, and the path-existence test; confirm no source under `src/` changed

## 2. Projector core

- [ ] 2.1 [M] Write projector tests over the fixtures in `refresh-architecture/scripts/tests/fixtures/` plus a synthetic baseline graph and a synthetic `-U0` diff: added, removed, modified by intersecting hunk, unchanged by non-intersecting hunk, one-hop neighbours, hero edge selection with tie-break, and byte-identical output across two runs; verify with `pytest .claude/skills/refresh-architecture/scripts/tests/test_project_change_graph.py`
  **Spec scenarios**: Same inputs, same bytes; Unchanged neighbours are always present; Modified is line-range precise; Hero edge is the highest-impact addition
  **Design decisions**: D2
  **Dependencies**: 1.3
- [ ] 2.2 [L] Implement `project_change_graph.py`: merge-base resolution, baseline graph via `git show`, reuse of `diff_architecture.py`, hunk intersection, one-hop expansion through `arch_utils.traversal`, provenance and stats from git, validation through 1.3, deterministic serialisation; verify 2.1 passes
  **Dependencies**: 2.1
- [ ] 2.3 [M] Write tests for lanes, views and flows: container lanes, six-lane fold into `group`, root view open, package child scoped with neighbours, feature-slice grandchild, duplicate child dropped, flows only through changed nodes with edge-type to message-kind mapping, lens declaration with and without flows; verify with the same test module
  **Spec scenarios**: A change with no cross-layer path has no flows; Lane budget is enforced; Views never repeat their parent
  **Design decisions**: D3
  **Dependencies**: 2.2
- [ ] 2.4 [M] Implement lane classification reuse from `generate_views.py`, the view tree, flow mapping from `cross_layer_flows.json`, and the structural walkthrough skeleton with template text; verify 2.3 passes
  **Dependencies**: 2.3
- [ ] 2.5 [S] Write coverage tests: all changed files uncovered, some uncovered, all covered; verify the `coverage` block and stat chip values
  **Spec scenarios**: Change outside analyzed roots; Partial coverage is visible on the comment
  **Design decisions**: D2
  **Dependencies**: 2.2
- [ ] 2.6 [S] Implement coverage counting against graph basenames and the warning chip; verify 2.5 passes
  **Dependencies**: 2.5
- [ ] 2.7 [S] Run the projector on three recent merged pull requests and store the outputs as fixtures under `refresh-architecture/scripts/tests/fixtures/change/`; verify each validates and each renders in 5.x
  **Dependencies**: 2.4, 2.6

- [ ] Checkpoint: run the projector test module twice and diff outputs; review one fixture by hand for lane sanity

## 3. Corrections overlay

- [ ] 3.1 [S] Write overlay tests: rename by id, rename by glob after a file rename, exclude cascading to edges, flow steps, view selections and walkthrough focus, walkthrough dropped below two steps, unmatched selector warning; verify with `test_change_graph_corrections.py`
  **Spec scenarios**: Correction survives a rename; Excluded node takes its references with it; Unmatched selector is reported
  **Contracts**: `contracts/corrections.schema.json`
  **Design decisions**: D7
  **Dependencies**: 2.4
- [ ] 3.2 [M] Implement `settings/change-graph.yaml` loading, validation against the vendored corrections schema, and application inside the projector before narration; verify 3.1 passes and the document still validates after exclusion
  **Dependencies**: 3.1

- [ ] Checkpoint: apply a sample overlay to a 2.7 fixture and confirm the rendered picture changes only where addressed

## 4. Narration

- [ ] 4.1 [S] Add a `change_narration` pipeline step to `settings/models.yaml` with a small default model and `MODEL_CHANGE_NARRATION` override; verify settings tests pass and `aca models` lists the step
  **Design decisions**: D4
  **Dependencies**: None
- [ ] 4.2 [M] Write narration tests with a stubbed router: text fields merged, non-text keys ignored, structural difference discards output and logs the first path, over-long text truncated at a word boundary, missing provider leaves template text and exits 0; verify with `test_narrate_change_graph.py`
  **Spec scenarios**: Narration cannot change structure; Offline projection succeeds; Narration text is bounded
  **Design decisions**: D4
  **Dependencies**: 2.4, 4.1
- [ ] 4.3 [M] Implement `narrate_change_graph.py` with the text-only merge, structural comparison and re-validation; verify 4.2 passes
  **Dependencies**: 4.2

- [ ] Checkpoint: narrate one fixture with a real key locally, read the captions, confirm no id changed

## 5. Rendering and pull request comment

- [ ] 5.1 [M] Write `web/scripts/render-change-graph.mts` producing light and dark SVGs and `manifest.json` via `renderAll`, applying the same overlay file; add golden SVGs for two 2.7 fixtures compared byte for byte; verify with `pnpm --dir web vitest run scripts/render-change-graph.test.ts`
  **Spec scenarios**: Asset survives an image proxy; Picture change means URL change
  **Design decisions**: D5
  **Dependencies**: 1.2, 2.7
- [ ] 5.2 [S] Add a test that every emitted SVG contains no `<script`, `<link`, `url(`, `@import`, `var(--`, or `<image` with an external `href`, and that changing one label changes that view's file name and no other; verify it passes
  **Spec scenarios**: Asset survives an image proxy; Picture change means URL change
  **Dependencies**: 5.1
- [ ] 5.3 [M] Write the comment composer as a Node script with tests: marker present, root view open and others collapsed in tree order, stats line with uncovered count, `@name` and `#42` neutralised, all document strings inside single-line HTML elements; verify with `comment.test.ts`
  **Spec scenarios**: Diff text cannot notify people; Partial coverage is visible on the comment
  **Design decisions**: D8
  **Dependencies**: 5.1
- [ ] 5.4 [M] Add `.github/workflows/change-graph.yml`: concurrency by PR, cached architecture refresh, project, optional narrate, render, publish to `change-graph-assets/<pr>/<head7>/`, upsert the marked comment, exit 0 without posting on an empty diff; verify on a draft pull request that a second push edits the same comment
  **Spec scenarios**: Second push updates the comment; Empty diff posts nothing
  **Design decisions**: D8
  **Dependencies**: 5.3, 3.2
- [ ] 5.5 [S] Add the assets-branch retention step deleting directories for pull requests closed more than 90 days ago, dry-run by default; verify with a unit test over a synthetic listing
  **Design decisions**: D8 risk
  **Dependencies**: 5.4

- [ ] Checkpoint: open a draft pull request, confirm one comment, both themes, and that image URLs change after a label edit

## 6. Atlas delta overlay and walkthrough

- [ ] 6.1 [M] Write view-model tests: `--change` stamps `delta` on matched nodes and edges, unmatched ids listed, invalid document refused with the first error, output still byte-stable; verify with `atlas` test module
  **Spec scenarios**: Overlay loads from the hash; Overlay names an unknown node; Invalid document is refused; Re-render without upstream change
  **Design decisions**: D6
  **Dependencies**: 1.3, 2.7
- [ ] 6.2 [M] Implement `delta` in `atlas_model.py` and the `change=` hash loader, delta palette, legend, colour-mode toggle and ghosting in `atlas_assets.py`; verify 6.1 passes and a Playwright smoke test opens a fixture with the overlay and asserts node colours
  **Dependencies**: 6.1
- [ ] 6.3 [M] Implement the walkthrough rail: step list, keyboard and button navigation, `step=` in the hash, focus applied as selection with hops 0, frame-to-selection without re-heating; verify with a Playwright test that step three restores from a pasted URL and that node positions are unchanged before and after a step
  **Spec scenarios**: Step focus becomes the view; Step URL is shareable; Click does not move nodes
  **Design decisions**: D6
  **Dependencies**: 6.2
- [ ] 6.4 [S] Add the coverage banner assertions and the undismissable check to the Playwright smoke test; verify it passes
  **Spec scenarios**: Graph outlived its source; Check mode detects drift
  **Dependencies**: 6.2

- [ ] Checkpoint: open the atlas on a 2.7 fixture, play the walkthrough end to end, paste a step URL into a fresh tab

## 7. Integration evidence and documentation

- [ ] 7.1 [S] Write `docs/CHANGE_VISUALIZATION.md` covering the document, the projector, corrections, narration, the comment, the atlas overlay and troubleshooting; add it to the `CLAUDE.md` documentation index; verify the markdown link check passes
  **Dependencies**: 5.4, 6.3
- [ ] 7.2 [S] Update `refresh-architecture/SKILL.md` and `codebase-atlas/SKILL.md` with the new scripts, flags and Make targets; verify the 1.5 path test still passes
  **Dependencies**: 7.1
- [ ] 7.3 [M] Run the full local gate: projector, corrections, narration, renderer goldens, atlas and Playwright tests, plus `make architecture-check` and `make atlas-check`; record results in the change's session log
  **Dependencies**: 7.2

- [ ] Checkpoint: review the cumulative diff for anything under `src/` or `web/src/` (there should be none), confirm task to scenario traceability

## Dependency Summary

- Independent roots: 1.1, 1.4, 4.1
- Sequential chains: contract -> projector -> corrections -> workflow; projector fixtures -> renderer goldens; projector fixtures -> atlas overlay -> walkthrough
- Parallel branches: after 2.7, groups 3, 4, 5.1 to 5.3 and 6 can proceed in parallel; group 5.4 waits on 3.2 and 5.3
- Maximum package parallel width: 3
- Shared-file conflicts: `atlas_assets.py` is touched only by group 6; `project_change_graph.py` by groups 2 and 3 in sequence; Makefile by 1.4 only
- Task sizes: S=15, M=13, L=1, XL=0
