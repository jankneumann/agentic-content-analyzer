## ADDED Requirements
### Requirement: Hoverfly-based API simulation for integration tests
The integration test suite SHALL support running external HTTP dependencies through a Hoverfly simulator using pre-recorded simulations.

#### Scenario: Run integration tests with Hoverfly simulations
- **WHEN** the integration test suite is executed with Hoverfly enabled
- **THEN** external HTTP calls are served from Hoverfly simulations
- **AND** tests run without contacting live external services

### Requirement: Test-time HTTP proxy/base URL configuration
The system SHALL provide a test-time configuration option to route external HTTP clients through a proxy or base URL for simulation.

#### Scenario: Proxy configured for integration tests
- **WHEN** the test configuration enables the HTTP proxy/base URL
- **THEN** supported external HTTP clients send requests through the configured proxy/base URL
