"""Compatibility import for the canonical ingestion command group."""

from src.cli.workflow_commands import ingest_app as app

__all__ = ["app"]
