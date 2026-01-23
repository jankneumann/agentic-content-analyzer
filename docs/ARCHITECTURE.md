# Architecture

## Technology Stack

- **Language**: Python 3.11+
- **Package Management**: uv
- **Databases**:
  - PostgreSQL + SQLAlchemy (structured data: newsletters, summaries, digests)
  - Graphiti + Neo4j (knowledge graph: concepts, themes, temporal relationships)
- **Agent Frameworks**: Multi-framework approach for comparison
  - Claude SDK (Anthropic) - Primary
  - OpenAI SDK (Agents/Assistants API)
  - Google ADK (Agent Development Kit)
  - Microsoft Agent Framework (Semantic Kernel or AutoGen)
- **Ingestion**: Gmail API, feedparser (RSS)
- **Task Queue**: Celery + Redis
- **Web**: FastAPI (APIs, web UI)
- **Testing**: pytest

## System Architecture

```
src/
  agents/           # Agent framework implementations
    base.py         # Abstract base classes
    claude/         # Claude SDK agents (primary)
    openai/         # OpenAI SDK agents
    google/         # Google ADK agents
    microsoft/      # MS Agent Framework agents
  ingestion/        # Content fetching and parsing
    gmail.py        # Gmail API integration
    rss.py          # RSS feed parser (Substack, etc.)
    youtube.py      # YouTube playlist/transcript ingestion
    files.py        # File upload processing
  models/           # Data models (Pydantic + SQLAlchemy)
    content.py      # Unified Content model (primary)
    newsletter.py   # Legacy Newsletter model (deprecated)
    summary.py      # NewsletterSummary model
    digest.py       # Digest model
    theme.py        # ThemeAnalysis model
    document.py     # Legacy Document model (deprecated)
  parsers/          # Document parsing
    base.py         # DocumentParser interface
    markitdown_parser.py  # Office docs, HTML, audio
    docling_parser.py     # Advanced PDF parsing with OCR
    youtube_parser.py     # YouTube transcript parsing
    router.py       # Parser routing and fallback
  services/         # Business logic
    content_service.py    # Content CRUD and deduplication
  storage/          # Data persistence
    database.py     # PostgreSQL
    graphiti_client.py  # Graphiti MCP integration
  processors/       # Core processing
    summarizer.py
    theme_analyzer.py
    digest_creator.py
    historical_context.py
  delivery/         # Output channels
    email.py
    tts_service.py  # Text-to-speech for podcasts
  utils/            # Shared utilities
    markdown.py     # Markdown parsing and rendering
    summary_markdown.py   # Summary markdown templates
    digest_markdown.py    # Digest markdown templates
    content_hash.py       # Content deduplication hashing
  tasks/            # Celery tasks
  api/              # FastAPI app
  config/           # Configuration
    models.py       # Model registry and configuration
    settings.py     # Application settings
    model_registry.yaml  # Model definitions and provider configs
```

## Key Workflows

### Newsletter Processing Pipeline

1. **Ingestion**: Fetch from Gmail/Substack → Parse content → Store raw
2. **Summarization**: Individual newsletter → Structured summary → Extract entities
3. **Knowledge Graph**: Store entities/relationships in Graphiti (concepts, temporal evolution)
4. **Theme Analysis**: Query Graphiti for common themes, trending topics, historical context
5. **Digest Generation**: Multi-audience formatting (CTO strategy + developer tactics)
6. **Delivery**: Email/web with daily/weekly schedules

### Knowledge Graph (Graphiti) Usage

- **Entity Extraction**: Technical concepts, companies, products, people, methodologies
- **Relationship Tracking**: How topics relate, co-occurrence patterns
- **Temporal Analysis**: Track concept evolution over time, identify emerging trends
- **Historical Context**: "We first discussed X when...", "This relates to previous theme Y..."
- **Queries**: "What topics are related to RAG?", "How has AI regulation discussion evolved?"

### Agent Framework Pattern

Each framework implementation provides:
- Newsletter summarization agent
- Theme analysis agent
- Digest generation agent
- Consistent interfaces for comparison

This enables **direct performance comparisons** across frameworks:
- API design differences
- Tool use patterns
- Orchestration approaches
- Performance (speed, quality, token usage)
- Cost implications

## Data Models

### Content (Primary - Unified Model)
The unified Content model is the primary data model for all ingested content:

- **Source Types**: GMAIL, RSS, YOUTUBE, FILE_UPLOAD
- **Source Tracking**: source_id, source_url for deduplication
- **Parsed Content**: markdown_content (LLM-optimized)
- **Structured Data**: tables_json, links_json, metadata_json
- **Raw Storage**: raw_content, raw_format for re-parsing
- **Parser Info**: parser_used, parser_version
- **Deduplication**: content_hash (SHA-256 of normalized markdown), canonical_id (FK to canonical record)
- **Status Tracking**: status, error_message, ingested_at, parsed_at, processed_at

```python
class ContentSource(str, Enum):
    GMAIL = "gmail"
    RSS = "rss"
    YOUTUBE = "youtube"
    FILE_UPLOAD = "file_upload"
```

### Newsletter (Deprecated)
Legacy model retained for backward compatibility. New code should use Content model.

- Source metadata (Gmail, RSS)
- Raw content (HTML, text)
- Processing status
- Publication information

### NewsletterSummary
- Linked to Content via content_id (and legacy newsletter_id)
- **markdown_content**: Full summary as structured markdown
- **theme_tags**: Extracted theme tags for cross-referencing
- Structured extraction with key themes, insights, technical details
- Relevance scores (CTO, teams, individuals)
- Model and cost tracking

### ThemeAnalysis
- Cross-newsletter theme detection
- Trend classification (emerging, growing, established)
- Historical context integration
- Relevance scoring

### Digest
- Multi-audience formatted output
- **markdown_content**: Complete digest as structured markdown
- **theme_tags**: Aggregated theme tags from summaries
- **source_content_ids**: List of Content IDs used in digest
- Strategic insights (CTO-level)
- Technical developments (practitioner-level)
- Emerging trends with historical context
- Actionable recommendations per role

## Markdown Format Conventions

All processed content uses markdown for LLM-optimized storage and rendering.

### Summary Markdown Structure
```markdown
# Newsletter Summary: {title}

## Executive Summary
Brief 2-3 sentence overview for leadership.

## Key Themes
- **Theme 1**: Description
- **Theme 2**: Description

## Strategic Insights
CTO-level implications and recommendations.

## Technical Details
Developer-focused technical information.

## Actionable Items
- [ ] Action item 1
- [ ] Action item 2

## Relevance Scores
- **CTO**: 0.85
- **Engineering Teams**: 0.75
- **Individual Contributors**: 0.65
```

### Embedded Reference Patterns
Content can embed references to tables and images:

- `[TABLE:id]` - References a table from tables_json
- `[IMAGE:id]` - References an image (with optional params: `[IMAGE:id|video=xxx&t=123]`)
- `[CODE:id]` - References a code block

The `render_with_embeds()` utility replaces these with actual content.

## Ingestion Services

### Gmail Ingestion (`GmailContentIngestionService`)
- Uses Gmail API with OAuth2 credentials
- Filters by labels/sender for newsletter detection
- Extracts HTML body → converts to markdown via `HtmlMarkdownConverter`
- Deduplicates by `source_id` (message ID)

### RSS Ingestion (`RSSContentIngestionService`)
- Processes feeds from `substack_feeds.txt` configuration
- Uses feedparser for Atom/RSS parsing
- **Timezone handling**: `published_parsed` returns UTC but as naive struct_time - always add `tzinfo=UTC`:
  ```python
  datetime(*entry.published_parsed[:6], tzinfo=UTC)  # Correct
  ```
- Supports `--after-date` filtering for incremental ingestion

### YouTube Ingestion (`YouTubeContentIngestionService`)
- Uses YouTube Data API (OAuth for private, API key for public playlists)
- Fetches video metadata and transcripts via `youtube-transcript-api`
- Generates timestamped markdown with deep links (`youtu.be/xxx?t=123`)
- Playlist config file: `youtube_playlists.txt` with `PLAYLIST_ID | description` format
- API key fallback: `settings.get_youtube_api_key()` returns YOUTUBE_API_KEY or falls back to GOOGLE_API_KEY

### File Upload Ingestion (`FileContentIngestionService`)
- Processes uploads via `ParserRouter` → stores as Content records
- SHA-256 file hash for deduplication, links duplicates to canonical record
- API endpoint: `POST /api/v1/documents/upload` (multipart form data)
- Size limits: `MAX_UPLOAD_SIZE_MB`, `DOCLING_MAX_FILE_SIZE_MB` settings

## Parser Ecosystem

### Parser Interface
All parsers implement `DocumentParser` interface from `src/parsers/base.py`:
- Input: File bytes or URL
- Output: `DocumentContent` with markdown_content, tables, metadata

### Parser Router
`ParserRouter` selects appropriate parser based on file format:
1. Checks file extension/MIME type
2. Routes to specialized parser (or default)
3. Fallback chain for resilience

### Available Parsers

| Parser | Formats | Use Case |
|--------|---------|----------|
| `MarkItDownParser` | Office docs, HTML, audio | Lightweight, fast (~50ms) |
| `DoclingParser` | PDF, complex layouts | OCR support, table extraction |
| `YouTubeParser` | YouTube URLs | Transcript with timestamps |

### HTML-to-Markdown Conversion
`HtmlMarkdownConverter` in `src/parsers/html_markdown.py`:
- Primary: Trafilatura extraction (~50ms) for academic-quality markdown
- Dual input: `url=` for RSS feeds, `html=` for Gmail
- Async-native: `await converter.convert()` in async contexts
- Quality validation: `validate_markdown_quality()` checks structure
- Batch processing: `batch_convert()` with semaphore limiting

## Processing Stages

### Stage 1: Ingestion
**Input**: Gmail messages, RSS feeds, YouTube playlists, uploaded files
**Output**: Content records with parsed markdown
**Technology**: Gmail API, feedparser, YouTube Data API, ParserRouter
**Services**:
- `GmailContentIngestionService` - Email ingestion
- `RSSContentIngestionService` - RSS/Atom feeds
- `YouTubeContentIngestionService` - YouTube transcripts with timestamps
- `FileContentIngestionService` - PDF, DOCX, PPTX, etc.

### Stage 2: Summarization
**Input**: Content markdown_content
**Output**: NewsletterSummary with markdown_content and theme_tags
**Technology**: Claude Haiku (default), Pydantic validation
**Cost**: ~$0.01-0.02 per content item

### Stage 3: Knowledge Graph Population
**Input**: Newsletter summaries
**Output**: Entities and relationships in Graphiti
**Technology**: Graphiti MCP, Neo4j
**Purpose**: Enable temporal analysis and historical context

### Stage 4: Theme Analysis
**Input**: Multiple summaries + Graphiti context
**Output**: Cross-cutting themes with trends and relevance
**Technology**: Claude Sonnet (default), Graphiti queries
**Cost**: ~$0.05-0.10 per analysis (5-10 newsletters)

### Stage 5: Digest Creation
**Input**: Theme analysis + historical context
**Output**: Multi-audience formatted digest
**Technology**: Claude Sonnet (default)
**Cost**: ~$0.10-0.15 per digest

### Stage 6: Delivery
**Input**: Completed digest
**Output**: Email, web view
**Technology**: SendGrid (email), FastAPI (web)

## Scalability Considerations

- **Database**: PostgreSQL with indexes on frequently queried fields (status, dates)
- **Async Processing**: Celery for background tasks, Redis for task queue
- **Knowledge Graph**: Neo4j optimized for temporal queries
- **Caching**: Redis for frequently accessed data
- **Provider Failover**: Automatic fallback across multiple LLM providers
- **Cost Control**: Configurable model selection per pipeline step

## API Endpoints

### Content API (`/api/v1/contents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contents` | List contents with pagination and filtering |
| GET | `/contents/{id}` | Get single content with legacy newsletter ID |
| POST | `/contents` | Create content manually |
| DELETE | `/contents/{id}` | Delete content |
| GET | `/contents/stats` | Statistics by source type and status |
| GET | `/contents/{id}/duplicates` | Find duplicate content |
| POST | `/contents/{id}/merge/{duplicate_id}` | Merge duplicate records |
| POST | `/contents/ingest` | Trigger background ingestion |
| GET | `/contents/ingest/status/{task_id}` | SSE progress stream |

### Summary API (`/api/v1/summaries`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/summaries` | List summaries with pagination |
| GET | `/summaries/{id}` | Get summary detail with markdown_content |
| GET | `/summaries/by-content/{content_id}` | Get summary by content ID |
| POST | `/summaries/trigger` | Trigger summarization |
| GET | `/summaries/stats` | Summary statistics |

### Newsletter API (`/api/v1/newsletters`) - DEPRECATED
All newsletter endpoints are deprecated with `Sunset: 2026-06-01` header.
Use Content API instead. Legacy endpoints maintained for backward compatibility.

### Document Upload API (`/api/v1/documents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload and parse document |
| GET | `/documents/formats` | List supported formats |
| GET | `/documents/{id}` | Get document status |

## Migration Guide for API Clients

### From Newsletter to Content API

**Before (deprecated):**
```python
# List newsletters
response = requests.get("/api/v1/newsletters")

# Get newsletter
response = requests.get(f"/api/v1/newsletters/{newsletter_id}")
```

**After (recommended):**
```python
# List contents
response = requests.get("/api/v1/contents")

# Get content
response = requests.get(f"/api/v1/contents/{content_id}")

# Get summary by content
response = requests.get(f"/api/v1/summaries/by-content/{content_id}")
```

### Key Differences

1. **Source Types**: Content has explicit `source_type` field (gmail, rss, youtube, file_upload)
2. **Markdown First**: `markdown_content` is primary, `raw_content` stored for re-parsing
3. **Deduplication**: Built-in via `content_hash` and `canonical_id`
4. **Richer Metadata**: `tables_json`, `links_json`, `metadata_json` for structured data
