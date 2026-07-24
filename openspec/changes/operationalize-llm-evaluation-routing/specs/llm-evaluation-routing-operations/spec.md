## ADDED Requirements

### Requirement: Effective routing configuration reaches runtime

Fresh production routers SHALL resolve routing configuration with environment
overrides above database values above YAML defaults and SHALL load the selected
versioned classifier when dynamic routing is enabled. Production classifier
artifacts SHALL use a non-executable schema-validated format, resolve beneath
an allowlisted storage root, and pass authenticated integrity verification
before loading.

#### Scenario: Database configuration enables dynamic routing

- **GIVEN** no environment override and a valid database routing configuration
- **WHEN** a fresh runtime router is constructed
- **THEN** it SHALL use the database configuration
- **AND** SHALL inject the configured embedding and classifier dependencies

#### Scenario: Classifier artifact is unsafe

- **WHEN** an artifact is malformed, tampered, outside the allowlisted root,
  escapes through a symlink, or uses pickle or another executable format
- **THEN** the production router SHALL reject it before deserialization
- **AND** SHALL fall back to fixed routing with an observable reason

### Requirement: Evaluation produces deployable routing state

The system SHALL support a bootstrap-free sequence from paired persisted inputs
through evaluation, classifier training, calibration, and atomic opt-in
enablement.

#### Scenario: An operator calibrates a new classifier

- **WHEN** a sufficient evaluated dataset is available
- **THEN** training and calibration SHALL produce a versioned classifier and
  threshold
- **AND** enablement SHALL be atomic, auditable, and reversible

### Requirement: Evaluation surfaces are truthful

CLI, API, documentation, judge configuration, failure rows, and cost reporting SHALL
expose only implemented semantics and SHALL use durable operations for retained
long-running remote execution.

#### Scenario: A routed generation completes

- **WHEN** dynamic routing selects a model and generation terminates
- **THEN** the decision SHALL persist selected model, config/classifier
  revision, complexity score, threshold, terminal outcome, and actual cost
- **AND** reports SHALL derive savings from complete persisted values
