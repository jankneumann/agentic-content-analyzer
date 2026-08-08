# API Versioning Capability

## ADDED Requirements

### Requirement: URL-Based Versioning

The system SHALL use URL-based API versioning.

#### Scenario: Version in URL path
- **WHEN** API endpoints are accessed
- **THEN** version SHALL be in URL path (e.g., `/api/v1/contents`)

#### Scenario: Multiple versions
- **GIVEN** v1 and v2 both exist
- **WHEN** clients access `/api/v1/` or `/api/v2/`
- **THEN** appropriate version SHALL be served

### Requirement: Deprecation Headers

The system SHALL include deprecation headers for deprecated versions.

#### Scenario: Deprecated version headers
- **GIVEN** API version is deprecated
- **WHEN** any endpoint is accessed
- **THEN** response SHALL include:
  - `Deprecation: true`
  - `Sunset: <date>`
  - `Link: <successor>; rel="successor-version"`

### Requirement: Version Lifecycle

The system SHALL enforce version lifecycle stages.

#### Scenario: Active version
- **GIVEN** version status is ACTIVE
- **WHEN** endpoints are accessed
- **THEN** normal responses SHALL be returned

#### Scenario: Deprecated version
- **GIVEN** version status is DEPRECATED
- **WHEN** endpoints are accessed
- **THEN** responses SHALL include deprecation headers
- **AND** functionality SHALL work normally

#### Scenario: Sunset version
- **GIVEN** version status is SUNSET
- **WHEN** any endpoint is accessed
- **THEN** 410 Gone SHALL be returned
- **AND** response SHALL include migration guide URL

### Requirement: Version Configuration

The system SHALL maintain centralized version configuration.

#### Scenario: Version metadata
- **WHEN** version configuration is defined
- **THEN** it SHALL include:
  - Status (active/deprecated/sunset)
  - Sunset date (if applicable)
  - Successor version (if applicable)
