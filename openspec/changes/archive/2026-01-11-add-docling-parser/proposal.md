# Proposal: Add Docling Parser Integration

## Change ID
`add-docling-parser`

## Status
`completed` (validated and ready for archive)

## Summary

Integrate [Docling](https://github.com/docling-project/docling) as an advanced document parser to complement the existing MarkItDown parser. This enables OCR for scanned documents, structured table extraction, and sophisticated PDF layout analysis—capabilities that MarkItDown lacks.

## Motivation

### Current State
The unified document parsing architecture is partially implemented:
- **Done**: `DocumentParser` interface, `DocumentContent` model, `ParserRouter`, `MarkItDownParser`, `YouTubeParser`
- **Missing**: `DoclingParser`, `FileIngestionService`, file upload API, Gmail attachment extraction

### Problem
1. **No OCR support**: Cannot process scanned PDFs or images with text
2. **Basic PDF handling**: MarkItDown provides text extraction but loses layout/structure
3. **No structured tables**: Tables extracted as markdown text, not queryable data
4. **No file upload path**: Users cannot upload documents directly to the system

### Solution
Implement DoclingParser and supporting infrastructure to:
- Process complex PDFs with ML-based layout analysis
- Extract tables as structured data (headers, rows, columns)
- Handle scanned documents via built-in OCR
- Enable direct file uploads through API endpoints

## Scope

### In Scope
1. `DoclingParser` implementation with table/metadata extraction
2. `FileIngestionService` for file upload processing
3. File upload REST API endpoint
4. Database migration for `documents` table
5. Parser configuration settings
6. Unit and integration tests

### Out of Scope
- Gmail attachment extraction (future work)
- VLM pipeline for complex layouts (future work)
- Batch processing API (future work)
- Audio transcription improvements (separate feature)

## Success Criteria

1. DoclingParser successfully processes PDF, DOCX, and image files
2. Tables extracted with structured data (>90% accuracy on test set)
3. OCR works on scanned documents when enabled
4. File upload API accepts and processes documents
5. Router correctly selects Docling for PDF/image formats
6. All existing tests continue to pass
7. New tests cover Docling-specific functionality

## Dependencies

### New Dependencies
- `docling>=2.60.0` - Core document conversion
- `docling[ocr]` (optional) - OCR support for scanned documents

### Existing Dependencies (no changes)
- `markitdown` - Continues as lightweight parser
- `pydantic` - Data models
- `fastapi` - API endpoints

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docling memory usage | Medium | High | File size limits, optional enablement |
| Slow PDF processing | Medium | Medium | Async processing, timeout configuration |
| Dependency conflicts | Low | Medium | Isolated optional dependency group |
| Breaking router changes | Low | High | Router already designed for optional parsers |

## Related Documents

- **Implementation Plan**: `docs/plans/2026-01-09-docling-document-parsing.md`
- **Existing Parser Code**: `src/parsers/`
- **Router Implementation**: `src/parsers/router.py`

## Affected Capabilities

- `document-parsing` - Adding new parser implementation and file ingestion
