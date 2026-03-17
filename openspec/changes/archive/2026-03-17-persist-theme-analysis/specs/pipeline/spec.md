## ADDED Requirements

### Requirement: Theme analysis persists results
The pipeline's theme analysis step SHALL persist analysis results to the PostgreSQL database and write a summary episode to the Neo4j knowledge graph, rather than storing results in ephemeral in-memory dicts.

#### Scenario: Pipeline theme analysis creates DB record
- **WHEN** `aca analyze themes` completes successfully
- **THEN** a `ThemeAnalysis` record SHALL exist in the database with `status=completed`

#### Scenario: Pipeline theme analysis writes to Neo4j
- **WHEN** `aca analyze themes` completes successfully
- **THEN** a Graphiti episode containing the theme analysis summary SHALL be added to the knowledge graph
