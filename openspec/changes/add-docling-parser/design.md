# Design: Add Docling Parser Integration

## Overview

This document captures architectural decisions for integrating Docling as an advanced document parser alongside the existing MarkItDown parser.

## Architecture Context

### Current State

```
                    ParserRouter
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   MarkItDown       YouTube          (empty)
   (11 formats)   (transcripts)
        │                │
        └────────────────┴────────────────┘
                         │
                         ▼
                 DocumentContent
```

### Target State

```
                    ParserRouter
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   MarkItDown       YouTube          Docling
   (lightweight)   (transcripts)    (advanced)
        │                │                │
        └────────────────┴────────────────┘
                         │
                         ▼
                 DocumentContent
                         │
                         ▼
              FileIngestionService
                         │
                         ▼
                 Newsletter Model
```

## Key Design Decisions

### Decision 1: Optional Parser Registration

**Context**: Docling has heavy dependencies (ML models, ~2GB disk space). Not all deployments need it.

**Decision**: DoclingParser is optional. Router only routes to it if explicitly provided.

**Implementation**:
```python
# Router accepts optional parser
router = ParserRouter(
    markitdown_parser=markitdown,
    youtube_parser=youtube,
    docling_parser=docling if settings.enable_docling else None
)

# Router checks availability before routing
def route(self, source, **kwargs):
    if format == "pdf" and self.has_docling:
        return self.parsers["docling"]
    return self.parsers["markitdown"]  # fallback
```

**Trade-offs**:
- (+) Lighter deployments possible without Docling
- (+) Graceful degradation when Docling unavailable
- (-) PDF quality varies based on deployment configuration

### Decision 2: Markdown as Primary Output

**Context**: Docling can export to multiple formats (Markdown, HTML, JSON, DocTags).

**Decision**: Use Markdown as primary output, with optional structured data extraction.

**Rationale**:
1. Consistency with MarkItDown output
2. LLMs are trained extensively on Markdown
3. Existing pipeline expects `markdown_content` field
4. Structured data (tables) captured separately when available

**Implementation**:
```python
def parse(self, source) -> DocumentContent:
    result = self.converter.convert(source)
    doc = result.document

    return DocumentContent(
        markdown_content=doc.export_to_markdown(),  # Primary
        tables=self._extract_tables(doc),           # Bonus structured data
        metadata=self._extract_metadata(doc),
        parser_used="docling"
    )
```

### Decision 3: Lazy Table Extraction

**Context**: Extracting structured tables is expensive and not always needed.

**Decision**: Always extract tables during parsing, but store as JSON for optional use.

**Rationale**:
1. Parse operation is already expensive; incremental cost is small
2. Tables are valuable for RAG and structured queries
3. Markdown representation always available as fallback
4. Storage cost is minimal (JSON in database)

**Implementation**:
```python
class TableData(BaseModel):
    caption: Optional[str] = None
    headers: list[str] = []
    rows: list[list[str]] = []
    markdown: str  # Always populated as fallback
```

### Decision 4: File Ingestion as Separate Service

**Context**: Need to handle file uploads and create Newsletter records.

**Decision**: Create `FileIngestionService` that orchestrates parsing and storage.

**Rationale**:
1. Separation of concerns (parsing vs. storage)
2. Reusable for different upload sources (API, Gmail attachments, batch)
3. Consistent deduplication and error handling
4. Transaction management in one place

**Implementation**:
```python
class FileIngestionService:
    def __init__(self, router: ParserRouter, db: Session):
        self.router = router
        self.db = db

    async def ingest_file(self, file_path: Path, **kwargs) -> Newsletter:
        # 1. Parse document
        content = await self.router.parse(file_path, **kwargs)

        # 2. Check for duplicates
        existing = self._find_duplicate(content.file_hash)
        if existing:
            return self._link_to_canonical(existing)

        # 3. Create newsletter record
        newsletter = Newsletter(
            source=NewsletterSource.FILE_UPLOAD,
            raw_text=content.markdown_content,
            extracted_links=content.links,
            content_hash=content.file_hash,
        )

        # 4. Store and return
        self.db.add(newsletter)
        self.db.commit()
        return newsletter
```

### Decision 5: Documents Table for Metadata

**Context**: Need to store parsing metadata and link to newsletters.

**Decision**: Create separate `documents` table with foreign key to `newsletters`.

**Rationale**:
1. Keep Newsletter model focused on content
2. Store parser-specific metadata (tables, processing time)
3. Support future features (document versioning, re-parsing)
4. Enable queries by format, parser, status

**Schema**:
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    source_format VARCHAR(50) NOT NULL,
    parser_used VARCHAR(50) NOT NULL,
    markdown_content TEXT NOT NULL,
    tables_json JSONB,
    metadata_json JSONB,
    newsletter_id INTEGER REFERENCES newsletters(id),
    file_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Decision 6: OCR as Opt-In Feature

**Context**: OCR requires additional dependencies and is slow.

**Decision**: OCR is disabled by default, enabled via configuration.

**Rationale**:
1. Most documents don't need OCR
2. OCR significantly increases processing time
3. OCR dependencies add installation complexity
4. Users should explicitly opt-in

**Implementation**:
```python
# Configuration
DOCLING_ENABLE_OCR=false  # Default off

# Parser respects setting
class DoclingParser:
    def __init__(self, enable_ocr: bool = False):
        self.enable_ocr = enable_ocr
        # Configure Docling pipeline accordingly
```

## Component Interactions

### Upload Flow Sequence

```
User                API              FileIngestionService    Router         DoclingParser
  │                  │                      │                  │                 │
  │─── POST /upload ─►│                      │                  │                 │
  │                  │─── ingest_file() ────►│                  │                 │
  │                  │                      │─── route() ──────►│                 │
  │                  │                      │                  │─── parse() ─────►│
  │                  │                      │                  │◄── DocContent ──│
  │                  │                      │◄─────────────────│                 │
  │                  │                      │                  │                 │
  │                  │                      │── create Newsletter ──►            │
  │                  │                      │── store Document ─────►            │
  │                  │◄── Newsletter ───────│                  │                 │
  │◄── Response ─────│                      │                  │                 │
```

### Error Handling Strategy

1. **Parse Failures**: Return partial content if possible, log warning
2. **OCR Failures**: Fall back to text extraction, log warning
3. **Timeout**: Kill processing, return error status
4. **Memory Issues**: Enforce file size limits, reject oversized files

## Security Considerations

1. **File Validation**: Check file type before processing (magic bytes, not just extension)
2. **Size Limits**: Enforce `max_file_size_mb` configuration
3. **Sandboxing**: Docling processes files locally, no external API calls
4. **Path Traversal**: Sanitize filenames before storage

## Performance Considerations

1. **Async Processing**: Parse operations are async to avoid blocking
2. **Timeout Configuration**: Default 300s timeout, configurable
3. **Memory Management**: Stream large files where possible
4. **Caching**: Docling caches ML models in configured directory

## Future Considerations

1. **Gmail Attachments**: FileIngestionService can be reused
2. **Batch API**: Add `ingest_batch()` method later
3. **Background Processing**: Move to Celery for large files
4. **Model Updates**: Docling models may need periodic updates
