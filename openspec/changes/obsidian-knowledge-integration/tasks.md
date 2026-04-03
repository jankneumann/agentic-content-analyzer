# Tasks: Obsidian Knowledge Integration

## Phase 1: Core Infrastructure (Frontmatter + Manifest)

- [ ] 1.1 Write tests for obsidian_frontmatter module — frontmatter generation, slugification, content hashing
  **Spec scenarios**: obsidian-sync: YAML frontmatter (all sub-scenarios), Date-prefixed file naming (all sub-scenarios)
  **Design decisions**: D2 (frontmatter as separate utility), D3 (prepend, don't modify generators)
  **Dependencies**: None

- [ ] 1.2 Create `src/sync/obsidian_frontmatter.py` — `build_frontmatter()`, `slugify_filename()`, `compute_content_hash()`
  **Dependencies**: 1.1

- [ ] 1.3 Write tests for obsidian_manifest module — load/save, needs_update, stale detection, collision handling
  **Spec scenarios**: obsidian-sync: Incremental sync with manifest (all sub-scenarios)
  **Design decisions**: D1 (manifest-based sync over timestamps)
  **Dependencies**: None

- [ ] 1.4 Create `src/sync/obsidian_manifest.py` — `SyncManifest` class with load, needs_update, record, get_stale_entries, save
  **Dependencies**: 1.3

## Phase 2: Content Exporters (Digests, Summaries, Insights, Stubs)

- [ ] 2.1 Write tests for digest export — frontmatter correctness, markdown body reuse, wikilink generation, incremental skip
  **Spec scenarios**: obsidian-sync: Digest frontmatter, Basic export to empty vault, Incremental re-export skips unchanged, Changed content is re-exported
  **Design decisions**: D3 (reuse existing markdown generators)
  **Dependencies**: 1.2, 1.4

- [ ] 2.2 Create `src/sync/obsidian_exporter.py` — `ObsidianExporter` class with `export_digests()` method
  **Dependencies**: 2.1

- [ ] 2.3 Write tests for summary export — frontmatter with source_type/source_url, markdown body, wikilinks
  **Spec scenarios**: obsidian-sync: Summary frontmatter, Wikilinks for cross-references (Internal citation link, Multiple reference types, Unresolved reference)
  **Design decisions**: D3 (reuse generate_summary_markdown)
  **Dependencies**: 2.2

- [ ] 2.4 Add `export_summaries()` method to ObsidianExporter
  **Dependencies**: 2.3

- [ ] 2.5 Write tests for insight export — frontmatter with insight_type/confidence, markdown body
  **Spec scenarios**: obsidian-sync: Insight frontmatter
  **Dependencies**: 2.2

- [ ] 2.6 Add `export_insights()` method to ObsidianExporter
  **Dependencies**: 2.5

- [ ] 2.7 Write tests for content stub export — minimal body, backlinks to summaries, source URL
  **Spec scenarios**: obsidian-sync: Content stub frontmatter
  **Design decisions**: D5 (stubs as minimal linked notes)
  **Dependencies**: 2.2

- [ ] 2.8 Add `export_content_stubs()` method to ObsidianExporter
  **Dependencies**: 2.7

## Phase 3: Knowledge Graph Entities

- [ ] 3.1 Write tests for entity export — entity note format, relationship wikilinks, Neo4j fallback
  **Spec scenarios**: obsidian-sync: Entity frontmatter, Graceful Neo4j fallback (both scenarios)
  **Design decisions**: D4 (Neo4j driver directly, not Graphiti client)
  **Dependencies**: 2.2

- [ ] 3.2 Add `export_entities()` method to ObsidianExporter — query Neo4j entities and relationships, write entity notes
  **Dependencies**: 3.1

## Phase 4: Theme MOCs and Cross-References

- [ ] 4.1 Write tests for theme MOC generation — grouping by type, wikilink correctness, MOC frontmatter
  **Spec scenarios**: obsidian-sync: Theme Maps of Content (MOC generation, MOC frontmatter)
  **Design decisions**: D6 (MOCs as aggregated wikilink lists)
  **Dependencies**: 2.8

- [ ] 4.2 Add `export_theme_mocs()` method to ObsidianExporter — aggregate theme tags, generate MOC files
  **Dependencies**: 4.1

- [ ] 4.3 Write tests for `_build_related_section()` — ContentReference query, wikilink formatting per ref type
  **Spec scenarios**: obsidian-sync: Wikilinks for cross-references (all sub-scenarios)
  **Dependencies**: 2.2

- [ ] 4.4 Add `_build_related_section()` helper and wire into all export methods
  **Dependencies**: 4.3

## Phase 5: CLI Integration and Export Orchestration

- [ ] 5.1 Write tests for `export_all()` orchestration — calls all exporters, handles options, returns summary
  **Spec scenarios**: obsidian-sync: Basic export to empty vault, Empty content types, Vault folder structure (Standard folder layout)
  **Dependencies**: 4.2, 4.4

- [ ] 5.2 Add `export_all()` method and `ExportSummary` dataclass to ObsidianExporter
  **Dependencies**: 5.1

- [ ] 5.3 Write tests for CLI command — argument parsing, option handling, error cases
  **Spec scenarios**: obsidian-sync: Obsidian sync CLI command (all sub-scenarios), Export filtering options (all sub-scenarios)
  **Design decisions**: D7 (non-destructive by default)
  **Dependencies**: 5.2

- [ ] 5.4 Add `obsidian` command to `src/cli/sync_commands.py` — wire CLI args to ObsidianExporter
  **Dependencies**: 5.3

## Phase 6: MCP Tool Integration

- [ ] 6.1 Write tests for `sync_obsidian` MCP tool — argument handling, delegation to ObsidianExporter, error response format
  **Spec scenarios**: obsidian-sync: MCP tool for Obsidian sync (all sub-scenarios)
  **Design decisions**: D8 (MCP delegates to same ObsidianExporter)
  **Dependencies**: 5.2

- [ ] 6.2 Add `sync_obsidian` tool to `src/mcp_server.py` — lazy import, argument parsing, serialize result
  **Dependencies**: 6.1

## Phase 7: Cleanup and Polish

- [ ] 7.1 Write tests for stale file cleanup — --clean flag, generator:aca check, user-modified file warning
  **Spec scenarios**: obsidian-sync: Stale file cleanup, User-modified managed files
  **Design decisions**: D7 (non-destructive by default, --clean for cleanup)
  **Dependencies**: 5.4

- [ ] 7.2 Add cleanup logic to ObsidianExporter — stale file detection and removal with user warnings
  **Dependencies**: 7.1

- [ ] 7.3 Write tests for dry-run mode — no files written, correct output of planned actions
  **Spec scenarios**: obsidian-sync: Dry run
  **Dependencies**: 5.4

- [ ] 7.4 Add dry-run support to ObsidianExporter
  **Dependencies**: 7.3

- [ ] 7.5 Integration test: end-to-end export with sample data — verify vault structure, frontmatter, wikilinks, manifest, incremental re-export, MCP tool
  **Spec scenarios**: All scenarios (integration coverage)
  **Design decisions**: All decisions (integration verification)
  **Dependencies**: 6.2, 7.2, 7.4
