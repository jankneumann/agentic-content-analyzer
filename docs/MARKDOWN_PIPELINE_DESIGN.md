# Markdown Pipeline Design

This document describes how markdown content flows through the agentic newsletter aggregator system—from ingestion through storage, processing, and rendering.

## Overview

The system uses a **markdown-first architecture** where all content is normalized to markdown as the canonical format. This design optimizes for:

1. **LLM consumption**: Markdown is structured but not verbose like HTML
2. **Universal rendering**: Works in terminals, web, and documentation
3. **Storage efficiency**: ~60-80% smaller than equivalent HTML
4. **Pipeline consistency**: Single format throughout the entire system

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   INGESTION     │ → │    STORAGE      │ → │   PROCESSING    │ → │   RENDERING     │
│                 │    │                 │    │                 │    │                 │
│ Gmail/RSS/      │    │ Content.        │    │ Summarizer →    │    │ ReactMarkdown   │
│ YouTube/Files   │    │ markdown_content│    │ Digest Creator  │    │ + Tailwind prose│
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 1. Ingestion & Parsing

### Entry Points

The system supports four primary content sources, all using the unified Content model:

| Source | Service Class | Parser |
|--------|---------------|--------|
| Gmail | `GmailContentIngestionService` | `HtmlMarkdownConverter` |
| RSS | `RSSContentIngestionService` | `HtmlMarkdownConverter` |
| YouTube | `YouTubeContentIngestionService` | `YouTubeParser` |
| Files | `FileContentIngestionService` | `ParserRouter` |

### HTML-to-Markdown Conversion

The `HtmlMarkdownConverter` (`src/parsers/html_markdown.py`) implements a two-tier extraction strategy:

```python
converter = HtmlMarkdownConverter()

# RSS: URL-based extraction (fetches full article from source)
result = await converter.convert(url="https://example.com/article")

# Gmail: Raw HTML extraction
result = await converter.convert(html="<html>...</html>")
```

**Extraction Tiers:**
1. **Primary (Trafilatura)**: Fast, academic-quality extraction (~50ms)
2. **Fallback (Crawl4AI)**: JS rendering for dynamic content (~2-5s, disabled by default)

**Quality Validation:**
- Minimum length threshold (200 chars)
- Structure checks (headings, paragraphs)
- Code block integrity (balanced ``` markers)

### Parser Routing

The `ParserRouter` (`src/parsers/router.py`) routes documents to specialized parsers:

| Parser | Formats | Use Case |
|--------|---------|----------|
| `MarkItDownParser` | docx, pptx, xlsx, html, mp3, wav, epub, msg | Fast, lightweight |
| `DoclingParser` | pdf, docx, png, jpg, pptx, xlsx | Complex layouts, OCR |
| `YouTubeParser` | youtube | Transcripts with timestamps |

### Output Model

All parsers produce `DocumentContent` (`src/models/document.py`):

```python
@dataclass
class DocumentContent:
    markdown_content: str      # PRIMARY - always populated
    source_path: str           # Original file/URL
    source_format: str         # Detected format
    parser_used: str           # Which parser produced this
    metadata: dict | None      # Title, author, dates, etc.
    tables: list[dict] | None  # Structured table data
    links: list[str] | None    # Extracted URLs
    warnings: list[str] | None # Non-fatal parsing issues
```

## 2. Storage

### Content Model

The unified `Content` model (`src/models/content.py`) stores markdown as the primary field:

```python
class Content(Base):
    __tablename__ = "contents"

    # Source identification
    source_type: ContentSource  # gmail, rss, youtube, file_upload
    source_id: str              # Unique ID from source system
    source_url: str | None      # Original URL if available

    # Identity/Metadata
    title: str
    author: str | None
    publication: str | None
    published_date: datetime

    # Content (Markdown First)
    markdown_content: str       # PRIMARY CONTENT FIELD
    tables_json: dict | None    # Structured table extraction
    links_json: list | None     # Extracted URLs
    metadata_json: dict | None  # Additional metadata

    # Raw preservation
    raw_content: str | None     # Original HTML/transcript
    raw_format: str | None      # "html", "text", "transcript_json"

    # Parsing metadata
    parser_used: str | None     # "trafilatura", "docling", etc.
    content_hash: str | None    # SHA-256 for deduplication

    # Processing status
    status: ContentStatus       # pending → parsing → parsed → completed
```

### Deduplication

Content is deduplicated using SHA-256 hashing on normalized markdown:

```python
from src.utils.content_hash import generate_markdown_hash

content_hash = generate_markdown_hash(markdown_content)
```

Duplicate detection checks both `source_id` (exact match) and `content_hash` (cross-source duplicate).

## 3. Processing

### Summarization Pipeline

The `ContentSummarizer` (`src/processors/summarizer.py`) processes markdown through LLM agents:

```
Content.markdown_content
    ↓
LLM Agent (SUMMARIZATION step)
    ↓
Structured JSON extraction
    ↓
generate_summary_markdown()
    ↓
Summary.markdown_content
```

**Summary Generation** (`src/utils/summary_markdown.py`):

```python
def generate_summary_markdown(summary_data: dict) -> str:
    """Convert structured summary data to formatted markdown."""
    # Generates sections:
    # - ## Executive Summary
    # - ## Key Themes
    # - ## Strategic Insights
    # - ## Technical Details
    # - ## Actionable Items
    # - ## Notable Quotes
    # - ## Relevant Links
    # - ## Relevance Scores
```

### Digest Creation

The `DigestCreator` (`src/processors/digest_creator.py`) aggregates summaries into multi-audience digests:

```
Multiple Summary records
    ↓
Theme aggregation + Historical context
    ↓
generate_digest_markdown()
    ↓
Digest.markdown_content
```

**Digest Format** (`src/utils/digest_markdown.py`):

```markdown
# Weekly AI Digest: Jan 13-19, 2025

## Executive Overview
Brief summary for leadership...

## Strategic Insights
CTO-level implications...

## Technical Developments
Developer-focused details...

## Emerging Trends
New topics with historical context...

## Actionable Recommendations
Role-specific next steps...

## Sources
- [Article Title](url)
```

### Markdown Utilities

Core utilities in `src/utils/markdown.py`:

```python
# Parse markdown into structured sections
sections = parse_sections(markdown_text)
# → [MarkdownSection(heading="Executive Summary", level=2, items=[...])]

# Extract theme tags from markdown
themes = extract_theme_tags(markdown_text)
# → ["ai-agents", "llm", "machine-learning"]

# Extract relevance scores
scores = extract_relevance_scores(markdown_text)
# → {"technical": 0.8, "strategic": 0.6}

# Handle embedded content markers
markdown = render_with_embeds(markdown_text, embeds)
# Replaces [TABLE:id], [IMAGE:id], [CODE:id] with rendered content
```

## 4. Frontend Rendering

### React Components

The frontend uses `react-markdown` with Tailwind Typography:

```tsx
// web/src/routes/review/summary.$id.tsx
import ReactMarkdown from 'react-markdown';

<div className="prose prose-sm max-w-none dark:prose-invert">
  <ReactMarkdown>
    {content?.markdown_content || ""}
  </ReactMarkdown>
</div>
```

### Styling

| Class | Purpose |
|-------|---------|
| `prose` | Tailwind Typography base styles |
| `prose-sm` | Smaller text size |
| `max-w-none` | Remove max-width constraint |
| `dark:prose-invert` | Dark mode support |

### TypeScript Types

```typescript
// web/src/types/content.ts
interface Content {
  id: number;
  source_type: ContentSource;
  markdown_content: string;      // Primary field
  tables_json: Record<string, unknown>[] | null;
  links_json: string[] | null;
  metadata_json: Record<string, unknown> | null;
  status: ContentStatus;
  // ...
}
```

## 5. Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       INGESTION & PARSING                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Gmail API ────┐                                                    │
│                ├─→ HtmlMarkdownConverter ──→ DocumentContent        │
│  RSS Feeds ────┤      (Trafilatura)           (markdown_content)    │
│                │                                                    │
│  File Upload ──┼─→ ParserRouter ──→ MarkItDown/Docling             │
│                │                                                    │
│  YouTube ──────┴─→ YouTubeParser ──→ Timestamped transcript        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       DATABASE STORAGE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Content Table:                                                     │
│  ├─ markdown_content (TEXT) ← PRIMARY FIELD                        │
│  ├─ raw_content (TEXT) ← Preservation                              │
│  ├─ tables_json, links_json, metadata_json (JSON)                  │
│  ├─ content_hash (SHA-256) ← Deduplication                         │
│  └─ status: pending → parsing → parsed → processing → completed    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       PROCESSING                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Summarizer:                                                        │
│  Content.markdown_content → LLM → generate_summary_markdown()       │
│                                   → Summary                         │
│                                                                     │
│  Theme Analyzer:                                                    │
│  extract_theme_tags() + extract_relevance_scores()                  │
│                                                                     │
│  Digest Creator:                                                    │
│  Summaries[] → LLM → generate_digest_markdown() → Digest           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       API & FRONTEND                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FastAPI:                                                           │
│  GET /api/v1/contents/{id} → Content (markdown_content)            │
│  GET /api/v1/summaries/by-content/{id} → Summary (markdown)        │
│  GET /api/v1/digests/{id} → Digest (markdown)                      │
│                                                                     │
│  React Frontend:                                                    │
│  <ReactMarkdown>{markdown_content}</ReactMarkdown>                  │
│  Styled with Tailwind prose classes                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 6. Key Files Reference

### Parsing Layer
| File | Purpose |
|------|---------|
| `src/parsers/base.py` | `DocumentParser` interface |
| `src/parsers/router.py` | Format-based parser routing |
| `src/parsers/html_markdown.py` | Two-tier HTML conversion |
| `src/parsers/markitdown_parser.py` | Lightweight document parsing |
| `src/parsers/docling_parser.py` | Advanced PDF/image parsing |
| `src/parsers/youtube_parser.py` | YouTube transcript extraction |

### Ingestion Layer
| File | Purpose |
|------|---------|
| `src/ingestion/gmail.py` | Gmail content ingestion |
| `src/ingestion/rss.py` | RSS feed ingestion |
| `src/ingestion/youtube.py` | YouTube playlist ingestion |
| `src/ingestion/files.py` | File upload ingestion |

### Storage Layer
| File | Purpose |
|------|---------|
| `src/models/content.py` | Unified Content model |
| `src/models/document.py` | DocumentContent from parsers |
| `src/utils/content_hash.py` | Deduplication hashing |

### Processing Layer
| File | Purpose |
|------|---------|
| `src/utils/markdown.py` | Core markdown utilities |
| `src/utils/summary_markdown.py` | Summary markdown generation |
| `src/utils/digest_markdown.py` | Digest markdown generation |
| `src/processors/summarizer.py` | Content summarization |
| `src/processors/digest_creator.py` | Digest creation |

### Frontend Layer
| File | Purpose |
|------|---------|
| `web/src/types/content.ts` | TypeScript Content interface |
| `web/src/routes/contents.tsx` | Content list view |
| `web/src/routes/review/summary.$id.tsx` | Summary review page |

## 7. Design Decisions

### Why Markdown-First?

1. **LLM Optimization**: Language models work better with markdown than HTML—it's structured without being verbose
2. **Consistency**: Single format throughout ingestion → storage → processing → rendering
3. **Efficiency**: Markdown is significantly smaller than HTML, reducing storage and API payload sizes
4. **Flexibility**: Easy to render in any context (web, CLI, documentation, email)

### Why Two-Tier Extraction?

1. **Speed**: Trafilatura handles 90%+ of content in ~50ms
2. **Quality**: Crawl4AI fallback catches JS-heavy pages that Trafilatura misses
3. **Cost**: Avoids browser overhead unless necessary

### Why Store Raw Content?

1. **Reprocessing**: Can re-extract with improved parsers later
2. **Debugging**: Compare extracted markdown against source
3. **Audit Trail**: Preserve original for compliance/verification
