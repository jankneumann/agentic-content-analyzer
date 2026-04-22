# knowledge-graph Specification Delta

## ADDED Requirements

### Requirement: HTTP graph query endpoint

The system SHALL expose a `POST /api/v1/graph/query` endpoint that performs semantic search against the knowledge graph (Graphiti-backed, Neo4j or FalkorDB). The endpoint accepts a query string and optional limit, returning matching entities and relationships.

#### Scenario: Graph query returns entities and relationships

- **WHEN** a client sends `POST /api/v1/graph/query` with body `{"query": "mixture of experts", "limit": 20}` and a valid admin key
- **THEN** the API returns a 200 response with `entities` and `relationships` arrays
- **AND** each entity includes `id`, `name`, `type`, and `score`
- **AND** each relationship includes `source_id`, `target_id`, `type`, and `score`

#### Scenario: Graph query with empty result

- **WHEN** a graph query matches no entities
- **THEN** the API returns 200 with empty `entities` and `relationships` arrays

#### Scenario: Graph query validates query field

- **WHEN** a client sends `POST /api/v1/graph/query` with an empty or missing `query` field
- **THEN** the API returns 422 Unprocessable Entity

### Requirement: HTTP graph entity extraction endpoint

The system SHALL expose a `POST /api/v1/graph/extract-entities` endpoint that accepts a content ID, reads the associated content summary, and pushes entities into the knowledge graph via the Graphiti client. This endpoint MUST be tagged `@audited` and write to the audit log.

#### Scenario: Extract entities for existing content

- **WHEN** a client sends `POST /api/v1/graph/extract-entities` with body `{"content_id": 42}` and a valid admin key
- **THEN** the API extracts entities from the content summary
- **AND** returns a 200 response with `entities_added`, `relationships_added`, and `graph_episode_id`
- **AND** the audit log records the operation with `operation=graph.extract_entities` and `notes.content_id=42`

#### Scenario: Extract entities for missing content

- **WHEN** the request references a `content_id` that does not exist
- **THEN** the API returns 404 Not Found

#### Scenario: Extract entities for content without summary

- **WHEN** the content exists but has no summary
- **THEN** the API returns 409 Conflict with message indicating summarization is required first
