## ADDED Requirements

### Requirement: GX-10 production profile declares observability

A production GX-10 profile SHALL declare local PostgreSQL, Redis, Neo4j, storage, Langfuse, and OTLP endpoints; required-observability policy; unique service identities by process role; environment/release sources; masking policy; retention targets; storage watermarks; and allowed external provider egress. Secrets SHALL remain external references.

#### Scenario: [PROFILE-001] Complete GX-10 profile validates

- **WHEN** profile validation runs with resolvable secret references and reachable required endpoints
- **THEN** it reports the resolved provider topology without printing secret values
- **AND** API, worker, scheduler, and maintenance identities are distinct

#### Scenario: [PROFILE-002] Observability is enabled but incomplete

- **WHEN** required observability is enabled without OTLP endpoint, Langfuse credentials, service identity, or masking policy
- **THEN** production profile activation fails with bounded missing-field diagnostics
- **AND** no process silently disables tracing
