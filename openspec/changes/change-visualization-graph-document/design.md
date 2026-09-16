# Design: Change visualization from a graph document

## Context

See `proposal.md` for motivation. The constraints that shape the approach:

- `/refresh-architecture` already produces `architecture.graph.json` (nodes with
  `id, name, kind, file, line, language`; edges with `from, to, type`),
  `cross_layer_flows.json`, `high_impact_nodes.json` and, with `--diff <sha>`,
  `architecture.diff.json` (added and removed node and edge ids, new cycles, new
  high-impact modules). `generate_views.py` already classifies nodes into
  container, backend component, frontend component, ERD and feature-slice views.
  All of it is deterministic and gitignored under `docs/architecture-analysis/`.
- `/codebase-atlas` is a rendering-only skill: canvas 2D, a hand-written force
  simulation, no external dependency, view state in the location hash. Its
  view-model is built in `atlas_model.py` and its page by `atlas_render.py` from
  assets in `atlas_assets.py`.
- pr-lens separates a strict document (zod, exported as JSON Schema draft
  2020-12) from a renderer that owns placement, treats layout hints as floors,
  measures text from a table, fixes lane width, and returns an `atlas` of where
  each id landed. Its canvas and walkthrough player are a hosted product and not
  in the repository; the renderer's `atlas` exists so other surfaces can build
  one. Schema contract `0.1.1`, packages `@coldtea/pr-lens-schema@0.2.1` and
  `@coldtea/pr-lens-renderer@0.2.2`, MIT.
- Node 22 and pnpm are available in `web/`; `jsonschema[format]` is already a
  Python dependency. The project's model router selects a model per pipeline
  step through `settings/models.yaml` and `MODEL_<STEP>` overrides.

## Goals / Non-Goals

**Goals:**

- One document, two surfaces: the same validated file feeds the pull request
  comment and the atlas overlay.
- Structure from artifacts, words from a model, and never the other way round.
- Determinism end to end so a second push that changed nothing shows nothing
  moving.
- Corrections that outlive regeneration.
- Bring the atlas under specification and fix its documentation drift.

**Non-Goals:**

- Re-implementing the SVG renderer in Python, or forking it.
- A hosted canvas, write tokens, or any server component.
- LLM extraction of graph structure from a diff.
- A product feature: nothing here touches `src/`, the API, MCP or the database.
- Generating Obsidian `.canvas` files, although the document makes that a later
  one-script addition.

## Decisions

### D1: Adopt the pr-lens graph document, vendored and pinned

The interchange format is the pr-lens graph document, contract `0.1.x`. The
JSON Schema and the corrections schema are vendored under `contracts/` and the
two npm packages are pinned in `web/package.json`. Python validates with
`jsonschema` at draft 2020-12; Node validates with the package. A contract
test asserts the vendored `version` equals the pinned package's contract
version so the two cannot drift silently.

Why not our own schema: pr-lens has already made and fixed the decisions this
format needs (step order is array order; view scope is two explicit states so
losing the last selected element cannot widen a view to everything; ids are
URL- and SVG-safe; per-delta counts are derivable and therefore absent). Writing
a fresh schema would repeat those mistakes minus the fixes.

Why vendor rather than fetch: a projector that depends on unpkg at run time is
not deterministic and does not work offline.

### D2: The projector is a `refresh-architecture` script and derives every delta

`project_change_graph.py` takes `--base <ref>` (default `origin/main`),
`--head` (default `HEAD`), the artifact directory, and an output directory
`docs/architecture-analysis/change/<base7>..<head7>/`. It ensures the graph is
fresh through the existing `run_architecture.py --ensure` path, runs the
existing `diff_architecture.py` against `git show <merge-base>:...` of the
baseline graph, and derives:

| Delta | Source |
|---|---|
| `added` | node or edge id in `architecture.diff.json` `added_*` |
| `removed` | id in `removed_*`; the node is kept in the document with its base-side file ref |
| `modified` | id present in both graphs whose file has a hunk in `git diff <merge-base>...<head> -U0` intersecting `[line, end_line]`; edges are `modified` when either endpoint is `modified` and the edge is not `added` |
| `unchanged` | node within one hop of a changed node via `arch_utils.traversal.build_adjacency`, and every node a surviving flow or view names |

`stats` gets `filesChanged`, `additions`, `deletions` from git, and a
`coverage` block beside the document counts changed files whose basename the
graph never recorded. The hero edge is the added edge whose target has the
highest rank in `high_impact_nodes.json`, ties broken by id.

Why one hop: pr-lens's own guidance calls unchanged neighbours "what turns a
diagram into a blast radius". Two hops on this repository's graph produces
several hundred nodes for a routine change; one hop keeps the container view
readable and the component view scoped. Wider neighbourhoods are the atlas's
job, where the hop slider already exists.

Why re-run the existing diff rather than diff inside the projector: the diff
script is already tested and already reports new cycles and new high-impact
modules, which become stat chips.

Alternative considered: ask a model to produce the document from the diff as
pr-lens does. Rejected. It would discard ground truth the repository already
has, break determinism, and cost a model call per push.

### D3: Lanes, views and flows reuse the existing zoom levels

Lanes are the container classification `generate_views.py` already applies
(frontend, backend, database, external), plus a `tests` lane when test files
change; the lane budget is six, enforced by folding into `group`. Views are:

1. root, `architecture`, scope `all`, `defaultOpen: true`
2. child per touched backend or frontend package, scope = nodes in that package
   plus their one-hop neighbours
3. grandchild feature slice, scope = changed symbols only

A child whose selection equals its parent's is dropped. Flows are the paths in
`cross_layer_flows.json` that contain at least one changed node, mapped one
path to one flow, participants in path order, one message per hop, `kind`
from the edge type (`api_call` and `http` become `sync`; `db_access` becomes
`sync` with a `return`; `event` becomes `async`). A document with any flow
declares both lenses; otherwise only `architecture`.

The walkthrough skeleton is fixed and structural: step one focuses every
changed node on the root view; one step per added flow focused on that flow;
one step per removed node; one step for the hero edge. Steps are dropped when
their focus is empty and the whole walkthrough is dropped below two steps.
Narration fills the words; the projector owns the ids.

### D4: Narration is a separate step under the model router

`narrate_change_graph.py` reads the projected document and writes
`graph.narrated.json`. It calls the project's LLM router under a new pipeline
step `change_narration` in `settings/models.yaml` (default a small fast model,
overridable with `MODEL_CHANGE_NARRATION`), with the document, the diff stat
and the file list as input, and asks only for text: `title`, `summary`,
per-node `summary`, up to eight `stats.chips`, and the `heading` and `body` of
each walkthrough step by step id. The output is merged field by field onto the
projected document; any key that is not one of those text fields is ignored.
After merge the document is re-validated and structurally compared to the
projected one (same ids, deltas, endpoints, orders, counts). On any difference
or validation failure the projected document is used and the first differing
path is logged.

Why a text-only contract: it makes the "model cannot change structure" rule
mechanical rather than a prompt instruction, so a hallucinated node cannot
survive. Why a separate step: projection must work offline and in CI without a
key; narration is an enhancement.

Alternative considered: pr-lens's repair loop that re-prompts on validation
failure. Not needed when the model can only produce text.

### D5: Render with the pinned pr-lens renderer from a Node script

`web/scripts/render-change-graph.mts` reads a document, optionally the
corrections overlay, and writes light and dark SVGs plus `manifest.json` to
the change directory using `renderAll`. Golden SVGs for two fixture documents
live under the script's tests and are compared byte for byte. The script is
invoked from `make change-graph` and from CI; it has no other consumer.

Why not Python: the renderer's determinism rules (text width table, fixed lane
width, rounded coordinates, code-unit sorting) are the hard part, and they are
already tested upstream. Why not Mermaid: the existing `.mmd` views have no
delta vocabulary and Mermaid's layout is not stable across pushes.

### D6: The atlas consumes the same document; a walkthrough is a list of hash states

`atlas_model.py` accepts `--change <graph.json>` and stamps `delta` on every
view-model node and edge it can match by node id, listing unmatched ids. Node
ids are matched through `arch_utils.node_id` so the projector and the atlas
agree by construction. `atlas_assets.py` gains a delta palette, a legend, a
colour-mode toggle, ghosting for `removed`, and a `change=<path>` hash
parameter. The walkthrough player is a rail plus keyboard handler that, for
step `n`, sets the same hash state a reader would reach by hand (selection =
focus ids, hops = 0, `step=n`), then calls the existing frame-to-selection
routine. It never re-heats the simulation.

Why not embed the pr-lens renderer's SVG in the atlas: the atlas is a
neighbourhood explorer over the whole graph; the SVG is a fixed picture of a
scope. They answer different questions and share a document, not a renderer.

### D7: Corrections live in `settings/change-graph.yaml`

The overlay follows the vendored corrections schema's `map` object and lives
with the repository's other YAML settings rather than under `.github/`, so it
is loaded through `ConfigRegistry` conventions and found by people who look
where settings live. It is applied in the projector after derivation and
before narration, and again by the Node renderer through the same file so the
two surfaces cannot disagree. Exclusion cascades to edges, flow steps, view
selections and walkthrough focus, and a walkthrough left below two steps is
dropped, which is the pr-lens rule and keeps the document valid.

### D8: CI posts one marked comment and publishes assets to a branch

`.github/workflows/change-graph.yml` runs on `pull_request`, with
`concurrency` keyed by PR number and `cancel-in-progress`. It refreshes the
graph, projects, narrates when a key is present, renders, commits the SVGs to
an orphan branch `change-graph-assets` under `<pr>/<head7>/`, and upserts one
comment identified by `<!-- change-graph -->`. Image URLs point at the raw
content of that branch, so a changed picture is a new URL and the image proxy
cannot serve a stale one. The comment body is built by the pr-lens comment
composer's escaping rules: every model string inside an HTML element on one
line, `@` and `#` neutralised with a zero-width space.

Why an assets branch: a comment image must be a URL, workflow artifacts are
not URLs, and committing SVGs to the pull request branch would dirty every
review diff.

### D9: Governance and documentation drift

Add `atlas`, `atlas-check` and `change-graph` Makefile targets. Remove the
reference to the non-existent proposal document from the atlas skill and point
its "later phases" line at this change. Add a test that every repository path
named in the two skill documents exists.

### D10: Coverage is a node property with semantic zoom, not a second graph

Test nodes are NOT drawn as graph nodes by default. `test_linker.py` links tests
to source by direct import, so drawing them roughly doubles the node count and
forces the reader to mentally join two graphs. Instead the atlas gains a third
colour mode, `coverage`, alongside `language` and `delta`, and a
`show-test-nodes` toggle that is off by default and, when on, draws test nodes
and their `TEST_COVERS` edges in a muted style.

Coverage has two sources, both optional-degrading:

| Source | Availability | Grain |
|---|---|---|
| `TEST_COVERS` edges in the architecture graph | always, no extra run | linkage: how many distinct tests import this node, `0` meaning unlinked |
| `coverage.xml` when present in the repository root | after `pytest --cov-report=xml` | line: covered and total statements per file, mapped to symbols by line range |

When only linkage is available the scale is ordinal (`unlinked`, `1 test`,
`2 to 4`, `5 or more`). When a line report is present the scale is a sequential
ramp over percentage, and the legend says which source is in use. A node the
report does not mention is `unknown` and rendered neutral, never zero: absence
of data must not look like absence of tests.

Zoom carries the grain. Below the semantic-zoom threshold a node is one module
card coloured by its aggregate coverage. Above it, the card expands in place
into its symbols, each coloured by its own coverage, and the cross-connections
pane lists the covering tests for whichever symbol is selected. Expansion is
purely visual: the force simulation is not re-heated and no module position
changes, which is the same rule that already governs selection.

Why aggregate by statements rather than by symbol count: a module of twenty
one-line accessors and one hundred-line handler is not 95% covered when only
the accessors are tested. Weighting by statements makes the colour mean what a
reader assumes it means.

Alternative considered: a fourth view listing test nodes. Rejected because it
answers "which tests exist" when the question a reviewer actually has is "is
the code I am looking at tested", which a colour answers without navigation.

### D11: The Obsidian canvas export is a timeboxed spike, not a deliverable

The dormant `json-canvas` skill could emit a `.canvas` file from the same
document. Whether that is worth maintaining is unknown, so the change funds a
one-day spike, not an implementation. The spike renders one fixture document
both ways, then records a decision in `docs/decisions/` against fixed criteria:
whether the canvas survives regeneration without losing hand placement, whether
delta and coverage colour survive the format (JSON Canvas has a six-colour
preset palette and no per-node style), whether edges carry labels, and whether
anything is gained over a URL that opens the atlas at the same view.

The default outcome is "not worth it": the atlas already gives pan, zoom,
tracing and shareable views, and a `.canvas` file cannot animate, cannot host a
walkthrough, and drifts the moment the graph is regenerated. The spike exists
to disprove that cheaply, and it ships no code into the pipeline either way.

### D12: A change that covers nothing produces no document

The contract requires at least one node and one lane, so "a document showing
that nothing is covered" cannot exist.  The two ways to satisfy the schema are
both worse than refusing: a placeholder node puts a claim on the page that no
artifact supports, and a relaxed local schema would let the Python and Node
validators disagree, which is the failure D1 exists to prevent.

So the projector writes the coverage report, names the roots it searched, and
exits 0 without a document.  Exit 0 rather than 1 because the change is
legitimate -- a documentation or tooling commit covers no analyzed source by
definition -- and a tooling-only pull request must not fail CI for being
tooling-only.  No rejection sidecar is written either: nothing was rejected,
there was simply nothing to draw.

This was found by running the projector on this change itself, which touches
only `.claude/skills/` and `openspec/`.

## Risks / Trade-offs

- [Upstream contract bump breaks the vendored schema] → versions are pinned;
  the contract test fails loudly; re-vendoring is a documented step in the
  contracts README.
- [One-hop neighbourhood is too wide for hub modules] → the component view is
  scoped to the touched package; the feature slice is changed symbols only;
  the `exclude` correction handles chronic hubs.
- [Graph refresh in CI is slow] → the workflow uses the existing `--ensure`
  path and caches `docs/architecture-analysis/` keyed by the graph inputs'
  hash; a stale cache only costs a full refresh, never a wrong picture.
- [Narration leaks diff content into a hosted model] → narration is off when
  no key is configured and is a separate opt-in secret in CI.
- [Assets branch grows without bound] → a retention step deletes directories
  for closed pull requests older than 90 days; the comment for a closed PR
  degrades to broken images, which is acceptable.
- [Basename matching over-reports coverage] → inherited from the atlas; the
  coverage block states it is an upper bound.
- [Two senses of the word coverage] → the graph's file coverage (what the
  analyzer saw) and test coverage (what the tests exercise) are different
  numbers with the same name. The banner owns the first, the colour legend owns
  the second, and neither uses the bare word without a qualifier.
- [A stale `coverage.xml` colours the graph confidently and wrongly] → the
  loader reads the report's own timestamp, refuses one older than the newest
  changed source file, and falls back to linkage colouring with a legend note.

## Migration Plan

1. Land contracts, projector, corrections and tests with no CI wiring; run
   `make change-graph` locally on three recent merged pull requests and keep
   the outputs as fixtures.
2. Land the renderer script with goldens generated from those fixtures.
3. Land the atlas overlay and walkthrough.
4. Land the workflow with narration disabled; enable narration by adding the
   secret once three comments have been reviewed by a person.

Rollback is deleting the workflow file; nothing else has a runtime consumer.

## Open Questions

None. The two questions this design opened during planning are resolved above:
test node display and coverage colouring in D10, the Obsidian canvas in D11.
