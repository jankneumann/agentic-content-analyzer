# Tasks: Add Docling Parser Integration

## Prerequisites
- [ ] Review existing parser architecture in `src/parsers/`
- [ ] Review `DocumentContent` model in `src/models/document.py`
- [ ] Review router implementation in `src/parsers/router.py`

## Phase 1: Dependencies and Configuration

### 1.1 Add Docling Dependency
- [ ] Add `docling>=2.60.0` to `requirements.txt`
- [ ] Add `docling[ocr]` as optional dependency group in `pyproject.toml`
- [ ] Verify installation works on target Python version (3.10+)
- [ ] Document any system dependencies (e.g., for OCR)

### 1.2 Add Parser Configuration
- [ ] Add parser settings to `src/config/settings.py`:
  - `enable_docling: bool = True`
  - `docling_enable_ocr: bool = False`
  - `docling_max_file_size_mb: int = 100`
  - `docling_timeout_seconds: int = 300`
  - `docling_cache_dir: str = "/tmp/docling"`
- [ ] Add environment variable mappings for all settings
- [ ] Update `.env.example` with new configuration options

## Phase 2: DoclingParser Implementation

### 2.1 Create DoclingParser Class
- [ ] Create `src/parsers/docling_parser.py`
- [ ] Implement `DoclingParser(DocumentParser)` class:
  - `supported_formats = {"pdf", "docx", "png", "jpg", "jpeg", "html"}`
  - `fallback_formats = {"pptx", "xlsx"}`
  - `name` property returning `"docling"`
- [ ] Implement `can_parse()` method with format checking
- [ ] Implement `parse()` method using `DocumentConverter`

### 2.2 Implement Content Extraction
- [ ] Implement `_extract_tables()` method:
  - Extract `TableData` with headers, rows, caption
  - Include markdown fallback for each table
- [ ] Implement `_extract_metadata()` method:
  - Extract title, author, created_date, page_count
  - Handle missing metadata gracefully
- [ ] Implement `_extract_links()` method:
  - Extract URLs from document content
  - Deduplicate and validate URLs

### 2.3 Add OCR Support
- [ ] Add OCR configuration option to constructor
- [ ] Configure Docling pipeline for OCR when enabled
- [ ] Handle OCR-specific errors gracefully
- [ ] Log warnings when OCR is needed but disabled

### 2.4 Register with Router
- [ ] Update `src/parsers/__init__.py` to export `DoclingParser`
- [ ] Update router instantiation to accept optional `DoclingParser`
- [ ] Verify routing table correctly routes PDF/images to Docling

## Phase 3: File Ingestion Service

### 3.1 Create FileIngestionService
- [ ] Create `src/ingestion/files.py`
- [ ] Implement `FileIngestionService` class:
  - Constructor accepts `ParserRouter` and database session
  - `ingest_file()` method for single file processing
  - `ingest_bytes()` method for in-memory content
- [ ] Implement file hash generation for deduplication
- [ ] Implement duplicate detection and linking

### 3.2 Integrate with Newsletter Model
- [ ] Map `DocumentContent` to `Newsletter` model fields
- [ ] Set `source = NewsletterSource.FILE_UPLOAD`
- [ ] Store extracted links in `extracted_links` field
- [ ] Generate unique `source_id` from file hash

## Phase 4: Database Schema

### 4.1 Create Documents Table Migration
- [ ] Create Alembic migration for `documents` table:
  - `id`, `filename`, `source_format`, `parser_used`
  - `markdown_content`, `tables_json`, `metadata_json`, `links_json`
  - `newsletter_id` (FK), `status`, `processing_time_ms`
  - `file_hash`, `file_size_bytes`, `uploaded_at`, `processed_at`
- [ ] Add indexes: `file_hash`, `status`, `parser_used`, `newsletter_id`
- [ ] Test migration up and down

### 4.2 Create Document Model (Optional)
- [ ] Decide if separate SQLAlchemy `Document` model is needed
- [ ] If yes, create `src/models/document_db.py` with ORM model
- [ ] Add relationship to `Newsletter` model

## Phase 5: File Upload API

### 5.1 Create Upload Endpoint
- [ ] Create `src/api/routes/upload.py`
- [ ] Implement `POST /api/v1/documents/upload` endpoint:
  - Accept `multipart/form-data` with file
  - Optional parameters: `publication`, `title`, `process_immediately`
  - Return document ID, status, metadata
- [ ] Implement file size validation
- [ ] Implement format validation

### 5.2 Create Status Endpoint
- [ ] Implement `GET /api/v1/documents/{id}` endpoint
- [ ] Return document status, metadata, content summary
- [ ] Include linked newsletter ID if available

### 5.3 Register Routes
- [ ] Register upload router in `src/api/app.py`
- [ ] Add OpenAPI documentation for endpoints
- [ ] Test endpoints manually with sample files

## Phase 6: Testing

### 6.1 Unit Tests for DoclingParser
- [ ] Create `tests/test_parsers/test_docling_parser.py`
- [ ] Test PDF parsing with tables
- [ ] Test DOCX parsing
- [ ] Test image parsing (with OCR mocked)
- [ ] Test error handling for corrupt files
- [ ] Test format detection

### 6.2 Unit Tests for FileIngestionService
- [ ] Create `tests/test_ingestion/test_files.py`
- [ ] Test successful file ingestion
- [ ] Test duplicate detection
- [ ] Test Newsletter model mapping
- [ ] Test error handling

### 6.3 Integration Tests
- [ ] Test end-to-end upload flow
- [ ] Test router selection with Docling available
- [ ] Test fallback when Docling unavailable

### 6.4 Test Fixtures
- [ ] Add sample PDF with tables to `tests/fixtures/documents/`
- [ ] Add sample DOCX to fixtures
- [ ] Add sample scanned PDF for OCR testing (optional)

## Phase 7: Documentation

### 7.1 Update Documentation
- [ ] Update `docs/plans/2026-01-09-docling-document-parsing.md` with completion status
- [ ] Add Docling configuration to `docs/SETUP.md`
- [ ] Update API documentation if auto-generated

### 7.2 Update CLAUDE.md
- [ ] Add lessons learned section for Docling integration
- [ ] Document any gotchas or best practices discovered

## Validation Checklist

- [ ] All existing tests pass (`pytest`)
- [ ] New tests pass with >80% coverage for new code
- [ ] Type checking passes (`mypy src/`)
- [ ] Linting passes (`ruff check src/`)
- [ ] Manual testing of file upload API works
- [ ] Router correctly selects Docling for PDFs
- [ ] Fallback to MarkItDown works when Docling disabled
