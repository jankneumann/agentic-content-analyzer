## ADDED Requirements

### Requirement: ParadeDB image identity is canonical

Build automation, profiles, deployment documentation, and Railway evidence SHALL
identify one immutable ParadeDB image and SHALL derive component versions from
the built artifact. The deployed digest SHALL be bound to a reviewed commit and
trusted build workflow or attestation with SBOM and vulnerability-scan
evidence.

#### Scenario: Operator prepares a database deployment

- **WHEN** the production preflight resolves the target image
- **THEN** the documented repository/tag SHALL be publicly pullable
- **AND** the immutable digest SHALL match the Railway deployment target
- **AND** deployment SHALL use that digest after provenance, SBOM, and
  vulnerability-scan evidence passes the approved policy

### Requirement: Production ParadeDB behavior is proven

Production evidence SHALL prove required extension versions and the active
ParadeDB BM25 strategy while health and rollback prerequisites remain valid.

#### Scenario: Production search verification runs

- **WHEN** the deployed database passes readiness
- **THEN** SQL SHALL report `vector`, `pg_search`, `pgmq`, and `pg_cron`
- **AND** authenticated BM25 search SHALL report
  `meta.bm25_strategy=paradedb_bm25`

### Requirement: Production Langfuse delivery is correlated

A sanitized production verification SHALL correlate one generation trace with
the tested application revision and a bounded observation window.

#### Scenario: Labeled verification generation completes

- **WHEN** the approved non-sensitive generation runs
- **THEN** its Langfuse trace identifier and arrival time SHALL correlate with
  the application revision and operation window
- **AND** no credentials, raw headers, or user content SHALL be persisted in
  repository evidence
