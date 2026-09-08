# Change: Change visualization from a graph document

> Change ID: `change-visualization-graph-document`
> Effort: L
> Priority: 6
> Inspiration: `coldteadotai/pr-lens` (MIT), whose open-source contract and renderer this change adopts; its hosted canvas and LLM extraction are deliberately not adopted.

## Why

The repository already computes a rich, typed architecture graph from AST,
tree-sitter and ts-morph (`/refresh-architecture`), renders it as an interactive
page (`/codebase-atlas`), and can diff two graphs (`diff_architecture.py`). Yet
no surface joins a *change* to a *picture*: review skills emit JSON findings,
the atlas colours by language only, and the architecture diff is never rendered.
Reviewers of agent-authored pull requests therefore read diffs line by line to
recover a shape the repository has already computed.

pr-lens demonstrates the missing join with one idea worth taking: an authored
graph document (lanes, nodes, edges with a delta each, ordered flows, a nested
view tree, a walkthrough) separated from a deterministic renderer that owns all
placement. Its contract is published under MIT. Its structure extraction, by
contrast, asks an LLM to guess a graph from a diff. This repository has ground
truth and does not need the guess.

The atlas skill is also ungoverned: no OpenSpec capability describes it, its
documented `make atlas` targets do not exist, and it cites a proposal document
that is not in the repository.

## What Changes

- Adopt the pr-lens graph document (schema contract `0.1.x`) as the single
  interchange format for change visualization. The JSON Schema is vendored under
  `contracts/` and validated in Python without Node.
- Add a deterministic **projector** in `/refresh-architecture` that turns a base
  SHA, the current architecture graph, the architecture diff, the cross-layer
  flows and the git diff into one validated change graph document. Every delta
  (`added`, `modified`, `removed`, `unchanged`) is derived from artifacts, never
  inferred by a model. Unchanged one-hop neighbours are always included so the
  picture shows blast radius, not just the change.
- Add an optional, structure-preserving **narration** step that may fill title,
  summary and walkthrough captions through the project's LLM router. It cannot
  add, remove or re-identify any element. Projection without narration is
  complete and offline.
- Add a human **corrections overlay** (`settings/change-graph.yaml`) with
  rename, exclude, lane and group operations addressed by node id or file glob,
  re-applied on every projection and never written back by inference.
- **Render** the document two ways from one source: self-contained,
  content-addressed light and dark SVGs via the pinned pr-lens renderer for pull
  request comments, and a delta overlay plus walkthrough playback inside the
  existing atlas page.
- Post one idempotent, marker-identified pull request comment with the nested
  disclosure tree (blast radius open, drill-downs collapsed) from CI.
- Bring `/codebase-atlas` under specification: add the missing `make atlas` and
  `make atlas-check` targets, add `make change-graph`, and remove the dangling
  proposal reference from its skill document.

## Capabilities

### New Capabilities
- `change-visualization`: projecting a code change onto the architecture graph
  as a validated graph document, correcting it, narrating it, rendering it to
  self-contained assets, and publishing it on a pull request.
- `codebase-atlas`: the existing self-contained interactive architecture page,
  now specified, plus delta overlay and walkthrough playback of a change graph
  document.

### Modified Capabilities
- None. `developer-workflow` describes profile and stack targets only; the new
  Make targets are specified under `codebase-atlas`.

## Impact

- **Affected skills**: `refresh-architecture` (new projector, corrections and
  narration scripts, `diff_architecture.py` consumed as input),
  `codebase-atlas` (view-model gains `delta`, page gains overlay and
  walkthrough, docs corrected), `parallel-review-implementation` and
  `implement-feature` (may attach the rendered comment).
- **New dependencies**: `@coldtea/pr-lens-schema` and
  `@coldtea/pr-lens-renderer`, pinned, as `devDependencies` in `web/`;
  `jsonschema` is already a Python dependency.
- **New files**: `settings/change-graph.yaml` (optional overlay),
  `.github/workflows/change-graph.yml`, `web/scripts/render-change-graph.mts`.
- **Generated artifacts**: `docs/architecture-analysis/change/<base>..<head>/`
  containing `graph.json`, `graph.narrated.json`, `manifest.json` and SVGs.
  The directory is already gitignored; published SVGs live on a dedicated
  assets branch, never on the pull request branch.
- **Makefile**: `atlas`, `atlas-check`, `change-graph` targets.
- **Security**: model-authored text is escaped before reaching GitHub and
  cannot mention users or cross-link issues; the CI job needs
  `pull-requests: write` and `contents: write` scoped to the assets branch.
- **Not affected**: product runtime, `src/`, database, `/api/v1`, MCP.

## Acceptance Outcomes

- Projecting the same base and head twice yields byte-identical documents and
  byte-identical SVGs.
- Every changed file that the architecture graph does not cover is counted and
  reported in the document's stats; the picture never silently claims full
  coverage.
- A document that validates against the vendored schema renders in both
  surfaces without further checks; a document that does not validate is never
  rendered.
- A correction in the overlay survives regeneration after the underlying file
  is renamed, as long as its glob still matches.
- A pull request receives exactly one change graph comment that is updated on
  every push and whose image URLs change whenever the picture changes.
- The atlas opens a change document from its URL hash, colours by delta, plays
  the walkthrough from the keyboard, and never moves a node the reader did not
  drag.
