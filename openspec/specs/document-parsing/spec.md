# document-parsing Specification

## Purpose
TBD - created by archiving change add-docling-parser. Update Purpose after archive.
## Requirements
### Requirement: Docling Parser Support

The system SHALL support Docling as an advanced document parser for complex PDFs, images with text, and documents requiring OCR.

#### Scenario: Parse PDF with complex layout
**Given** a PDF document with multi-column layout and tables
**When** the document is processed through DoclingParser
**Then** the content is extracted with correct reading order
**And** tables are extracted as structured data with headers and rows
**And** the result includes markdown representation

#### Scenario: Parse scanned document with OCR
**Given** a scanned PDF document (image-based, no text layer)
**And** OCR is enabled in configuration
**When** the document is processed through DoclingParser
**Then** text is extracted using OCR
**And** the result includes markdown representation of extracted text
**And** processing time is logged

#### Scenario: Parse image with text
**Given** an image file (PNG, JPG, JPEG) containing text
**When** the document is processed through DoclingParser
**Then** text is extracted from the image
**And** the result includes markdown representation

#### Scenario: Docling unavailable fallback
**Given** Docling parser is not configured or disabled
**When** a PDF document is submitted for parsing
**Then** the router falls back to MarkItDown parser
**And** a warning is logged about reduced capability

---

### Requirement: File Upload Ingestion

The system SHALL support direct file uploads as a document source, processing them through the parser system and storing as newsletters.

#### Scenario: Upload PDF document
**Given** a user uploads a PDF file via API
**When** the file is received
**Then** the file is validated for size and format
**And** the file is routed to appropriate parser
**And** a Newsletter record is created with FILE_UPLOAD source
**And** the response includes document ID and status

#### Scenario: Upload duplicate document
**Given** a user uploads a file that has been processed before
**When** the file hash matches an existing document
**Then** a new Newsletter record is created
**And** it is linked to the canonical Newsletter via `canonical_newsletter_id`
**And** the duplicate is not re-parsed

#### Scenario: Upload oversized file
**Given** a user uploads a file exceeding the size limit
**When** the file size is checked
**Then** the upload is rejected with 413 status
**And** an error message indicates the size limit

#### Scenario: Upload unsupported format
**Given** a user uploads a file with unsupported format
**When** the format is checked
**Then** the upload is rejected with 415 status
**And** an error message lists supported formats

---

### Requirement: Structured Table Extraction

The system SHALL extract tables from documents as structured data when using Docling parser.

#### Scenario: Extract table from PDF
**Given** a PDF document containing a data table
**When** processed through DoclingParser
**Then** tables are extracted with column headers identified
**And** each row is captured as a list of cell values
**And** table caption is captured if present
**And** markdown representation is included as fallback

#### Scenario: Multiple tables in document
**Given** a document containing multiple tables
**When** processed through DoclingParser
**Then** all tables are extracted in document order
**And** each table has unique identification
**And** page number is recorded for each table

---

### Requirement: Document Metadata Extraction

The system SHALL extract metadata from documents during parsing.

#### Scenario: Extract PDF metadata
**Given** a PDF document with embedded metadata
**When** processed through DoclingParser
**Then** title is extracted if present
**And** author is extracted if present
**And** creation date is extracted if present
**And** page count is calculated

#### Scenario: Missing metadata handling
**Given** a document without embedded metadata
**When** processed through DoclingParser
**Then** the filename is used as fallback title
**And** other metadata fields are null
**And** no error is raised

---

### Requirement: File Upload REST API

The system SHALL provide REST API endpoints for document upload and status checking.

#### Scenario: POST upload endpoint
**Given** a multipart form request with file attachment
**When** POST /api/v1/documents/upload is called
**Then** the file is processed asynchronously
**And** response includes document ID and initial status
**And** response status is 202 Accepted

#### Scenario: GET document status
**Given** a document ID from previous upload
**When** GET /api/v1/documents/{id} is called
**Then** response includes current processing status
**And** response includes metadata if available
**And** response includes linked newsletter ID if processed

---

### Requirement: Parser Router Selection

The parser router SHALL select the appropriate parser based on document format, with Docling as preferred parser for complex formats.

#### Scenario: Route PDF to Docling
**Given** Docling parser is available
**When** a PDF document is submitted for parsing
**Then** DoclingParser is selected

#### Scenario: Route PDF with OCR hint
**Given** a document filename contains "scanned" or "ocr"
**When** the document is submitted for parsing
**Then** DoclingParser is selected
**And** OCR is enabled for this document

#### Scenario: Route image to Docling
**Given** Docling parser is available
**When** an image file (PNG, JPG, JPEG) is submitted
**Then** DoclingParser is selected for text extraction

---
