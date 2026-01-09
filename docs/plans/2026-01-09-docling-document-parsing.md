# Docling Document Parsing Integration

**Date**: 2026-01-09
**Status**: Proposed

## Summary

Integrate [Docling](https://github.com/docling-project/docling) as the primary document parsing library to enable structured ingestion of diverse document formats (PDF, DOCX, PPTX, XLSX, HTML, images) into the newsletter aggregation system. This provides unified document representation, better content extraction, and support for file uploads beyond email/RSS sources.

---

## Motivation

### Current Limitations

1. **Limited format support**: Only plain text and HTML from Gmail/RSS
2. **No file upload capability**: Sources are read-only (Gmail API, RSS feeds)
3. **No PDF/Office support**: Cannot process attached documents or linked reports
4. **Basic HTML parsing**: Simple BeautifulSoup extraction loses document structure
5. **No OCR capability**: Cannot process scanned documents or images

### Why Docling?

- **Unified representation**: DoclingDocument format provides consistent structure across all formats
- **Advanced PDF parsing**: Layout analysis, table extraction, reading order detection
- **Multiple export formats**: Markdown, HTML, JSON (lossless), DocTags
- **Local processing**: No external API calls, suitable for sensitive content
- **LLM integration ready**: Native support for LangChain, LlamaIndex, Haystack
- **Active development**: 49k+ GitHub stars, MIT license, IBM Research backing
- **OCR support**: Built-in handling of scanned documents

---

## Requirements

### Functional Requirements

1. **Parse multiple document formats**: PDF, DOCX, PPTX, XLSX, HTML, images
2. **Extract structured content**: Preserve headings, paragraphs, tables, lists, code blocks
3. **Extract document metadata**: Title, author, creation date, page count
4. **Support file uploads**: New ingestion source for user-submitted documents
5. **Handle email attachments**: Parse PDF/Office attachments from Gmail
6. **Preserve document hierarchy**: Maintain section/subsection relationships
7. **Extract images and tables**: Store references for potential downstream use

### Non-Functional Requirements

1. **Performance**: Process typical documents (< 50 pages) within 30 seconds
2. **Memory efficiency**: Handle documents up to 100MB without issues
3. **Error resilience**: Graceful degradation for partially corrupted documents
4. **Extensibility**: Easy to add new format support as Docling evolves

---

## Architecture Design

### High-Level Integration

```
                                    ┌─────────────────────────────────┐
                                    │         Document Sources        │
                                    │ (Files, URLs, Email Attachments)│
                                    └─────────────┬───────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DoclingParser Service                               │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │ DocumentConverter │→ │  DoclingDocument  │→ │ Structured Extraction │   │
│  │   (Docling Core)  │  │  (Unified Format) │  │   (Text, Tables, etc) │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                              ┌───────────────────────────────────┐
                              │        Existing Pipeline          │
                              │  Newsletter Model → Summarization │
                              └───────────────────────────────────┘
```

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `DoclingParser` | `src/parsers/docling_parser.py` | Core Docling integration service |
| `DocumentContent` | `src/models/document.py` | Structured content model for parsed documents |
| `FileIngestionService` | `src/ingestion/files.py` | File upload handling and processing |
| `AttachmentExtractor` | `src/ingestion/attachments.py` | Email attachment extraction |

### Data Flow

```
1. Document Input (file path, URL, or bytes)
          │
          ▼
2. DoclingParser.parse(source) → DoclingDocument
          │
          ▼
3. DoclingParser.extract_structured_content() → DocumentContent
          │
          ▼
4. Map to Newsletter model (for pipeline compatibility)
          │
          ▼
5. Existing summarization pipeline processes content
```

---

## Data Models

### DocumentContent (New Pydantic Model)

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    IMAGE = "image"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"

class TableData(BaseModel):
    """Extracted table with structure"""
    id: str
    caption: Optional[str] = None
    headers: list[str]
    rows: list[list[str]]
    page_number: Optional[int] = None

class ImageReference(BaseModel):
    """Reference to extracted image"""
    id: str
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    page_number: Optional[int] = None
    # Actual image bytes stored separately if needed

class Section(BaseModel):
    """Document section with hierarchy"""
    id: str
    level: int  # 1=h1, 2=h2, etc.
    title: str
    content: str  # Text content within section
    children: list["Section"] = []

class DocumentContent(BaseModel):
    """Unified structured document representation"""
    # Identification
    source_path: str
    source_format: DocumentFormat

    # Metadata
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None

    # Content (multiple representations)
    markdown_content: str  # Primary content as markdown
    plain_text: str  # Fallback plain text
    structured_sections: list[Section] = []  # Hierarchical structure

    # Extracted elements
    tables: list[TableData] = []
    images: list[ImageReference] = []
    links: list[str] = []

    # Processing metadata
    docling_version: str
    processing_time_ms: int
    warnings: list[str] = []
```

### Database Schema Extension

```sql
-- New table for document uploads
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,

    -- Source information
    filename VARCHAR(500) NOT NULL,
    source_format VARCHAR(50) NOT NULL,
    file_size_bytes INTEGER,
    file_hash VARCHAR(64),  -- SHA-256 for deduplication

    -- Extracted metadata
    title VARCHAR(1000),
    author VARCHAR(500),
    created_date TIMESTAMP,
    page_count INTEGER,
    word_count INTEGER,

    -- Content storage
    markdown_content TEXT,
    plain_text TEXT,
    structured_json JSONB,  -- Full DocumentContent as JSON

    -- Extracted elements
    tables_json JSONB,
    links_json JSONB,

    -- Relationship to newsletter (optional)
    newsletter_id INTEGER REFERENCES newsletters(id),

    -- Processing status
    status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    error_message TEXT,

    -- Timestamps
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_newsletter ON documents(newsletter_id);
```

---

## Implementation Plan

### Phase 1: Core Parser Integration

**Goal**: Implement DoclingParser service with basic document conversion

#### Tasks

1. **Add Docling dependency**
   - Add `docling>=2.60.0` to requirements.txt
   - Consider optional extras for OCR: `docling[ocr]`

2. **Create DoclingParser service** (`src/parsers/docling_parser.py`)
   ```python
   from docling.document_converter import DocumentConverter
   from docling.datamodel.document import DoclingDocument

   class DoclingParser:
       def __init__(self, enable_ocr: bool = False):
           self.converter = DocumentConverter()
           self.enable_ocr = enable_ocr

       def parse(self, source: str | Path | bytes) -> DoclingDocument:
           """Parse document from file path, URL, or bytes"""
           result = self.converter.convert(source)
           return result.document

       def extract_content(self, doc: DoclingDocument) -> DocumentContent:
           """Extract structured content from DoclingDocument"""
           # Implementation details below
   ```

3. **Implement content extraction methods**
   - `to_markdown()`: Export as markdown
   - `to_plain_text()`: Export as plain text
   - `extract_tables()`: Parse table structures
   - `extract_sections()`: Build section hierarchy
   - `extract_metadata()`: Get document metadata

4. **Create DocumentContent model** (`src/models/document.py`)

5. **Add configuration options** (`src/config/settings.py`)
   ```python
   # Docling settings
   DOCLING_ENABLE_OCR: bool = False
   DOCLING_MAX_FILE_SIZE_MB: int = 100
   DOCLING_TIMEOUT_SECONDS: int = 300
   DOCLING_SUPPORTED_FORMATS: list = ["pdf", "docx", "pptx", "xlsx", "html"]
   ```

### Phase 2: File Ingestion Service

**Goal**: Enable file uploads as a new ingestion source

#### Tasks

1. **Create FileIngestionService** (`src/ingestion/files.py`)
   ```python
   class FileIngestionService:
       def __init__(self, parser: DoclingParser, db: Session):
           self.parser = parser
           self.db = db

       async def ingest_file(
           self,
           file_path: Path,
           metadata: Optional[dict] = None
       ) -> Newsletter:
           """Ingest a file and create newsletter record"""
           # 1. Parse with Docling
           # 2. Extract content
           # 3. Create newsletter record
           # 4. Store document metadata
   ```

2. **Add file upload API endpoint** (`src/api/routes/upload.py`)
   ```python
   @router.post("/upload")
   async def upload_document(
       file: UploadFile,
       publication: Optional[str] = None,
       db: Session = Depends(get_db)
   ) -> UploadResponse:
       """Upload and process a document"""
   ```

3. **Implement file validation**
   - Check file size limits
   - Validate file format
   - Virus/malware scanning (optional)
   - Deduplication via file hash

4. **Create database migration** for `documents` table

### Phase 3: Gmail Attachment Support

**Goal**: Parse PDF/Office attachments from Gmail newsletters

#### Tasks

1. **Extend Gmail ingestion** (`src/ingestion/gmail.py`)
   ```python
   def extract_attachments(self, message: dict) -> list[Attachment]:
       """Extract file attachments from email message"""

   async def process_attachment(
       self,
       attachment: Attachment
   ) -> Optional[DocumentContent]:
       """Process attachment through Docling"""
   ```

2. **Link attachments to newsletters**
   - Store attachment metadata in `documents` table
   - Foreign key relationship to parent newsletter
   - Include attachment content in summarization

3. **Update summarization prompt**
   - Include attachment content context
   - Handle multi-document newsletters

### Phase 4: Enhanced HTML Processing

**Goal**: Replace BeautifulSoup with Docling for HTML parsing

#### Tasks

1. **Migrate HTML parsing to Docling**
   - Replace `html_to_text()` with Docling conversion
   - Preserve table extraction improvements
   - Maintain link extraction functionality

2. **Update existing ingestion services**
   - Gmail: Use Docling for HTML body parsing
   - RSS: Use Docling for entry content parsing

3. **Benchmark and compare**
   - Quality of extracted text
   - Preservation of structure
   - Processing speed

### Phase 5: Advanced Features (Future)

**Goal**: Leverage advanced Docling capabilities

#### Tasks

1. **OCR integration** for scanned PDFs
2. **VLM pipeline** for complex layouts
3. **Image extraction and storage**
4. **Structured information extraction** (beta feature)
5. **LangChain/LlamaIndex integration** for RAG

---

## API Design

### Upload Endpoint

```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Parameters:
  - file: File (required) - Document to upload
  - publication: string (optional) - Publisher/source name
  - title: string (optional) - Override extracted title
  - process_immediately: boolean (default: true) - Queue for summarization

Response:
{
  "id": 123,
  "filename": "report.pdf",
  "status": "processing",
  "format": "pdf",
  "page_count": 15,
  "word_count": 4500,
  "newsletter_id": 456  // If linked to newsletter record
}
```

### Document Status Endpoint

```
GET /api/v1/documents/{id}

Response:
{
  "id": 123,
  "filename": "report.pdf",
  "status": "completed",
  "format": "pdf",
  "metadata": {
    "title": "Q4 AI Trends Report",
    "author": "Research Team",
    "page_count": 15
  },
  "content": {
    "markdown": "...",
    "tables_count": 3,
    "images_count": 7
  },
  "newsletter_id": 456,
  "processed_at": "2026-01-09T12:00:00Z"
}
```

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/parsers/__init__.py` | Parser module init |
| `src/parsers/docling_parser.py` | Core Docling integration |
| `src/models/document.py` | DocumentContent and related models |
| `src/ingestion/files.py` | File upload ingestion service |
| `src/ingestion/attachments.py` | Email attachment extraction |
| `src/api/routes/upload.py` | File upload API endpoints |
| `alembic/versions/xxx_add_documents_table.py` | Database migration |
| `tests/test_parsers/test_docling_parser.py` | Parser unit tests |
| `tests/test_ingestion/test_files.py` | File ingestion tests |

### Modified Files

| File | Changes |
|------|---------|
| `requirements.txt` | Add docling dependency |
| `src/config/settings.py` | Add Docling configuration options |
| `src/ingestion/gmail.py` | Add attachment extraction |
| `src/api/app.py` | Register upload routes |
| `src/utils/html_parser.py` | Optional: integrate Docling for HTML |

---

## Testing Strategy

### Unit Tests

1. **DoclingParser tests**
   - Parse sample PDF document
   - Parse sample DOCX document
   - Handle corrupt/invalid files
   - Extract tables correctly
   - Extract sections with hierarchy

2. **DocumentContent model tests**
   - Serialization/deserialization
   - Validation of required fields

3. **FileIngestionService tests**
   - Successful file processing
   - Duplicate detection
   - Error handling

### Integration Tests

1. **End-to-end upload flow**
   - Upload → Parse → Store → Summarize

2. **Gmail attachment processing**
   - Fetch email with attachment
   - Parse attachment
   - Link to newsletter

### Test Fixtures

Create sample documents in `tests/fixtures/documents/`:
- `sample.pdf` - Multi-page PDF with tables
- `sample.docx` - Word document with formatting
- `sample.pptx` - PowerPoint presentation
- `sample_scanned.pdf` - Scanned document (OCR test)

---

## Configuration

### Environment Variables

```bash
# Docling settings
DOCLING_ENABLE_OCR=false           # Enable OCR for scanned documents
DOCLING_MAX_FILE_SIZE_MB=100       # Maximum file size to process
DOCLING_TIMEOUT_SECONDS=300        # Processing timeout
DOCLING_CACHE_DIR=/tmp/docling     # Cache directory for models

# Optional: VLM pipeline (requires GPU)
DOCLING_USE_VLM=false
DOCLING_VLM_MODEL=granite_docling
```

### Settings Class Update

```python
# src/config/settings.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Docling configuration
    docling_enable_ocr: bool = False
    docling_max_file_size_mb: int = 100
    docling_timeout_seconds: int = 300
    docling_cache_dir: str = "/tmp/docling"
    docling_use_vlm: bool = False
    docling_vlm_model: str = "granite_docling"
    docling_supported_formats: list[str] = [
        "pdf", "docx", "pptx", "xlsx", "html", "md", "png", "jpg", "jpeg"
    ]
```

---

## Dependencies

### Required

```
docling>=2.60.0
```

### Optional (for advanced features)

```
docling[ocr]      # For OCR support
torch             # For VLM pipeline (if using GPU)
```

### System Requirements

- Python 3.10+
- 4GB+ RAM recommended for PDF processing
- GPU optional (for VLM pipeline)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large file memory issues | Medium | High | Implement file size limits, streaming where possible |
| Slow processing for complex PDFs | Medium | Medium | Add async processing, timeout limits |
| OCR quality on poor scans | Medium | Low | Provide fallback to original text extraction |
| Docling breaking changes | Low | Medium | Pin version, test on upgrade |
| GPU dependency for VLM | Low | Low | VLM is optional, CPU fallback available |

---

## Success Metrics

1. **Format coverage**: Successfully parse 95%+ of uploaded PDF/Office documents
2. **Content quality**: Extracted text matches original with 98%+ accuracy
3. **Table extraction**: Correctly identify and structure 90%+ of tables
4. **Processing speed**: Average document processed in < 10 seconds
5. **Error rate**: < 5% of documents fail processing completely

---

## Future Enhancements

1. **Batch processing**: Upload and process multiple documents
2. **Watch folders**: Automatically ingest from monitored directories
3. **URL ingestion**: Fetch and parse documents from URLs
4. **Image analysis**: Extract insights from document images using VLM
5. **Cross-document linking**: Identify references between documents
6. **RAG integration**: Use docling chunks for retrieval-augmented generation

---

## References

- [Docling GitHub Repository](https://github.com/docling-project/docling)
- [Docling Documentation](https://docling-project.github.io/docling/)
- [DoclingDocument Schema](https://github.com/docling-project/docling-core/blob/main/docs/DoclingDocument.json)
- [Docling Core Library](https://github.com/docling-project/docling-core)
