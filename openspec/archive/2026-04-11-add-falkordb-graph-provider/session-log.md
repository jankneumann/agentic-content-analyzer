## Phase: Plan (2026-04-03)

**Agent**: claude-opus-4-6 | **Session**: plan-feature

### Decisions
1. **Graphiti Driver Delegation approach** — leverage graphiti-core's built-in GraphDriver abstraction (FalkorDriver, Neo4jDriver) rather than building a fully custom graph abstraction. Minimizes custom code while achieving full backend portability.
2. **Full abstraction scope** — abstract all graph DB access including Graphiti client, reference_graph_sync, and export/import (not just the Graphiti layer). User confirmed this over partial abstraction.
3. **Both deployment modes for FalkorDB** — Docker container for E2E/production, FalkorDB Lite (embedded) for test fixtures. Mirrors the coordinator's embedded-for-testing/Docker-for-E2E pattern already proven in the project.
4. **Bundle graphiti-core upgrade with FalkorDB** — upgrade from >=0.5.0 to >=0.28.0 in the same proposal since the driver API change is a prerequisite for FalkorDB support.
5. **Neo4j + FalkorDB only** — no Kuzu or Neptune support in initial scope. graphiti-core's driver abstraction makes adding backends easy later.

### Alternatives Considered
- Full Custom Abstraction: rejected because it duplicates abstractions graphiti-core already provides, significantly more code to maintain
- Configuration-Only Switch: rejected because it doesn't abstract raw Cypher in reference_graph_sync/exporters, doesn't meet full abstraction goal
- Separate upgrade prerequisite: rejected because bundling is more efficient when the upgrade is required for FalkorDB anyway
- Kuzu/Neptune in initial scope: deferred to avoid scope expansion when two backends validate the abstraction pattern

### Trade-offs
- Accepted tight coupling to graphiti-core's driver API over building a custom abstraction — upstream alignment outweighs the risk of API changes
- Accepted FalkorDB's openCypher subset compatibility for raw queries over rewriting all queries in a native FalkorDB API — 14 queries all use basic patterns that openCypher covers
- Accepted datetime as ISO-8601 strings over native datetime objects — ensures FalkorDB compatibility at the cost of slightly less ergonomic temporal queries

### Open Questions
- [ ] FalkorDB port conflict with Redis (both default to 6379) — may need to map to 6380 in docker-compose
- [ ] FalkorDB Lite availability as a pip package — needs verification during implementation
- [ ] Exact graphiti-core 0.28 breaking changes beyond constructor signature — may discover more during Phase 1 upgrade

### Context
Planning session to add FalkorDB as a second graph database backend behind a graphdb_provider abstraction. Discovered that graphiti-core 0.28 already provides the driver abstraction needed (FalkorDriver, Neo4jDriver), so the approach delegates driver construction to graphiti-core while wrapping raw query execution in a thin protocol. The codebase has 14 raw Cypher queries across 4 files that need migration. Coordinated tier selected due to full coordinator availability.
