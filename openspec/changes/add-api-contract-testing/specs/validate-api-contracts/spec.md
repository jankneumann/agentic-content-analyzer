## ADDED Requirements
### Requirement: OpenAPI contract inventory
The system SHALL document the FastAPI OpenAPI schema coverage for critical API endpoints before contract enforcement begins.

#### Scenario: Capture critical endpoint coverage
- **WHEN** the API contract workflow is introduced
- **THEN** a documented inventory of critical endpoints and their OpenAPI schema coverage is produced

### Requirement: Schema-driven fuzz testing
The system SHALL run Schemathesis-based contract and fuzz tests against a seeded test environment for the critical API endpoints.

#### Scenario: Validate schema and fuzz cases in CI
- **WHEN** CI runs the API contract test job
- **THEN** Schemathesis validates the OpenAPI schema responses and fuzz cases for targeted endpoints

### Requirement: Contract broker workflow
The system SHALL publish and verify consumer-driven contracts via an open-source broker to coordinate multi-agent API changes.

#### Scenario: Publish and verify contract artifacts
- **WHEN** a producer or consumer contract changes
- **THEN** the updated contract is published to the broker and verified in the CI workflow
