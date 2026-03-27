## ADDED Requirements

### Requirement: Optional Kreuzberg Parser Support
The system SHALL support Kreuzberg as an optional document parser backend that can be enabled or disabled independently of MarkItDown and Docling.

#### Scenario: Kreuzberg enabled and installed
- **GIVEN** `enable_kreuzberg=true` and Kreuzberg dependencies are installed
- **WHEN** parser router initialization runs
- **THEN** Kreuzberg is registered as an available parser backend
- **AND** router availability metadata indicates Kreuzberg support

#### Scenario: Kreuzberg enabled but unavailable
- **GIVEN** `enable_kreuzberg=true` and Kreuzberg is not installed in the runtime environment
- **WHEN** parser router initialization runs
- **THEN** initialization completes without crashing
- **AND** a warning is logged indicating Kreuzberg is unavailable
- **AND** MarkItDown/Docling routing remains operational

### Requirement: Kreuzberg Output Normalization
The system SHALL normalize Kreuzberg extraction output into the existing `DocumentContent` model with markdown as canonical content.

#### Scenario: Kreuzberg parse success
- **GIVEN** a document format routed to Kreuzberg
- **WHEN** Kreuzberg parsing succeeds
- **THEN** the result stores markdown in `DocumentContent.markdown_content`
- **AND** `parser_used` is set to `kreuzberg`
- **AND** extracted metadata, links, and tables are mapped to existing optional fields when available

#### Scenario: Kreuzberg parse failure fallback
- **GIVEN** a document routed to Kreuzberg
- **WHEN** Kreuzberg parsing fails with a recoverable error
- **THEN** the router falls back to the configured fallback parser for the format
- **AND** the failure reason is logged with parser and format context

### Requirement: Parser Routing Preference Controls
The system SHALL support deterministic routing precedence when MarkItDown, Docling, and Kreuzberg are concurrently available.

#### Scenario: OCR-required document prefers Docling
- **GIVEN** `ocr_needed=true` for a PDF/image input and Docling is available
- **WHEN** routing is resolved
- **THEN** Docling remains the selected parser regardless of Kreuzberg availability

#### Scenario: Explicit Kreuzberg format preference
- **GIVEN** Kreuzberg is enabled and a format is configured as Kreuzberg-preferred
- **WHEN** a document of that format is routed without OCR override
- **THEN** Kreuzberg is selected as the parser
- **AND** fallback parser selection remains deterministic if Kreuzberg is unavailable or fails

### Requirement: Shadow Evaluation Mode for Parser Comparison
The system SHALL provide an optional shadow mode to compare Kreuzberg output against canonical parser output before production promotion.

#### Scenario: Shadow mode comparison run
- **GIVEN** shadow mode is enabled for a supported format
- **WHEN** a document is ingested
- **THEN** canonical parsing uses the active production parser
- **AND** Kreuzberg runs as a non-canonical comparison parse
- **AND** comparison telemetry is emitted for quality and performance evaluation

#### Scenario: Shadow mode failure isolation
- **GIVEN** shadow mode is enabled
- **WHEN** the shadow Kreuzberg parse fails
- **THEN** canonical ingestion success/failure semantics remain unchanged
- **AND** the shadow parse error is logged and metered separately
