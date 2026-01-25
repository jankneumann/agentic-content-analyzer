"""Data migration scripts for the unified content model.

Scripts:
- migrate_summaries_markdown.py: Populate markdown_content and theme_tags for summaries
- migrate_digests_markdown.py: Populate markdown_content, theme_tags, and source_content_ids for digests

Usage:
    # Dry run to validate without making changes
    python -m src.scripts.migrate_summaries_markdown --dry-run
    python -m src.scripts.migrate_digests_markdown --dry-run

    # Full migration (run in order)
    python -m src.scripts.migrate_summaries_markdown
    python -m src.scripts.migrate_digests_markdown
    python -m src.scripts.migrate_digests_markdown --link-content-ids

    # Rollback if needed
    python -m src.scripts.migrate_summaries_markdown --rollback
    python -m src.scripts.migrate_digests_markdown --rollback
"""
