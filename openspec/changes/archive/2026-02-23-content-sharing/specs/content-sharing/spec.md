# Content Sharing Capability

## ADDED Requirements

### Requirement: Shareable Content

The system SHALL support sharing content via public links.

#### Scenario: Share token generation
- **GIVEN** content exists without a share token
- **WHEN** sharing is enabled
- **THEN** a UUID4 share token SHALL be generated
- **AND** `is_public` SHALL be set to `True`

#### Scenario: Disable sharing preserves token
- **GIVEN** content is currently shared
- **WHEN** sharing is disabled
- **THEN** `is_public` SHALL be `False`
- **AND** `share_token` SHALL be preserved

### Requirement: Public Access

The system SHALL provide public endpoints for shared content.

#### Scenario: Access shared content
- **GIVEN** content has `is_public=True`
- **WHEN** `/shared/content/{token}` is accessed
- **THEN** the content SHALL be returned without authentication

#### Scenario: Access disabled share
- **GIVEN** content has `is_public=False`
- **WHEN** `/shared/content/{token}` is accessed
- **THEN** 404 SHALL be returned

#### Scenario: HTML response
- **GIVEN** `Accept: text/html` header
- **WHEN** shared content is accessed
- **THEN** mobile-friendly HTML page SHALL be returned

### Requirement: Open Graph Tags

The system SHALL include Open Graph meta tags in shared content HTML pages.

#### Scenario: Social sharing preview
- **WHEN** shared content HTML is rendered
- **THEN** Open Graph meta tags SHALL be included for:
  - `og:title`, `og:description`, `og:type`, `og:url`

### Requirement: Rate Limiting

The system SHALL rate-limit public shared endpoints to prevent abuse.

#### Scenario: Prevent abuse
- **WHEN** more than 100 requests/minute from same IP
- **THEN** 429 Too Many Requests SHALL be returned
