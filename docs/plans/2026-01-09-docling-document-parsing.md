# Unified Document Parsing Integration

**Date**: 2026-01-09
**Updated**: 2026-01-10
**Status**: Proposed

## Summary

Integrate a unified document parsing layer with multiple parser backends—[Docling](https://github.com/docling-project/docling) and [MarkItDown](https://github.com/microsoft/markitdown)—to enable structured ingestion of diverse document formats into the newsletter aggregation system. The architecture uses **markdown as the primary document representation** (optimized for LLM consumption) with optional structured metadata extraction when available.

### Key Design Decisions

1. **Markdown-centric representation**: Both parsers output markdown, which LLMs natively understand
2. **Parser abstraction**: Unified `DocumentParser` interface allows swapping/adding parsers
3. **Format-based routing**: Automatically select the best parser for each document type
4. **Optional structure preservation**: Tables and metadata captured when parsers provide them

---

## Motivation

### Current Limitations

1. **Limited format support**: Only plain text and HTML from Gmail/RSS
2. **No file upload capability**: Sources are read-only (Gmail API, RSS feeds)
3. **No PDF/Office support**: Cannot process attached documents or linked reports
4. **Basic HTML parsing**: Simple BeautifulSoup extraction loses document structure
5. **No OCR capability**: Cannot process scanned documents or images
6. **No multimedia support**: Cannot extract content from audio/video sources

### Why Multiple Parsers?

No single library excels at all document types. A hybrid approach leverages each library's strengths:

| Capability | Docling | MarkItDown |
|------------|---------|------------|
| Complex PDF layouts | ✅ Excellent | ⚠️ Basic |
| Table extraction | ✅ Structured data | ✅ Markdown tables |
| OCR for scanned docs | ✅ Built-in | ❌ No |
| YouTube transcripts | ❌ No | ✅ Yes |
| Audio transcription | ❌ No | ✅ Yes |
| Outlook MSG files | ❌ No | ✅ Yes |
| EPUB ebooks | ❌ No | ✅ Yes |
| Memory footprint | ⚠️ Heavy (ML models) | ✅ Light |
| Processing speed | ⚠️ Slower | ✅ Fast |

---

## Parser Comparison

### Docling (IBM Research)

**Best for**: Complex PDFs, documents requiring layout analysis, table extraction, OCR

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("report.pdf")
markdown = result.document.export_to_markdown()
```

**Strengths**:
- Advanced PDF layout understanding with ML models
- Preserves document hierarchy (sections, subsections)
- Extracts tables as structured data (rows/columns)
- Built-in OCR for scanned documents
- Lossless JSON export for full document structure
- Native integrations with LangChain, LlamaIndex, Haystack

**Trade-offs**:
- Heavier dependencies (ML models)
- Slower processing
- Higher memory usage

### MarkItDown (Microsoft)

**Best for**: Simple conversions, multimedia content, lightweight processing

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("presentation.pptx")
markdown = result.text_content
```

**Strengths**:
- Lightweight, fast processing
- Designed specifically for LLM consumption
- Unique format support: YouTube URLs, audio transcription, Outlook MSG
- Modular dependencies (install only what you need)
- Plugin ecosystem for community extensions
- Stream-based processing (no temp files)

**Trade-offs**:
- No structured data extraction (markdown only)
- Basic PDF handling (no layout analysis)
- No OCR support

### Output Format Comparison

Both produce markdown, but with different characteristics:

**Docling output** (from PDF with table):
```markdown
# Q4 Financial Report

## Executive Summary

Revenue increased 15% year-over-year...

## Financial Highlights

| Metric | Q4 2025 | Q4 2024 | Change |
|--------|---------|---------|--------|
| Revenue | $1.2B | $1.04B | +15% |
| Profit | $180M | $156M | +15% |
```

**MarkItDown output** (from same PDF):
```markdown
# Q4 Financial Report

Executive Summary

Revenue increased 15% year-over-year...

Financial Highlights

| Metric | Q4 2025 | Q4 2024 | Change |
|--------|---------|---------|--------|
| Revenue | $1.2B | $1.04B | +15% |
| Profit | $180M | $156M | +15% |
```

Key difference: Docling preserves heading hierarchy (`##`), MarkItDown may flatten structure.

---

## Architecture Design

### High-Level Integration

```
                         ┌─────────────────────────────────────┐
                         │          Document Sources           │
                         │ (Files, URLs, Attachments, YouTube) │
                         └─────────────────┬───────────────────┘
                                           │
                                           ▼
                         ┌─────────────────────────────────────┐
                         │         ParserRouter                │
                         │   (Format-based parser selection)   │
                         └─────────────────┬───────────────────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              │                            │                            │
              ▼                            ▼                            ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│     DoclingParser       │  │   MarkItDownParser      │  │    Future Parsers...    │
│  ┌───────────────────┐  │  │  ┌───────────────────┐  │  │                         │
│  │ - Complex PDFs    │  │  │  │ - YouTube URLs    │  │  │  (e.g., Unstructured,   │
│  │ - OCR/scanned     │  │  │  │ - Audio files     │  │  │   LlamaParse, etc.)     │
│  │ - Table extraction│  │  │  │ - Outlook MSG     │  │  │                         │
│  │ - Layout analysis │  │  │  │ - Simple docs     │  │  │                         │
│  └───────────────────┘  │  │  └───────────────────┘  │  │                         │
└────────────┬────────────┘  └────────────┬────────────┘  └─────────────────────────┘
             │                            │
             └────────────┬───────────────┘
                          │
                          ▼
              ┌─────────────────────────────────────┐
              │        DocumentContent              │
              │  (Unified markdown-centric model)   │
              │  ┌─────────────────────────────┐    │
              │  │ markdown_content: str       │    │  ← Primary LLM input
              │  │ tables: list[TableData]     │    │  ← Optional structured data
              │  │ metadata: DocumentMetadata  │    │  ← Source info
              │  └─────────────────────────────┘    │
              └─────────────────┬───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │        Existing Pipeline            │
              │   Newsletter Model → Summarization  │
              └─────────────────────────────────────┘
```

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `DocumentParser` | `src/parsers/base.py` | Abstract interface for all parsers |
| `DoclingParser` | `src/parsers/docling_parser.py` | Docling integration |
| `MarkItDownParser` | `src/parsers/markitdown_parser.py` | MarkItDown integration |
| `ParserRouter` | `src/parsers/router.py` | Format-based parser selection |
| `DocumentContent` | `src/models/document.py` | Unified content model |
| `FileIngestionService` | `src/ingestion/files.py` | File upload handling |

### Data Flow

```
1. Document Input (file path, URL, or bytes)
          │
          ▼
2. ParserRouter.route(source, format) → appropriate parser
          │
          ▼
3. Parser.parse(source) → DocumentContent
          │
          ▼
4. Map to Newsletter model:
   - newsletter.raw_text = content.markdown_content
   - newsletter.extracted_links = content.links
          │
          ▼
5. Existing summarization pipeline processes markdown content
```

---

## Data Models

### DocumentParser Interface (Abstract Base)

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, BinaryIO

class DocumentParser(ABC):
    """Abstract interface for document parsers"""

    # Formats this parser handles well
    supported_formats: set[str]

    # Formats this parser handles but another may do better
    fallback_formats: set[str]

    @abstractmethod
    def parse(
        self,
        source: Union[str, Path, BinaryIO, bytes],
        format_hint: str | None = None
    ) -> "DocumentContent":
        """Parse document and return unified content model"""
        pass

    @abstractmethod
    def can_parse(self, source: Union[str, Path], format_hint: str | None = None) -> bool:
        """Check if this parser can handle the given source"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser identifier for logging/metrics"""
        pass
```

### DocumentContent (Markdown-Centric Model)

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class DocumentFormat(str, Enum):
    """Supported input formats"""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    MARKDOWN = "md"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    YOUTUBE = "youtube"
    OUTLOOK_MSG = "msg"
    EPUB = "epub"
    UNKNOWN = "unknown"

class TableData(BaseModel):
    """Extracted table (optional, when parser provides structured data)"""
    caption: Optional[str] = None
    headers: list[str] = []
    rows: list[list[str]] = []
    markdown: str  # Always available as fallback

class DocumentMetadata(BaseModel):
    """Document metadata extracted during parsing"""
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None

class DocumentContent(BaseModel):
    """
    Unified document representation.

    Markdown is the PRIMARY content format - optimized for LLM consumption.
    Structured data (tables, metadata) is OPTIONAL and parser-dependent.
    """
    # === Required: Always populated ===
    markdown_content: str = Field(
        description="Primary content as markdown - the main LLM input"
    )
    source_path: str = Field(
        description="Original file path, URL, or identifier"
    )
    source_format: DocumentFormat = Field(
        description="Detected or specified input format"
    )
    parser_used: str = Field(
        description="Which parser produced this content (docling/markitdown)"
    )

    # === Optional: Populated when available ===
    metadata: DocumentMetadata = Field(
        default_factory=DocumentMetadata,
        description="Document metadata (title, author, etc.)"
    )
    tables: list[TableData] = Field(
        default_factory=list,
        description="Extracted tables with structure (Docling only)"
    )
    links: list[str] = Field(
        default_factory=list,
        description="URLs extracted from document"
    )

    # === Processing info ===
    processing_time_ms: int = 0
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues during parsing"
    )

    def to_newsletter_content(self) -> tuple[str, str, list[str]]:
        """Convert to newsletter model fields: (raw_text, raw_html, links)"""
        return (
            self.markdown_content,  # Goes to raw_text
            self.markdown_content,  # Also raw_html (markdown is valid)
            self.links
        )
```

### ParserRouter (Format-Based Selection)

```python
from pathlib import Path
from typing import Union
import mimetypes

class ParserRouter:
    """Routes documents to the appropriate parser based on format"""

    # Format → preferred parser mapping
    ROUTING_TABLE: dict[str, str] = {
        # Docling excels at these
        "pdf": "docling",           # Complex layouts, tables, OCR
        "docx": "docling",          # Better structure preservation
        "pptx": "markitdown",       # MarkItDown handles well, lighter
        "xlsx": "markitdown",       # Both work, MarkItDown lighter
        "html": "markitdown",       # MarkItDown sufficient for most HTML

        # MarkItDown exclusive formats
        "youtube": "markitdown",    # YouTube transcript extraction
        "mp3": "markitdown",        # Audio transcription
        "wav": "markitdown",        # Audio transcription
        "msg": "markitdown",        # Outlook email
        "epub": "markitdown",       # Ebooks

        # Images - depends on needs
        "png": "docling",           # OCR capability
        "jpg": "docling",           # OCR capability
        "jpeg": "docling",          # OCR capability
    }

    # Formats requiring OCR should always use Docling
    OCR_REQUIRED_INDICATORS = ["scanned", "scan", "ocr"]

    def __init__(
        self,
        docling_parser: "DoclingParser",
        markitdown_parser: "MarkItDownParser",
        default_parser: str = "markitdown"  # Lighter default
    ):
        self.parsers = {
            "docling": docling_parser,
            "markitdown": markitdown_parser,
        }
        self.default_parser = default_parser

    def route(
        self,
        source: Union[str, Path],
        format_hint: str | None = None,
        prefer_structured: bool = False,
        ocr_needed: bool = False,
    ) -> "DocumentParser":
        """
        Select the best parser for the given document.

        Args:
            source: File path or URL
            format_hint: Explicit format override
            prefer_structured: If True, prefer Docling for table extraction
            ocr_needed: If True, force Docling for OCR capability
        """
        # Detect format
        format = format_hint or self._detect_format(source)

        # OCR always needs Docling
        if ocr_needed or self._likely_needs_ocr(source):
            return self.parsers["docling"]

        # Prefer structured extraction for PDFs with tables
        if prefer_structured and format == "pdf":
            return self.parsers["docling"]

        # Use routing table
        parser_name = self.ROUTING_TABLE.get(format, self.default_parser)
        return self.parsers[parser_name]

    def _detect_format(self, source: Union[str, Path]) -> str:
        """Detect format from file extension or URL pattern"""
        source_str = str(source)

        # YouTube URL detection
        if "youtube.com" in source_str or "youtu.be" in source_str:
            return "youtube"

        # File extension
        ext = Path(source_str).suffix.lower().lstrip(".")
        return ext or "unknown"

    def _likely_needs_ocr(self, source: Union[str, Path]) -> bool:
        """Heuristic: filename contains OCR indicators"""
        name = Path(source).stem.lower()
        return any(ind in name for ind in self.OCR_REQUIRED_INDICATORS)

    async def parse(
        self,
        source: Union[str, Path, bytes],
        **routing_kwargs
    ) -> "DocumentContent":
        """Route and parse in one call"""
        parser = self.route(source, **routing_kwargs)
        return await parser.parse(source)
```

### Database Schema Extension

```sql
-- New table for parsed documents
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,

    -- Source information
    filename VARCHAR(500) NOT NULL,
    source_format VARCHAR(50) NOT NULL,
    source_url VARCHAR(2000),
    file_size_bytes INTEGER,
    file_hash VARCHAR(64),  -- SHA-256 for deduplication

    -- Parser information
    parser_used VARCHAR(50) NOT NULL,  -- 'docling' or 'markitdown'

    -- Content storage (markdown-centric)
    markdown_content TEXT NOT NULL,    -- Primary content

    -- Optional structured data (JSON, parser-dependent)
    tables_json JSONB,                 -- Extracted tables if available
    metadata_json JSONB,               -- Document metadata
    links_json JSONB,                  -- Extracted URLs

    -- Relationship to newsletter (optional)
    newsletter_id INTEGER REFERENCES newsletters(id),

    -- Processing status
    status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    error_message TEXT,
    warnings_json JSONB,

    -- Timestamps
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_parser ON documents(parser_used);
CREATE INDEX idx_documents_newsletter ON documents(newsletter_id);
```

---

## Implementation Plan

### Phase 1: Core Parser Interface & MarkItDown Integration

**Goal**: Establish parser abstraction and implement the lighter MarkItDown parser first

#### Tasks

1. **Create parser interface** (`src/parsers/base.py`)
   - Define `DocumentParser` abstract base class
   - Define `DocumentContent` model

2. **Add MarkItDown dependency**
   ```
   markitdown>=0.1.0
   ```

3. **Implement MarkItDownParser** (`src/parsers/markitdown_parser.py`)
   ```python
   from markitdown import MarkItDown

   class MarkItDownParser(DocumentParser):
       supported_formats = {"docx", "pptx", "xlsx", "html", "youtube", "mp3", "wav", "msg", "epub"}
       fallback_formats = {"pdf"}  # Can do it, but Docling better

       def __init__(self, llm_client=None):
           self.md = MarkItDown(llm_client=llm_client)

       def parse(self, source) -> DocumentContent:
           result = self.md.convert(source)
           return DocumentContent(
               markdown_content=result.text_content,
               source_path=str(source),
               source_format=self._detect_format(source),
               parser_used="markitdown",
               links=self._extract_links(result.text_content),
           )
   ```

4. **Create DocumentContent model** (`src/models/document.py`)

5. **Add basic tests** for MarkItDown parser

### Phase 2: Docling Integration

**Goal**: Add Docling for advanced PDF/OCR capabilities

#### Tasks

1. **Add Docling dependency**
   ```
   docling>=2.60.0
   docling[ocr]  # Optional
   ```

2. **Implement DoclingParser** (`src/parsers/docling_parser.py`)
   ```python
   from docling.document_converter import DocumentConverter

   class DoclingParser(DocumentParser):
       supported_formats = {"pdf", "docx", "png", "jpg", "jpeg", "html"}
       fallback_formats = {"pptx", "xlsx"}

       def __init__(self, enable_ocr: bool = False):
           self.converter = DocumentConverter()
           self.enable_ocr = enable_ocr

       def parse(self, source) -> DocumentContent:
           result = self.converter.convert(source)
           doc = result.document

           return DocumentContent(
               markdown_content=doc.export_to_markdown(),
               source_path=str(source),
               source_format=self._detect_format(source),
               parser_used="docling",
               tables=self._extract_tables(doc),
               metadata=self._extract_metadata(doc),
               links=self._extract_links(doc),
           )

       def _extract_tables(self, doc) -> list[TableData]:
           """Extract structured table data from DoclingDocument"""
           tables = []
           for table in doc.tables:
               tables.append(TableData(
                   caption=table.caption,
                   headers=[cell.text for cell in table.header_rows[0]] if table.header_rows else [],
                   rows=[[cell.text for cell in row] for row in table.body_rows],
                   markdown=table.export_to_markdown(),
               ))
           return tables
   ```

3. **Add configuration options** (`src/config/settings.py`)

4. **Add tests** for Docling parser

### Phase 3: Parser Router & File Ingestion

**Goal**: Implement intelligent routing and file upload capability

#### Tasks

1. **Implement ParserRouter** (`src/parsers/router.py`)

2. **Create FileIngestionService** (`src/ingestion/files.py`)
   ```python
   class FileIngestionService:
       def __init__(self, router: ParserRouter, db: Session):
           self.router = router
           self.db = db

       async def ingest_file(
           self,
           file_path: Path,
           prefer_structured: bool = False,
           ocr_needed: bool = False,
       ) -> Newsletter:
           # 1. Route to appropriate parser
           content = await self.router.parse(
               file_path,
               prefer_structured=prefer_structured,
               ocr_needed=ocr_needed,
           )

           # 2. Create newsletter record
           newsletter = Newsletter(
               source=NewsletterSource.FILE_UPLOAD,
               source_id=content.file_hash,
               title=content.metadata.title or file_path.name,
               raw_text=content.markdown_content,
               raw_html=content.markdown_content,
               extracted_links=content.links,
           )

           # 3. Store and return
           self.db.add(newsletter)
           self.db.commit()
           return newsletter
   ```

3. **Add file upload API endpoint** (`src/api/routes/upload.py`)

4. **Create database migration**

### Phase 4: Gmail Attachment & YouTube Support

**Goal**: Enable attachment parsing and YouTube transcript ingestion

#### Tasks

1. **Extend Gmail ingestion** for attachments
   - Extract PDF/Office attachments
   - Route through parser system
   - Link to parent newsletter

2. **Add YouTube ingestion capability**
   - New source type: `NewsletterSource.YOUTUBE`
   - Use MarkItDown for transcript extraction
   - Store as newsletter for summarization

3. **Update summarization** to handle multimedia content

### Phase 5: Advanced Features (Future)

**Goal**: Leverage advanced parser capabilities

#### Tasks

1. **OCR integration** for scanned PDFs (Docling)
2. **Audio transcription** for podcasts (MarkItDown)
3. **VLM pipeline** for complex layouts (Docling)
4. **Image description** with LLM integration (MarkItDown)
5. **Batch processing** for multiple documents
6. **RAG chunking** using Docling's built-in chunker

---

## Configuration

### Environment Variables

```bash
# Parser selection
DEFAULT_PARSER=markitdown              # Default parser for unknown formats
ENABLE_DOCLING=true                    # Enable Docling (heavier dependencies)
ENABLE_MARKITDOWN=true                 # Enable MarkItDown

# Docling settings (when enabled)
DOCLING_ENABLE_OCR=false               # Enable OCR for scanned documents
DOCLING_MAX_FILE_SIZE_MB=100           # Maximum file size
DOCLING_TIMEOUT_SECONDS=300            # Processing timeout
DOCLING_CACHE_DIR=/tmp/docling         # Model cache directory

# MarkItDown settings
MARKITDOWN_LLM_MODEL=                  # Optional LLM for image descriptions
MARKITDOWN_ENABLE_PLUGINS=false        # Enable community plugins

# General
MAX_UPLOAD_SIZE_MB=50                  # File upload limit
```

### Settings Class

```python
class ParserSettings(BaseSettings):
    # Parser selection
    default_parser: str = "markitdown"
    enable_docling: bool = True
    enable_markitdown: bool = True

    # Docling configuration
    docling_enable_ocr: bool = False
    docling_max_file_size_mb: int = 100
    docling_timeout_seconds: int = 300
    docling_cache_dir: str = "/tmp/docling"

    # MarkItDown configuration
    markitdown_llm_model: str | None = None
    markitdown_enable_plugins: bool = False

    # Routing preferences
    prefer_structured_pdf: bool = True  # Use Docling for PDFs by default

    # General
    max_upload_size_mb: int = 50
```

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/parsers/__init__.py` | Parser module init, exports router |
| `src/parsers/base.py` | DocumentParser interface, DocumentContent model |
| `src/parsers/docling_parser.py` | Docling implementation |
| `src/parsers/markitdown_parser.py` | MarkItDown implementation |
| `src/parsers/router.py` | ParserRouter with format-based selection |
| `src/models/document.py` | DocumentContent and related models |
| `src/ingestion/files.py` | File upload ingestion service |
| `src/api/routes/upload.py` | File upload API endpoints |
| `alembic/versions/xxx_add_documents_table.py` | Database migration |
| `tests/test_parsers/test_base.py` | Interface tests |
| `tests/test_parsers/test_docling.py` | Docling parser tests |
| `tests/test_parsers/test_markitdown.py` | MarkItDown parser tests |
| `tests/test_parsers/test_router.py` | Router tests |

### Modified Files

| File | Changes |
|------|---------|
| `requirements.txt` | Add docling, markitdown dependencies |
| `src/config/settings.py` | Add parser configuration |
| `src/ingestion/gmail.py` | Add attachment extraction |
| `src/api/app.py` | Register upload routes |

---

## Dependencies

### Required

```
markitdown>=0.1.0          # Lightweight, always included
```

### Optional (feature groups)

```
# For advanced PDF processing
docling>=2.60.0

# For OCR support
docling[ocr]

# For MarkItDown audio transcription
markitdown[audio]

# For MarkItDown PDF support (if not using Docling)
markitdown[pdf]
```

### Recommended Installation

```bash
# Minimal (MarkItDown only)
pip install markitdown

# Full (both parsers)
pip install markitdown docling

# With OCR
pip install markitdown "docling[ocr]"
```

---

## Testing Strategy

### Unit Tests

1. **Parser interface tests**
   - Verify both parsers implement interface correctly
   - Test DocumentContent model validation

2. **MarkItDown parser tests**
   - Parse DOCX, PPTX, XLSX
   - Parse YouTube URL (mock transcript)
   - Handle invalid files gracefully

3. **Docling parser tests**
   - Parse PDF with tables
   - Verify table extraction structure
   - Test OCR on image (when enabled)

4. **Router tests**
   - Correct parser selected for each format
   - OCR flag forces Docling
   - Unknown formats use default

### Integration Tests

1. **End-to-end upload flow**
   - Upload PDF → Route to Docling → Store → Summarize

2. **YouTube ingestion**
   - URL → MarkItDown → Newsletter → Summary

### Test Fixtures

```
tests/fixtures/documents/
├── sample.pdf              # Multi-page PDF with tables
├── sample.docx             # Word document
├── sample.pptx             # PowerPoint
├── sample.xlsx             # Excel spreadsheet
├── sample_scanned.pdf      # Scanned document (OCR test)
└── sample.html             # HTML page
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Parser output inconsistency | Medium | Medium | Normalize markdown output, test both parsers |
| Docling memory issues | Medium | High | Make Docling optional, file size limits |
| MarkItDown missing features | Low | Low | Fall back to Docling when needed |
| Dependency conflicts | Low | Medium | Use separate optional dependency groups |
| YouTube API changes | Medium | Low | MarkItDown handles, we just consume |

---

## Success Metrics

1. **Format coverage**: Support 10+ document formats
2. **Parser routing accuracy**: Correct parser selected 95%+ of time
3. **Markdown quality**: LLM summarization quality unchanged or improved
4. **Processing speed**: < 5s for typical documents (MarkItDown), < 30s for complex PDFs (Docling)
5. **Memory efficiency**: Process 50MB files without OOM

---

## Future Enhancements

1. **Additional parsers**: Unstructured, LlamaParse, Azure Document Intelligence
2. **Parser benchmarking**: Compare quality/speed across parsers for same documents
3. **Adaptive routing**: Learn which parser works best for specific sources
4. **Streaming processing**: Handle very large documents
5. **Multi-modal RAG**: Use extracted tables/images in retrieval

---

## References

### Docling
- [GitHub Repository](https://github.com/docling-project/docling)
- [Documentation](https://docling-project.github.io/docling/)
- [DoclingDocument Schema](https://github.com/docling-project/docling-core/blob/main/docs/DoclingDocument.json)

### MarkItDown
- [GitHub Repository](https://github.com/microsoft/markitdown)
- [PyPI Package](https://pypi.org/project/markitdown/)

### Related
- [LangChain Document Loaders](https://python.langchain.com/docs/modules/data_connection/document_loaders/)
- [LlamaIndex Document Readers](https://docs.llamaindex.ai/en/stable/module_guides/loading/connector/)
