## MODIFIED Requirements

### Requirement: HTTP graph query endpoint

The system SHALL expose a `POST /api/v1/graph/query` endpoint that performs semantic search against the knowledge graph (Graphiti-backed, Neo4j or FalkorDB). The endpoint accepts a query string and optional limit, returning matching entities and relationships together with a truncation indicator, because the graph backend exposes no offset or cursor.

#### Scenario: Graph query returns entities and relationships

- **WHEN** a client sends `POST /api/v1/graph/query` with body `{"query": "mixture of experts", "limit": 20}` and a valid admin key
- **THEN** the API returns a 200 response with `entities`, `relationships`, `total_hits`, and `truncated`
- **AND** each entity includes `id`, `name`, `type`, and `score`
- **AND** each relationship includes `source_id`, `target_id`, `type`, and `score`

#### Scenario: Graph query with empty result

- **WHEN** a graph query matches no entities
- **THEN** the API returns 200 with empty `entities` and `relationships` arrays, `total_hits = 0`, and `truncated = false`

#### Scenario: Graph query reports truncation

- **WHEN** the backend returns more than `limit` hits for the query
- **THEN** the API returns exactly `limit` hits split into entities and relationships
- **AND** `truncated` is `true`
- **AND** `total_hits` is `limit + 1`, the number of hits observed, not a corpus count

#### Scenario: Graph query validates query field

- **WHEN** a client sends `POST /api/v1/graph/query` with an empty or missing `query` field
- **THEN** the API returns 422 Unprocessable Entity
