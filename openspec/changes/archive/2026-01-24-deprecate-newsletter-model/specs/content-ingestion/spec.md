# Content Ingestion Spec Delta

## REMOVED Requirements

### Requirement: Newsletter Model Support

The system SHALL NOT use the Newsletter model for new content ingestion.

**Reason**: Newsletter model is superseded by the unified Content model which supports multiple source types (Gmail, RSS, YouTube, file uploads, webpages) with markdown-first storage.

**Migration**: All Newsletter functionality is available via Content model. Use `ContentSource` enum instead of `NewsletterSource`.

#### Scenario: Newsletter model import triggers deprecation warning
- **WHEN** code imports `Newsletter` from `src.models.newsletter`
- **THEN** a `DeprecationWarning` is raised
- **AND** the warning message directs to use `Content` model instead

#### Scenario: Newsletter API endpoints return deprecation headers
- **WHEN** a client calls any `/api/v1/newsletters/*` endpoint
- **THEN** response includes `Deprecation: true` header
- **AND** response includes `Sunset` header with removal date
- **AND** response includes `Link` header pointing to successor endpoint

### Requirement: Newsletter Frontend Route

The system SHALL NOT maintain the `/newsletters` route as a primary navigation destination.

**Reason**: Replaced by `/contents` route which provides unified content management.

**Migration**: Users should bookmark `/contents` instead. The `/newsletters` route will redirect to `/contents`.

#### Scenario: Newsletters route redirects to Contents
- **WHEN** user navigates to `/newsletters`
- **THEN** user is redirected to `/contents` with HTTP 301
- **AND** a deprecation banner is shown (during transition period)

#### Scenario: Newsletters removed from navigation
- **WHEN** user views the application sidebar
- **THEN** "Newsletters" link is not present
- **AND** "Content" link is present and functional

## MODIFIED Requirements

### Requirement: Summary Foreign Key Reference

The `NewsletterSummary` model SHALL reference content via `content_id` instead of `newsletter_id`.

#### Scenario: Summary links to Content
- **WHEN** a summary is created for ingested content
- **THEN** the summary's `content_id` references the Content record
- **AND** the legacy `newsletter_id` field is NULL or removed

#### Scenario: Querying summaries by content
- **WHEN** querying summaries for a specific content item
- **THEN** the query uses `content_id` as the join key
- **AND** results include all summaries for that content
