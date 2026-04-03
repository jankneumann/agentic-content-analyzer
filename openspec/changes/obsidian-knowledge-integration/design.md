# Design: Obsidian Knowledge Integration

## Selected Approach: Single-Module Exporter (Approach A)

## Architecture Overview

```
CLI Layer                    Export Layer                     Data Sources
─────────                    ────────────                     ────────────
src/cli/                     src/sync/                        
  sync_commands.py ───────►  obsidian_exporter.py ──────────► PostgreSQL (SQLAlchemy)
    obsidian() cmd             ObsidianExporter                 - digests
                                .export_all()                   - summaries
                                .export_digests()               - agent_insights
                                .export_summaries()             - content (stubs)
                                .export_insights()            
                                .export_content_stubs()       ► Neo4j (Graphiti)
                                .export_entities()               - entities
                                .export_theme_mocs()             - relationships
                              
                              obsidian_manifest.py ──────────► .obsidian-sync-manifest.json
                                SyncManifest
                                .needs_update()
                                .record()
                                .get_stale()
                              
                              obsidian_frontmatter.py ────────► YAML frontmatter generation
                                build_frontmatter()
                                slugify_filename()
```

## Design Decisions

### D1: Manifest-based incremental sync over timestamp comparison

**Decision**: Use a JSON manifest file (`.obsidian-sync-manifest.json`) in the vault root that stores content hashes rather than relying on filesystem timestamps.

**Rationale**: Filesystem timestamps are unreliable (can change due to OS indexing, backup tools, or Obsidian plugins). Content hashes (SHA-256 of the generated markdown) provide deterministic change detection. The manifest also tracks the mapping from `aca_id` to filename, enabling rename detection and stale file cleanup.

**Manifest schema**:
```json
{
  "version": 1,
  "last_sync": "2026-04-03T10:00:00Z",
  "entries": {
    "digest-42": {
      "filename": "Digests/2026-04-03-daily-ai-digest.md",
      "content_hash": "sha256:abc123...",
      "aca_type": "digest",
      "exported_at": "2026-04-03T10:00:00Z"
    }
  }
}
```

**Rejected alternative**: Git-based tracking (too heavy, assumes vault is a git repo).

### D2: Frontmatter as separate utility module

**Decision**: Extract YAML frontmatter generation and filename slugification into `src/sync/obsidian_frontmatter.py` rather than inlining in the exporter.

**Rationale**: Frontmatter generation is pure logic (dict → YAML string) that benefits from focused unit testing. Keeping it separate from the exporter (which has DB dependencies) means frontmatter tests don't need database fixtures. The slugification logic is also reusable for filename collision handling.

### D3: Reuse existing markdown generators with frontmatter prepend

**Decision**: Call `generate_digest_markdown()` and `generate_summary_markdown()` to produce the body, then prepend YAML frontmatter. Do NOT modify the existing generators.

**Rationale**: The existing generators produce well-structured markdown that's already used in the web UI and API. Modifying them to optionally include frontmatter would add conditional logic to stable code. Prepending is simple string concatenation.

### D4: Entity notes from Neo4j driver directly, not Graphiti client

**Decision**: Query Neo4j entities using the bolt driver directly (like `Neo4jExporter`) rather than the higher-level Graphiti client.

**Rationale**: The Graphiti client is optimized for semantic search and episode management, not bulk entity enumeration. The `Neo4jExporter` already demonstrates the pattern: connect via bolt, run Cypher queries, iterate results. Entity export needs `MATCH (e:Entity) RETURN e` with optional relationship traversal — simpler at the driver level.

**Fallback**: If Neo4j is unavailable, skip entity export entirely and warn the user. Other content types proceed normally.

### D5: Content stubs as minimal linked notes

**Decision**: Export raw content as minimal stub notes (title, source URL, date, backlinks to summaries) rather than full content or no notes at all.

**Rationale**: Full content would make the vault very large and duplicate what's already in digests/summaries. No notes would leave dangling wikilinks. Stubs are ~10 lines each and keep the graph connected — Obsidian's graph view shows the relationship between a summary and its source content, which is valuable for navigation.

### D6: Theme MOCs as aggregated wikilink lists

**Decision**: Generate one MOC per unique theme tag, containing grouped wikilinks to all notes with that tag.

**Rationale**: MOCs are an established Obsidian pattern for navigating large vaults. By generating them automatically from the theme tags already extracted by `extract_theme_tags()`, users get a ready-made navigation layer without manual curation. MOCs link to notes; notes link back via tags. This creates a two-way navigation path.

### D7: Non-destructive by default, --clean for cleanup

**Decision**: Never delete files unless `--clean` flag is explicitly passed. Managed files are identified by `generator: aca` in frontmatter.

**Rationale**: Users may add their own notes to the vault folders. Automatic deletion could destroy user content. The `generator: aca` frontmatter tag acts as a "this file is managed" marker. Even with `--clean`, only files with this marker AND no longer present upstream are removed.

### D8: MCP tool delegates to the same ObsidianExporter

**Decision**: The MCP tool `sync_obsidian` calls the same `ObsidianExporter.export_all()` that the CLI uses. No separate code path.

**Rationale**: The existing MCP server pattern uses lazy imports and delegates to the same service functions as the CLI (e.g., `ingest_gmail` MCP tool calls `ingest_gmail` from the orchestrator). Following this pattern means the MCP tool is a thin wrapper: parse args → create exporter → call export_all() → serialize result. This ensures CLI and MCP always produce identical output.

## Module Breakdown

### `src/sync/obsidian_frontmatter.py` (~100 lines)
- `build_frontmatter(aca_id, aca_type, date, tags, **extra) -> str`: Produce `---\n...\n---\n` YAML block
- `slugify_filename(title, date, aca_type) -> str`: Produce `YYYY-MM-DD-slugified-title.md`
- `compute_content_hash(content: str) -> str`: SHA-256 hex digest

### `src/sync/obsidian_manifest.py` (~120 lines)
- `SyncManifest` class:
  - `load(vault_path) -> SyncManifest`: Read or create manifest
  - `needs_update(aca_id, content_hash) -> bool`: Check if item needs re-export
  - `record(aca_id, filename, aca_type, content_hash)`: Update entry
  - `get_stale_entries() -> list[ManifestEntry]`: Items in manifest but not in current export set
  - `remove(aca_id)`: Remove entry
  - `save()`: Write manifest to disk

### `src/sync/obsidian_exporter.py` (~350 lines)
- `ObsidianExporter` class:
  - `__init__(engine, neo4j_driver, vault_path, options)`: Configure exporter
  - `export_all() -> ExportSummary`: Orchestrate full export
  - `export_digests() -> int`: Query + export digests
  - `export_summaries() -> int`: Query + export summaries
  - `export_insights() -> int`: Query + export insights
  - `export_content_stubs() -> int`: Query + export minimal content stubs
  - `export_entities() -> int`: Query Neo4j + export entity notes
  - `export_theme_mocs() -> int`: Aggregate themes + generate MOC files
  - `_write_note(folder, filename, content, aca_id, aca_type)`: Write file + update manifest
  - `_build_related_section(content_id) -> str`: Query ContentReference and format wikilinks

### `src/cli/sync_commands.py` (additions ~40 lines)
- `obsidian()` command function with Typer decorators
- Options: `vault_path`, `--since`, `--no-entities`, `--no-themes`, `--clean`, `--dry-run`, `--json`

## Data Flow

```
1. CLI parses args → creates SQLAlchemy engine + optional Neo4j driver
2. ObsidianExporter.__init__(engine, driver, vault_path, options)
3. SyncManifest.load(vault_path) → reads or creates manifest
4. For each content type:
   a. Query database (streaming with server-side cursor for large datasets)
   b. For each item:
      - Generate markdown body (reuse existing generators or build from model)
      - Build frontmatter (via obsidian_frontmatter)
      - Compute content hash
      - Check manifest.needs_update(aca_id, hash)
      - If needed: write file, update manifest
5. Optionally: export entities from Neo4j (graceful fallback if unavailable)
6. Generate theme MOCs from collected tags
7. If --clean: remove stale files identified by manifest
8. manifest.save()
9. Display summary (Rich table or JSON)
```
