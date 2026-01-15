# Content Sharing Capability

## ADDED Requirements

### Requirement: Shareable Content Models

The system SHALL support sharing of content, summaries, digests, and audio via public links.

#### Scenario: Share fields on models
- **WHEN** sharing capability is added
- **THEN** the following models SHALL have sharing fields:
  - `Content`: `is_public`, `share_token`
  - `NewsletterSummary`: `is_public`, `share_token`
  - `Digest`: `is_public`, `share_token`
- **AND** `is_public` SHALL default to `False`
- **AND** `share_token` SHALL be nullable

#### Scenario: Share token generation
- **GIVEN** a content item has no share token
- **WHEN** sharing is enabled for the item
- **THEN** a UUID4 share token SHALL be generated
- **AND** the token SHALL be stored in `share_token` field
- **AND** `is_public` SHALL be set to `True`

#### Scenario: Share token uniqueness
- **WHEN** share tokens are generated
- **THEN** each token SHALL be globally unique (UUID4)
- **AND** the database SHALL enforce uniqueness via index

### Requirement: Share API Endpoints

The system SHALL provide API endpoints for managing content sharing.

#### Scenario: Enable sharing
- **GIVEN** an authenticated request (owner of the instance)
- **WHEN** `POST /api/v1/content/{id}/share` is called
- **THEN** a share token SHALL be generated if not exists
- **AND** `is_public` SHALL be set to `True`
- **AND** the response SHALL include:
  - `share_token`: the generated token
  - `share_url`: full URL to shared content

#### Scenario: Get share status
- **GIVEN** a content item exists
- **WHEN** `GET /api/v1/content/{id}/share` is called
- **THEN** the response SHALL include:
  - `is_public`: current sharing status
  - `share_token`: token if shared
  - `share_url`: URL if shared

#### Scenario: Disable sharing
- **GIVEN** a content item is currently shared
- **WHEN** `DELETE /api/v1/content/{id}/share` is called
- **THEN** `is_public` SHALL be set to `False`
- **AND** `share_token` SHALL be preserved (for re-enabling)
- **AND** the shared URL SHALL return 404

#### Scenario: Share endpoints for other models
- **WHEN** sharing is implemented
- **THEN** similar endpoints SHALL exist for:
  - `/api/v1/summaries/{id}/share`
  - `/api/v1/digests/{id}/share`

### Requirement: Public Shared Content Access

The system SHALL provide public endpoints for accessing shared content without authentication.

#### Scenario: Access shared content
- **GIVEN** a content item has `is_public=True` and valid `share_token`
- **WHEN** `GET /shared/content/{share_token}` is accessed
- **THEN** the content SHALL be returned
- **AND** no authentication SHALL be required

#### Scenario: Access non-existent share
- **GIVEN** a share token that does not exist
- **WHEN** `GET /shared/content/{token}` is accessed
- **THEN** a 404 response SHALL be returned
- **AND** no information about token validity SHALL be leaked

#### Scenario: Access disabled share
- **GIVEN** a content item has `is_public=False` but valid `share_token`
- **WHEN** `GET /shared/content/{share_token}` is accessed
- **THEN** a 404 response SHALL be returned

#### Scenario: Shared content response format
- **GIVEN** a shared content is accessed via browser
- **WHEN** `Accept: text/html` header is present
- **THEN** a mobile-friendly HTML page SHALL be returned
- **AND** the page SHALL include Open Graph meta tags

#### Scenario: Shared content JSON format
- **GIVEN** a shared content is accessed programmatically
- **WHEN** `Accept: application/json` header is present
- **THEN** JSON content SHALL be returned
- **AND** the response SHALL include content details

### Requirement: Shared Audio Access

The system SHALL provide public access to audio files for shared content.

#### Scenario: Access shared audio
- **GIVEN** a digest has audio and is shared
- **WHEN** `GET /shared/audio/{share_token}` is accessed
- **THEN** the audio file SHALL be served or redirected
- **AND** appropriate `Content-Type` header SHALL be set

#### Scenario: Audio redirect for cloud storage
- **GIVEN** audio is stored in Supabase Storage
- **WHEN** shared audio is accessed
- **THEN** a redirect to the storage URL SHALL be returned
- **AND** for private storage, a signed URL SHALL be generated

#### Scenario: Audio streaming headers
- **GIVEN** a shared audio file is accessed
- **WHEN** the response is sent
- **THEN** `Accept-Ranges: bytes` SHALL be included
- **AND** range requests SHALL be supported for seeking

### Requirement: Shared Content Web UI

The system SHALL provide a mobile-friendly web interface for shared content.

#### Scenario: Shared content page layout
- **GIVEN** a shared content page is loaded
- **WHEN** the page renders
- **THEN** it SHALL display:
  - Content title
  - Publication/author info
  - Content body (markdown rendered)
  - Audio player (if audio exists)
  - "Shared via Newsletter Aggregator" attribution

#### Scenario: Shared summary page layout
- **GIVEN** a shared summary page is loaded
- **WHEN** the page renders
- **THEN** it SHALL display:
  - Executive summary
  - Key themes
  - Strategic insights
  - Technical details
  - Link to original content (if public)

#### Scenario: Shared digest page layout
- **GIVEN** a shared digest page is loaded
- **WHEN** the page renders
- **THEN** it SHALL display:
  - Digest title and period
  - Executive overview
  - All digest sections
  - Audio player (if audio exists)
  - List of source content (if public)

#### Scenario: Mobile responsiveness
- **GIVEN** a shared page is accessed on mobile
- **WHEN** the page renders
- **THEN** it SHALL be fully responsive
- **AND** text SHALL be readable without zooming
- **AND** audio player SHALL be touch-friendly

### Requirement: Open Graph Meta Tags

The system SHALL include Open Graph meta tags for social sharing.

#### Scenario: Content Open Graph tags
- **GIVEN** a shared content page is loaded
- **WHEN** the HTML is rendered
- **THEN** the following meta tags SHALL be included:
  - `og:title`: Content title
  - `og:description`: First 200 chars of content
  - `og:type`: "article"
  - `og:url`: Canonical share URL

#### Scenario: Audio Open Graph tags
- **GIVEN** shared content has audio
- **WHEN** the HTML is rendered
- **THEN** additional tags SHALL be included:
  - `og:audio`: Audio URL
  - `og:audio:type`: "audio/mpeg"

### Requirement: Rate Limiting

The system SHALL implement rate limiting on public share endpoints.

#### Scenario: Share endpoint rate limiting
- **GIVEN** public share endpoints are accessed
- **WHEN** more than 100 requests per minute from same IP
- **THEN** subsequent requests SHALL receive 429 Too Many Requests
- **AND** `Retry-After` header SHALL indicate wait time

#### Scenario: Rate limit by token
- **GIVEN** a specific share token is accessed frequently
- **WHEN** more than 1000 requests per hour for same token
- **THEN** rate limiting SHALL apply
- **AND** this prevents abuse of individual shared content

### Requirement: Share Analytics (Optional)

The system MAY track basic analytics for shared content.

#### Scenario: View count tracking
- **GIVEN** shared content is accessed
- **WHEN** the request is processed
- **THEN** a view count MAY be incremented
- **AND** the count SHALL be stored efficiently (not per-request DB write)

#### Scenario: Analytics privacy
- **GIVEN** view analytics are collected
- **WHEN** data is stored
- **THEN** no personally identifiable information SHALL be stored
- **AND** only aggregate counts SHALL be maintained
