"""Contract: Settings fields for graph database provider configuration.

These fields will be added to src/config/settings.py.
Orthogonal model: provider (what backend) x mode (how deployed).
"""

from __future__ import annotations

from typing import Literal

# Type definitions
GraphDBProviderType = Literal["neo4j", "falkordb"]
GraphDBModeType = Literal["local", "cloud", "embedded"]

# Settings fields (to be added to Settings class)
SETTINGS_FIELDS = {
    # Orthogonal axes
    "graphdb_provider": {"type": "GraphDBProviderType", "default": "neo4j"},
    "graphdb_mode": {"type": "GraphDBModeType", "default": "local"},
    # Neo4j local connection
    "neo4j_uri": {"type": "str", "default": "bolt://localhost:7687"},
    "neo4j_user": {"type": "str", "default": "neo4j"},
    "neo4j_password": {"type": "str", "default": "newsletter_password"},
    # Neo4j cloud connection (AuraDB etc.)
    "neo4j_cloud_uri": {"type": "str | None", "default": None},
    "neo4j_cloud_user": {"type": "str", "default": "neo4j"},
    "neo4j_cloud_password": {"type": "str | None", "default": None},
    # FalkorDB local connection (Docker)
    "falkordb_host": {"type": "str", "default": "localhost"},
    "falkordb_port": {"type": "int", "default": 6379},
    "falkordb_username": {"type": "str | None", "default": None},
    "falkordb_password": {"type": "str | None", "default": None},
    "falkordb_database": {"type": "str", "default": "newsletter_graph"},
    # FalkorDB cloud connection (Railway etc.)
    "falkordb_cloud_host": {"type": "str | None", "default": None},
    "falkordb_cloud_port": {"type": "int", "default": 6379},
    "falkordb_cloud_password": {"type": "str | None", "default": None},
    # FalkorDB embedded (Lite)
    "falkordb_lite_data_dir": {"type": "str | None", "default": None},
}

# Valid combinations
VALID_COMBINATIONS = {
    ("neo4j", "local"),
    ("neo4j", "cloud"),
    # ("neo4j", "embedded") — INVALID, rejected by validator
    ("falkordb", "local"),
    ("falkordb", "cloud"),
    ("falkordb", "embedded"),
}

# Deprecated alias mapping (old → new)
DEPRECATED_ALIASES = {
    "neo4j_provider": {
        "local": {"graphdb_provider": "neo4j", "graphdb_mode": "local"},
        "auradb": {"graphdb_provider": "neo4j", "graphdb_mode": "cloud"},
    },
    "neo4j_auradb_uri": "neo4j_cloud_uri",
    "neo4j_auradb_user": "neo4j_cloud_user",
    "neo4j_auradb_password": "neo4j_cloud_password",
    "neo4j_local_uri": "neo4j_uri",
    "neo4j_local_user": "neo4j_user",
    "neo4j_local_password": "neo4j_password",
}

# Profile YAML structure
PROFILE_YAML_EXAMPLE = """
providers:
  graphdb: falkordb  # or neo4j (default)

settings:
  graphdb:
    graphdb_mode: local  # or cloud, embedded
    falkordb_host: ${FALKORDB_HOST:-localhost}
    falkordb_port: ${FALKORDB_PORT:-6379}
    falkordb_username: ${FALKORDB_USERNAME:-}
    falkordb_password: ${FALKORDB_PASSWORD:-}
    falkordb_database: ${FALKORDB_DATABASE:-newsletter_graph}
"""
