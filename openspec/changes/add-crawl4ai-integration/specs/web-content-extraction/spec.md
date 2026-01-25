# Web Content Extraction Spec Delta

## ADDED Requirements

### Requirement: Crawl4AI Fallback for JavaScript Content

The system SHALL use Crawl4AI as a fallback extractor for JavaScript-heavy pages when Trafilatura produces insufficient content.

#### Scenario: Fallback triggered for JS-heavy page
- **GIVEN** a URL pointing to a JavaScript-rendered page
- **AND** Crawl4AI is enabled via configuration
- **WHEN** Trafilatura extraction returns content below the quality threshold
- **THEN** the system SHALL automatically retry with Crawl4AI
- **AND** the extraction method SHALL be logged as "crawl4ai"

#### Scenario: Crawl4AI disabled by default
- **GIVEN** a fresh installation without Crawl4AI setup
- **WHEN** extraction is attempted on any URL
- **THEN** only Trafilatura SHALL be used
- **AND** no browser launch SHALL be attempted

### Requirement: Crawl4AI Configuration Options

The system SHALL support configuration of Crawl4AI behavior via settings.

#### Scenario: Enable Crawl4AI via settings
- **GIVEN** `crawl4ai_enabled=True` in configuration
- **AND** Crawl4AI dependencies are installed
- **WHEN** extraction quality validation fails
- **THEN** Crawl4AI fallback SHALL be attempted

#### Scenario: Cache mode configuration
- **GIVEN** `crawl4ai_cache_mode` is set to "enabled"
- **WHEN** extracting a previously visited URL
- **THEN** the cached result SHALL be returned
- **AND** no browser request SHALL be made

### Requirement: Docker Deployment Support

The system SHALL support running Crawl4AI as a separate Docker service.

#### Scenario: Remote Crawl4AI server
- **GIVEN** `CRAWL4AI_SERVER_URL` is configured
- **WHEN** Crawl4AI extraction is triggered
- **THEN** the request SHALL be sent to the remote server
- **AND** local browser launch SHALL NOT occur

#### Scenario: Health check for Crawl4AI service
- **GIVEN** Crawl4AI is deployed as a Docker service
- **WHEN** the service health is checked
- **THEN** the system SHALL verify browser availability
- **AND** report service status accurately
