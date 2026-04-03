# Proposal: Obsidian Knowledge Integration

## Status: PROPOSED

## Why

Users of the newsletter aggregator accumulate a rich knowledge base — digests, summaries, agent insights, entity graphs — but currently browse it only through the web UI or CLI queries. Obsidian is a popular, mature knowledge management tool with powerful features (graph view, backlinks, tags, search, canvas) that would be expensive to replicate. By exporting the aggregator's knowledge base as an Obsidian-compatible vault, users get:

1. **Offline, local-first access** to their entire knowledge base
2. **Graph visualization** of entity relationships and content citations for free
3. **Personal annotation** — users can add their own notes alongside curated content
4. **Advanced search** — Obsidian's full-text + tag + link search across all knowledge
5. **Plugin ecosystem** — Dataview, Canvas, Templater, etc. extend functionality without dev work

## What Changes

Add an `aca sync obsidian <vault-path>` CLI command that exports the aggregator's knowledge base as a folder of Obsidian-compatible markdown files with YAML frontmatter, wikilinks, and theme-based Maps of Content.

### Content Scope
- **Processed outputs**: Digests, summaries, and agent insights as full notes
- **Raw content stubs**: Minimal placeholder notes for source content (title, source URL, date, backlink) so the graph stays connected without bloating the vault
- **Knowledge graph entities**: Neo4j entities exported as linked notes in an Entities/ folder
- **Theme MOCs**: Auto-generated Map of Content files per theme linking all related notes

### Sync Behavior
- **Incremental with manifest**: A `.obsidian-sync-manifest.json` file in the vault root tracks content hashes and timestamps. On re-run, only new or changed items are written. Deleted upstream items are optionally removed.
- **Non-destructive**: User-created files in the vault are never touched. Only files with a `generator: aca` frontmatter field are managed.

### Vault Structure
```
<vault-path>/
├── .obsidian-sync-manifest.json    # Sync state tracking
├── Digests/
│   ├── 2026-04-03-daily-ai-digest.md
│   └── 2026-03-30-weekly-ai-digest.md
├── Summaries/
│   ├── 2026-04-03-newsletter-title.md
│   └── ...
├── Insights/
│   ├── 2026-04-01-trend-ai-adoption.md
│   └── ...
├── Content/
│   ├── 2026-04-02-original-article-stub.md    # Minimal stubs
│   └── ...
├── Entities/
│   ├── OpenAI.md
│   ├── Transformer-Architecture.md
│   └── ...
└── Themes/
    ├── MOC - Large Language Models.md
    ├── MOC - AI Safety.md
    └── ...
```

### File Format
Each file gets YAML frontmatter + markdown body + wikilinks:
```yaml
---
generator: aca
aca_id: "digest-42"
aca_type: digest
date: 2026-04-03
tags: [ai, transformers, llm]
sources: ["[[2026-04-03-newsletter-a]]", "[[2026-04-03-newsletter-b]]"]
content_hash: "sha256:abc123..."
---
# Daily AI Digest — 2026-04-03

## Executive Overview
...

## Related
- Extends: [[2026-03-30-weekly-ai-digest]]
- Cites: [[2026-04-02-original-paper]]
```

### CLI Interface
```bash
# Full export
aca sync obsidian ./my-vault

# With options
aca sync obsidian ./my-vault --since 2026-03-01 --exclude entities --dry-run
aca sync obsidian ./my-vault --clean  # Remove stale managed files
aca sync obsidian ./my-vault --no-entities --no-themes  # Skip optional sections
```

## Approaches Considered

### Approach A: Single-Module Exporter (Recommended) ★

Add a single `src/sync/obsidian_exporter.py` module containing an `ObsidianExporter` class that queries the database and Neo4j, generates markdown files with frontmatter, and writes them to the vault path. Register it as the `aca sync obsidian` command in `src/cli/sync_commands.py`.

**How it works**: One class with methods for each content type (`export_digests()`, `export_summaries()`, `export_insights()`, `export_content_stubs()`, `export_entities()`, `export_theme_mocs()`). Reuses existing `generate_digest_markdown()` and `generate_summary_markdown()` utilities, prepending YAML frontmatter. Manifest tracking in a simple JSON file.

**Pros:**
- Follows the existing `PGExporter` / `Neo4jExporter` pattern exactly
- Single file to understand, test, and maintain
- Reuses all existing markdown generation utilities
- Easy to add new content types later

**Cons:**
- File may grow large as content types are added
- Tight coupling between vault structure decisions and export logic

**Effort:** M

### Approach B: Strategy-per-Content-Type Pattern

Create an abstract `VaultNoteStrategy` base class with concrete implementations per content type (`DigestStrategy`, `SummaryStrategy`, `InsightStrategy`, `EntityStrategy`). An `ObsidianVaultWriter` orchestrates strategies and manages the manifest.

**How it works**: Each strategy knows how to query its data source, generate frontmatter, convert to markdown, and produce wikilinks. The writer iterates strategies, calls `export()` on each, and updates the manifest.

**Pros:**
- Clean separation of concerns per content type
- Easy to add new content types without modifying existing code
- Each strategy is independently testable

**Cons:**
- More files and abstractions for a feature that may not grow much
- Over-engineered for the current 5-6 content types
- Doesn't match the simpler patterns used elsewhere in the sync module

**Effort:** L

### Approach C: Template-Driven Export

Use Jinja2 templates for each note type. Store templates in `settings/obsidian/` as `.md.j2` files. A lightweight exporter loads templates, queries data, and renders files.

**How it works**: Each template defines the frontmatter and body structure. Data is queried and passed as context to the template engine. Users can customize templates to change vault output format.

**Pros:**
- Users can customize output format without code changes
- Templates are easy to understand and modify
- Separation of data from presentation

**Cons:**
- Adds Jinja2 dependency (or requires building a mini-template system)
- Wikilink generation still needs code — can't fully live in templates
- Template debugging is harder than Python code
- Existing markdown generators don't use templates — inconsistent pattern

**Effort:** M

### Selected Approach

**Approach A: Single-Module Exporter** is recommended because it directly follows the established `PGExporter`/`Neo4jExporter` pattern, minimizes new abstractions, and reuses the existing markdown utilities. The vault structure is well-defined enough that a single module with clear methods per content type is maintainable and testable.

### MCP Tool
Expose the export as an MCP tool (`sync_obsidian`) so the analytics agent and other MCP clients can trigger vault exports programmatically:
```python
@mcp.tool()
def sync_obsidian(vault_path: str, since: str | None = None, ...) -> str:
    """Export knowledge base to an Obsidian vault."""
```

## Out of Scope

- **Obsidian plugin**: No custom plugin — just markdown files that Obsidian reads natively
- **Two-way sync**: Notes created in Obsidian are not ingested back (use `aca ingest files` for that)
- **Obsidian settings**: No `.obsidian/` config folder management — users configure Obsidian themselves
- **Real-time sync**: This is a batch CLI command, not a daemon or file watcher
- **Canvas/Dataview**: No auto-generated Canvas files or Dataview queries (users can add these)

## Risks

| Risk | Mitigation |
|------|------------|
| Large vaults (10k+ notes) slow Obsidian | Exclude raw content by default; stubs are tiny |
| Neo4j unavailable during export | Graceful fallback — skip entities, warn user |
| Wikilink targets may not exist yet | Forward-link is fine in Obsidian — unresolved links show as suggestions |
| Filename collisions (same date + title) | Append content ID suffix when collision detected |
| User modifies managed files | Overwrite only files with `generator: aca` frontmatter; warn on hash mismatch |
