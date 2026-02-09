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
    help="Sync data between environments (PostgreSQL, Neo4j, file storage)",
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
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", help="Export Neo4j data only"),
    ] = False,
) -> None:
    """Export database data to a JSONL file.

    Exports PostgreSQL tables and/or Neo4j knowledge graph data
    to a JSONL file for later import into another environment.
    """
    settings_instance = _resolve_settings(from_profile)
    table_list = [t.strip() for t in tables.split(",")] if tables else None

    export_pg = not neo4j_only
    export_neo4j = not pg_only

    if pg_only and neo4j_only:
        typer.echo("Error: Cannot specify both --pg-only and --neo4j-only.", err=True)
        raise typer.Exit(1)

    if export_pg:
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

    if export_neo4j:
        neo4j_path = output_path.with_suffix(".neo4j.jsonl")
        try:
            driver = _create_neo4j_driver(settings_instance)
        except Exception as e:
            typer.echo(f"Neo4j connection failed (skipping): {e}", err=True)
            return

        try:
            from src.sync.neo4j_exporter import Neo4jExporter

            neo4j_exporter = Neo4jExporter(driver)
            result = neo4j_exporter.export(neo4j_path, force=force)
            typer.echo(
                f"Neo4j export: {result.get('nodes', 0)} nodes, "
                f"{result.get('relationships', 0)} relationships"
            )
        finally:
            driver.close()


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
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", help="Import Neo4j data only"),
    ] = False,
) -> None:
    """Import data from a JSONL file into the target database.

    Supports three import modes:
    - merge: Skip existing rows (default, safest)
    - replace: Update existing rows, insert new ones
    - clean: Truncate all tables first, then insert (destructive!)
    """
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

    import_pg = not neo4j_only
    import_neo4j = not pg_only

    if pg_only and neo4j_only:
        typer.echo("Error: Cannot specify both --pg-only and --neo4j-only.", err=True)
        raise typer.Exit(1)

    if import_pg:
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

    if import_neo4j:
        # Look for Neo4j JSONL file
        neo4j_path = input_path.with_suffix(".neo4j.jsonl")
        if not neo4j_path.exists():
            # Also check if the main file contains Neo4j records
            neo4j_path = input_path

        try:
            driver = _create_neo4j_driver(settings_instance)
        except Exception as e:
            typer.echo(f"Neo4j connection failed (skipping): {e}", err=True)
            return

        try:
            from src.sync.neo4j_importer import Neo4jImporter

            neo4j_importer = Neo4jImporter(driver, mode=mode)
            neo4j_stats = neo4j_importer.import_file(neo4j_path, dry_run=dry_run)

            typer.echo("Neo4j import results:")
            for key, value in neo4j_stats.items():
                typer.echo(f"  {key}: {value}")
        finally:
            driver.close()


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
    neo4j_only: Annotated[
        bool,
        typer.Option("--neo4j-only", help="Sync Neo4j data only"),
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

    Orchestrates a full sync: PG export → file discovery → file sync
    → PG import → Neo4j export → Neo4j import. Both --from-profile
    and --to-profile are required.

    Re-running is safe: file sync skips existing files, merge mode
    skips existing database records.
    """
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
    do_pg = not neo4j_only and not files_only
    do_files = not pg_only and not neo4j_only
    do_neo4j = not pg_only and not files_only

    only_flags = [pg_only, neo4j_only, files_only]
    if sum(only_flags) > 1:
        typer.echo(
            "Error: Cannot specify more than one of --pg-only, --neo4j-only, --files-only.",
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

        # Stage 5: Neo4j Export
        if do_neo4j:
            typer.echo(f"\n[Neo4j Export] Exporting Neo4j from '{from_profile}'...")
            try:
                source_driver = _create_neo4j_driver(source_settings)
            except Exception as e:
                typer.echo(f"  Neo4j connection failed (skipping): {e}", err=True)
                do_neo4j = False

            if do_neo4j:
                try:
                    from src.sync.neo4j_exporter import Neo4jExporter

                    fd, tmp = tempfile.mkstemp(suffix=".neo4j.jsonl", prefix="sync_")
                    os.close(fd)
                    neo4j_path = Path(tmp)
                    temp_files.append(neo4j_path)
                    neo4j_exporter = Neo4jExporter(source_driver)  # type: ignore[possibly-undefined]
                    result = neo4j_exporter.export(neo4j_path, force=True)
                    typer.echo(
                        f"  Exported {result.get('nodes', 0)} nodes, "
                        f"{result.get('relationships', 0)} relationships"
                    )
                    stages_completed.append("neo4j_export")
                finally:
                    source_driver.close()  # type: ignore[possibly-undefined]

        # Stage 6: Neo4j Import
        if do_neo4j:
            typer.echo(f"\n[Neo4j Import] Importing Neo4j into '{to_profile}'...")
            try:
                target_driver = _create_neo4j_driver(target_settings)
            except Exception as e:
                typer.echo(f"  Neo4j connection failed (skipping): {e}", err=True)
                do_neo4j = False

            if do_neo4j:
                try:
                    from src.sync.neo4j_importer import Neo4jImporter

                    neo4j_importer = Neo4jImporter(target_driver, mode=mode)  # type: ignore[possibly-undefined]
                    neo4j_importer.import_file(neo4j_path, dry_run=dry_run)  # type: ignore[possibly-undefined]
                    stages_completed.append("neo4j_import")
                finally:
                    target_driver.close()  # type: ignore[possibly-undefined]

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
