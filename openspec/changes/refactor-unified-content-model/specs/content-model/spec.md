# Content Model Specification

## ADDED Requirements

### Requirement: Unified Content Storage

The system SHALL store all ingested content in a single `contents` table.

The system SHALL support the following content sources:
- GMAIL: Email newsletters
- RSS: RSS feed articles
- SUBSTACK_RSS: Substack-specific RSS
- FILE_UPLOAD: Uploaded documents (PDF, DOCX, etc.)
- YOUTUBE: YouTube video transcripts
- OTHER: Manually added content

The system SHALL store a unique source_id for each content item based on its origin.

The system SHALL support deduplication via content_hash with canonical_id linking.

#### Scenario: Gmail newsletter ingested as Content

- **WHEN** a Gmail newsletter is ingested
- **THEN** the system creates a Content record with source_type=GMAIL
- **AND** source_id is set to the Gmail message ID
- **AND** markdown_content contains the parsed email body
- **AND** raw_content preserves the original HTML

#### Scenario: File upload creates Content record

- **WHEN** a document is uploaded and parsed
- **THEN** the system creates a Content record with source_type=FILE_UPLOAD
- **AND** source_id is set to the file hash
- **AND** markdown_content contains the parser output
- **AND** parser_used records which parser was used

#### Scenario: YouTube transcript ingested as Content

- **WHEN** a YouTube video transcript is ingested
- **THEN** the system creates a Content record with source_type=YOUTUBE
- **AND** source_id is set to the video ID
- **AND** markdown_content contains timestamped transcript
- **AND** raw_content contains the original transcript segments as JSON

#### Scenario: Duplicate content detected

- **WHEN** content with matching content_hash already exists
- **THEN** the system creates a new Content record
- **AND** sets canonical_id to reference the existing content
- **AND** does not duplicate processing

---

### Requirement: Markdown as Canonical Format

The system SHALL store all content as markdown in the markdown_content field.

The system SHALL use markdown as the primary content format for:
- Ingested newsletters, documents, and transcripts
- Generated summaries
- Generated digests

The system SHALL preserve original content in raw_content when re-parsing may be needed.

#### Scenario: Email converted to markdown

- **WHEN** an HTML email is ingested
- **THEN** the system converts HTML to markdown
- **AND** stores the result in markdown_content
- **AND** preserves links and formatting

#### Scenario: PDF parsed to markdown

- **WHEN** a PDF document is parsed by DoclingParser
- **THEN** the system stores the markdown output in markdown_content
- **AND** extracts tables to tables_json
- **AND** extracts metadata to metadata_json

#### Scenario: Summary stored as markdown

- **WHEN** a summary is generated for content
- **THEN** the summary is stored as structured markdown
- **AND** follows the defined section conventions

---

### Requirement: Markdown Section Conventions

The system SHALL use consistent markdown section conventions for summaries and digests.

The system SHALL support the following sections for summaries:
- `## Executive Summary` - 2-3 sentence overview
- `## Key Themes` - Bulleted list with bold theme names
- `## Strategic Insights` - H3 subsections with relevance tags
- `## Technical Details` - Bulleted technical points
- `## Actionable Items` - Checkbox list of actions
- `## Notable Quotes` - Blockquoted excerpts
- `## Relevance Scores` - Key-value list of audience scores

The system SHALL support the following sections for digests:
- `## Executive Overview` - Multi-paragraph summary
- `## Strategic Insights` - H3 subsections with source references
- `## Technical Developments` - H3 subsections
- `## Emerging Trends` - H3 subsections with first-seen dates
- `## Actionable Recommendations` - H3 subsections by audience
- `## Sources` - Table of included content

#### Scenario: Summary markdown follows conventions

- **WHEN** a summary is generated
- **THEN** it contains all required sections in order
- **AND** each section uses the specified format
- **AND** the markdown is parseable by the section parser

#### Scenario: Digest markdown follows conventions

- **WHEN** a digest is generated
- **THEN** it contains all required sections in order
- **AND** strategic insights include source references
- **AND** the sources section lists all included content

#### Scenario: Relevance tags in subsections

- **WHEN** a strategic insight is written
- **THEN** it includes a relevance tag like `[Relevance: CTO, Engineering]`
- **AND** the tag appears on the line after the H3 heading

---

### Requirement: Embedded References

The system SHALL support embedded references for structured elements within markdown.

The system SHALL use the pattern `[TYPE:id]: description` for references.

Supported reference types:
- `[TABLE:id]` - Reference to table in tables_json
- `[IMAGE:id]` - Reference to image in metadata_json
- `[CODE:id]` - Reference to code block in metadata_json

The system SHALL store referenced data in the appropriate JSON field.

#### Scenario: Table embedded in content

- **WHEN** content contains a complex table
- **THEN** the table data is stored in tables_json with a unique ID
- **AND** the markdown contains `[TABLE:id]: caption`
- **AND** the reference can be resolved to render the table

#### Scenario: Image embedded in content

- **WHEN** content contains an image
- **THEN** image metadata is stored in metadata_json.images
- **AND** the markdown contains `[IMAGE:id]: description`
- **AND** the reference can be resolved to render the image

#### Scenario: Embedded reference rendering

- **WHEN** markdown with embedded references is rendered
- **THEN** references are replaced with rendered content
- **AND** tables are rendered as markdown tables or HTML
- **AND** images are rendered as img tags with appropriate paths

---

### Requirement: Section Parsing for UI

The system SHALL provide utilities to parse markdown into hierarchical sections.

The system SHALL extract section metadata including:
- Level (H1, H2, H3, etc.)
- Title
- Content (raw markdown)
- Metadata (extracted patterns like `[Relevance: ...]`)
- Subsections (nested sections)

The system SHALL support collapsible section rendering in the UI.

#### Scenario: Parse summary into sections

- **WHEN** a summary markdown is parsed
- **THEN** the system returns a list of MarkdownSection objects
- **AND** each section contains title, content, and subsections
- **AND** relevance tags are extracted to section metadata

#### Scenario: UI renders collapsible sections

- **WHEN** parsed sections are rendered in the UI
- **THEN** H2 sections become top-level collapsibles
- **AND** H3 sections become nested collapsibles
- **AND** sections can be expanded/collapsed independently

#### Scenario: Extract theme tags from sections

- **WHEN** the Key Themes section is parsed
- **THEN** the system extracts theme names as a list
- **AND** themes are stored in theme_tags for filtering

---

### Requirement: Content API

The system SHALL expose Content via REST API endpoints.

The system SHALL provide:
- GET /api/v1/contents - List with pagination and filtering
- GET /api/v1/contents/{id} - Get single content with markdown
- POST /api/v1/contents - Create content (for manual/API ingestion)
- DELETE /api/v1/contents/{id} - Delete content and related data

The system SHALL support filtering by:
- source_type
- publication
- date range (published_date)
- status
- author

#### Scenario: List contents with filtering

- **WHEN** a client requests GET /api/v1/contents?source_type=GMAIL&status=COMPLETED
- **THEN** the system returns paginated Content records
- **AND** only GMAIL sources with COMPLETED status are included
- **AND** response includes total count

#### Scenario: Get content with parsed sections

- **WHEN** a client requests GET /api/v1/contents/{id}?include=parsed_sections
- **THEN** the response includes the markdown_content
- **AND** the response includes parsed_sections array
- **AND** each section has title, content, and metadata

#### Scenario: Delete content cascades

- **WHEN** a client deletes a Content record
- **THEN** related Summary records are deleted
- **AND** related DocumentChunk records are deleted
- **AND** the operation is atomic

---

## MODIFIED Requirements

### Requirement: Summary Storage

The system SHALL store summaries with markdown_content as the primary content field.

The system SHALL reference Content via content_id foreign key.

The system SHALL extract theme_tags and relevance_scores from markdown for filtering.

The system SHALL deprecate separate JSON fields (key_themes, strategic_insights, etc.) in favor of markdown sections.

#### Scenario: Summary created with markdown

- **WHEN** the summarizer processes content
- **THEN** it generates structured markdown following section conventions
- **AND** stores the markdown in Summary.markdown_content
- **AND** extracts theme_tags from the Key Themes section
- **AND** extracts relevance_scores from the Relevance Scores section

#### Scenario: Summary API returns markdown

- **WHEN** a client requests a Summary
- **THEN** the response includes markdown_content
- **AND** optionally includes parsed_sections
- **AND** deprecated JSON fields are omitted or marked deprecated

---

### Requirement: Digest Storage

The system SHALL store digests with markdown_content as the primary content field.

The system SHALL track source content via source_content_ids JSON array.

The system SHALL extract theme_tags from markdown for filtering.

The system SHALL deprecate separate JSON fields in favor of markdown sections.

#### Scenario: Digest created with markdown

- **WHEN** the digest creator processes summaries
- **THEN** it generates structured markdown following section conventions
- **AND** stores the markdown in Digest.markdown_content
- **AND** populates source_content_ids with included Content IDs
- **AND** extracts theme_tags from the content

#### Scenario: Digest sources tracked

- **WHEN** a digest is created
- **THEN** source_content_ids contains IDs of all Content items included
- **AND** the Sources section in markdown lists these with titles and dates

---

## REMOVED Requirements

### Requirement: Newsletter Table

**Reason**: Merged into Content table. All newsletter data now stored in contents table with source_type indicating origin.

**Migration**: Data migrated to contents table with source_type=GMAIL, RSS, or SUBSTACK_RSS.

### Requirement: Document Table

**Reason**: Merged into Content table. Parsed document data now stored directly in contents.markdown_content with parser metadata.

**Migration**: Data migrated to contents table, joined with related Newsletter record where applicable.

### Requirement: Separate JSON Fields for Summary Sections

**Reason**: Replaced by markdown sections. JSON fields (key_themes, strategic_insights, technical_details, actionable_items, notable_quotes, relevant_links) are replaced by structured markdown with section conventions.

**Migration**: Existing summaries converted to markdown format. Theme tags and relevance scores extracted to indexed columns for filtering.
