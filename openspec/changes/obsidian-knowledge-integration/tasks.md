# Tasks: Obsidian Knowledge Integration

## Phase 1: Core Infrastructure (Frontmatter + Manifest + Path Validation)

- [ ] 1.1 Write tests for obsidian_frontmatter module — frontmatter generation, slugification, content hashing, tag sanitization
  **Spec scenarios**: obsidian-sync: YAML frontmatter (all sub-scenarios incl. Content hash format, Tag sanitization), Date-prefixed file naming (all sub-scenarios incl. Filename collision)
  **Design decisions**: D2 (frontmatter as separate utility), D3 (prepend, don't modify generators), D10 (tag sanitization)
  **Dependencies**: None

- [ ] 1.2 Create `src/sync/obsidian_frontmatter.py` — `build_frontmatter()`, `slugify_filename()`, `compute_content_hash()`, `sanitize_tag()`
  **Dependencies**: 1.1

- [ ] 1.3 Write tests for obsidian_manifest module — load/save, needs_update, stale detection, collision tracking, corrupt manifest recovery, atomic writes
  **Spec scenarios**: obsidian-sync: Incremental sync with manifest (all sub-scenarios incl. Corrupt manifest recovery, Atomic manifest writes)
  **Design decisions**: D1 (manifest-based sync), D9 (atomic writes with corruption recovery)
  **Dependencies**: None

- [ ] 1.4 Create `src/sync/obsidian_manifest.py` — `SyncManifest` class with load, needs_update, record, get_stale_entries, save (atomic via tempfile + os.replace)
  **Dependencies**: 1.3

- [ ] 1.5 Write tests for vault path validation — symlink rejection, traversal rejection, non-writable path, creation of new directory
  **Spec scenarios**: obsidian-sync: Vault path safety validation, Invalid vault path
  **Design decisions**: D8 (vault path safety)
  **Dependencies**: None

- [ ] 1.6 Create `validate_vault_path()` in `src/sync/obsidian_exporter.py` — resolve, check safety, reject symlinks/traversal
  **Dependencies**: 1.5

## Phase 2: Related Section Helper (moved up — depended on by all exporters)

- [ ] 2.1 Write tests for `_build_related_section()` — ContentReference query, wikilink formatting per ref type, external URL fallback, no-refs case
  **Spec scenarios**: obsidian-sync: Related section with wikilinks (all sub-scenarios: Related section generation, Internal citation link, Multiple reference types, External reference, Unresolved reference, No references exist)
  **Dependencies**: 1.2

- [ ] 2.2 Add `_build_related_section()` helper to `src/sync/obsidian_exporter.py`
  **Dependencies**: 2.1, 1.6

## Phase 3: Content Exporters (Digests, Summaries, Insights, Stubs)

- [ ] 3.1 Write tests for digest export — frontmatter correctness, markdown body reuse, related section, incremental skip, streaming query
  **Spec scenarios**: obsidian-sync: Digest frontmatter, Basic export to empty vault, Incremental re-export skips unchanged, Changed content is re-exported, Streaming database queries
  **Design decisions**: D3 (reuse existing markdown generators), D11 (streaming queries)
  **Dependencies**: 2.2, 1.4

- [ ] 3.2 Add `export_digests()` method to ObsidianExporter — query with yield_per(500), generate markdown, prepend frontmatter, append related section
  **Dependencies**: 3.1

- [ ] 3.3 Write tests for summary export — frontmatter with source_type/source_url, markdown body, related section
  **Spec scenarios**: obsidian-sync: Summary frontmatter
  **Design decisions**: D3 (reuse generate_summary_markdown)
  **Dependencies**: 3.2

- [ ] 3.4 Add `export_summaries()` method to ObsidianExporter
  **Dependencies**: 3.3

- [ ] 3.5 Write tests for insight export — frontmatter with insight_type/confidence, markdown body
  **Spec scenarios**: obsidian-sync: Insight frontmatter
  **Dependencies**: 3.2

- [ ] 3.6 Add `export_insights()` method to ObsidianExporter
  **Dependencies**: 3.5

- [ ] 3.7 Write tests for content stub export — minimal body, backlinks to summaries, source URL
  **Spec scenarios**: obsidian-sync: Content stub frontmatter
  **Design decisions**: D5 (stubs as minimal linked notes)
  **Dependencies**: 3.2

- [ ] 3.8 Add `export_content_stubs()` method to ObsidianExporter
  **Dependencies**: 3.7

## Phase 4: Knowledge Graph Entities (parallel with Phase 3 after 2.2)

- [ ] 4.1 Write tests for entity export — entity note format, relationship wikilinks, Neo4j fallback, entity limit
  **Spec scenarios**: obsidian-sync: Entity frontmatter, Graceful Neo4j fallback (both scenarios)
  **Design decisions**: D4 (Neo4j driver directly), D13 (LIMIT on entity queries)
  **Dependencies**: 2.2, 1.4

- [ ] 4.2 Add `export_entities()` method to ObsidianExporter — query Neo4j with LIMIT, write entity notes with Relationships and Facts sections
  **Dependencies**: 4.1

## Phase 5: Theme MOCs

- [ ] 5.1 Write tests for theme MOC generation — grouping by type, wikilink correctness, MOC frontmatter, empty themes
  **Spec scenarios**: obsidian-sync: Theme Maps of Content (MOC generation, MOC frontmatter), Empty content types
  **Design decisions**: D6 (MOCs as aggregated wikilink lists)
  **Dependencies**: 3.8

- [ ] 5.2 Add `export_theme_mocs()` method to ObsidianExporter — aggregate theme tags from all exported notes, generate MOC files
  **Dependencies**: 5.1

## Phase 6: CLI Integration and Export Orchestration

- [ ] 6.1 Write tests for `ExportSummary` dataclass and `export_all()` orchestration — calls all exporters, handles options, returns summary, structured logging
  **Spec scenarios**: obsidian-sync: Basic export to empty vault, Empty content types, Vault folder structure, Structured logging (both scenarios), Export with Rich output, Export with JSON output
  **Design decisions**: D7 (non-destructive by default)
  **Dependencies**: 5.2, 4.2

- [ ] 6.2 Add `export_all()` method, `ExportSummary` dataclass, and structured logging to ObsidianExporter
  **Dependencies**: 6.1

- [ ] 6.3 Write tests for CLI command — argument parsing, option handling, --since date filter, --no-entities, --no-themes, error cases, path validation
  **Spec scenarios**: obsidian-sync: Obsidian sync CLI command (all sub-scenarios), Export filtering options (all sub-scenarios incl. --since scope clarification)
  **Dependencies**: 6.2

- [ ] 6.4 Add `obsidian` command to `src/cli/sync_commands.py` — wire CLI args to ObsidianExporter
  **Dependencies**: 6.3

## Phase 7: MCP Tool Integration (parallel with Phase 6 after 6.2)

- [ ] 7.1 Write tests for `sync_obsidian` MCP tool — argument handling, delegation to ObsidianExporter, JSON result schema, error response format
  **Spec scenarios**: obsidian-sync: MCP tool for Obsidian sync (all sub-scenarios)
  **Design decisions**: D12 (MCP delegates to same ObsidianExporter)
  **Dependencies**: 6.2

- [ ] 7.2 Add `sync_obsidian` tool to `src/mcp_server.py` — lazy import, argument parsing, serialize result
  **Dependencies**: 7.1

## Phase 8: Cleanup, Dry-Run, and Integration Tests

- [ ] 8.1 Write tests for stale file cleanup — --clean flag, generator:aca check, user-modified file warning
  **Spec scenarios**: obsidian-sync: Stale file cleanup, User-modified managed files
  **Design decisions**: D7 (non-destructive by default, --clean for cleanup)
  **Dependencies**: 6.4

- [ ] 8.2 Add cleanup logic to ObsidianExporter — stale file detection and removal with user warnings
  **Dependencies**: 8.1

- [ ] 8.3 Write tests for dry-run mode — no files written, correct output of planned actions
  **Spec scenarios**: obsidian-sync: Dry run
  **Dependencies**: 6.4

- [ ] 8.4 Add dry-run support to ObsidianExporter
  **Dependencies**: 8.3

- [ ] 8.5 Integration test: end-to-end export with sample data — verify vault structure, frontmatter, wikilinks, manifest, incremental re-export, MCP tool, path validation, streaming queries
  **Spec scenarios**: All scenarios (integration coverage)
  **Design decisions**: All decisions (integration verification)
  **Dependencies**: 7.2, 8.2, 8.4
