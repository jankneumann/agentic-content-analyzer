"""Contract: Settings fields for graph database provider configuration.

These fields will be added to src/config/settings.py.
"""

from __future__ import annotations

from typing import Literal

# Type definitions
GraphDBProviderType = Literal["neo4j", "falkordb"]
FalkorDBSubProviderType = Literal["local", "lite"]

# Settings fields (to be added to Settings class)
SETTINGS_FIELDS = {
    # Top-level graph backend selection (default preserves backward compat)
    "graphdb_provider": {"type": "GraphDBProviderType", "default": "neo4j"},
    # FalkorDB sub-provider variant
    "falkordb_provider": {"type": "FalkorDBSubProviderType", "default": "local"},
    # FalkorDB connection settings
    "falkordb_host": {"type": "str", "default": "localhost"},
    "falkordb_port": {"type": "int", "default": 6379},
    "falkordb_username": {"type": "str | None", "default": None},
    "falkordb_password": {"type": "str | None", "default": None},
    "falkordb_database": {"type": "str", "default": "newsletter_graph"},
    # FalkorDB Lite specific
    "falkordb_lite_data_dir": {"type": "str | None", "default": None},
}

# Profile YAML structure
PROFILE_YAML_EXAMPLE = """
providers:
  graphdb: falkordb  # or neo4j (default)

settings:
  graphdb:
    falkordb_provider: local  # or lite
    falkordb_host: ${FALKORDB_HOST:-localhost}
    falkordb_port: ${FALKORDB_PORT:-6379}
    falkordb_username: ${FALKORDB_USERNAME:-}
    falkordb_password: ${FALKORDB_PASSWORD:-}
    falkordb_database: ${FALKORDB_DATABASE:-newsletter_graph}
    falkordb_lite_data_dir: ${FALKORDB_LITE_DATA_DIR:-}
"""
