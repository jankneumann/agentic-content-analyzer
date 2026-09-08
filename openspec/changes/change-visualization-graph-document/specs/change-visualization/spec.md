## Purpose

Turns a code change into a validated graph document that shows what the change touched, what it sits next to, and how data moves through it, and renders that document to self-contained assets a reviewer can read on the pull request or explore in the atlas.

## ADDED Requirements

### Requirement: Change graph document is the interchange contract

Every change visualization SHALL be expressed as one JSON document that validates against the vendored graph document schema (`contracts/graph-doc.schema.json`, contract `0.1.x`). Every node, edge, flow and flow step SHALL carry exactly one delta from `added`, `modified`, `removed`, `unchanged`. Provenance (repository, base and head commit, generator name and version) SHALL be filled from the repository, and any provenance or numeric stats a producer or model emits SHALL be overwritten by the repository's own values. Unknown fields SHALL be rejected. No surface SHALL render a document that does not validate.

#### Scenario: Document validates before any rendering

- **WHEN** a producer writes a change graph document
- **THEN** it SHALL be validated against the vendored schema before it is written to its final path
- **AND** a document that fails validation SHALL be written to a `*.rejected.json` sibling with the validation errors, and the run SHALL exit non-zero

#### Scenario: Repository facts overwrite authored facts

- **WHEN** any producer supplies `provenance`, `stats.filesChanged`, `stats.additions` or `stats.deletions`
- **THEN** the projector SHALL replace them with values computed from git and the architecture artifacts

#### Scenario: Contract version mismatch is refused

- **WHEN** a document declares a `schemaVersion` outside the vendored contract's major and minor version
- **THEN** every consumer SHALL refuse it with a stable error naming both versions

### Requirement: Projection is deterministic and artifact-derived

The projector SHALL derive the document only from the architecture graph, the architecture diff, the cross-layer flows and the git diff between the merge base and head. It SHALL NOT call a language model. Given identical inputs it SHALL produce byte-identical output. Deltas SHALL be derived as follows: nodes and edges present only at head are `added`; present only at base are `removed`; present at both with a git diff hunk intersecting the node's file and line range are `modified`; every other node within one dependency hop of a changed node is `unchanged`. Nodes more than one hop away SHALL be excluded unless a flow or view names them.

#### Scenario: Same inputs, same bytes

- **WHEN** the projector runs twice on the same base, head and artifacts
- **THEN** the two documents SHALL be byte-identical
- **AND** the two rendered SVG sets SHALL be byte-identical

#### Scenario: Unchanged neighbours are always present

- **WHEN** a changed node has at least one dependency or dependant in the graph
- **THEN** the document SHALL include at least one node with delta `unchanged`
- **AND** a document whose every node is `added` SHALL be reported as a coverage warning, not silently accepted

#### Scenario: Modified is line-range precise

- **WHEN** a file changed but no hunk intersects a given symbol's recorded line range
- **THEN** that symbol's node SHALL be `unchanged`, not `modified`

#### Scenario: Hero edge is the highest-impact addition

- **WHEN** the change adds at least one edge
- **THEN** exactly one added edge whose target has the highest impact rank SHALL carry `emphasis: hero`
- **AND** no other edge SHALL carry `hero`

### Requirement: Lanes, views and flows follow the existing zoom levels

Lanes SHALL be the container classification the architecture views already use (frontend, backend, database, external), not directory names, and SHALL number no more than six. Views SHALL form a tree whose root is the container view with `defaultOpen: true`, with a backend or frontend component child scoped to the touched packages, and a feature-slice grandchild scoped to the changed symbols. Each child SHALL narrow scope relative to its parent. Flows SHALL be exactly the cross-layer flows that pass through at least one changed node, with participants in traversal order and messages in execution order.

#### Scenario: A change with no cross-layer path has no flows

- **WHEN** no traced cross-layer flow passes through a changed node
- **THEN** the document SHALL declare only the `architecture` lens and no flows

#### Scenario: Lane budget is enforced

- **WHEN** the projected lanes would exceed six
- **THEN** the projector SHALL merge by container and express the finer split as node `group`
- **AND** the document SHALL still validate

#### Scenario: Views never repeat their parent

- **WHEN** a child view would select the same nodes and edges as its parent
- **THEN** the child SHALL be omitted

### Requirement: Narration is optional and structure-preserving

A narration step MAY fill the document's title, summary, node summaries, stat chips and walkthrough headings and bodies through the project's model router under a dedicated pipeline step. It SHALL NOT add, remove, rename or re-identify any lane, node, edge, flow, message, view or walkthrough focus. A walkthrough's steps and focus ids SHALL be produced by the projector; narration only writes their text. When narration is unavailable or its output fails validation, the projector's template text SHALL stand and the run SHALL still succeed.

#### Scenario: Narration cannot change structure

- **WHEN** narration output differs from the projected document in any id, delta, endpoint, order or count
- **THEN** the narrated output SHALL be discarded and the projected document kept
- **AND** the discard SHALL be logged with the first differing path

#### Scenario: Offline projection succeeds

- **WHEN** no model provider is configured
- **THEN** projection, correction and rendering SHALL complete with template titles and captions

#### Scenario: Narration text is bounded

- **WHEN** narration returns text longer than the schema's label, summary or line limits
- **THEN** it SHALL be truncated at a word boundary before validation rather than rejected whole

### Requirement: Corrections overlay is applied, never absorbed

An optional overlay file SHALL support `rename`, `exclude`, `lane` and `group` corrections addressed by exact node id (`id:<node-id>`) or a repository-relative path glob. The overlay SHALL be applied on every projection after derivation and before narration and rendering. Excluding a node SHALL remove every edge, flow step, view selection and walkthrough focus that referenced it, and SHALL drop any walkthrough left with fewer than two steps. Nothing SHALL write to the overlay.

#### Scenario: Correction survives a rename

- **WHEN** a corrected node's file is renamed and the overlay glob still matches the new path
- **THEN** the correction SHALL still apply on the next projection

#### Scenario: Excluded node takes its references with it

- **WHEN** an overlay excludes a node that an edge, a flow step and a walkthrough step reference
- **THEN** the edge and flow step SHALL be removed, the walkthrough step SHALL lose that focus or be dropped, and the document SHALL validate

#### Scenario: Unmatched selector is reported

- **WHEN** an overlay selector matches nothing in the projected document
- **THEN** the projector SHALL warn with the selector text and continue

### Requirement: Rendered assets are self-contained and content-addressed

Each view SHALL render to one light and one dark SVG containing no script, external stylesheet, external image, font file or CSS custom property. Animation SHALL be declarative so the file plays when loaded as an image. An asset's file name SHALL include a hash of its content so a changed picture arrives at a new URL. Text from the document SHALL be escaped for XML and stripped of characters XML 1.0 cannot represent.

#### Scenario: Asset survives an image proxy

- **WHEN** a rendered SVG is loaded through an `<img>` element with no surrounding page
- **THEN** it SHALL display and animate without any additional request

#### Scenario: Picture change means URL change

- **WHEN** any pixel-affecting field of a view changes between two pushes
- **THEN** the view's asset file name SHALL differ
- **AND** an unchanged view SHALL keep its file name

### Requirement: Pull request receives one idempotent comment

CI SHALL post exactly one comment per pull request, identified by a hidden marker, and SHALL update that comment on every push rather than adding another. The comment SHALL show the root view open, other views inside collapsed disclosures in tree order, and a stats line. Every string from the document SHALL land inside an HTML element on one line so it is not parsed as markdown, and `@` and `#` followed by a word character SHALL be neutralised so the comment cannot mention a user or link an issue. Rendered assets SHALL be published to a dedicated assets branch, never to the pull request branch.

#### Scenario: Second push updates the comment

- **WHEN** a pull request that already carries the marked comment receives a new push
- **THEN** the existing comment body SHALL be replaced and no second comment SHALL exist

#### Scenario: Diff text cannot notify people

- **WHEN** a summary contains `@octocat` or `#42`
- **THEN** the posted comment SHALL render the text without a mention or issue link

#### Scenario: Empty diff posts nothing

- **WHEN** the merge base and head have identical content
- **THEN** the job SHALL exit successfully without posting or updating a comment

### Requirement: Coverage is reported, never assumed

The projector SHALL count changed files that the architecture graph does not cover and SHALL write that count as a stat chip and as a `coverage` block beside the document. A change whose covered fraction is below a configurable floor SHALL still render, with a warning chip, so a reviewer knows the picture is partial.

#### Scenario: Change outside analyzed roots

- **WHEN** every changed file lies outside the analyzed source roots
- **THEN** the document SHALL contain no changed nodes, a coverage chip reading that zero of N files are covered, and the run SHALL exit successfully with a warning

#### Scenario: Partial coverage is visible on the comment

- **WHEN** some changed files are uncovered
- **THEN** the comment's stats line SHALL include the uncovered count
