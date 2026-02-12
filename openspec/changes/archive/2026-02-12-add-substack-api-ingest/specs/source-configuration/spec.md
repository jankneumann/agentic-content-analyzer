## ADDED Requirements
### Requirement: Substack Subscription Sync
The system SHALL provide a Substack subscription sync that fetches the authenticated user's Substack subscriptions and writes them to `sources.d/substack.yaml` (Substack.yml).

The sync process SHALL preserve existing `enabled`, `tags`, and `name` fields for matching subscriptions and append new subscriptions with `enabled: false` by default so users can opt in.

#### Scenario: Sync adds new Substack subscriptions
- **WHEN** a user runs the Substack subscription sync with a valid session cookie
- **THEN** the system writes `sources.d/substack.yaml` (Substack.yml) with one entry per subscription
- **AND** newly discovered subscriptions are added with `enabled: false`
- **AND** existing entries keep their prior `enabled` and `tags` values

### Requirement: Substack Session Cookie Configuration
The system SHALL read a Substack session cookie from configuration (e.g., `SUBSTACK_SESSION_COOKIE`) and use it for authenticated Substack API requests.

#### Scenario: Missing session cookie
- **WHEN** Substack ingestion runs without a configured session cookie
- **THEN** the system logs a warning explaining how to provide the cookie
- **AND** only public Substack data is ingested

### Requirement: Substack URL Deduplication
The system SHALL deduplicate Substack ingested posts by canonical Substack URL across RSS, Gmail, and Substack sources before creating new Content records.

#### Scenario: Duplicate Substack URLs across sources
- **WHEN** RSS, Gmail, or Substack ingestion produces posts with the same canonical Substack URL
- **THEN** the system creates a single Content record for that URL
- **AND** logs a debug message noting the deduplication decision

## MODIFIED Requirements
### Requirement: Source Type Support
The system SHALL support the following source types in the configuration file:
- `rss` — RSS/Atom article feeds
- `youtube_playlist` — YouTube playlist IDs
- `youtube_channel` — YouTube channel IDs (resolved to uploads playlist)
- `youtube_rss` — YouTube channel RSS feeds
- `podcast` — Podcast RSS feeds with audio enclosures
- `gmail` — Gmail inbox queries
- `substack` — Substack newsletters via the Substack API

#### Scenario: RSS source entry
- **WHEN** a source with `type: rss` and `url` field is defined
- **THEN** the system includes it in RSS ingestion with optional `name`, `tags`, and `max_entries` override

#### Scenario: YouTube playlist source entry
- **WHEN** a source with `type: youtube_playlist` and `id` field is defined
- **THEN** the system ingests videos from the playlist using the existing `ingest_playlist()` method
- **AND** respects the `visibility` field for OAuth graceful degradation

#### Scenario: YouTube channel source entry
- **WHEN** a source with `type: youtube_channel` and `channel_id` field is defined
- **THEN** the system resolves the channel ID to an uploads playlist ID via the YouTube Data API
- **AND** ingests videos from the resolved playlist

#### Scenario: YouTube RSS source entry
- **WHEN** a source with `type: youtube_rss` and `url` field is defined
- **THEN** the system parses the YouTube RSS feed to extract video IDs and metadata
- **AND** fetches transcripts for discovered videos using the existing transcript pipeline

#### Scenario: Podcast source entry
- **WHEN** a source with `type: podcast` and `url` field is defined
- **THEN** the system fetches the podcast RSS feed and applies the transcript-first strategy
- **AND** stores the transcript as a Content record with `source_type=PODCAST`

#### Scenario: Substack source entry
- **WHEN** a source with `type: substack` and `url` field is defined in `sources.d/substack.yaml` (Substack.yml)
- **THEN** the system fetches the latest Substack posts via the Substack API
- **AND** stores Content records with the canonical Substack URL in metadata
