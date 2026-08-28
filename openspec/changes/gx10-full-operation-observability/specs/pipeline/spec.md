## ADDED Requirements

### Requirement: Pipeline workflow has one navigable trace topology

The durable PipelineWorkflow SHALL be the root operation for one trace topology. Each source operation and downstream summarization, graph, theme, digest, and delivery operation SHALL preserve root/parent operation identities and create nested or linked attempt observations.

#### Scenario: [PIPE-001] Partial source failure remains visible

- **WHEN** one source fails while other source operations and later eligible stages continue
- **THEN** the pipeline trace shows the failed source attempt and continuing siblings
- **AND** the terminal pipeline result remains partial with source operation IDs

#### Scenario: [PIPE-002] Pipeline retry does not flatten history

- **WHEN** one pipeline child operation retries
- **THEN** each attempt appears separately under that child operation
- **AND** the overall pipeline/root identity does not change
