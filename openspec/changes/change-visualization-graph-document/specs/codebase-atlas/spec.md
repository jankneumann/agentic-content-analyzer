## Purpose

Renders the architecture graph as one self-contained interactive page for reading a codebase's shape, and plays a change graph document over that page as a delta overlay and guided walkthrough.

## ADDED Requirements

### Requirement: Atlas is a self-contained deterministic page

The atlas SHALL render the architecture graph into a single HTML file that makes no network request, needs no server or build step, and works under a strict content security policy. For a fixed input graph the output SHALL be byte-stable: collections sorted, JSON keys sorted, initial positions seeded from a hash of each module key. A read-only check mode SHALL exit `0` when the written page matches the input, `2` when it is stale, and `1` on error.

#### Scenario: Check mode detects drift

- **WHEN** the graph changes after the page was written and check mode runs
- **THEN** it SHALL exit `2` and write nothing

#### Scenario: Re-render without upstream change

- **WHEN** the page is rendered twice from the same graph
- **THEN** the two files SHALL be byte-identical

### Requirement: Coverage banner cannot be dismissed

The page SHALL open with a banner reporting, per language, the fraction of on-disk files the graph covers, the top-level directories the graph never saw, and the count of graph files no longer on disk. The banner SHALL NOT be dismissable. Coverage SHALL be described as an upper bound because matching is by file name.

#### Scenario: Graph outlived its source

- **WHEN** the graph names a file that no longer exists on disk
- **THEN** the banner SHALL count it as stale and remain visible

### Requirement: Any view is a URL

Selection, hop depth, filter text, disabled language and edge-type filters, the loaded change document and the current walkthrough step SHALL round-trip through the location hash, so that a pasted URL reopens the same view. Selecting a node SHALL NOT re-heat the layout simulation.

#### Scenario: Pasted URL restores the view

- **WHEN** a URL carrying selection, hop depth and a change document reference is opened
- **THEN** the page SHALL restore that selection, neighbourhood and overlay without user interaction

#### Scenario: Click does not move nodes

- **WHEN** the reader selects a node after the layout has settled
- **THEN** no node position SHALL change

### Requirement: Delta overlay colours the graph by change

When the page is given a change graph document that validates against the vendored contract, it SHALL colour nodes and edges by delta (added, modified, removed, unchanged) instead of by language, dim every element the document does not name, show a delta legend, and offer a toggle back to language colouring. Removed elements SHALL remain visible, ghosted. A document that fails validation SHALL be refused with its first error shown, and the page SHALL fall back to language colouring.

#### Scenario: Overlay loads from the hash

- **WHEN** the hash names a change document the page can read
- **THEN** every element the document names SHALL be coloured by its delta and every other element SHALL be dimmed

#### Scenario: Overlay names an unknown node

- **WHEN** the document names a node id absent from the atlas graph
- **THEN** the page SHALL list the unmatched ids in the coverage banner and colour the rest

#### Scenario: Invalid document is refused

- **WHEN** a loaded document fails contract validation
- **THEN** the page SHALL show the first validation error and keep language colouring

### Requirement: Walkthrough plays as a sequence of views

When the loaded document carries a walkthrough, the page SHALL show a step rail with each step's heading and body, and playing a step SHALL apply that step's focus as the current selection and neighbourhood, dim everything else, and frame the focused elements without moving them. Steps SHALL advance with a keyboard shortcut and with buttons, and the current step SHALL be part of the URL. A walkthrough with fewer than two surviving steps SHALL NOT be offered.

#### Scenario: Step focus becomes the view

- **WHEN** the reader advances to a step focused on two nodes and one edge
- **THEN** those three elements SHALL be highlighted, the rest dimmed, and the viewport SHALL pan and zoom to frame them

#### Scenario: Step URL is shareable

- **WHEN** the reader copies the URL on step three and opens it elsewhere
- **THEN** the page SHALL open on step three with the same focus

### Requirement: Source checkout exposes Make targets

In this repository the Makefile SHALL provide `atlas` (write the page), `atlas-check` (read-only drift check with the exit codes above) and `change-graph` (project a change document for a given base, default `origin/main`, and open-ready atlas URL). The skill document SHALL describe only targets and files that exist.

#### Scenario: Documented targets exist

- **WHEN** `make atlas`, `make atlas-check` and `make change-graph BASE=<ref>` are invoked in a source checkout
- **THEN** each SHALL run the corresponding script and exit with its documented code

#### Scenario: Skill document references resolve

- **WHEN** the atlas skill document is checked for referenced repository paths
- **THEN** every referenced path SHALL exist

### Requirement: Coverage is a colour mode, test nodes are an option

The page SHALL offer `coverage` as a third colour mode alongside `language` and `delta`, and SHALL persist the active mode in the location hash. Coverage SHALL be read from `TEST_COVERS` edges in the architecture graph, and, when a line-coverage report is present and not older than the newest analyzed source file, from that report instead. The legend SHALL name which source is in use. A node the active source does not mention SHALL render as `unknown` in a neutral colour distinct from the zero-coverage colour. Aggregate coverage for a module SHALL be weighted by statements when a line report is in use, not by symbol count.

Test nodes SHALL NOT be drawn as graph nodes by default. A `show-test-nodes` toggle SHALL draw them with their `TEST_COVERS` edges in a muted style, and SHALL round-trip through the location hash.

#### Scenario: Unlinked code is visibly distinct from unmeasured code

- **WHEN** one node has no `TEST_COVERS` edge and another is absent from the loaded line-coverage report
- **THEN** the first SHALL render in the zero-coverage colour and the second SHALL render as `unknown`
- **AND** the legend SHALL distinguish the two

#### Scenario: Stale coverage report is refused

- **WHEN** the line-coverage report is older than the newest analyzed source file
- **THEN** the page SHALL fall back to linkage colouring and state in the legend that the report was stale

#### Scenario: Test nodes are off until asked for

- **WHEN** the page opens with no explicit toggle in the hash
- **THEN** no test node SHALL be drawn
- **AND** enabling the toggle SHALL draw test nodes and their edges without changing the position of any non-test node

#### Scenario: Module coverage is statement-weighted

- **WHEN** a module holds twenty fully covered one-statement symbols and one uncovered hundred-statement symbol
- **THEN** its aggregate coverage SHALL be below 25 percent

### Requirement: Node-level zoom reveals symbol detail in place

Beyond a zoom threshold a module node SHALL expand in place into its symbols, each carrying its own colour under the active colour mode, and SHALL collapse back below that threshold. Expansion SHALL NOT re-heat the layout simulation or move any module. Selecting an expanded symbol SHALL show its covering tests in the cross-connections pane when coverage data is available. The expansion state SHALL follow from the zoom level in the hash so that a shared URL reopens at the same grain.

#### Scenario: Zooming in changes grain, not layout

- **WHEN** the reader zooms past the expansion threshold
- **THEN** module nodes in view SHALL show their symbols
- **AND** no module centre SHALL move

#### Scenario: Covering tests are reachable from a symbol

- **WHEN** an expanded symbol with at least one `TEST_COVERS` edge is selected
- **THEN** the cross-connections pane SHALL list the covering tests, each clickable

#### Scenario: Grain is part of the shared view

- **WHEN** a URL captured at an expanded zoom level is opened elsewhere
- **THEN** the page SHALL open with the same nodes expanded
