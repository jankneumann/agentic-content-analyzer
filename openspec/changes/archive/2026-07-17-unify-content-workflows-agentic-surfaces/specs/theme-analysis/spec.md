## ADDED Requirements

### Requirement: Theme analysis consumes resolved content

Workflow theme analysis SHALL require a `ResolvedContentSet` or persisted selection reference and MUST NOT independently re-query content by period. Persisted theme analysis metadata SHALL record the selection fingerprint and content IDs analyzed.

#### Scenario: Digest and theme use identical selection
- **WHEN** theme analysis is run as part of digest creation
- **THEN** the analyzer receives the digest workflow's resolved set
- **AND** every theme content ID belongs to that set
- **AND** the persisted analysis records the same fingerprint

#### Scenario: Standalone theme operation resolves once
- **WHEN** a standalone theme operation is submitted with a content query
- **THEN** the worker resolves the query once using workflow defaults
- **AND** the analyzer consumes that immutable resolved set
