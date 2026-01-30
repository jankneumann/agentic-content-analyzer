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
- Unified config for all ingestion source definitions, split by type into `sources.d/*.yaml`
- Human-readable format with metadata (names, tags, descriptions)
- Support YouTube playlists, channels, RSS feeds, and podcast RSS feeds
- Per-source configuration (language prefs, max entries, enabled/disabled)
- Backward compatibility with existing config files during transition
- Parseable by both humans and tooling

### Non-Goals
- UI-based source management (future enhancement)
- Real-time feed validation on config change
- Automatic source discovery or recommendation
- Full podcast audio storage (only transcripts are stored)

## Decisions

### Decision 1: YAML format with `sources.d/` directory and per-file defaults
**Choice**: YAML config files in a `sources.d/` directory. Each file can define `defaults` at the top level (including `type`), which are applied to all `sources` entries in that file. Files can be organized by source type (e.g., `rss.yaml`) or by topic (e.g., `ai-research.yaml` mixing RSS + YouTube + Podcast).
**Rationale**: With ~500+ sources across 6 types, a single monolithic file becomes unwieldy (~2000 lines). Per-file defaults eliminate repetition — a file like `rss.yaml` sets `type: rss` once in defaults rather than on every entry. Topic-based files (e.g., `ai-research.yaml`) can mix types by overriding `type` per entry. YAML supports comments (critical for documenting sources) and is the standard for configuration files in Python ecosystems.
**Loading order**: The system loads all `*.yaml` files from `sources.d/` alphabetically and merges them into a single `SourcesConfig`. Global defaults from `_defaults.yaml` (if present) are applied first, then per-file defaults override globals, then per-entry fields override file defaults.
**Default resolution**: `_defaults.yaml globals` → `per-file defaults` → `per-entry fields` (most specific wins)
**Alternatives considered**:
- Single `sources.yaml` — unwieldy at 500+ entries, hard to navigate by type
- JSON — no comments, verbose for nested config
- TOML — awkward for arrays of heterogeneous objects
- Python dict — not editable by non-developers

### Decision 2: Flat source list with type discriminator
**Choice**: Each source entry has an explicit `type` field (`rss`, `youtube_playlist`, `youtube_channel`, `youtube_rss`, `podcast`, `gmail`)
**Rationale**: Simpler to validate, search, and filter than nested grouping. Enables mixed ordering (e.g., grouping by topic across types). Tags provide the grouping mechanism. YouTube playlists remain a first-class type — the existing `youtube_playlists.txt` entries map directly to `type: youtube_playlist` entries.
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
**Choice**: If `sources.d/` directory exists, load all YAML files from it. Else if `sources.yaml` exists, use it. Otherwise, fall back to `rss_feeds.txt` + `youtube_playlists.txt`.
**Rationale**: Clean migration path with three tiers. Operators can migrate at their own pace. The `sources.d/` directory is the recommended layout for production use. A single `sources.yaml` is supported for simpler setups. Legacy files work until migration is complete.

## Config Directory Structure

The recommended layout uses a `sources.d/` directory at the project root. Files can be organized **by type** or **by topic** — or a mix of both:

```
sources.d/
├── _defaults.yaml          # Global defaults (loaded first due to _ prefix)
├── rss.yaml                # RSS article feeds (~350 entries)
├── youtube.yaml            # YouTube playlists, channels, and RSS feeds (~120+ entries)
├── podcasts.yaml           # Podcast RSS feeds (~70 entries)
├── gmail.yaml              # Gmail query sources
└── ai-research.yaml        # (optional) Mixed-type file grouped by topic
```

A single `sources.yaml` file is also supported for simpler setups.

### Default Resolution Order

Each file can define its own `defaults` section. Values cascade in this order (most specific wins):

```
_defaults.yaml (global) → per-file defaults → per-entry fields
```

For example, `rss.yaml` sets `defaults.type: rss` so entries don't need to repeat `type: rss` on every line. A topic file like `ai-research.yaml` leaves `type` unset in defaults and specifies it per entry instead.

### `sources.d/_defaults.yaml`

```yaml
# Global defaults — applied to all sources across all files
version: 1

defaults:
  max_entries: 10
  days_back: 7
  enabled: true
```

### `sources.d/rss.yaml`

```yaml
# Per-file default: all entries in this file are type: rss
defaults:
  type: rss

sources:
  # No need to repeat "type: rss" — inherited from file defaults
  - url: https://www.latent.space/feed
    name: Latent Space
    tags: [ai, engineering, newsletter]
    max_entries: 20  # Override global default

  - url: https://blog.bytebytego.com/feed
    name: ByteByteGo
    tags: [architecture, systems]
    enabled: false  # Temporarily disabled
```

### `sources.d/youtube.yaml`

```yaml
# YouTube file — mixes playlists, channels, and RSS feeds
# No single type default since this file contains multiple YouTube types
sources:
  # --- YouTube Playlists (existing, migrated from youtube_playlists.txt) ---
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

  # --- YouTube Channels (NEW — resolved to uploads playlist via API) ---
  - type: youtube_channel
    channel_id: UCbfYPyITQ-7l4upoX8nvctg
    name: Two Minute Papers
    visibility: public
    tags: [ai, research, video]
    languages: [en]

  # --- YouTube RSS Feeds (NEW — zero API quota, parsed via feedparser) ---
  - type: youtube_rss
    url: https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg
    name: Two Minute Papers
    tags: [ai, research]
```

### `sources.d/podcasts.yaml`

```yaml
# Per-file default: all entries are type: podcast
defaults:
  type: podcast
  transcribe: true
  stt_provider: openai

sources:
  - url: https://feeds.megaphone.fm/hubermanlab
    name: Huberman Lab
    tags: [science, health]
    languages: [en]

  - url: https://lexfridman.com/feed/podcast/
    name: Lex Fridman Podcast
    tags: [ai, interviews]
    transcribe: false  # Override: transcripts available in feed
```

### `sources.d/gmail.yaml`

```yaml
defaults:
  type: gmail

sources:
  - query: "label:newsletters-ai"
    name: AI Newsletter Label
    tags: [newsletters]
    max_results: 50
```

### `sources.d/ai-research.yaml` (optional — topic-based mixed-type file)

```yaml
# Topic-based file: groups AI research sources across types
# No type default — each entry specifies its own type
sources:
  - type: rss
    url: https://arxiv.org/rss/cs.AI
    name: arXiv CS.AI
    tags: [ai, research, papers]

  - type: youtube_channel
    channel_id: UCbfYPyITQ-7l4upoX8nvctg
    name: Two Minute Papers
    tags: [ai, research, video]

  - type: podcast
    url: https://feeds.megaphone.fm/TWiML
    name: TWIML AI Podcast
    tags: [ai, research, interviews]
    transcribe: true
```

## Pydantic Model Hierarchy

```python
class SourceDefaults(BaseModel):
    """Defaults that can be set globally (_defaults.yaml) or per file.
    Any field here can be overridden per source entry."""
    type: str | None = None  # Allows per-file type default (e.g., "rss")
    enabled: bool = True
    max_entries: int = 10
    days_back: int = 7
    tags: list[str] = []
    # Type-specific defaults (only applied when type matches)
    visibility: Literal["public", "private"] = "public"
    transcribe: bool = True
    stt_provider: Literal["openai", "local_whisper"] = "openai"
    languages: list[str] = ["en"]

class SourceBase(BaseModel):
    """Base for all source definitions."""
    type: str
    name: str | None = None
    tags: list[str] = []
    enabled: bool = True
    max_entries: int | None = None  # Override global/file default

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

class SourceFileConfig(BaseModel):
    """Schema for each YAML file in sources.d/"""
    defaults: SourceDefaults = SourceDefaults()  # Per-file defaults
    sources: list[dict] = []  # Raw dicts — defaults applied before validation

class SourcesConfig(BaseModel):
    """Merged config after loading all files."""
    version: int = 1
    defaults: SourceDefaults = SourceDefaults()  # Global defaults
    sources: list[Source] = []
```

### Default Application Logic

```python
def load_sources_directory(sources_dir: Path) -> SourcesConfig:
    """Load and merge all YAML files from sources.d/"""
    global_defaults = {}
    all_sources = []

    for yaml_file in sorted(sources_dir.glob("*.yaml")):
        file_config = SourceFileConfig(**yaml.safe_load(yaml_file))

        if yaml_file.name == "_defaults.yaml":
            global_defaults = file_config.defaults.model_dump(exclude_unset=True)
            continue

        file_defaults = file_config.defaults.model_dump(exclude_unset=True)

        for raw_source in file_config.sources:
            # Merge: global defaults → file defaults → entry fields
            merged = {**global_defaults, **file_defaults, **raw_source}
            all_sources.append(merged)

    # Validate all merged entries via discriminated union
    return SourcesConfig(sources=all_sources)
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
# Output split by type into sources.d/ (recommended)
python -m src.config.migrate_sources [--from-markdown AI-ML-Data-News.md] [--output-dir sources.d]

# Output single file (simpler setups)
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
6. Output either:
   - `--output-dir sources.d/` → split files by type: `_defaults.yaml`, `rss.yaml`, `youtube.yaml`, `podcasts.yaml`, `gmail.yaml`
   - `--output sources.yaml` → single merged file (default)

## Risks / Trade-offs

- **Config file management at scale**: ~500+ sources across 6 types. Mitigation: `sources.d/` directory splits by type, keeping each file focused (~50-350 entries). Migration script outputs split layout by default.
- **Podcast transcription costs**: Tier 1-2 (text transcripts) are free. Tier 3 (audio STT) costs $0.006/min. With transcript-first strategy, most podcasts won't need audio transcription. Mitigation: `transcribe: false` default for bulk import, enable selectively.
- **YouTube API quota**: Channel resolution uses 1 unit per call (10,000 daily quota). With ~120 channels, this is negligible. Playlist ingestion uses existing quota. RSS feeds use zero quota.
- **STT dependency**: Adds OpenAI Whisper as a new dependency for podcast audio fallback. Already have `OPENAI_API_KEY`.
- **YouTube OAuth expiry**: Token expires periodically, blocking private playlist access. Mitigation: `visibility` flag enables graceful degradation — public playlists and channels continue via API key.

## Open Questions

1. Should podcast audio transcription (Tier 3) be synchronous or queued via Celery for long episodes?
2. Should YouTube RSS feeds trigger transcript fetching (requires video ID extraction)?
