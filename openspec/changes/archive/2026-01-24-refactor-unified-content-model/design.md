# Design: Unified Content Model with Markdown-First Storage

## Context

The newsletter aggregator ingests content from multiple sources (Gmail, RSS, file uploads, YouTube) and processes it through summarization and digest creation. The current data model evolved organically, resulting in:

- Newsletter table: Stores ingested content with raw_html/raw_text
- Document table: Stores parsed content with markdown_content, linked to Newsletter via FK
- Summary table: Stores processed summaries with text + JSON list fields
- Digest table: Stores aggregated digests with text + JSON list fields

This creates complexity for:
1. The upcoming search feature (must handle multiple tables/formats)
2. The chunking service (different content fields per table)
3. UI rendering (different structures to handle)
4. LLM prompts (inconsistent input/output formats)

**Stakeholders**: Search feature, UI rendering, LLM processing pipeline, data migrations

**Constraints**:
- Must migrate existing data without loss
- Must support all existing ingestion sources
- Must enable collapsible section UI from markdown
- Must maintain parser integration (all parsers output markdown)

## Goals / Non-Goals

**Goals**:
- Single Content table for all ingested content
- Markdown as canonical storage format
- Consistent section conventions for summaries/digests
- Simplified chunking (one content field to process)
- Enable structured UI rendering from markdown
- Preserve all existing metadata (source, timestamps, deduplication)

**Non-Goals**:
- Changing the parser interfaces (they already output markdown)
- Real-time migration (batch migration is acceptable)
- Backward compatibility for API responses (breaking change is acceptable)
- Supporting non-markdown content formats long-term

## Decisions

### Decision 1: Unified Content Model

**What**: Replace Newsletter and Document tables with a single Content table.

**Why**:
- Eliminates redundant storage (raw_html in Newsletter, markdown_content in Document)
- Single source of truth for all ingested content
- Simplifies foreign keys from Summary, Digest, Chunk tables
- Aligns with how parsers work (input → markdown output)

**Schema**:
```python
class Content(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Source identification
    source_type: Mapped[ContentSource]  # GMAIL, RSS, FILE_UPLOAD, YOUTUBE, etc.
    source_id: Mapped[str]  # Unique ID from source (email ID, RSS guid, file hash, video ID)
    source_url: Mapped[str | None]  # Original URL if available

    # Identity
    title: Mapped[str]
    author: Mapped[str | None]  # Sender for email, channel for YouTube, author for docs
    publication: Mapped[str | None]  # Newsletter name, channel name
    published_date: Mapped[datetime | None]

    # Canonical content - MARKDOWN FIRST
    markdown_content: Mapped[str]  # Primary content, always populated

    # Structured extractions (parsed from markdown or source)
    tables_json: Mapped[dict | None]  # List of TableData for complex table queries
    links_json: Mapped[list | None]  # Extracted URLs for link analysis
    metadata_json: Mapped[dict | None]  # Title, page_count, word_count, language, etc.

    # Raw preservation (optional, for re-parsing)
    raw_content: Mapped[str | None]  # Original HTML, transcript JSON, etc.
    raw_format: Mapped[str | None]  # "html", "text", "transcript_json", "pdf_base64"

    # Parsing metadata
    parser_used: Mapped[str | None]  # "DoclingParser", "YouTubeParser", "MarkItDownParser"
    parser_version: Mapped[str | None]  # For tracking re-parsing needs

    # Deduplication
    content_hash: Mapped[str]  # SHA-256 of normalized markdown
    canonical_id: Mapped[int | None]  # FK to canonical Content if this is a duplicate

    # Processing status
    status: Mapped[ProcessingStatus]  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message: Mapped[str | None]

    # Timestamps
    ingested_at: Mapped[datetime]
    parsed_at: Mapped[datetime | None]
    processed_at: Mapped[datetime | None]  # When summarization completed

    # Relationships
    summary: Mapped["Summary"] = relationship(back_populates="content")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="content")
```

**Migration from Newsletter + Document**:
```sql
INSERT INTO contents (
    source_type, source_id, source_url,
    title, author, publication, published_date,
    markdown_content,
    tables_json, links_json, metadata_json,
    raw_content, raw_format,
    parser_used, parser_version,
    content_hash, canonical_id,
    status, error_message,
    ingested_at, parsed_at, processed_at
)
SELECT
    n.source, n.source_id, n.url,
    n.title, n.sender, n.publication, n.published_date,
    COALESCE(d.markdown_content, n.raw_text, ''),  -- Prefer parsed markdown
    d.tables_json, COALESCE(d.links_json, n.extracted_links), d.metadata_json,
    n.raw_html, 'html',
    d.parser_used, NULL,
    COALESCE(d.file_hash, n.content_hash), n.canonical_newsletter_id,
    n.status, COALESCE(d.error_message, n.error_message),
    n.ingested_at, d.processed_at, n.processed_at
FROM newsletters n
LEFT JOIN documents d ON d.newsletter_id = n.id;
```

### Decision 2: Markdown as Canonical Format

**What**: Store all content as markdown, including summaries and digests.

**Why**:
- LLMs generate markdown naturally
- Parsers already output markdown
- Enables consistent chunking
- Human-readable and editable
- Supports rich formatting (headings, lists, tables, links)

**Format Conventions**:

**For Ingested Content**:
```markdown
# [Title from source]

[Body content as markdown]

## Tables
[TABLE:benchmark-results]: Performance comparison across models

## Links
- [Original article](https://...)
- [Related paper](https://arxiv.org/...)
```

**For Summaries** (replaces JSON fields):
```markdown
# Summary: [Newsletter Title]

## Executive Summary
[2-3 sentence overview]

## Key Themes
- **[Theme 1]**: [Description]
- **[Theme 2]**: [Description]

## Strategic Insights
### [Insight Title 1]
[Relevance: CTO, Engineering]
[Detailed insight content]

### [Insight Title 2]
[Relevance: Product, Design]
[Detailed insight content]

## Technical Details
- [Technical point 1]
- [Technical point 2]

## Actionable Items
- [ ] [Action 1]
- [ ] [Action 2]

## Notable Quotes
> "[Quote 1]" — Source

## Relevance Scores
- Leadership: 0.8
- Engineering: 0.9
- Product: 0.6
```

**For Digests** (replaces JSON fields):
```markdown
# [Digest Type] Digest: [Date Range]

## Executive Overview
[2-3 paragraph summary of the period]

## Strategic Insights
### [Insight 1 Title]
[Relevance: CTO, VP Engineering]
[Content]
[Sources: Content #123, #145]

### [Insight 2 Title]
...

## Technical Developments
### [Development 1]
...

## Emerging Trends
### [Trend 1]
[First seen: 2024-06-01]
[Mentions: 5]
[Content]

## Actionable Recommendations
### For Leadership
- [Recommendation 1]
- [Recommendation 2]

### For Engineering
- [Recommendation 1]

## Sources
| # | Title | Publication | Date |
|---|-------|-------------|------|
| 123 | AI Weekly | TechCrunch | 2024-06-15 |
```

### Decision 3: Embedded References for Structured Elements

**What**: Use a convention for referencing structured data within markdown.

**Why**:
- Tables with complex data need queryable JSON storage
- Images/media need separate storage
- Maintains markdown readability while preserving structure

**Pattern**:
```markdown
Results are shown below:

[TABLE:benchmark-001]: Model performance across datasets

The architecture diagram:

[IMAGE:arch-001]: Transformer with sparse attention

Code example:

[CODE:example-001]: Python implementation
```

**Storage**:
```python
# In Content.tables_json
{
    "benchmark-001": {
        "caption": "Model performance across datasets",
        "headers": ["Model", "Accuracy", "Latency"],
        "rows": [["GPT-4", "94.2%", "120ms"], ...]
    }
}

# In Content.metadata_json
{
    "images": {
        "arch-001": {"path": "/uploads/arch-001.png", "alt": "Transformer..."}
    },
    "code_blocks": {
        "example-001": {"language": "python", "content": "def ..."}
    }
}
```

**Rendering**: UI parses markdown, replaces `[TABLE:id]` with rendered table from JSON.

### Decision 4: Summary Model Refactor

**What**: Refactor Summary to use markdown_content instead of separate JSON fields.

**Current**:
```python
class Summary(Base):
    executive_summary: str
    key_themes: JSON  # list[str]
    strategic_insights: JSON  # list[str]
    technical_details: JSON  # list[str]
    actionable_items: JSON  # list[str]
    notable_quotes: JSON  # list[str]
    relevant_links: JSON  # list[dict]
    relevance_scores: JSON  # dict[str, float]
```

**Proposed**:
```python
class Summary(Base):
    id: int
    content_id: int  # FK to Content (was newsletter_id)

    # Canonical content
    markdown_content: str  # Full summary as structured markdown

    # Extracted for querying/filtering (derived from markdown)
    theme_tags: JSON  # ["attention", "scaling", "cost"] for filtering
    relevance_scores: JSON  # {"leadership": 0.8, "engineering": 0.9}

    # Processing metadata
    agent_framework: str
    model_used: str
    model_version: str
    token_usage: int
    processing_time_seconds: float
    created_at: datetime
```

**Benefits**:
- LLM generates markdown directly (no JSON parsing/formatting)
- Sections naturally map to collapsible UI
- Easier to edit/review
- Consistent with Content model

### Decision 5: Digest Model Refactor

**What**: Similar refactor for Digest model.

**Current**:
```python
class Digest(Base):
    executive_overview: str
    strategic_insights: JSON  # list[dict]
    technical_developments: JSON  # list[dict]
    emerging_trends: JSON  # list[dict]
    actionable_recommendations: JSON  # dict[str, list[str]]
    sources: JSON  # list[dict]
    historical_context: JSON
```

**Proposed**:
```python
class Digest(Base):
    id: int
    digest_type: DigestType  # DAILY, WEEKLY, SUB_DIGEST
    period_start: datetime
    period_end: datetime

    # Canonical content
    markdown_content: str  # Full digest as structured markdown
    title: str  # Extracted/generated title

    # Extracted for querying (derived from markdown)
    theme_tags: JSON  # Aggregated themes for filtering
    source_content_ids: JSON  # list[int] - Content IDs included

    # Hierarchy
    parent_digest_id: int | None
    child_digest_ids: JSON  # list[int]

    # Review workflow
    status: DigestStatus
    reviewed_by: str | None
    review_notes: str | None
    reviewed_at: datetime | None

    # Processing metadata
    agent_framework: str
    model_used: str
    token_usage: int
    processing_time_seconds: float
    created_at: datetime
```

### Decision 6: Section Parsing for UI

**What**: Provide utilities to parse markdown sections for UI rendering.

**Implementation**:
```python
from dataclasses import dataclass
import re

@dataclass
class MarkdownSection:
    level: int  # 1 for H1, 2 for H2, etc.
    title: str
    content: str  # Raw markdown content of section
    metadata: dict  # Extracted [Key: Value] patterns
    subsections: list["MarkdownSection"]

def parse_sections(markdown: str) -> list[MarkdownSection]:
    """Parse markdown into hierarchical sections for UI rendering."""
    # Split on heading patterns
    # Build tree structure
    # Extract metadata like [Relevance: CTO, Engineering]
    ...

def extract_theme_tags(markdown: str) -> list[str]:
    """Extract theme tags from ## Key Themes section."""
    ...

def extract_relevance_scores(markdown: str) -> dict[str, float]:
    """Extract relevance scores from ## Relevance Scores section."""
    ...
```

**UI Usage**:
```typescript
const sections = parseMarkdownSections(summary.markdown_content);

return (
  <div>
    {sections.map(section => (
      <CollapsibleSection
        key={section.title}
        title={section.title}
        defaultOpen={section.level <= 2}
      >
        <MarkdownRenderer content={section.content} />
        {section.subsections.map(sub => (
          <CollapsibleSection key={sub.title} title={sub.title}>
            <MarkdownRenderer content={sub.content} />
          </CollapsibleSection>
        ))}
      </CollapsibleSection>
    ))}
  </div>
);
```

### Decision 7: Unified Image Storage and References

**What**: Store all images (extracted, keyframes, AI-generated) in a dedicated `images` table with consistent markdown references.

**Why**:
- Images come from multiple sources: extracted from articles, YouTube keyframes, future AI generation
- Need consistent storage and referencing across content, summaries, and digests
- Must support provenance tracking (where did this image come from?)
- Prepares for AI-assisted image generation in revision workflows

**Image Sources**:

| Source | Description | Metadata |
|--------|-------------|----------|
| **EXTRACTED** | Pulled from article HTML/PDF | Original URL, alt text |
| **KEYFRAME** | YouTube video frame (from KeyframeExtractor) | Video ID, timestamp, deep-link URL |
| **AI_GENERATED** | Created by AI during revision | Prompt, model, parameters |

**Image Model**:
```python
class Image(Base):
    __tablename__ = "images"

    id: Mapped[str]  # UUID for URL-safe references

    # Source tracking
    source_type: Mapped[ImageSource]  # EXTRACTED, KEYFRAME, AI_GENERATED
    source_content_id: Mapped[int | None]  # FK to contents (for extracted)
    source_summary_id: Mapped[int | None]  # FK to summaries (for AI-generated)
    source_digest_id: Mapped[int | None]  # FK to digests (for AI-generated)
    source_url: Mapped[str | None]  # Original URL if extracted

    # YouTube keyframe metadata
    video_id: Mapped[str | None]
    timestamp_seconds: Mapped[float | None]
    deep_link_url: Mapped[str | None]  # youtube.com/watch?v=xxx&t=123

    # Storage
    storage_path: Mapped[str]  # Path in object storage or filesystem
    storage_provider: Mapped[str]  # "local", "s3"

    # File metadata
    filename: Mapped[str]
    mime_type: Mapped[str]  # image/png, image/jpeg, image/webp
    width: Mapped[int | None]
    height: Mapped[int | None]
    file_size_bytes: Mapped[int]

    # Semantic metadata
    alt_text: Mapped[str | None]  # Accessibility
    caption: Mapped[str | None]  # Human-readable description
    ai_description: Mapped[str | None]  # AI-generated description for search

    # AI generation metadata (for future)
    generation_prompt: Mapped[str | None]
    generation_model: Mapped[str | None]
    generation_params: Mapped[dict | None]  # JSON

    # Deduplication
    phash: Mapped[str | None]  # Perceptual hash (from KeyframeExtractor)

    # Lifecycle
    created_at: Mapped[datetime]
```

**Markdown Reference Patterns**:

Standard image reference:
```markdown
The benchmark results are visualized below:

[IMAGE:img-abc123]: Performance comparison chart

As we can see, the new model outperforms...
```

YouTube keyframe with timestamp link:
```markdown
The presenter explains the architecture:

[IMAGE:img-def456]: Architecture diagram at 2:34
[Watch at 2:34](https://youtube.com/watch?v=xxx&t=154)

This shows the attention mechanism...
```

Combined reference (image + video link):
```markdown
[IMAGE:img-def456|video=xxx&t=154]: Slide explaining attention mechanism
```

**Storage Strategy**:

| Environment | Storage | Path Pattern |
|-------------|---------|--------------|
| Development | Local filesystem | `./uploads/images/{id}.{ext}` |
| Production | S3-compatible | `s3://bucket/images/{id}.{ext}` |

**Image Extraction Pipeline**:
```python
class ImageExtractor:
    def extract_from_content(self, content: Content) -> list[Image]:
        """Extract images from content markdown and source."""
        images = []

        # 1. Parse [IMAGE:...] references already in markdown
        # 2. Download external images from source URLs
        # 3. Extract embedded images from HTML/PDF
        # 4. Generate perceptual hashes for dedup
        # 5. Upload to storage
        # 6. Create Image records

        return images

    def extract_youtube_keyframes(self, content: Content) -> list[Image]:
        """Extract keyframes using existing KeyframeExtractor."""
        # Leverages existing src/ingestion/youtube_keyframes.py
        # Creates Image records with KEYFRAME source_type
        # Includes timestamp and deep_link_url
        pass
```

**Future AI Generation Integration**:
```python
class ImageGenerator:
    def generate_for_summary(
        self,
        summary: Summary,
        prompt: str,
        style: str = "professional"
    ) -> Image:
        """Generate image for summary during revision workflow."""
        # 1. Call AI image generation API (DALL-E, Midjourney, etc.)
        # 2. Upload result to storage
        # 3. Create Image record with AI_GENERATED source_type
        # 4. Store prompt and parameters for reproducibility
        pass

    def suggest_images(self, content: str) -> list[ImageSuggestion]:
        """Suggest images to generate based on content."""
        # Analyze content for visualization opportunities
        # Return suggestions with prompts
        pass
```

**UI Integration**:
```typescript
// Render markdown with image resolution
function renderMarkdown(markdown: string, images: Record<string, Image>) {
  return markdown.replace(
    /\[IMAGE:([^\]|]+)(?:\|([^\]]+))?\]: ([^\n]+)/g,
    (match, id, params, caption) => {
      const image = images[id];
      if (!image) return match;

      const videoLink = params?.match(/video=([^&]+)&t=(\d+)/);

      return `
        <figure>
          <img src="${image.url}" alt="${image.alt_text || caption}" />
          <figcaption>${caption}</figcaption>
          ${videoLink ? `<a href="https://youtube.com/watch?v=${videoLink[1]}&t=${videoLink[2]}">Watch video</a>` : ''}
        </figure>
      `;
    }
  );
}
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data migration complexity | Data loss, downtime | Thorough testing, backup, staged rollout |
| API breaking changes | Client updates needed | Version API, deprecation period |
| Markdown parsing overhead | Slower UI rendering | Cache parsed sections, parse on write |
| Loss of query flexibility | Can't query JSON fields directly | Extract key fields to indexed columns |
| LLM output format changes | Inconsistent markdown | Strong prompt engineering, validation |
| Image storage costs | Increased storage needs | Compression, dedup via phash, lazy extraction |
| External image availability | Source images may disappear | Download and store locally on extraction |

## Migration Plan

1. **Phase 1: Create new schema** (non-breaking)
   - Create `contents` table alongside existing tables
   - Add `markdown_content` column to Summary and Digest
   - Deploy new models with dual-write capability

2. **Phase 2: Migrate data**
   - Batch migrate Newsletter + Document → Content
   - Generate markdown for existing Summary/Digest records
   - Validate migrated data

3. **Phase 3: Update application code**
   - Update ingestion to write to Content
   - Update summarizer/digest_creator to output markdown
   - Update API responses
   - Update UI to render from markdown

4. **Phase 4: Cleanup**
   - Remove dual-write
   - Drop deprecated tables (newsletters, documents)
   - Remove deprecated JSON columns from Summary/Digest

5. **Rollback**: Restore from backup, revert code changes

## Open Questions

1. Should we keep raw_content for all sources or only for formats that benefit from re-parsing?
2. Should theme_tags and relevance_scores be extracted at write time or computed on read?
3. How do we handle existing API clients during the transition?
4. Should we version the markdown format conventions?
