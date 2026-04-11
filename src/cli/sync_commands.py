"""CLI commands for cross-environment database sync.

Usage:
    aca sync export [OPTIONS] OUTPUT_PATH
    aca sync import [OPTIONS] INPUT_PATH
    aca sync push --from-profile SOURCE --to-profile TARGET [OPTIONS]
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="sync",
    help="Sync data between environments (PostgreSQL, graph DB, file storage)",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _resolve_settings(profile_name: str | None = None):  # type: ignore[no-untyped-def]
    """Resolve Settings instance from profile name or active environment."""
    if profile_name:
        from src.config.settings import resolve_profile_settings

        return resolve_profile_settings(profile_name)
    else:
        from src.config.settings import get_settings

        return get_settings()


def _create_pg_engine(settings_instance):  # type: ignore[no-untyped-def]
    """Create a SQLAlchemy engine from a Settings instance."""
    from sqlalchemy import create_engine

    url = settings_instance.get_effective_database_url()
    return create_engine(url)


def _get_graph_provider():  # type: ignore[no-untyped-def]
    """Get graph provider from settings."""
    from src.storage.graph_provider import get_graph_provider

    return get_graph_provider()


def _create_neo4j_driver(settings_instance):  # type: ignore[no-untyped-def]
    """Create a Neo4j driver from a Settings instance."""
    from neo4j import GraphDatabase

    uri = settings_instance.get_effective_neo4j_uri()
    user = settings_instance.get_effective_neo4j_user()
    password = settings_instance.get_effective_neo4j_password()
    return GraphDatabase.driver(uri, auth=(user, password))


def _create_storage_providers(settings_instance, buckets=None):  # type: ignore[no-untyped-def]
    """Create storage provider dict from a Settings instance."""
    from src.services.file_storage import get_storage_for_settings

    all_buckets = buckets or ["images", "podcasts", "audio-digests"]
    return {b: get_storage_for_settings(settings_instance, bucket=b) for b in all_buckets}


@app.command("export")
def export_cmd(
    output_path: Annotated[
        Path,
        typer.Argument(help="Output JSONL file path"),
    ],
    from_profile: Annotated[
        str | None,
        typer.Option(
            "--from-profile",
            help="Source profile name (default: active profile/env)",
        ),
    ] = None,
    tables: Annotated[
        str | None,
        typer.Option(
            "--tables",
            help="Comma-separated table names to export (auto-includes FK parents)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing output file"),
    ] = False,
    pg_only: Annotated[
        bool,
        typer.Option("--pg-only", help="Export PostgreSQL data only"),
    ] = False,
    graph_only: Annotated[
        bool,
        typer.Option("--graph-only/--no-graph-only", help="Export only graph data"),
    ] = False,
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", hidden=True, help="Deprecated: use --graph-only"),
    ] = False,
) -> None:
    """Export database data to a JSONL file.

    Exports PostgreSQL tables and/or knowledge graph data
    to a JSONL file for later import into another environment.
    """
    # Combine --graph-only and deprecated --neo4j-only
    export_graph = graph_only or neo4j_only
    if neo4j_only:
        from src.config.settings import get_settings

        settings = get_settings()
        provider_type = getattr(settings, "graphdb_provider", "neo4j")
        if provider_type != "neo4j":
            logger.warning(
                "--neo4j-only is deprecated and graph provider is '%s'. Use --graph-only instead.",
                provider_type,
            )

    settings_instance = _resolve_settings(from_profile)
    table_list = [t.strip() for t in tables.split(",")] if tables else None

    do_export_pg = not export_graph
    do_export_graph = not pg_only

    if pg_only and export_graph:
        typer.echo("Error: Cannot specify both --pg-only and --graph-only.", err=True)
        raise typer.Exit(1)

    if do_export_pg:
        from src.sync.pg_exporter import PGExporter

        engine = _create_pg_engine(settings_instance)
        try:
            exporter = PGExporter(engine)
            counts = exporter.export(output_path, tables=table_list, force=force)
            total = sum(counts.values())
            typer.echo(f"PostgreSQL export: {total} rows across {len(counts)} tables")
            for tbl, cnt in counts.items():
                typer.echo(f"  {tbl}: {cnt} rows")
        finally:
            engine.dispose()

    if do_export_graph:
        graph_path = output_path.with_suffix(".graph.jsonl")
        try:
            provider = _get_graph_provider()
        except Exception as e:
            typer.echo(f"Graph connection failed (skipping): {e}", err=True)
            return

        try:
            result = provider.export_graph(graph_path, force=force)
            typer.echo(
                f"Graph export: {result.get('nodes', 0)} nodes, "
                f"{result.get('relationships', 0)} relationships"
            )
        finally:
            provider.close()


@app.command("import")
def import_cmd(
    input_path: Annotated[
        Path,
        typer.Argument(help="Input JSONL file path"),
    ],
    to_profile: Annotated[
        str | None,
        typer.Option(
            "--to-profile",
            help="Target profile name (default: active profile/env)",
        ),
    ] = None,
    tables: Annotated[
        str | None,
        typer.Option(
            "--tables",
            help="Comma-separated table names to import",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Import mode: merge (skip existing), replace (upsert), clean (truncate+insert)",
        ),
    ] = "merge",
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation for clean mode"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview import without writing data"),
    ] = False,
    pg_only: Annotated[
        bool,
        typer.Option("--pg-only", help="Import PostgreSQL data only"),
    ] = False,
    graph_only: Annotated[
        bool,
        typer.Option("--graph-only/--no-graph-only", help="Import only graph data"),
    ] = False,
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", hidden=True, help="Deprecated: use --graph-only"),
    ] = False,
) -> None:
    """Import data from a JSONL file into the target database.

    Supports three import modes:
    - merge: Skip existing rows (default, safest)
    - replace: Update existing rows, insert new ones
    - clean: Truncate all tables first, then insert (destructive!)
    """
    # Combine --graph-only and deprecated --neo4j-only
    import_graph_flag = graph_only or neo4j_only
    if neo4j_only:
        from src.config.settings import get_settings

        settings = get_settings()
        provider_type = getattr(settings, "graphdb_provider", "neo4j")
        if provider_type != "neo4j":
            logger.warning(
                "--neo4j-only is deprecated and graph provider is '%s'. Use --graph-only instead.",
                provider_type,
            )

    if not input_path.exists():
        typer.echo(f"Error: File not found: {input_path}", err=True)
        raise typer.Exit(1)

    if mode not in ("merge", "replace", "clean"):
        typer.echo(f"Error: Invalid mode '{mode}'. Use: merge, replace, clean", err=True)
        raise typer.Exit(1)

    # Clean mode confirmation
    if mode == "clean" and not yes and not dry_run:
        typer.confirm(
            "Clean mode will TRUNCATE all target tables before importing. Continue?",
            abort=True,
        )

    if dry_run:
        typer.echo("[DRY RUN] No data will be modified.")

    settings_instance = _resolve_settings(to_profile)
    table_list = [t.strip() for t in tables.split(",")] if tables else None

    do_import_pg = not import_graph_flag
    do_import_graph = not pg_only

    if pg_only and import_graph_flag:
        typer.echo("Error: Cannot specify both --pg-only and --graph-only.", err=True)
        raise typer.Exit(1)

    if do_import_pg:
        from src.sync.pg_importer import PGImporter

        engine = _create_pg_engine(settings_instance)
        try:
            importer = PGImporter(engine, mode=mode)
            stats = importer.import_file(input_path, tables=table_list, dry_run=dry_run)

            typer.echo("PostgreSQL import results:")
            for tbl, st in stats.items():
                typer.echo(
                    f"  {tbl}: inserted={st.inserted}, skipped={st.skipped}, "
                    f"updated={st.updated}, failed={st.failed}"
                )

            if importer.errors:
                typer.echo(f"\n{len(importer.errors)} errors:")
                for err in importer.errors[:10]:
                    typer.echo(f"  [{err.table}:{err.row_index}] {err.message}")
                if len(importer.errors) > 10:
                    typer.echo(f"  ... and {len(importer.errors) - 10} more")
        finally:
            engine.dispose()

    if do_import_graph:
        # Look for graph JSONL file (new naming), fall back to legacy neo4j naming
        graph_path = input_path.with_suffix(".graph.jsonl")
        if not graph_path.exists():
            graph_path = input_path.with_suffix(".neo4j.jsonl")
        if not graph_path.exists():
            # Also check if the main file contains graph records
            graph_path = input_path

        try:
            provider = _get_graph_provider()
        except Exception as e:
            typer.echo(f"Graph connection failed (skipping): {e}", err=True)
            return

        try:
            graph_stats = provider.import_graph(graph_path, mode=mode, dry_run=dry_run)

            typer.echo("Graph import results:")
            for key, value in graph_stats.items():
                typer.echo(f"  {key}: {value}")
        finally:
            provider.close()


@app.command("push")
def push_cmd(
    from_profile: Annotated[
        str,
        typer.Option("--from-profile", help="Source profile name (required)"),
    ],
    to_profile: Annotated[
        str,
        typer.Option("--to-profile", help="Target profile name (required)"),
    ],
    tables: Annotated[
        str | None,
        typer.Option(
            "--tables",
            help="Comma-separated table names to sync (auto-includes FK parents)",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Import mode: merge (skip existing), replace (upsert), clean (truncate+insert)",
        ),
    ] = "merge",
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompts"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview all sync stages without writing"),
    ] = False,
    pg_only: Annotated[
        bool,
        typer.Option("--pg-only", help="Sync PostgreSQL data only"),
    ] = False,
    graph_only: Annotated[
        bool,
        typer.Option("--graph-only/--no-graph-only", help="Sync only graph data"),
    ] = False,
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", hidden=True, help="Deprecated: use --graph-only"),
    ] = False,
    files_only: Annotated[
        bool,
        typer.Option(
            "--files-only",
            help="Sync file storage only (requires DB connection for file discovery)",
        ),
    ] = False,
    buckets: Annotated[
        str | None,
        typer.Option(
            "--buckets",
            help="Comma-separated bucket names for file sync (default: all)",
        ),
    ] = None,
) -> None:
    """Push data from one profile to another.

    Orchestrates a full sync: PG export -> file discovery -> file sync
    -> PG import -> graph export -> graph import. Both --from-profile
    and --to-profile are required.

    Re-running is safe: file sync skips existing files, merge mode
    skips existing database records.
    """
    # Combine --graph-only and deprecated --neo4j-only
    graph_only_flag = graph_only or neo4j_only
    if neo4j_only:
        from src.config.settings import get_settings

        settings = get_settings()
        provider_type = getattr(settings, "graphdb_provider", "neo4j")
        if provider_type != "neo4j":
            logger.warning(
                "--neo4j-only is deprecated and graph provider is '%s'. Use --graph-only instead.",
                provider_type,
            )

    if from_profile == to_profile:
        typer.echo("Error: Source and target profiles must be different.", err=True)
        raise typer.Exit(1)

    if mode == "clean" and not yes and not dry_run:
        typer.confirm(
            f"Clean mode will TRUNCATE all tables in '{to_profile}' before importing. Continue?",
            abort=True,
        )

    if dry_run:
        typer.echo("[DRY RUN] No data will be modified.")

    source_settings = _resolve_settings(from_profile)
    target_settings = _resolve_settings(to_profile)

    source_url = source_settings.get_effective_database_url()
    target_url = target_settings.get_effective_database_url()
    if source_url == target_url:
        typer.echo(
            "Error: Source and target profiles resolve to the same database URL. "
            "Sync requires different source and target databases.",
            err=True,
        )
        raise typer.Exit(1)

    table_list = [t.strip() for t in tables.split(",")] if tables else None
    bucket_list = [b.strip() for b in buckets.split(",")] if buckets else None

    # Determine which stages to run
    do_pg = not graph_only_flag and not files_only
    do_files = not pg_only and not graph_only_flag
    do_graph = not pg_only and not files_only

    only_flags = [pg_only, graph_only_flag, files_only]
    if sum(only_flags) > 1:
        typer.echo(
            "Error: Cannot specify more than one of --pg-only, --graph-only, --files-only.",
            err=True,
        )
        raise typer.Exit(1)

    stages_completed: list[str] = []
    temp_files: list[Path] = []

    try:
        # Stage 1: PG Export
        if do_pg:
            typer.echo(f"\n[PG Export] Exporting PostgreSQL from '{from_profile}'...")
            from src.sync.pg_exporter import PGExporter

            source_engine = _create_pg_engine(source_settings)
            try:
                fd, tmp = tempfile.mkstemp(suffix=".jsonl", prefix="sync_pg_")
                os.close(fd)
                pg_export_path = Path(tmp)
                temp_files.append(pg_export_path)
                exporter = PGExporter(source_engine)
                counts = exporter.export(pg_export_path, tables=table_list, force=True)
                total = sum(counts.values())
                typer.echo(f"  Exported {total} rows across {len(counts)} tables")
                stages_completed.append("pg_export")
            finally:
                source_engine.dispose()

        # Stage 2: File Discovery
        if do_files:
            typer.echo(f"\n[File Discovery] Discovering files from '{from_profile}'...")
            from src.sync.file_syncer import FileSyncer

            source_engine = _create_pg_engine(source_settings)
            source_storage = _create_storage_providers(source_settings, bucket_list)
            target_storage = _create_storage_providers(target_settings, bucket_list)

            # Check same-storage edge case
            if FileSyncer.check_same_storage(source_storage, target_storage):
                typer.echo("  Source and target storage are the same — skipping file sync.")
                do_files = False
            else:
                syncer = FileSyncer(source_engine, source_storage, target_storage)
                file_refs = syncer.discover_files(buckets=bucket_list)
                typer.echo(f"  Discovered {len(file_refs)} file references")
                stages_completed.append("file_discovery")

        # Stage 3: File Sync
        if do_files and file_refs:  # type: ignore[possibly-undefined]
            typer.echo(f"\n[File Sync] Syncing files to '{to_profile}'...")
            file_stats = syncer.sync_files(file_refs, dry_run=dry_run)  # type: ignore[possibly-undefined]
            typer.echo(f"  {file_stats.summary()}")
            stages_completed.append("file_sync")
            source_engine.dispose()  # type: ignore[possibly-undefined]

        # Stage 4: PG Import
        if do_pg:
            typer.echo(f"\n[PG Import] Importing PostgreSQL into '{to_profile}'...")
            from src.sync.pg_importer import PGImporter

            target_engine = _create_pg_engine(target_settings)
            try:
                importer = PGImporter(target_engine, mode=mode)
                stats = importer.import_file(
                    pg_export_path,
                    tables=table_list,
                    dry_run=dry_run,  # type: ignore[possibly-undefined]
                )
                total_inserted = sum(s.inserted for s in stats.values())
                total_skipped = sum(s.skipped for s in stats.values())
                typer.echo(f"  Inserted {total_inserted}, skipped {total_skipped}")
                stages_completed.append("pg_import")
            finally:
                target_engine.dispose()

            # Temp file tracked in temp_files list for cleanup in finally block

        # Stage 5: Graph Export
        if do_graph:
            typer.echo(f"\n[Graph Export] Exporting graph from '{from_profile}'...")
            try:
                source_provider = _get_graph_provider()
            except Exception as e:
                typer.echo(f"  Graph connection failed (skipping): {e}", err=True)
                do_graph = False

            if do_graph:
                try:
                    fd, tmp = tempfile.mkstemp(suffix=".graph.jsonl", prefix="sync_")
                    os.close(fd)
                    graph_path = Path(tmp)
                    temp_files.append(graph_path)
                    result = source_provider.export_graph(graph_path, force=True)  # type: ignore[possibly-undefined]
                    typer.echo(
                        f"  Exported {result.get('nodes', 0)} nodes, "
                        f"{result.get('relationships', 0)} relationships"
                    )
                    stages_completed.append("graph_export")
                finally:
                    source_provider.close()  # type: ignore[possibly-undefined]

        # Stage 6: Graph Import
        if do_graph:
            typer.echo(f"\n[Graph Import] Importing graph into '{to_profile}'...")
            try:
                target_provider = _get_graph_provider()
            except Exception as e:
                typer.echo(f"  Graph connection failed (skipping): {e}", err=True)
                do_graph = False

            if do_graph:
                try:
                    target_provider.import_graph(  # type: ignore[possibly-undefined]
                        graph_path,
                        mode=mode,
                        dry_run=dry_run,  # type: ignore[possibly-undefined]
                    )
                    stages_completed.append("graph_import")
                finally:
                    target_provider.close()  # type: ignore[possibly-undefined]

                # Temp file tracked in temp_files list for cleanup in finally block

    except Exception as e:
        typer.echo(f"\nSync failed at stage: {e}", err=True)
        typer.echo(f"Completed stages: {', '.join(stages_completed) or 'none'}", err=True)
        raise typer.Exit(1)
    finally:
        for tf in temp_files:
            try:
                tf.unlink(missing_ok=True)
            except OSError:
                logger.debug("Failed to clean up temp file: %s", tf)

    typer.echo(f"\nSync complete! Stages: {', '.join(stages_completed)}")


@app.command("obsidian")
def obsidian_cmd(
    vault_path: Annotated[
        Path,
        typer.Argument(help="Path to the Obsidian vault directory"),
    ],
    from_profile: Annotated[
        str | None,
        typer.Option(
            "--from-profile",
            help="Source profile name (default: active profile/env)",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Only export content dated on or after this ISO date (e.g., 2026-03-01)",
        ),
    ] = None,
    no_entities: Annotated[
        bool,
        typer.Option("--no-entities", help="Skip Neo4j entity export"),
    ] = False,
    no_themes: Annotated[
        bool,
        typer.Option("--no-themes", help="Skip theme MOC generation"),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Remove stale managed files no longer in the database"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview export without writing files"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    max_entities: Annotated[
        int,
        typer.Option("--max-entities", help="Maximum entities to export from Neo4j"),
    ] = 10000,
) -> None:
    """Export knowledge base to an Obsidian-compatible markdown vault.

    Creates markdown files with YAML frontmatter, wikilinks, and theme
    Maps of Content. Uses incremental sync to only write new or changed items.
    """
    import json as json_mod
    from datetime import UTC, datetime

    from src.sync.obsidian_exporter import (
        ExportOptions,
        ObsidianExporter,
        validate_vault_path,
    )

    # Validate vault path
    try:
        resolved_path = validate_vault_path(vault_path)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Check writability
    if resolved_path.exists() and not os.access(resolved_path, os.W_OK):
        typer.echo(f"Error: Vault path is not writable: {resolved_path}", err=True)
        raise typer.Exit(1)

    # Parse --since date
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=UTC)
        except ValueError:
            typer.echo(
                f"Error: Invalid date format: {since}. Use ISO format (e.g., 2026-03-01)", err=True
            )
            raise typer.Exit(1)

    options = ExportOptions(
        since=since_dt,
        include_entities=not no_entities,
        include_themes=not no_themes,
        clean=clean,
        dry_run=dry_run,
        max_entities=max_entities,
    )

    settings_instance = _resolve_settings(from_profile)
    engine = _create_pg_engine(settings_instance)

    # Try Neo4j connection (optional)
    neo4j_driver = None
    if not no_entities:
        try:
            neo4j_driver = _create_neo4j_driver(settings_instance)
        except Exception as e:
            print(
                f"WARNING: Neo4j unavailable; entity export skipped ({e})",
                file=__import__("sys").stderr,
            )
            options.include_entities = False

    try:
        exporter = ObsidianExporter(
            engine=engine,
            vault_path=resolved_path,
            neo4j_driver=neo4j_driver,
            options=options,
        )

        if dry_run:
            typer.echo("[DRY RUN] No files will be written.")

        summary = exporter.export_all()

        if json_output:
            typer.echo(json_mod.dumps(summary.to_dict(), indent=2))
        else:
            typer.echo(f"\nObsidian vault export to: {resolved_path}")
            typer.echo(f"{'Type':<20} {'Created':>8} {'Updated':>8} {'Skipped':>8}")
            typer.echo("-" * 48)
            for name in ("digests", "summaries", "insights", "content_stubs", "entities", "themes"):
                stats = getattr(summary, name)
                label = name.replace("_", " ").title()
                typer.echo(f"{label:<20} {stats.created:>8} {stats.updated:>8} {stats.skipped:>8}")
            if summary.cleaned > 0:
                typer.echo(f"\nCleaned {summary.cleaned} stale file(s)")
            typer.echo(f"\nCompleted in {summary.elapsed_seconds:.1f}s")

            if summary.warnings:
                for w in summary.warnings:
                    typer.echo(w, err=True)

    finally:
        engine.dispose()
        if neo4j_driver:
            neo4j_driver.close()
