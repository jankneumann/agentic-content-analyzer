# Design: Add FalkorDB Graph Provider

## Selected Approach

**Approach 1: Graphiti Driver Delegation** — leverage graphiti-core's built-in `GraphDriver` abstraction (`Neo4jDriver`, `FalkorDriver`) as the primary switching mechanism. Build a thin `GraphDBProvider` protocol that wraps driver construction, raw query execution, and export/import operations.

## Architecture Overview

```
Settings (graphdb_provider)
    │
    ▼
GraphDBProviderFactory
    ├── Neo4jGraphDBProvider
    │     ├── Neo4jDriver (from graphiti_core)
    │     └── neo4j.GraphDatabase.driver (for raw Cypher)
    └── FalkorDBGraphDBProvider
          ├── FalkorDriver (from graphiti_core)
          └── falkordb.FalkorDB client (for raw queries)
```

## Key Design Decisions

### D1: GraphDBProvider Protocol — Thin Wrapper Over graphiti-core Drivers

The `GraphDBProvider` protocol defines three responsibilities:

```python
class GraphDBProvider(Protocol):
    # 1. Construct a graphiti-core GraphDriver for the Graphiti() constructor
    def create_graphiti_driver(self) -> GraphDriver: ...

    # 2. Execute raw graph queries (for reference_graph_sync, export/import)
    async def execute_query(self, query: str, params: dict) -> list[dict]: ...
    async def execute_write(self, query: str, params: dict) -> dict: ...

    # 3. Lifecycle
    async def close(self) -> None: ...
    async def health_check(self) -> bool: ...

    # 4. Export/Import operations
    def create_exporter(self) -> GraphExporter: ...
    def create_importer(self, mode: str) -> GraphImporter: ...
```

**Why:** We need raw query execution because `reference_graph_sync.py` and the exporters use Cypher directly, not Graphiti's API. Both Neo4j and FalkorDB speak openCypher, so the same queries work on both — but the driver/session management differs.

**How to apply:** `GraphitiClient.__init__` calls `provider.create_graphiti_driver()` and passes it to `Graphiti(graph_driver=...)`. Raw-query callers use `provider.execute_query()`.

### D2: Settings Structure — graphdb_provider with Sub-Variants

```python
GraphDBProviderType = Literal["neo4j", "falkordb"]

# Settings fields
graphdb_provider: GraphDBProviderType = "neo4j"  # Top-level backend selection

# Neo4j sub-variants (existing, renamed from neo4j_provider)
neo4j_provider: Neo4jSubProviderType = "local"  # "local" | "auradb"

# FalkorDB sub-variants (new)
falkordb_provider: FalkorDBSubProviderType = "local"  # "local" | "lite"
falkordb_host: str = "localhost"
falkordb_port: int = 6379
falkordb_username: str | None = None
falkordb_password: str | None = None
falkordb_database: str = "newsletter_graph"

# FalkorDB Lite specific
falkordb_lite_data_dir: str | None = None  # File-based storage path
```

**Why:** Two-level provider selection mirrors the existing `neo4j_provider: "local" | "auradb"` pattern. The top-level `graphdb_provider` selects the backend (Neo4j vs FalkorDB), then sub-provider selects deployment mode.

**How to apply:** `get_effective_*()` methods on Settings route to the correct sub-variant. Factory uses `graphdb_provider` to construct the right `GraphDBProvider` implementation.

### D3: Backward Compatibility — neo4j_provider Preserved as Sub-Provider

The existing `neo4j_provider` setting continues to work. If `graphdb_provider` is not set (defaults to `"neo4j"`), behavior is identical to today. The `get_effective_neo4j_*()` methods remain but are now called internally by `Neo4jGraphDBProvider`.

**Why:** Zero-disruption upgrade path. Existing profiles, .env files, and documentation continue to work.

**How to apply:** `neo4j_provider` becomes a sub-provider under `graphdb_provider: "neo4j"`. Migration is purely additive — no renaming, no removal.

### D4: FalkorDB Lite for Test Fixtures

FalkorDB Lite runs as an embedded subprocess with file-based storage — no Docker required. Test fixtures create an ephemeral FalkorDB Lite instance per test session.

```python
# tests/helpers/falkordb_lite.py
class FalkorDBLiteFixture:
    """Manage embedded FalkorDB for testing."""
    def start(self, data_dir: Path) -> tuple[str, int]:  # returns (host, port)
    def stop(self) -> None:
    def reset(self) -> None:  # clear all data between tests
```

**Why:** Mirrors the coordinator's embedded-process-for-testing / Docker-for-E2E pattern that the user validated. Unit and integration tests get a fast, isolated graph backend. E2E tests use Docker FalkorDB for production fidelity.

**How to apply:** Session-scoped pytest fixture starts FalkorDB Lite, function-scoped fixture resets data. Test profiles set `graphdb_provider: falkordb`, `falkordb_provider: lite`.

### D5: GraphitiClient Refactoring — Constructor Takes Provider

```python
# Before (current)
class GraphitiClient:
    def __init__(self, neo4j_uri="", neo4j_user="", neo4j_password="", ...):
        self.driver = GraphDatabase.driver(uri, auth=(...))
        self.graphiti = Graphiti(uri, user, password, ...)

# After (new)
class GraphitiClient:
    def __init__(self, provider: GraphDBProvider | None = None, ...):
        self.provider = provider or get_graph_provider()
        graph_driver = self.provider.create_graphiti_driver()
        self.graphiti = Graphiti(graph_driver=graph_driver, ...)
```

**Why:** The `Graphiti()` constructor in v0.28 accepts `graph_driver` instead of raw credentials. Our `GraphitiClient` wraps this with the provider pattern for raw query access.

**How to apply:** All callers that construct `GraphitiClient()` without arguments continue to work — `get_graph_provider()` reads settings and constructs the default provider. Callers that pass explicit credentials (tests, sync commands) pass a provider instead.

### D6: Export/Import Abstraction — GraphExporter/GraphImporter Protocols

```python
class GraphExporter(Protocol):
    async def export_nodes(self, label: str) -> AsyncIterator[NodeRecord]: ...
    async def export_relationships(self, rel_type: str) -> AsyncIterator[RelationshipRecord]: ...
    async def count_nodes(self, label: str) -> int: ...
    async def count_relationships(self, rel_type: str) -> int: ...

class GraphImporter(Protocol):
    async def import_node(self, record: NodeRecord) -> str: ...
    async def import_relationship(self, record: RelationshipRecord) -> str: ...
    async def delete_all(self) -> tuple[int, int]: ...  # (nodes, rels)
```

**Why:** The existing `Neo4jExporter`/`Neo4jImporter` use raw Cypher. FalkorDB speaks openCypher, so the queries are likely compatible — but session management and transaction handling differ. The protocol lets each backend handle these differences.

**How to apply:** Rename existing data models from `Neo4jNodeRecord` → `NodeRecord` etc. The JSONL format stays the same — it's the backend that changes, not the serialization.

### D7: Raw Cypher Compatibility Assessment

All 14 raw Cypher queries in the codebase use basic openCypher patterns:
- `MATCH (n:Label) WHERE ... RETURN ...`
- `MERGE (n:Label {uuid: $uuid}) ON CREATE SET ... ON MATCH SET ...`
- `MATCH (a)-[r:TYPE]->(b) ...`
- `DELETE`, `SET`, `ORDER BY`, `LIMIT`
- Functions: `count()`, `toLower()`, `CONTAINS`, `datetime()`

FalkorDB supports the openCypher subset. The only potential issue is `datetime()` — FalkorDB may not support Neo4j's built-in `datetime()` function. Mitigation: pass ISO-8601 strings and store as string properties rather than native datetime types.

**How to apply:** Audit each query during implementation. Queries that use Neo4j-specific functions get a compatibility shim in the FalkorDB provider.

### D8: graphiti-core Upgrade Strategy

The version jump from `>=0.5.0` to `>=0.28.0` involves these breaking changes:

1. **Constructor signature**: `Graphiti(uri, user, password)` → `Graphiti(graph_driver=driver)`
2. **Driver operations redesign**: Low-level queries moved to `driver.search_ops`, `driver.entity_node_ops`, etc.
3. **NodeNamespace/EdgeNamespace**: New pattern for accessing graph data
4. **`build_indices_and_constraints()`**: Must be called after initialization
5. **Pip extras**: `[anthropic,google-genai]` → `[neo4j,falkordb,anthropic,google-genai]`

**How to apply:** Phase 1 of tasks handles the upgrade with Neo4j-only to validate no regressions, Phase 2 adds FalkorDB.

## Component Diagram

```
┌─────────────────────────────────────────────────┐
│                   Settings                       │
│  graphdb_provider: "neo4j" | "falkordb"         │
│  neo4j_provider: "local" | "auradb"             │
│  falkordb_provider: "local" | "lite"            │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────▼────────┐
              │ GraphDBProvider  │ (Protocol)
              │   Factory       │
              └───┬─────────┬───┘
                  │         │
     ┌────────────▼──┐  ┌──▼─────────────┐
     │Neo4jGraphDB   │  │FalkorDBGraphDB │
     │Provider       │  │Provider        │
     │               │  │                │
     │ Neo4jDriver   │  │ FalkorDriver   │
     │ (graphiti)    │  │ (graphiti)     │
     │               │  │                │
     │ neo4j.Driver  │  │ falkordb.      │
     │ (raw queries) │  │ FalkorDB       │
     └───────┬───────┘  └───────┬────────┘
             │                  │
     ┌───────▼──────────────────▼────────┐
     │         GraphitiClient            │
     │   (provider.create_graphiti_      │
     │    driver() → Graphiti())         │
     ├───────────────────────────────────┤
     │  ReferenceGraphSync               │
     │   (provider.execute_query())      │
     ├───────────────────────────────────┤
     │  GraphExporter / GraphImporter    │
     │   (provider.create_exporter())    │
     └──────────────────────────────────┘
```

## File Changes Summary

| File | Change |
|------|--------|
| `src/storage/graph_provider.py` | **NEW** — GraphDBProvider protocol, Neo4j + FalkorDB implementations, factory |
| `src/storage/graph_export.py` | **NEW** — GraphExporter/GraphImporter protocols, NodeRecord, RelationshipRecord |
| `src/storage/graphiti_client.py` | **MODIFY** — Use provider instead of direct Neo4j driver |
| `src/services/reference_graph_sync.py` | **MODIFY** — Use provider.execute_query() instead of driver.session() |
| `src/sync/neo4j_exporter.py` | **MODIFY** → Refactor to use GraphExporter protocol |
| `src/sync/neo4j_importer.py` | **MODIFY** → Refactor to use GraphImporter protocol |
| `src/sync/graph_exporter.py` | **NEW** — Generic exporter using GraphExporter protocol |
| `src/sync/graph_importer.py` | **NEW** — Generic importer using GraphImporter protocol |
| `src/config/settings.py` | **MODIFY** — Add graphdb_provider, falkordb_* fields |
| `src/config/profiles.py` | **MODIFY** — Add GraphDBProviderType, FalkorDBSubProviderType |
| `src/cli/sync_commands.py` | **MODIFY** — Use provider instead of direct Neo4j driver |
| `docker-compose.yml` | **MODIFY** — Add FalkorDB service |
| `pyproject.toml` | **MODIFY** — Upgrade graphiti-core, add falkordb extra |
| `tests/helpers/falkordb_lite.py` | **NEW** — FalkorDB Lite test fixture |
| `profiles/*.yaml` | **MODIFY** — Add graphdb_provider settings |
