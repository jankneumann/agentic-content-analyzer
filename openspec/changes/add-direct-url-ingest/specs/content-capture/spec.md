## ADDED Requirements
### Requirement: Direct URL submission UI
The system SHALL provide a web UI that lets users submit a URL for ingestion using the save-url workflow.

#### Scenario: Submit URL for ingestion
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits a valid URL
- **THEN** the system SHALL call the save-url workflow
- **AND** the UI SHALL display the returned content ID and status

#### Scenario: Validation error
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits an invalid or empty URL
- **THEN** the UI SHALL display a validation error
- **AND** no save-url request SHALL be sent
