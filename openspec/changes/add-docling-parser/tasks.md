# Tasks: Add Docling Parser Integration

## Prerequisites
- [x] Review existing parser architecture in `src/parsers/`
- [x] Review `DocumentContent` model in `src/models/document.py`
- [x] Review router implementation in `src/parsers/router.py`

## Phase 1: Dependencies and Configuration

### 1.1 Add Docling Dependency
- [x] Add `docling>=2.60.0` to `pyproject.toml`
- [x] Add `docling[ocr]` as optional dependency group in `pyproject.toml`
- [ ] Verify installation works on target Python version (3.10+)
- [ ] Document any system dependencies (e.g., for OCR)

### 1.2 Add Parser Configuration
- [x] Add parser settings to `src/config/settings.py`:
  - `enable_docling: bool = True`
  - `docling_enable_ocr: bool = False`
  - `docling_max_file_size_mb: int = 100`
  - `docling_timeout_seconds: int = 300`
  - `docling_cache_dir: str = "/tmp/docling"`
- [x] Add environment variable mappings for all settings
- [x] Update `.env.example` with new configuration options

## Phase 2: DoclingParser Implementation

### 2.1 Create DoclingParser Class
- [x] Create `src/parsers/docling_parser.py`
- [x] Implement `DoclingParser(DocumentParser)` class:
  - `supported_formats = {"pdf", "docx", "png", "jpg", "jpeg", "html"}`
  - `fallback_formats = {"pptx", "xlsx"}`
  - `name` property returning `"docling"`
- [x] Implement `can_parse()` method with format checking
- [x] Implement `parse()` method using `DocumentConverter`

### 2.2 Implement Content Extraction
- [x] Implement `_extract_tables()` method:
  - Extract `TableData` with headers, rows, caption
  - Include markdown fallback for each table
- [x] Implement `_extract_metadata()` method:
  - Extract title, author, created_date, page_count
  - Handle missing metadata gracefully
- [x] Implement `_extract_links()` method:
  - Extract URLs from document content
  - Deduplicate and validate URLs

### 2.3 Add OCR Support
- [x] Add OCR configuration option to constructor
- [x] Configure Docling pipeline for OCR when enabled
- [x] Handle OCR-specific errors gracefully
- [x] Log warnings when OCR is needed but disabled

### 2.4 Register with Router
- [x] Update `src/parsers/__init__.py` to export `DoclingParser`
- [x] Update router instantiation to accept optional `DoclingParser`
- [x] Verify routing table correctly routes PDF/images to Docling

## Phase 3: File Ingestion Service

### 3.1 Create FileIngestionService
- [x] Create `src/ingestion/files.py`
- [x] Implement `FileIngestionService` class:
  - Constructor accepts `ParserRouter` and database session
  - `ingest_file()` method for single file processing
  - `ingest_bytes()` method for in-memory content
- [x] Implement file hash generation for deduplication
- [x] Implement duplicate detection and linking

### 3.2 Integrate with Newsletter Model
- [x] Map `DocumentContent` to `Newsletter` model fields
- [x] Set `source = NewsletterSource.FILE_UPLOAD`
- [x] Store extracted links in `extracted_links` field
- [x] Generate unique `source_id` from file hash

## Phase 4: Database Schema

### 4.1 Create Documents Table Migration
- [x] Create Alembic migration for `documents` table:
  - `id`, `filename`, `source_format`, `parser_used`
  - `markdown_content`, `tables_json`, `metadata_json`, `links_json`
  - `newsletter_id` (FK), `status`, `processing_time_ms`
  - `file_hash`, `file_size_bytes`, `uploaded_at`, `processed_at`
- [x] Add indexes: `file_hash`, `status`, `parser_used`, `newsletter_id`
- [ ] Test migration up and down

### 4.2 Create Document Model (Optional)
- [x] Decide if separate SQLAlchemy `Document` model is needed
  - Decision: Not needed for initial implementation. Newsletter model with FILE_UPLOAD source is sufficient.
- [ ] If yes, create `src/models/document_db.py` with ORM model
- [ ] Add relationship to `Newsletter` model

## Phase 5: File Upload API

### 5.1 Create Upload Endpoint
- [x] Create `src/api/upload_routes.py`
- [x] Implement `POST /api/v1/documents/upload` endpoint:
  - Accept `multipart/form-data` with file
  - Optional parameters: `publication`, `title`, `prefer_structured`, `ocr_needed`
  - Return document ID, status, metadata
- [x] Implement file size validation
- [x] Implement format validation

### 5.2 Create Status Endpoint
- [x] Implement `GET /api/v1/documents/{id}` endpoint
- [x] Return document status, metadata, content summary
- [x] Include linked newsletter ID if available

### 5.3 Register Routes
- [x] Register upload router in `src/api/app.py`
- [x] Add OpenAPI documentation for endpoints
- [ ] Test endpoints manually with sample files

## Phase 6: Testing

### 6.1 Unit Tests for DoclingParser
- [x] Create `tests/test_parsers/test_docling_parser.py`
- [x] Test PDF parsing with tables (mocked)
- [x] Test DOCX parsing (mocked)
- [x] Test image parsing (with OCR mocked)
- [x] Test error handling for corrupt files
- [x] Test format detection

### 6.2 Unit Tests for FileIngestionService
- [x] Create `tests/test_ingestion/test_files.py`
- [x] Test successful file ingestion
- [x] Test duplicate detection
- [x] Test Newsletter model mapping
- [x] Test error handling

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
- [x] Add lessons learned section for Docling integration
- [x] Document any gotchas or best practices discovered

## Validation Checklist

- [ ] All existing tests pass (`pytest`)
- [ ] New tests pass with >80% coverage for new code
- [ ] Type checking passes (`mypy src/`)
- [ ] Linting passes (`ruff check src/`)
- [ ] Manual testing of file upload API works
- [ ] Router correctly selects Docling for PDFs
- [ ] Fallback to MarkItDown works when Docling disabled

## Implementation Notes

### Completed: 2026-01-10

The following files were created/modified:
- `pyproject.toml` - Added docling dependency and optional ocr group
- `src/config/settings.py` - Added parser configuration settings
- `.env.example` - Added environment variable documentation
- `src/parsers/docling_parser.py` - Full DoclingParser implementation
- `src/parsers/__init__.py` - Added DoclingParser export
- `src/ingestion/files.py` - FileIngestionService implementation
- `alembic/versions/4d78f715c284_add_documents_table.py` - Database migration
- `src/api/upload_routes.py` - File upload API endpoints
- `src/api/app.py` - Registered upload router
- `tests/test_parsers/test_docling_parser.py` - Unit tests
- `tests/test_ingestion/test_files.py` - Unit tests
- `CLAUDE.md` - Added lessons learned
