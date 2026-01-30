## Context

The project ingests content from Gmail, RSS feeds, YouTube playlists, and file uploads. Each source type has its own config format:
- `rss_feeds.txt` — one URL per line, comments with `#`
- `youtube_playlists.txt` — `PLAYLIST_ID | description` format
- `.env` — Gmail credentials, YouTube API keys

A reference file (`AI-ML-Data-News.md`) contains ~350 RSS news feeds, ~70 podcast RSS feeds, and ~120 YouTube channel RSS feeds that need to be importable.

### Stakeholders
- Content operators who add/remove sources
- Developers maintaining ingestion pipelines
- CI/CD systems validating config

## Goals / Non-Goals

### Goals
- Single file for all ingestion source definitions
- Human-readable format with metadata (names, tags, descriptions)
- Support YouTube channels and podcast RSS feeds as new source types
- Per-source configuration (language prefs, max entries, enabled/disabled)
- Backward compatibility with existing config files during transition
- Parseable by both humans and tooling

### Non-Goals
- UI-based source management (future enhancement)
- Real-time feed validation on config change
- Automatic source discovery or recommendation
- Full podcast audio storage (only transcripts are stored)

## Decisions

### Decision 1: YAML over JSON for config format
**Choice**: YAML (`sources.yaml`)
**Rationale**: YAML supports comments (critical for documenting sources), is more readable for large lists, and is the standard for configuration files in Python ecosystems. JSON lacks comments and becomes unwieldy at 500+ entries.
**Alternatives considered**:
- JSON — no comments, verbose for nested config
- TOML — awkward for arrays of heterogeneous objects
- Python dict — not editable by non-developers

### Decision 2: Flat source list with type discriminator
**Choice**: Each source entry has an explicit `type` field (`rss`, `youtube_playlist`, `youtube_channel`, `youtube_rss`, `podcast`, `gmail`)
**Rationale**: Simpler to validate, search, and filter than nested grouping. Enables mixed ordering (e.g., grouping by topic across types). Tags provide the grouping mechanism.
**Alternative considered**: Nested by source type (e.g., `youtube.channels[]`, `rss.feeds[]`) — harder to reorder, duplicates structure.

### Decision 3: Pydantic models for source config validation
**Choice**: Use Pydantic `BaseModel` subclasses with discriminated unions for source-specific fields
**Rationale**: Consistent with existing settings pattern, provides type safety, auto-generates JSON Schema for editor support.

### Decision 4: Podcast transcript-first strategy with audio fallback
**Choice**: Three-tier transcript acquisition: (1) feed-embedded transcript, (2) linked transcript page, (3) audio STT as last resort
**Rationale**:
- Many podcasts include full transcripts in RSS `<content:encoded>`, show notes, or linked pages
- Text-based transcripts are free, instant, and often higher quality (human-edited)
- Audio transcription is expensive ($0.006/min), slow (download + STT), and requires audio enclosure
- This approach minimizes cost while maximizing coverage
**Transcript resolution order**:
1. Check for text transcript in feed entry (`content:encoded`, `description`, `itunes:summary`)
2. Check for transcript link in show notes (common patterns: `/transcript`, `/show-notes`)
3. If `transcribe: true` and audio enclosure exists, download and transcribe via STT
4. If none available, store episode metadata only (title, date, description) without full content

**STT provider choice** (for audio fallback):
- OpenAI Whisper API: reliable, fast, no GPU needed, $0.006/minute
- Project already has `OPENAI_API_KEY` configured
- Local Whisper: free but requires significant compute and `whisper` package
**Alternatives considered**:
- Deepgram — excellent quality but adds another API key dependency
- AssemblyAI — good but same concern
- Google Speech-to-Text — complex auth, not needed given existing OpenAI key

### Decision 5: YouTube channel → playlist resolution strategy
**Choice**: Resolve channel ID to uploads playlist ID at ingestion time using YouTube Data API `channels().list()`, then use existing playlist ingestion
**Rationale**: Minimal code change — only need a single API call to convert `UC...` channel ID to `UU...` uploads playlist ID. The existing `ingest_playlist()` handles everything else.
**Alternative**: Parse YouTube RSS feeds for channel videos — lighter weight (no API quota) but no transcript access without video IDs.

### Decision 7: YouTube public/private visibility with OAuth graceful degradation
**Choice**: Each YouTube source (`youtube_playlist`, `youtube_channel`) has a `visibility` field (`public` or `private`, default: `public`). When the OAuth token is expired or unavailable, the system:
1. Logs a warning about the expired/missing OAuth token
2. Skips all `visibility: private` sources
3. Falls back to the API key (`GOOGLE_API_KEY` / `YOUTUBE_API_KEY`) for `visibility: public` sources
4. Continues ingestion without crashing

**Rationale**: We observed during debugging that an expired YouTube OAuth token (`RefreshError: Token has been expired or revoked`) causes the entire YouTube ingestion to fail — including public playlists that don't need OAuth. By marking visibility per source, the system can gracefully degrade and still ingest public content.

**Implementation**:
- `YouTubeClient.__init__()` attempts OAuth first, catches `RefreshError`, falls back to API key
- `ingest_all_playlists()` filters out private sources when only API key is available
- Logs clearly indicate which sources were skipped and why

### Decision 6: Backward compatibility approach
**Choice**: If `sources.yaml` exists, use it exclusively. If not, fall back to `rss_feeds.txt` + `youtube_playlists.txt`.
**Rationale**: Clean migration path. Operators can migrate at their own pace. Once `sources.yaml` is adopted, legacy files can be removed.

## Config File Schema

```yaml
# sources.yaml — Unified ingestion source configuration
version: 1

# Global defaults (overridable per source)
defaults:
  max_entries: 10
  days_back: 7
  enabled: true

sources:
  # --- RSS Article Feeds ---
  - type: rss
    url: https://www.latent.space/feed
    name: Latent Space
    tags: [ai, engineering, newsletter]
    max_entries: 20  # Override default

  - type: rss
    url: https://blog.bytebytego.com/feed
    name: ByteByteGo
    tags: [architecture, systems]
    enabled: false  # Temporarily disabled

  # --- YouTube Playlists ---
  - type: youtube_playlist
    id: PLN4UY0S3lPrs40eHdRIiJ-iXJYMkjI4P6
    name: Public test playlist
    visibility: public  # public (default) or private
    tags: [ai, tutorials]

  - type: youtube_playlist
    id: PLgmaR0EXVZsLXQ30zPCMobz0p02XrNBJq
    name: Private curated playlist
    visibility: private  # Requires OAuth — skipped if token expired
    tags: [ai, curated]

  # --- YouTube Channels (NEW) ---
  - type: youtube_channel
    channel_id: UCbfYPyITQ-7l4upoX8nvctg
    name: Two Minute Papers
    visibility: public  # Channels are public by default
    tags: [ai, research, video]
    languages: [en]

  # --- YouTube RSS Feeds (NEW) ---
  - type: youtube_rss
    url: https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg
    name: Two Minute Papers
    tags: [ai, research]

  # --- Podcast RSS Feeds (NEW) ---
  - type: podcast
    url: https://feeds.megaphone.fm/hubermanlab
    name: Huberman Lab
    tags: [science, health]
    transcribe: true  # Enable audio STT fallback if no text transcript found
    stt_provider: openai  # openai | local_whisper (only used as fallback)
    languages: [en]

  # --- Gmail (existing, now in config) ---
  - type: gmail
    query: "label:newsletters-ai"
    name: AI Newsletter Label
    tags: [newsletters]
    max_results: 50
```

## Pydantic Model Hierarchy

```python
class SourceBase(BaseModel):
    """Base for all source definitions."""
    type: str
    name: str | None = None
    tags: list[str] = []
    enabled: bool = True
    max_entries: int | None = None  # Override global default

class RSSSource(SourceBase):
    type: Literal["rss"] = "rss"
    url: str

class YouTubePlaylistSource(SourceBase):
    type: Literal["youtube_playlist"] = "youtube_playlist"
    id: str
    visibility: Literal["public", "private"] = "public"

class YouTubeChannelSource(SourceBase):
    type: Literal["youtube_channel"] = "youtube_channel"
    channel_id: str
    visibility: Literal["public", "private"] = "public"
    languages: list[str] = ["en"]

class YouTubeRSSSource(SourceBase):
    type: Literal["youtube_rss"] = "youtube_rss"
    url: str

class PodcastSource(SourceBase):
    type: Literal["podcast"] = "podcast"
    url: str
    transcribe: bool = True
    stt_provider: Literal["openai", "local_whisper"] = "openai"
    languages: list[str] = ["en"]

class GmailSource(SourceBase):
    type: Literal["gmail"] = "gmail"
    query: str = "label:newsletters-ai"
    max_results: int = 50

# Discriminated union
Source = Annotated[
    RSSSource | YouTubePlaylistSource | YouTubeChannelSource |
    YouTubeRSSSource | PodcastSource | GmailSource,
    Field(discriminator="type"),
]

class SourcesConfig(BaseModel):
    version: int = 1
    defaults: SourceDefaults = SourceDefaults()
    sources: list[Source] = []
```

## Podcast Ingestion Architecture

### Transcript-First Strategy (3-Tier)

```
Podcast RSS Feed
    ↓ feedparser
Parse feed entries (title, date, content, enclosure URL)
    ↓
┌─── Tier 1: Feed-Embedded Transcript ───────────────────┐
│ Check <content:encoded>, <description>, <itunes:summary> │
│ If text ≥ 500 chars → use as transcript                  │
│ raw_format = "feed_transcript"                           │
└─── Found? ──→ Store as Content ─────────────────────────┘
    ↓ Not found
┌─── Tier 2: Linked Transcript Page ─────────────────────┐
│ Scan show notes for transcript URLs                     │
│ Common patterns: /transcript, /show-notes, /episodes/X  │
│ Fetch page → extract text via Trafilatura               │
│ raw_format = "linked_transcript"                        │
└─── Found? ──→ Store as Content ─────────────────────────┘
    ↓ Not found
┌─── Tier 3: Audio STT Fallback ─────────────────────────┐
│ Requires: transcribe=true AND audio enclosure exists    │
│ Download audio → OpenAI Whisper API / local Whisper     │
│ raw_format = "audio_transcript"                         │
│ Clean up temp audio file after transcription            │
└─── Found? ──→ Store as Content ─────────────────────────┘
    ↓ None available
Log warning, store metadata-only Content (title, date, description)
    ↓
Generate content_hash from markdown
    ↓
Dedup check (source_id = podcast:{episode_guid})
```

### Audio Handling (Tier 3 only)
- Download to temp directory, transcribe, then delete audio file
- No permanent audio storage (only transcript is kept as Content)
- Max episode duration configurable (default: 120 minutes)
- Only triggered when `transcribe: true` and no text transcript found in Tiers 1-2
- Skip episodes without audio enclosures when audio fallback is needed

## Migration Script Design

```bash
python -m src.config.migrate_sources [--from-markdown AI-ML-Data-News.md] [--output sources.yaml]
```

The migration script will:
1. Read existing `rss_feeds.txt` → emit `type: rss` entries
2. Read existing `youtube_playlists.txt` → emit `type: youtube_playlist` entries
3. Read `.env` Gmail config → emit `type: gmail` entry
4. Optionally parse `AI-ML-Data-News.md` sections:
   - "AI, ML, Big Data News" → `type: rss` entries (with name and URL extracted from markdown)
   - "AI, ML, Big Data Podcasts" → `type: podcast` entries
   - "AI, ML, Big Data Videos" → `type: youtube_rss` entries (with channel_id extracted from URL)
5. Deduplicate URLs across all inputs
6. Output merged `sources.yaml`

## Risks / Trade-offs

- **Large config file**: ~500+ sources will make `sources.yaml` long (~2000 lines). Mitigation: good commenting, tags for filtering, and future support for `sources.d/` directory pattern.
- **Podcast transcription costs**: Tier 1-2 (text transcripts) are free. Tier 3 (audio STT) costs $0.006/min. With transcript-first strategy, most podcasts won't need audio transcription. Mitigation: `transcribe: false` default for bulk import, enable selectively.
- **YouTube API quota**: Channel resolution uses 1 unit per call (10,000 daily quota). With ~120 channels, this is negligible. RSS feeds use zero quota.
- **STT dependency**: Adds OpenAI Whisper as a new dependency for podcast audio fallback. Already have `OPENAI_API_KEY`.
- **YouTube OAuth expiry**: Token expires periodically, blocking private playlist access. Mitigation: `visibility` flag enables graceful degradation — public sources continue via API key.

## Open Questions

1. Should we support `sources.d/*.yaml` directory for splitting large configs by category?
2. Should podcast audio transcription (Tier 3) be synchronous or queued via Celery for long episodes?
3. Should YouTube RSS feeds trigger transcript fetching (requires video ID extraction)?
