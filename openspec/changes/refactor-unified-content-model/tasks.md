# Tasks: Unified Content Model Refactor

## 1. Database Schema

- [x] 1.1 Create `contents` table with all columns:
  - source_type, source_id, source_url
  - title, author, publication, published_date
  - markdown_content
  - tables_json, links_json, metadata_json
  - raw_content, raw_format
  - parser_used, parser_version
  - content_hash, canonical_id
  - status, error_message
  - ingested_at, parsed_at, processed_at
- [x] 1.2 Create indexes on contents:
  - source_type, source_id (unique composite)
  - content_hash
  - status
  - published_date
  - publication
- [ ] 1.3 Add `markdown_content` column to newsletter_summaries table
- [ ] 1.4 Add `theme_tags` JSON column to newsletter_summaries table
- [ ] 1.5 Add `markdown_content` column to digests table
- [ ] 1.6 Add `theme_tags` and `source_content_ids` JSON columns to digests table
- [ ] 1.7 Create `images` table with all columns:
  - id (UUID), source_type (EXTRACTED, KEYFRAME, AI_GENERATED)
  - source_content_id, source_summary_id, source_digest_id (FKs)
  - source_url, video_id, timestamp_seconds, deep_link_url
  - storage_path, storage_provider
  - filename, mime_type, width, height, file_size_bytes
  - alt_text, caption, ai_description
  - generation_prompt, generation_model, generation_params (JSON)
  - phash (perceptual hash for dedup)
  - created_at
- [ ] 1.8 Create indexes on images:
  - source_content_id, source_summary_id, source_digest_id
  - source_type
  - phash (for deduplication)
  - video_id (for YouTube keyframes)
- [ ] 1.9 Update foreign keys:
  - newsletter_summaries.newsletter_id → content_id
  - document_chunks.source_id → content_id (after search implementation)

## 2. Content Model

- [x] 2.1 Create `src/models/content.py` with Content SQLAlchemy model
- [x] 2.2 Create ContentSource enum (merge NewsletterSource + new values)
- [ ] 2.3 Add relationships: Content → Summary, Content → Chunks (deferred to Phase 2)
- [x] 2.4 Create Pydantic schemas:
  - ContentCreate, ContentUpdate, ContentResponse
  - ContentListResponse with pagination
- [x] 2.5 Add content_hash generation utility (SHA-256 of normalized markdown)
  - Extended `src/utils/content_hash.py` with `normalize_markdown()` and `generate_markdown_hash()`
  - Added `generate_file_hash()` for file upload deduplication
- [x] 2.6 Add canonical_id logic for deduplication
  - Created `src/services/content_service.py` with `ContentService` class
  - Implements `find_by_hash()`, `merge_duplicates()`, `get_duplicates()`
- [x] 2.7 Write unit tests for Content model

## 3. Markdown Utilities

- [x] 3.1 Create `src/utils/markdown.py` with parsing utilities
  - Created `MarkdownSection` dataclass for structured section representation
  - Added helper functions: `get_section_by_name()`, `sections_to_dict()`, `_flatten_sections()`
- [x] 3.2 Implement `parse_sections(markdown) -> list[MarkdownSection]`
  - Parses heading hierarchy (H1-H6), extracts content, list items, and nested subsections
- [x] 3.3 Implement `extract_theme_tags(markdown) -> list[str]`
  - Extracts from Key Themes section and hashtags (#ai, #MachineLearning)
  - Handles camelCase and kebab-case conversion, deduplication
- [x] 3.4 Implement `extract_relevance_scores(markdown) -> dict[str, float]`
  - Parses Relevance Scores section with **Category**: 0.85 format
  - Normalizes percentages (>1) to 0-1 range, clamps to valid bounds
- [x] 3.5 Implement `extract_embedded_refs(markdown) -> dict[str, list[str]]`
  - Extracts [TABLE:id], [IMAGE:id], [CODE:id] references
  - Handles optional params: [IMAGE:id|video=xxx&t=123]
- [x] 3.6 Implement `render_with_embeds(markdown, tables_json, images) -> str`
  - Replaces [TABLE:id] with rendered markdown tables
  - Replaces [IMAGE:id] with markdown/HTML img tags (with size params)
  - Handles [IMAGE:id|video=xxx&t=123] for YouTube thumbnails with deep links
- [x] 3.7 Write unit tests for markdown utilities
  - Created `tests/test_utils/test_markdown.py` with 54 comprehensive tests

## 4. Image Model and Services

- [ ] 4.1 Create `src/models/image.py` with Image SQLAlchemy model
- [ ] 4.2 Create ImageSource enum (EXTRACTED, KEYFRAME, AI_GENERATED)
- [ ] 4.3 Create Pydantic schemas:
  - ImageCreate, ImageResponse, ImageMetadata
- [ ] 4.4 Create `src/services/image_storage.py`:
  - Abstract storage interface
  - Local filesystem implementation for development
  - S3-compatible implementation for production
  - Configure via IMAGE_STORAGE_PROVIDER env var
- [ ] 4.5 Create `src/services/image_extractor.py`:
  - `extract_from_html(html) -> list[Image]` - Download external images
  - `extract_from_pdf(pdf_content) -> list[Image]` - Extract embedded images
  - `extract_youtube_keyframes(content) -> list[Image]` - Use existing KeyframeExtractor
  - Generate perceptual hashes for deduplication
- [ ] 4.6 Implement image deduplication via phash:
  - Check phash before storing new images
  - Link to existing image if duplicate found
- [ ] 4.7 Create `src/services/image_generator.py` (stub for future):
  - `generate_for_summary(summary, prompt) -> Image`
  - `suggest_images(content) -> list[ImageSuggestion]`
  - Store generation_prompt and generation_model for reproducibility
- [ ] 4.8 Add image configuration to settings.py:
  - IMAGE_STORAGE_PROVIDER (local, s3)
  - IMAGE_STORAGE_PATH (local path or S3 bucket)
  - IMAGE_MAX_SIZE_MB
  - ENABLE_YOUTUBE_KEYFRAMES
  - ENABLE_IMAGE_EXTRACTION
- [ ] 4.9 Write unit tests for image services

## 5. Summary Model Refactor

- [ ] 5.1 Update `src/models/summary.py`:
  - Add markdown_content column
  - Add theme_tags column
  - Rename newsletter_id → content_id
  - Keep legacy columns temporarily for migration
- [ ] 5.2 Create markdown template for summaries:
  ```
  ## Executive Summary
  ## Key Themes
  ## Strategic Insights
  ## Technical Details
  ## Actionable Items
  ## Notable Quotes
  ## Relevance Scores
  ```
- [ ] 5.3 Update summarizer prompt to output markdown format
- [ ] 5.4 Add post-processing to extract theme_tags from markdown
- [ ] 5.5 Add post-processing to extract relevance_scores from markdown
- [ ] 5.6 Update Summary Pydantic schemas
- [ ] 5.7 Write unit tests for Summary model changes

## 6. Digest Model Refactor

- [ ] 6.1 Update `src/models/digest.py`:
  - Add markdown_content column
  - Add theme_tags column
  - Add source_content_ids column
  - Keep legacy columns temporarily for migration
- [ ] 6.2 Create markdown template for digests:
  ```
  ## Executive Overview
  ## Strategic Insights
  ## Technical Developments
  ## Emerging Trends
  ## Actionable Recommendations
  ## Sources
  ```
- [ ] 6.3 Update digest_creator prompt to output markdown format
- [ ] 6.4 Add post-processing to extract theme_tags
- [ ] 6.5 Add post-processing to populate source_content_ids
- [ ] 6.6 Update Digest Pydantic schemas
- [ ] 6.7 Write unit tests for Digest model changes

## 7. Ingestion Updates

- [ ] 6.1 Update `src/ingestion/gmail.py`:
  - Create Content record instead of Newsletter
  - Store raw_html in raw_content
  - Parse to markdown immediately (or defer to processing)
- [ ] 6.2 Update `src/ingestion/substack.py`:
  - Create Content record
  - Store RSS content appropriately
- [ ] 6.3 Update `src/ingestion/files.py`:
  - Create Content record
  - Remove Document table creation
  - Store parser output directly in Content
- [ ] 6.4 Update `src/ingestion/youtube.py`:
  - Create Content record
  - Store transcript segments in raw_content as JSON
  - Store formatted markdown in markdown_content
- [ ] 6.5 Update deduplication logic to use Content.content_hash
- [ ] 6.6 Write integration tests for updated ingestion

## 8. Processor Updates

- [ ] 7.1 Update `src/processors/summarizer.py`:
  - Accept Content instead of Newsletter
  - Output markdown format
  - Store in Summary.markdown_content
  - Extract theme_tags and relevance_scores
- [ ] 7.2 Update `src/processors/digest_creator.py`:
  - Accept list of Content/Summary instead of Newsletter/Summary
  - Output markdown format
  - Store in Digest.markdown_content
  - Populate source_content_ids
- [ ] 7.3 Update `src/processors/theme_analyzer.py` if needed
- [ ] 7.4 Write unit tests for processor changes

## 9. API Updates

- [x] 8.1 Create `src/api/content_routes.py`:
  - GET /api/v1/contents - List with pagination, filtering
  - GET /api/v1/contents/{id} - Get single content
  - POST /api/v1/contents - Create (for manual/API ingestion)
  - DELETE /api/v1/contents/{id} - Delete content
  - GET /api/v1/contents/stats - Statistics endpoint
  - GET /api/v1/contents/{id}/duplicates - Get duplicates
  - POST /api/v1/contents/{id}/merge/{duplicate_id} - Merge duplicates
- [ ] 8.2 Update `src/api/newsletter_routes.py`:
  - Deprecate or redirect to content routes
  - Add deprecation warnings
- [ ] 8.3 Update `src/api/summary_routes.py`:
  - Return markdown_content in response
  - Add parsed_sections option for structured response
- [ ] 8.4 Update `src/api/digest_routes.py`:
  - Return markdown_content in response
  - Add parsed_sections option
- [x] 8.5 Register new routes in `src/api/app.py`
- [ ] 8.6 Write API tests

## 10. Data Migration

- [ ] 9.1 Create Alembic migration for new schema
- [ ] 9.2 Create migration script `src/scripts/migrate_to_content.py`:
  - Read Newsletter + Document pairs
  - Create Content records with merged data
  - Handle orphaned Documents (no Newsletter)
  - Handle Newsletters without Documents
  - Log progress and errors
- [ ] 9.3 Create migration script for Summary markdown:
  - Read existing Summary records
  - Generate markdown from JSON fields
  - Update markdown_content column
  - Extract and store theme_tags
- [ ] 9.4 Create migration script for Digest markdown:
  - Read existing Digest records
  - Generate markdown from JSON fields
  - Update markdown_content column
  - Populate source_content_ids from sources JSON
- [ ] 9.5 Add dry-run mode to all migration scripts
- [ ] 9.6 Add rollback capability
- [ ] 9.7 Test migrations on copy of production data

## 11. Cleanup

- [ ] 10.1 Remove dual-write code after migration verified
- [ ] 10.2 Create Alembic migration to:
  - Drop newsletters table
  - Drop documents table
  - Drop legacy JSON columns from newsletter_summaries
  - Drop legacy JSON columns from digests
  - Rename content_id back if needed
- [ ] 10.3 Remove deprecated model files:
  - src/models/newsletter.py (or mark deprecated)
  - src/models/document.py (or mark deprecated)
- [ ] 10.4 Update imports throughout codebase
- [ ] 10.5 Update CLAUDE.md with new model documentation

## 12. Documentation

- [ ] 11.1 Update `docs/ARCHITECTURE.md` with new data model
- [ ] 11.2 Document markdown format conventions
- [ ] 11.3 Document embedded reference patterns
- [ ] 11.4 Update API documentation
- [ ] 11.5 Add migration guide for API clients

## 13. Testing & Validation

- [ ] 12.1 Run full test suite
- [ ] 12.2 Test ingestion from all sources (Gmail, RSS, Files, YouTube)
- [ ] 12.3 Test summarization with markdown output
- [ ] 12.4 Test digest creation with markdown output
- [ ] 12.5 Test API responses
- [ ] 12.6 Test UI rendering of markdown sections
- [ ] 12.7 Validate migrated data integrity
- [ ] 12.8 Performance testing (query speed, storage size)
- [ ] 12.9 Fix test database setup to auto-apply migrations
  - API tests use `newsletters_test` database which needs migrations
  - Update `tests/api/conftest.py` to run alembic migrations or use `Base.metadata.create_all()`
  - Ensure test database includes new `contents` table and enums
