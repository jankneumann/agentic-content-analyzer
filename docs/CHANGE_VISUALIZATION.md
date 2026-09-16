# Change Visualization

Draws what a change touches, against the code around it. One validated
document feeds two surfaces: diagrams on the pull request, and a colour mode in
the [codebase atlas](../.claude/skills/codebase-atlas/SKILL.md).

Nothing here infers structure. The deltas come from the architecture graph the
analyzer computes from Python AST, tree-sitter and ts-morph, intersected with
the diff. A model may write the prose; it cannot write the shape.

## Quick start

```bash
make architecture-refresh                  # the graph everything reads
make change-graph BASE=origin/main         # project this branch onto it
make atlas                                 # the interactive page
```

The projector writes to `docs/architecture-analysis/change/<base>..<head>/`,
which is gitignored. To render it:

```bash
cd web
node --experimental-strip-types scripts/render-change-graph.mts \
  ../docs/architecture-analysis/change/<base>..<head>/graph.json \
  --out /tmp/change --asset-base-url https://example/assets
```

To colour the atlas by that change:

```bash
python3 .claude/skills/codebase-atlas/scripts/build_atlas.py \
  --change docs/architecture-analysis/change/<base>..<head>/graph.json
```

## The document

The interchange format is the [pr-lens](https://github.com/coldteadotai/pr-lens)
graph document, contract `0.1.x`, MIT. Its schema is vendored at
`.claude/skills/refresh-architecture/contracts/graph-doc.schema.json`, with the
same bytes recorded as the OpenSpec contract for the change that introduced it.

Vendoring rather than fetching keeps projection deterministic and offline. It
only stays honest because a test pins the vendored copy byte-for-byte against
both the governance record and the installed `@coldtea/pr-lens-schema`.

**Two validators read that contract, and the JSON Schema alone cannot make them
agree.** The upstream contract is authored in zod, where rules like *every edge
endpoint is a declared node* live in `.refine()` calls that do not survive
export to JSON Schema. A document with a dangling edge passes the exported
schema and is then rejected by the renderer. So `arch_utils.change_graph`
validates in two passes: the schema for shape, then the referential rules the
schema cannot express. Skipping the second pass moves that failure from
projection, where the message names the offending id, to CI, where it does not.

## The projector

`project_change_graph.py` derives every delta:

| Delta | Where it comes from |
|---|---|
| `added` | in the head graph, not the base |
| `removed` | in the base graph, not the head |
| `modified` | in both, and a diff hunk intersects the symbol's own line span |
| `unchanged` | within one dependency hop of something that changed |

`modified` is span-precise on purpose: a file that changed elsewhere leaves its
other symbols `unchanged`, because a file-level delta would claim more than the
diff supports. The `unchanged` neighbours are what make the picture a blast
radius rather than a list.

**`TEST_COVERS` is not a dependency edge.** It is 96% of this repository's edges
and test functions are 57% of its nodes, so one hop across it would turn every
change into a picture of the test suite. Coverage travels as a badge on the
covered node, and a test appears as a node only when the change edited it.

### Without a base graph

The architecture graph is gitignored, so there is no committed history to
compare against. Without `BASE_GRAPH=<path>` the projector cannot tell added and
removed symbols from unchanged ones and marks only what a hunk touches. It says
so on every run. Pass a baseline graph when that distinction matters:

```bash
make change-graph BASE=origin/main BASE_GRAPH=/tmp/baseline.graph.json
```

### When nothing is drawn

A change touching nothing under the analyzed roots (`src`, `web`) writes a
coverage report and no document, and exits 0. The contract requires at least
one node, so a document saying "nothing is covered" cannot exist, and inventing
a placeholder would put a claim on the page that no artifact supports. A
documentation or tooling pull request covers no analyzed source by definition
and must not fail CI for being what it is.

## Corrections

`settings/change-graph.yaml` is an overlay: inference never writes to it, and
every projection re-applies it over freshly derived output. That is what lets a
correction keep holding as the code moves.

```yaml
map:
  rename:
    - match: src/services/legacy_mailer.py    # a path glob, or id:<graph-id>
      to: Postmark sender
  exclude: ["**/*.test.ts"]
  lane:
    - match: src/telemetry/*.py
      lane: infrastructure                     # a lane need not already exist
```

Prefer the glob form. It survives the analyzer renaming a symbol, which is the
case a correction most often has to outlive. Excluding a node takes its edges,
view selections and walkthrough focus with it; excluding everything a change
touched leaves nothing to draw, and the projector says so rather than emitting
a document that cannot render.

## Narration

Optional, and off unless a provider is configured. `narrate_change_graph.py`
fills the title, summary, node summaries and walkthrough captions through the
model router.

It cannot change structure, and that is mechanical rather than prompted: the
merge reads a closed set of text keys, so a hallucinated node has no path by
which it could be written, and a structural comparison over the document with
its prose stripped catches the rest. **Stat chips are not narratable** — a chip
is a number beside a diagram, so it reads as measured, and the comparison can
catch an invented id but not an invented quantity.

Every failure mode leaves the projection standing: no provider, a refusal, a
non-JSON answer, over-long text, or output that fails validation. The model is
declared as data in `settings/models.yaml` under `default_models.change_narration`
and overridden with `MODEL_CHANGE_NARRATION`; it is deliberately not a member of
the `ModelStep` enum, so no product code depends on this tooling.

## On a pull request

`.github/workflows/change-graph.yml` refreshes the graph, projects, renders and
posts one comment, identified by `<!-- change-graph -->` and updated in place on
every push.

Assets go to an orphan `change-graph-assets` branch, never the branch under
review, because committing SVGs there would dirty every reviewer's diff. Image
file names carry a hash of their own bytes, so a changed diagram arrives at a
new URL rather than as new bytes at an old one GitHub's image proxy has cached.

Every string in the comment is treated as untrusted, because it was written
from a diff and a pull request can carry any text into one. Each lands inside an
HTML element on a single line, where markdown is not parsed, and `@name` and
`#42` get a zero-width space so a diff cannot notify a person or link an issue.

Narration stays off until the `CHANGE_NARRATION_ENABLED` variable is set, so the
workflow needs no model credentials to be useful.

`change-graph-retention.yml` prunes assets for pull requests closed more than
ninety days ago, dry run unless someone dispatches it with `apply`.

## In the atlas

With `--change`, the atlas gains a `delta` colour mode beside `language` and
`coverage`. Colour mode, test-file visibility, hop depth, selection, zoom and
walkthrough step all round-trip through the location hash, so any view is a URL.

**Coverage means two different things on that page, and neither uses the bare
word.** The banner reports how much of the repository the *graph* saw. The
colour legend reports how much of the code the *tests* exercise, from
`TEST_COVERS` linkage or, when `--test-coverage coverage.xml` supplies a report
newer than the sources, from measured lines. A report older than the source is
refused: it would colour the graph as confidently as a fresh one and the reader
could not tell.

Untested and unmeasured are different colours. A symbol no test reaches is on
the scale; a symbol the report never mentions is neutral, because absence of
data is not absence of tests.

Test files are hidden until the `tests` toggle asks for them, detected both by
symbol kind and by path — the Python analyzer marks test symbols, ts-morph does
not, and a kind-only rule would hide one language's tests while leaving the
other's on the canvas.

Past a zoom threshold a file opens into its symbols, each carrying its own
colour, without any module moving. Zoom back out and they collapse.

## Troubleshooting

**"no architecture graph at …"** — run `make architecture-refresh` first.

**"the projected document does not validate"** — the errors are in a
`graph.rejected.json` beside where the document would have gone. An invalid
document never reaches its final path, because a half-valid graph read by a
later step is worse than no file.

**"correction selector matched nothing"** — the glob addresses a repository
path, not a symbol name, and Python paths are matched against `src/...` even
though the graph records them relative to the source root.

**The atlas says a change document names nodes it does not have** — the two were
built from different commits. Re-run `make architecture-refresh`, then project
again.

**`make atlas-check` exits 2** — the page is stale against the current graph,
which is what that exit code means. Run `make atlas`.

**The comment did not appear** — check whether the projector found anything to
draw. A change entirely outside `src` and `web` posts nothing by design.

## Related

- [`refresh-architecture`](../.claude/skills/refresh-architecture/SKILL.md) — produces the graph and the projector
- [`codebase-atlas`](../.claude/skills/codebase-atlas/SKILL.md) — renders the interactive page
- [Architecture](ARCHITECTURE.md) — the system the graph describes
