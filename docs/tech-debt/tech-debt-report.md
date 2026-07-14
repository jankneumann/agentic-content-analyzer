# Tech Debt Analysis Report

**Timestamp**: 2026-07-04T21:38:16.887212+00:00
**Analyzers**: coupling, imports, duplication, complexity
**Severity filter**: high
**Total findings**: 689
**Filtered out**: 6345 findings below 'high' severity

## Summary

### By Severity

| Severity | Count |
|----------|-------|
| high | 689 |

### By Category (Code Smell)

| Category | Count | Refactoring Reference |
|----------|-------|-----------------------|
| duplicate-code | 393 | Fowler: Extract Method / Pull Up Method |
| long-method | 119 | Fowler: Extract Method |
| parameter-excess | 56 | Fowler: Introduce Parameter Object |
| complex-function | 51 | Fowler: Decompose Conditional |
| deep-nesting | 36 | Fowler: Guard Clauses |
| import-complexity | 19 | Extract shared types module |
| large-file | 12 | Fowler: Extract Class / Move Method |
| high-coupling | 3 | AWS Builders' Library: Minimize Blast Radius |

### Hotspot Files (most findings)

| File | Findings |
|------|----------|
| src/cli/ingest_commands.py | 34 |
| tests/integration/test_digest_creation_flow_functional.py | 33 |
| src/services/llm_router.py | 25 |
| src/ingestion/blog_scraper.py | 22 |
| scripts/analyze_themes.py | 17 |
| tests/api/conftest.py | 17 |
| src/ingestion/youtube.py | 16 |
| src/api/chat_routes.py | 14 |
| src/agents/specialists/analysis.py | 13 |
| src/services/chunking.py | 11 |

## Critical / High Findings

### [HIGH] Complex function: interactive_script_review() has complexity 20

- **Category**: complex-function
- **Location**: `scripts/generate_podcast.py:81`
- **Span**: lines 81-232
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'interactive_script_review' in scripts/generate_podcast.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: generate_podcast() has complexity 23

- **Category**: complex-function
- **Location**: `scripts/generate_podcast.py:251`
- **Span**: lines 251-494
- **Metric**: cyclomatic_complexity = 23 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'generate_podcast' in scripts/generate_podcast.py has McCabe complexity 23 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: main() has complexity 38

- **Category**: complex-function
- **Location**: `scripts/railway_env_sync.py:195`
- **Span**: lines 195-355
- **Metric**: cyclomatic_complexity = 38 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'main' in scripts/railway_env_sync.py has McCabe complexity 38 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: interactive_revision_session() has complexity 23

- **Category**: complex-function
- **Location**: `scripts/review_digest.py:102`
- **Span**: lines 102-330
- **Metric**: cyclomatic_complexity = 23 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'interactive_revision_session' in scripts/review_digest.py has McCabe complexity 23 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: get_artifact_content() has complexity 40

- **Category**: complex-function
- **Location**: `src/api/chat_routes.py:225`
- **Span**: lines 225-394
- **Metric**: cyclomatic_complexity = 40 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'get_artifact_content' in src/api/chat_routes.py has McCabe complexity 40 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: apply_action_to_summary() has complexity 22

- **Category**: complex-function
- **Location**: `src/api/chat_routes.py:572`
- **Span**: lines 572-648
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'apply_action_to_summary' in src/api/chat_routes.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: apply_action_to_digest() has complexity 23

- **Category**: complex-function
- **Location**: `src/api/chat_routes.py:651`
- **Span**: lines 651-722
- **Metric**: cyclomatic_complexity = 23 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'apply_action_to_digest' in src/api/chat_routes.py has McCabe complexity 23 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: apply_action_to_script() has complexity 23

- **Category**: complex-function
- **Location**: `src/api/chat_routes.py:725`
- **Span**: lines 725-848
- **Metric**: cyclomatic_complexity = 23 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'apply_action_to_script' in src/api/chat_routes.py has McCabe complexity 23 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: get_digest_sources() has complexity 25

- **Category**: complex-function
- **Location**: `src/api/digest_routes.py:607`
- **Span**: lines 607-685
- **Metric**: cyclomatic_complexity = 25 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'get_digest_sources' in src/api/digest_routes.py has McCabe complexity 25 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: readiness_check() has complexity 20

- **Category**: complex-function
- **Location**: `src/api/health_routes.py:103`
- **Span**: lines 103-196
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'readiness_check' in src/api/health_routes.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: upload_document() has complexity 26

- **Category**: complex-function
- **Location**: `src/api/upload_routes.py:257`
- **Span**: lines 257-404
- **Metric**: cyclomatic_complexity = 26 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'upload_document' in src/api/upload_routes.py has McCabe complexity 26 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: update_voice_setting() has complexity 20

- **Category**: complex-function
- **Location**: `src/api/voice_settings_routes.py:253`
- **Span**: lines 253-330
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'update_voice_setting' in src/api/voice_settings_routes.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: sync_secrets() has complexity 25

- **Category**: complex-function
- **Location**: `src/cli/deploy_commands.py:50`
- **Span**: lines 50-179
- **Metric**: cyclomatic_complexity = 25 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'sync_secrets' in src/cli/deploy_commands.py has McCabe complexity 25 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: backfill_tree_index_cmd() has complexity 20

- **Category**: complex-function
- **Location**: `src/cli/manage_commands.py:547`
- **Span**: lines 547-632
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'backfill_tree_index_cmd' in src/cli/manage_commands.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _list_scripts_direct() has complexity 21

- **Category**: complex-function
- **Location**: `src/cli/podcast_commands.py:160`
- **Span**: lines 160-239
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_list_scripts_direct' in src/cli/podcast_commands.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: migrate_env() has complexity 25

- **Category**: complex-function
- **Location**: `src/cli/profile_commands.py:438`
- **Span**: lines 438-606
- **Metric**: cyclomatic_complexity = 25 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'migrate_env' in src/cli/profile_commands.py has McCabe complexity 25 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: restore_from_cloud() has complexity 20

- **Category**: complex-function
- **Location**: `src/cli/restore_commands.py:125`
- **Span**: lines 125-305
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'restore_from_cloud' in src/cli/restore_commands.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: import_cmd() has complexity 24

- **Category**: complex-function
- **Location**: `src/cli/sync_commands.py:178`
- **Span**: lines 178-324
- **Metric**: cyclomatic_complexity = 24 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'import_cmd' in src/cli/sync_commands.py has McCabe complexity 24 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: push_cmd() has complexity 32

- **Category**: complex-function
- **Location**: `src/cli/sync_commands.py:328`
- **Span**: lines 328-579
- **Metric**: cyclomatic_complexity = 32 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'push_cmd' in src/cli/sync_commands.py has McCabe complexity 32 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: __init__() has complexity 20

- **Category**: complex-function
- **Location**: `src/config/models.py:309`
- **Span**: lines 309-402
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '__init__' in src/config/models.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _ingest_paper() has complexity 22

- **Category**: complex-function
- **Location**: `src/ingestion/arxiv.py:399`
- **Span**: lines 399-486
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_ingest_paper' in src/ingestion/arxiv.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: ingest_feed() has complexity 22

- **Category**: complex-function
- **Location**: `src/ingestion/podcast.py:176`
- **Span**: lines 176-327
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'ingest_feed' in src/ingestion/podcast.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _upsert_book() has complexity 20

- **Category**: complex-function
- **Location**: `src/ingestion/readwise.py:324`
- **Span**: lines 324-415
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_upsert_book' in src/ingestion/readwise.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _sync_highlights() has complexity 22

- **Category**: complex-function
- **Location**: `src/ingestion/readwise.py:421`
- **Span**: lines 421-495
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_sync_highlights' in src/ingestion/readwise.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: ingest_content() has complexity 26

- **Category**: complex-function
- **Location**: `src/ingestion/rss.py:462`
- **Span**: lines 462-732
- **Metric**: cyclomatic_complexity = 26 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'ingest_content' in src/ingestion/rss.py has McCabe complexity 26 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: ingest_content() has complexity 24

- **Category**: complex-function
- **Location**: `src/ingestion/substack.py:241`
- **Span**: lines 241-452
- **Metric**: cyclomatic_complexity = 24 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'ingest_content' in src/ingestion/substack.py has McCabe complexity 24 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _post_to_content() has complexity 25

- **Category**: complex-function
- **Location**: `src/ingestion/substack.py:454`
- **Span**: lines 454-514
- **Metric**: cyclomatic_complexity = 25 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_post_to_content' in src/ingestion/substack.py has McCabe complexity 25 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _process_video() has complexity 20

- **Category**: complex-function
- **Location**: `src/ingestion/youtube.py:615`
- **Span**: lines 615-850
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_process_video' in src/ingestion/youtube.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: ingest_all_playlists() has complexity 20

- **Category**: complex-function
- **Location**: `src/ingestion/youtube.py:962`
- **Span**: lines 962-1102
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'ingest_all_playlists' in src/ingestion/youtube.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _process_rss_video() has complexity 22

- **Category**: complex-function
- **Location**: `src/ingestion/youtube.py:1471`
- **Span**: lines 1471-1599
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_process_rss_video' in src/ingestion/youtube.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: extract_references() has complexity 21

- **Category**: complex-function
- **Location**: `src/mcp_server.py:1877`
- **Span**: lines 1877-1972
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'extract_references' in src/mcp_server.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: to_llm_context() has complexity 21

- **Category**: complex-function
- **Location**: `src/models/revision.py:109`
- **Span**: lines 109-226
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'to_llm_context' in src/models/revision.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _extract_metadata() has complexity 27

- **Category**: complex-function
- **Location**: `src/parsers/kreuzberg_parser.py:371`
- **Span**: lines 371-445
- **Metric**: cyclomatic_complexity = 27 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_extract_metadata' in src/parsers/kreuzberg_parser.py has McCabe complexity 27 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _run_ingestion() has complexity 25

- **Category**: complex-function
- **Location**: `src/pipeline/runner.py:21`
- **Span**: lines 21-148
- **Metric**: cyclomatic_complexity = 25 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_run_ingestion' in src/pipeline/runner.py has McCabe complexity 25 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _handle_tool_call() has complexity 21

- **Category**: complex-function
- **Location**: `src/processors/digest_reviser.py:213`
- **Span**: lines 213-298
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_handle_tool_call' in src/processors/digest_reviser.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _construct_from_fields() has complexity 28

- **Category**: complex-function
- **Location**: `src/processors/digest_text_preparer.py:412`
- **Span**: lines 412-513
- **Metric**: cyclomatic_complexity = 28 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_construct_from_fields' in src/processors/digest_text_preparer.py has McCabe complexity 28 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _register_content_handlers() has complexity 51

- **Category**: complex-function
- **Location**: `src/queue/worker.py:323`
- **Span**: lines 323-673
- **Metric**: cyclomatic_complexity = 51 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_register_content_handlers' in src/queue/worker.py has McCabe complexity 51 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: ingest_content() has complexity 38

- **Category**: complex-function
- **Location**: `src/queue/worker.py:420`
- **Span**: lines 420-640
- **Metric**: cyclomatic_complexity = 38 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'ingest_content' in src/queue/worker.py has McCabe complexity 38 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: chunk_content() has complexity 21

- **Category**: complex-function
- **Location**: `src/services/chunking.py:779`
- **Span**: lines 779-884
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'chunk_content' in src/services/chunking.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: generate_report() has complexity 20

- **Category**: complex-function
- **Location**: `src/services/evaluation_service.py:233`
- **Span**: lines 233-313
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'generate_report' in src/services/evaluation_service.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: search() has complexity 26

- **Category**: complex-function
- **Location**: `src/services/search.py:104`
- **Span**: lines 104-281
- **Metric**: cyclomatic_complexity = 26 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'search' in src/services/search.py has McCabe complexity 26 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: _import_table() has complexity 28

- **Category**: complex-function
- **Location**: `src/sync/pg_importer.py:286`
- **Span**: lines 286-429
- **Metric**: cyclomatic_complexity = 28 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function '_import_table' in src/sync/pg_importer.py has McCabe complexity 28 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: to_markdown() has complexity 40

- **Category**: complex-function
- **Location**: `src/utils/digest_formatter.py:10`
- **Span**: lines 10-165
- **Metric**: cyclomatic_complexity = 40 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'to_markdown' in src/utils/digest_formatter.py has McCabe complexity 40 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: to_plain_text() has complexity 27

- **Category**: complex-function
- **Location**: `src/utils/digest_formatter.py:168`
- **Span**: lines 168-285
- **Metric**: cyclomatic_complexity = 27 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'to_plain_text' in src/utils/digest_formatter.py has McCabe complexity 27 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: to_html() has complexity 42

- **Category**: complex-function
- **Location**: `src/utils/digest_formatter.py:288`
- **Span**: lines 288-631
- **Metric**: cyclomatic_complexity = 42 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'to_html' in src/utils/digest_formatter.py has McCabe complexity 42 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: generate_digest_markdown() has complexity 21

- **Category**: complex-function
- **Location**: `src/utils/digest_markdown.py:35`
- **Span**: lines 35-142
- **Metric**: cyclomatic_complexity = 21 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'generate_digest_markdown' in src/utils/digest_markdown.py has McCabe complexity 21 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: test_create_daily_digest_with_summaries() has complexity 22

- **Category**: complex-function
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:50`
- **Span**: lines 50-166
- **Metric**: cyclomatic_complexity = 22 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'test_create_daily_digest_with_summaries' in tests/integration/test_digest_creation_flow_functional.py has McCabe complexity 22 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: test_summarize_content_success() has complexity 20

- **Category**: complex-function
- **Location**: `tests/integration/test_summarization_workflow.py:21`
- **Span**: lines 21-64
- **Metric**: cyclomatic_complexity = 20 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'test_summarize_content_success' in tests/integration/test_summarization_workflow.py has McCabe complexity 20 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: test_to_markdown() has complexity 28

- **Category**: complex-function
- **Location**: `tests/test_utils/test_digest_formatter.py:98`
- **Span**: lines 98-143
- **Metric**: cyclomatic_complexity = 28 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'test_to_markdown' in tests/test_utils/test_digest_formatter.py has McCabe complexity 28 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: test_to_plain_text() has complexity 28

- **Category**: complex-function
- **Location**: `tests/test_utils/test_digest_formatter.py:146`
- **Span**: lines 146-188
- **Metric**: cyclomatic_complexity = 28 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'test_to_plain_text' in tests/test_utils/test_digest_formatter.py has McCabe complexity 28 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Complex function: test_to_html() has complexity 36

- **Category**: complex-function
- **Location**: `tests/test_utils/test_digest_formatter.py:324`
- **Span**: lines 324-376
- **Metric**: cyclomatic_complexity = 36 (threshold: 10)
- **Smell**: Complex Function — Fowler: Replace Conditional with Polymorphism
- **Detail**: Function 'test_to_html' in tests/test_utils/test_digest_formatter.py has McCabe complexity 36 (threshold: 10). High complexity correlates with bugs and makes testing harder.
- **Recommendation**: Replace Conditional with Polymorphism, or Extract Method to isolate branches.

### [HIGH] Long method: upgrade() is 100 lines

- **Category**: long-method
- **Location**: `alembic/versions/a1b2c3d4e5f8_add_podcast_tables.py:23`
- **Span**: lines 23-122
- **Metric**: function_lines = 100 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/a1b2c3d4e5f8_add_podcast_tables.py spans 100 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upgrade() is 131 lines

- **Category**: long-method
- **Location**: `alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:30`
- **Span**: lines 30-160
- **Metric**: function_lines = 131 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py spans 131 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upgrade() is 132 lines

- **Category**: long-method
- **Location**: `alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:28`
- **Span**: lines 28-159
- **Metric**: function_lines = 132 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/bc56c4b2e94d_add_evaluation_tables.py spans 132 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upgrade() is 230 lines

- **Category**: long-method
- **Location**: `alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:32`
- **Span**: lines 32-261
- **Metric**: function_lines = 230 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/c5f6a7b8d9e0_add_topic_tables.py spans 230 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upgrade() is 123 lines

- **Category**: long-method
- **Location**: `alembic/versions/f00ddf1d2b47_add_agent_tables.py:29`
- **Span**: lines 29-151
- **Metric**: function_lines = 123 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/f00ddf1d2b47_add_agent_tables.py spans 123 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upgrade() is 111 lines

- **Category**: long-method
- **Location**: `alembic/versions/f1a2b3c4d5e6_add_pgqueuer_jobs_table.py:26`
- **Span**: lines 26-136
- **Metric**: function_lines = 111 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upgrade' in alembic/versions/f1a2b3c4d5e6_add_pgqueuer_jobs_table.py spans 111 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: main_async() is 145 lines

- **Category**: long-method
- **Location**: `scripts/analyze_themes.py:19`
- **Span**: lines 19-163
- **Metric**: function_lines = 145 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'main_async' in scripts/analyze_themes.py spans 145 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: main_async() is 128 lines

- **Category**: long-method
- **Location**: `scripts/generate_daily_digest.py:19`
- **Span**: lines 19-146
- **Metric**: function_lines = 128 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'main_async' in scripts/generate_daily_digest.py spans 128 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: interactive_script_review() is 152 lines

- **Category**: long-method
- **Location**: `scripts/generate_podcast.py:81`
- **Span**: lines 81-232
- **Metric**: function_lines = 152 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'interactive_script_review' in scripts/generate_podcast.py spans 152 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_podcast() is 244 lines

- **Category**: long-method
- **Location**: `scripts/generate_podcast.py:251`
- **Span**: lines 251-494
- **Metric**: function_lines = 244 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_podcast' in scripts/generate_podcast.py spans 244 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: main_async() is 138 lines

- **Category**: long-method
- **Location**: `scripts/generate_weekly_digest.py:19`
- **Span**: lines 19-156
- **Metric**: function_lines = 138 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'main_async' in scripts/generate_weekly_digest.py spans 138 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: main() is 161 lines

- **Category**: long-method
- **Location**: `scripts/railway_env_sync.py:195`
- **Span**: lines 195-355
- **Metric**: function_lines = 161 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'main' in scripts/railway_env_sync.py spans 161 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: interactive_revision_session() is 229 lines

- **Category**: long-method
- **Location**: `scripts/review_digest.py:102`
- **Span**: lines 102-330
- **Metric**: function_lines = 229 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'interactive_revision_session' in scripts/review_digest.py spans 229 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: main() is 103 lines

- **Category**: long-method
- **Location**: `scripts/review_digest.py:375`
- **Span**: lines 375-477
- **Metric**: function_lines = 103 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'main' in scripts/review_digest.py spans 103 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: execute_task() is 190 lines

- **Category**: long-method
- **Location**: `src/agents/conductor.py:96`
- **Span**: lines 96-285
- **Metric**: function_lines = 190 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'execute_task' in src/agents/conductor.py spans 190 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _execute_tool() is 123 lines

- **Category**: long-method
- **Location**: `src/agents/specialists/analysis.py:134`
- **Span**: lines 134-256
- **Metric**: function_lines = 123 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_execute_tool' in src/agents/specialists/analysis.py spans 123 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_audio_digest_task() is 147 lines

- **Category**: long-method
- **Location**: `src/api/audio_digest_routes.py:35`
- **Span**: lines 35-181
- **Metric**: function_lines = 147 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_audio_digest_task' in src/api/audio_digest_routes.py spans 147 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: get_artifact_content() is 170 lines

- **Category**: long-method
- **Location**: `src/api/chat_routes.py:225`
- **Span**: lines 225-394
- **Metric**: function_lines = 170 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'get_artifact_content' in src/api/chat_routes.py spans 170 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: apply_action_to_script() is 124 lines

- **Category**: long-method
- **Location**: `src/api/chat_routes.py:725`
- **Span**: lines 725-848
- **Metric**: function_lines = 124 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'apply_action_to_script' in src/api/chat_routes.py spans 124 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: regenerate_last_message() is 115 lines

- **Category**: long-method
- **Location**: `src/api/chat_routes.py:1110`
- **Span**: lines 1110-1224
- **Metric**: function_lines = 115 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'regenerate_last_message' in src/api/chat_routes.py spans 115 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: list_contents() is 111 lines

- **Category**: long-method
- **Location**: `src/api/content_routes.py:371`
- **Span**: lines 371-481
- **Metric**: function_lines = 111 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'list_contents' in src/api/content_routes.py spans 111 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: register_error_handlers() is 163 lines

- **Category**: long-method
- **Location**: `src/api/middleware/error_handler.py:71`
- **Span**: lines 71-233
- **Metric**: function_lines = 163 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'register_error_handlers' in src/api/middleware/error_handler.py spans 163 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: proxy_traces() is 110 lines

- **Category**: long-method
- **Location**: `src/api/otel_proxy_routes.py:34`
- **Span**: lines 34-143
- **Metric**: function_lines = 110 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'proxy_traces' in src/api/otel_proxy_routes.py spans 110 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: upload_document() is 148 lines

- **Category**: long-method
- **Location**: `src/api/upload_routes.py:257`
- **Span**: lines 257-404
- **Metric**: function_lines = 148 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'upload_document' in src/api/upload_routes.py spans 148 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: voice_stream() is 110 lines

- **Category**: long-method
- **Location**: `src/api/voice_stream_routes.py:48`
- **Span**: lines 48-157
- **Metric**: function_lines = 110 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'voice_stream' in src/api/voice_stream_routes.py spans 110 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: task_status() is 111 lines

- **Category**: long-method
- **Location**: `src/cli/agent_commands.py:92`
- **Span**: lines 92-202
- **Metric**: function_lines = 111 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'task_status' in src/cli/agent_commands.py spans 111 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: themes() is 126 lines

- **Category**: long-method
- **Location**: `src/cli/analyze_commands.py:175`
- **Span**: lines 175-300
- **Metric**: function_lines = 126 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'themes' in src/cli/analyze_commands.py spans 126 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: curate_rss() is 114 lines

- **Category**: long-method
- **Location**: `src/cli/curate_commands.py:42`
- **Span**: lines 42-155
- **Metric**: function_lines = 114 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'curate_rss' in src/cli/curate_commands.py spans 114 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: find_moved() is 109 lines

- **Category**: long-method
- **Location**: `src/cli/curate_commands.py:221`
- **Span**: lines 221-329
- **Metric**: function_lines = 109 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'find_moved' in src/cli/curate_commands.py spans 109 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: sync_secrets() is 130 lines

- **Category**: long-method
- **Location**: `src/cli/deploy_commands.py:50`
- **Span**: lines 50-179
- **Metric**: function_lines = 130 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'sync_secrets' in src/cli/deploy_commands.py spans 130 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: create_weekly_digest() is 102 lines

- **Category**: long-method
- **Location**: `src/cli/digest_commands.py:213`
- **Span**: lines 213-314
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'create_weekly_digest' in src/cli/digest_commands.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: edit_summary() is 116 lines

- **Category**: long-method
- **Location**: `src/cli/edit_commands.py:113`
- **Span**: lines 113-228
- **Metric**: function_lines = 116 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'edit_summary' in src/cli/edit_commands.py spans 116 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: query() is 113 lines

- **Category**: long-method
- **Location**: `src/cli/graph_commands.py:206`
- **Span**: lines 206-318
- **Metric**: function_lines = 113 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'query' in src/cli/graph_commands.py spans 113 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: list_jobs() is 123 lines

- **Category**: long-method
- **Location**: `src/cli/job_commands.py:223`
- **Span**: lines 223-345
- **Metric**: function_lines = 123 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'list_jobs' in src/cli/job_commands.py spans 123 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: history() is 150 lines

- **Category**: long-method
- **Location**: `src/cli/job_commands.py:374`
- **Span**: lines 374-523
- **Metric**: function_lines = 150 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'history' in src/cli/job_commands.py spans 150 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: list_topics() is 102 lines

- **Category**: long-method
- **Location**: `src/cli/kb_commands.py:144`
- **Span**: lines 144-245
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'list_topics' in src/cli/kb_commands.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: update_model_pricing_cmd() is 111 lines

- **Category**: long-method
- **Location**: `src/cli/manage_commands.py:636`
- **Span**: lines 636-746
- **Metric**: function_lines = 111 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'update_model_pricing_cmd' in src/cli/manage_commands.py spans 111 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _run_ingestion_stage_async() is 126 lines

- **Category**: long-method
- **Location**: `src/cli/pipeline_commands.py:143`
- **Span**: lines 143-268
- **Metric**: function_lines = 126 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_run_ingestion_stage_async' in src/cli/pipeline_commands.py spans 126 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: daily() is 156 lines

- **Category**: long-method
- **Location**: `src/cli/pipeline_commands.py:477`
- **Span**: lines 477-632
- **Metric**: function_lines = 156 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'daily' in src/cli/pipeline_commands.py spans 156 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: weekly() is 156 lines

- **Category**: long-method
- **Location**: `src/cli/pipeline_commands.py:636`
- **Span**: lines 636-791
- **Metric**: function_lines = 156 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'weekly' in src/cli/pipeline_commands.py spans 156 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: migrate_env() is 169 lines

- **Category**: long-method
- **Location**: `src/cli/profile_commands.py:438`
- **Span**: lines 438-606
- **Metric**: function_lines = 169 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'migrate_env' in src/cli/profile_commands.py spans 169 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: restore_from_cloud() is 181 lines

- **Category**: long-method
- **Location**: `src/cli/restore_commands.py:125`
- **Span**: lines 125-305
- **Metric**: function_lines = 181 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'restore_from_cloud' in src/cli/restore_commands.py spans 181 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: revise() is 142 lines

- **Category**: long-method
- **Location**: `src/cli/review_commands.py:485`
- **Span**: lines 485-626
- **Metric**: function_lines = 142 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'revise' in src/cli/review_commands.py spans 142 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: summarize_pending() is 139 lines

- **Category**: long-method
- **Location**: `src/cli/summarize_commands.py:78`
- **Span**: lines 78-216
- **Metric**: function_lines = 139 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'summarize_pending' in src/cli/summarize_commands.py spans 139 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: import_cmd() is 147 lines

- **Category**: long-method
- **Location**: `src/cli/sync_commands.py:178`
- **Span**: lines 178-324
- **Metric**: function_lines = 147 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'import_cmd' in src/cli/sync_commands.py spans 147 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: push_cmd() is 252 lines

- **Category**: long-method
- **Location**: `src/cli/sync_commands.py:328`
- **Span**: lines 328-579
- **Metric**: function_lines = 252 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'push_cmd' in src/cli/sync_commands.py spans 252 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: obsidian_cmd() is 147 lines

- **Category**: long-method
- **Location**: `src/cli/sync_commands.py:583`
- **Span**: lines 583-729
- **Metric**: function_lines = 147 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'obsidian_cmd' in src/cli/sync_commands.py spans 147 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_audio() is 122 lines

- **Category**: long-method
- **Location**: `src/delivery/audio_generator.py:82`
- **Span**: lines 82-203
- **Metric**: function_lines = 122 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_audio' in src/delivery/audio_generator.py spans 122 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_audio() is 140 lines

- **Category**: long-method
- **Location**: `src/delivery/audio_generator_v2.py:137`
- **Span**: lines 137-276
- **Metric**: function_lines = 140 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_audio' in src/delivery/audio_generator_v2.py spans 140 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: concatenate_mp3_files() is 146 lines

- **Category**: long-method
- **Location**: `src/delivery/audio_utils.py:16`
- **Span**: lines 16-161
- **Metric**: function_lines = 146 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'concatenate_mp3_files' in src/delivery/audio_utils.py spans 146 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _ingest_source() is 109 lines

- **Category**: long-method
- **Location**: `src/ingestion/blog_scraper.py:476`
- **Span**: lines 476-584
- **Metric**: function_lines = 109 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_ingest_source' in src/ingestion/blog_scraper.py spans 109 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _persist_contents() is 138 lines

- **Category**: long-method
- **Location**: `src/ingestion/blog_scraper.py:586`
- **Span**: lines 586-723
- **Metric**: function_lines = 138 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_persist_contents' in src/ingestion/blog_scraper.py spans 138 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _fetch_and_parse_content() is 107 lines

- **Category**: long-method
- **Location**: `src/ingestion/gmail.py:369`
- **Span**: lines 369-475
- **Metric**: function_lines = 107 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_fetch_and_parse_content' in src/ingestion/gmail.py spans 107 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_content() is 198 lines

- **Category**: long-method
- **Location**: `src/ingestion/gmail.py:490`
- **Span**: lines 490-687
- **Metric**: function_lines = 198 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_content' in src/ingestion/gmail.py spans 198 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _persist_contents() is 170 lines

- **Category**: long-method
- **Location**: `src/ingestion/huggingface_papers.py:583`
- **Span**: lines 583-752
- **Metric**: function_lines = 170 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_persist_contents' in src/ingestion/huggingface_papers.py spans 170 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_content() is 175 lines

- **Category**: long-method
- **Location**: `src/ingestion/perplexity_search.py:253`
- **Span**: lines 253-427
- **Metric**: function_lines = 175 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_content' in src/ingestion/perplexity_search.py spans 175 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_feed() is 152 lines

- **Category**: long-method
- **Location**: `src/ingestion/podcast.py:176`
- **Span**: lines 176-327
- **Metric**: function_lines = 152 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_feed' in src/ingestion/podcast.py spans 152 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: fetch_content() is 110 lines

- **Category**: long-method
- **Location**: `src/ingestion/rss.py:65`
- **Span**: lines 65-174
- **Metric**: function_lines = 110 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'fetch_content' in src/ingestion/rss.py spans 110 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _parse_entry_content() is 107 lines

- **Category**: long-method
- **Location**: `src/ingestion/rss.py:211`
- **Span**: lines 211-317
- **Metric**: function_lines = 107 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_parse_entry_content' in src/ingestion/rss.py spans 107 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_content() is 271 lines

- **Category**: long-method
- **Location**: `src/ingestion/rss.py:462`
- **Span**: lines 462-732
- **Metric**: function_lines = 271 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_content' in src/ingestion/rss.py spans 271 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_from_search() is 112 lines

- **Category**: long-method
- **Location**: `src/ingestion/scholar.py:414`
- **Span**: lines 414-525
- **Metric**: function_lines = 112 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_from_search' in src/ingestion/scholar.py spans 112 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_content() is 212 lines

- **Category**: long-method
- **Location**: `src/ingestion/substack.py:241`
- **Span**: lines 241-452
- **Metric**: function_lines = 212 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_content' in src/ingestion/substack.py spans 212 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_threads() is 160 lines

- **Category**: long-method
- **Location**: `src/ingestion/xsearch.py:394`
- **Span**: lines 394-553
- **Metric**: function_lines = 160 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_threads' in src/ingestion/xsearch.py spans 160 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _process_video() is 236 lines

- **Category**: long-method
- **Location**: `src/ingestion/youtube.py:615`
- **Span**: lines 615-850
- **Metric**: function_lines = 236 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_process_video' in src/ingestion/youtube.py spans 236 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_playlist() is 109 lines

- **Category**: long-method
- **Location**: `src/ingestion/youtube.py:852`
- **Span**: lines 852-960
- **Metric**: function_lines = 109 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_playlist' in src/ingestion/youtube.py spans 109 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_all_playlists() is 141 lines

- **Category**: long-method
- **Location**: `src/ingestion/youtube.py:962`
- **Span**: lines 962-1102
- **Metric**: function_lines = 141 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_all_playlists' in src/ingestion/youtube.py spans 141 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_channels() is 149 lines

- **Category**: long-method
- **Location**: `src/ingestion/youtube.py:1104`
- **Span**: lines 1104-1252
- **Metric**: function_lines = 149 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_channels' in src/ingestion/youtube.py spans 149 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _process_rss_video() is 129 lines

- **Category**: long-method
- **Location**: `src/ingestion/youtube.py:1471`
- **Span**: lines 1471-1599
- **Metric**: function_lines = 129 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_process_rss_video' in src/ingestion/youtube.py spans 129 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: to_llm_context() is 118 lines

- **Category**: long-method
- **Location**: `src/models/revision.py:109`
- **Span**: lines 109-226
- **Metric**: function_lines = 118 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'to_llm_context' in src/models/revision.py spans 118 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: parse() is 107 lines

- **Category**: long-method
- **Location**: `src/parsers/kreuzberg_parser.py:149`
- **Span**: lines 149-255
- **Metric**: function_lines = 107 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'parse' in src/parsers/kreuzberg_parser.py spans 107 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _run_ingestion() is 128 lines

- **Category**: long-method
- **Location**: `src/pipeline/runner.py:21`
- **Span**: lines 21-148
- **Metric**: function_lines = 128 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_run_ingestion' in src/pipeline/runner.py spans 128 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate() is 119 lines

- **Category**: long-method
- **Location**: `src/processors/audio_digest_generator.py:78`
- **Span**: lines 78-196
- **Metric**: function_lines = 119 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate' in src/processors/audio_digest_generator.py spans 119 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: create_digest() is 143 lines

- **Category**: long-method
- **Location**: `src/processors/digest_creator.py:88`
- **Span**: lines 88-230
- **Metric**: function_lines = 143 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'create_digest' in src/processors/digest_creator.py spans 143 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _create_hierarchical_digest() is 120 lines

- **Category**: long-method
- **Location**: `src/processors/digest_creator.py:395`
- **Span**: lines 395-514
- **Metric**: function_lines = 120 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_create_hierarchical_digest' in src/processors/digest_creator.py spans 120 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _combine_sub_digests() is 158 lines

- **Category**: long-method
- **Location**: `src/processors/digest_creator.py:516`
- **Span**: lines 516-673
- **Metric**: function_lines = 158 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_combine_sub_digests' in src/processors/digest_creator.py spans 158 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_digest_content() is 137 lines

- **Category**: long-method
- **Location**: `src/processors/digest_creator.py:787`
- **Span**: lines 787-923
- **Metric**: function_lines = 137 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_digest_content' in src/processors/digest_creator.py spans 137 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _construct_from_fields() is 102 lines

- **Category**: long-method
- **Location**: `src/processors/digest_text_preparer.py:412`
- **Span**: lines 412-513
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_construct_from_fields' in src/processors/digest_text_preparer.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _analyze_evolution_with_llm() is 102 lines

- **Category**: long-method
- **Location**: `src/processors/historical_context.py:253`
- **Span**: lines 253-354
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_analyze_evolution_with_llm' in src/processors/historical_context.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_audio() is 168 lines

- **Category**: long-method
- **Location**: `src/processors/podcast_creator.py:168`
- **Span**: lines 168-335
- **Metric**: function_lines = 168 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_audio' in src/processors/podcast_creator.py spans 168 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_script_with_anthropic() is 101 lines

- **Category**: long-method
- **Location**: `src/processors/podcast_script_generator.py:307`
- **Span**: lines 307-407
- **Metric**: function_lines = 101 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_script_with_anthropic' in src/processors/podcast_script_generator.py spans 101 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_script_with_gemini() is 146 lines

- **Category**: long-method
- **Location**: `src/processors/podcast_script_generator.py:409`
- **Span**: lines 409-554
- **Metric**: function_lines = 146 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_script_with_gemini' in src/processors/podcast_script_generator.py spans 146 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _build_user_prompt() is 117 lines

- **Category**: long-method
- **Location**: `src/processors/podcast_script_generator.py:741`
- **Span**: lines 741-857
- **Metric**: function_lines = 117 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_build_user_prompt' in src/processors/podcast_script_generator.py spans 117 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: summarize_content() is 108 lines

- **Category**: long-method
- **Location**: `src/processors/summarizer.py:62`
- **Span**: lines 62-169
- **Metric**: function_lines = 108 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'summarize_content' in src/processors/summarizer.py spans 108 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: analyze_themes() is 105 lines

- **Category**: long-method
- **Location**: `src/processors/theme_analyzer.py:104`
- **Span**: lines 104-208
- **Metric**: function_lines = 105 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'analyze_themes' in src/processors/theme_analyzer.py spans 105 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _extract_themes_with_llm() is 138 lines

- **Category**: long-method
- **Location**: `src/processors/theme_analyzer.py:289`
- **Span**: lines 289-426
- **Metric**: function_lines = 138 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_extract_themes_with_llm' in src/processors/theme_analyzer.py spans 138 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: list_job_history() is 109 lines

- **Category**: long-method
- **Location**: `src/queue/setup.py:952`
- **Span**: lines 952-1060
- **Metric**: function_lines = 109 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'list_job_history' in src/queue/setup.py spans 109 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _register_content_handlers() is 351 lines

- **Category**: long-method
- **Location**: `src/queue/worker.py:323`
- **Span**: lines 323-673
- **Metric**: function_lines = 351 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_register_content_handlers' in src/queue/worker.py spans 351 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: ingest_content() is 221 lines

- **Category**: long-method
- **Location**: `src/queue/worker.py:420`
- **Span**: lines 420-640
- **Metric**: function_lines = 221 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'ingest_content' in src/queue/worker.py spans 221 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _backfill_full() is 118 lines

- **Category**: long-method
- **Location**: `src/scripts/backfill_chunks.py:91`
- **Span**: lines 91-208
- **Metric**: function_lines = 118 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_backfill_full' in src/scripts/backfill_chunks.py spans 118 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: switch_embeddings() is 121 lines

- **Category**: long-method
- **Location**: `src/scripts/switch_embeddings.py:25`
- **Span**: lines 25-145
- **Metric**: function_lines = 121 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'switch_embeddings' in src/scripts/switch_embeddings.py spans 121 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: chunk_content() is 106 lines

- **Category**: long-method
- **Location**: `src/services/chunking.py:779`
- **Span**: lines 779-884
- **Metric**: function_lines = 106 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'chunk_content' in src/services/chunking.py spans 106 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: classify() is 111 lines

- **Category**: long-method
- **Location**: `src/services/complexity_router.py:58`
- **Span**: lines 58-168
- **Metric**: function_lines = 111 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'classify' in src/services/complexity_router.py spans 111 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: preview() is 107 lines

- **Category**: long-method
- **Location**: `src/services/content_query.py:76`
- **Span**: lines 76-182
- **Metric**: function_lines = 107 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'preview' in src/services/content_query.py spans 107 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: process_client_html() is 106 lines

- **Category**: long-method
- **Location**: `src/services/html_processor.py:25`
- **Span**: lines 25-130
- **Metric**: function_lines = 106 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'process_client_html' in src/services/html_processor.py spans 106 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: build_tree_index() is 124 lines

- **Category**: long-method
- **Location**: `src/services/indexing.py:270`
- **Span**: lines 270-393
- **Metric**: function_lines = 124 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'build_tree_index' in src/services/indexing.py spans 124 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: query() is 100 lines

- **Category**: long-method
- **Location**: `src/services/kb_qa.py:66`
- **Span**: lines 66-165
- **Metric**: function_lines = 100 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'query' in src/services/kb_qa.py spans 100 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _run_compile() is 102 lines

- **Category**: long-method
- **Location**: `src/services/knowledge_base.py:166`
- **Span**: lines 166-267
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_run_compile' in src/services/knowledge_base.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate() is 105 lines

- **Category**: long-method
- **Location**: `src/services/llm_router.py:209`
- **Span**: lines 209-313
- **Metric**: function_lines = 105 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate' in src/services/llm_router.py spans 105 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_with_tools() is 160 lines

- **Category**: long-method
- **Location**: `src/services/llm_router.py:315`
- **Span**: lines 315-474
- **Metric**: function_lines = 160 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_with_tools' in src/services/llm_router.py spans 160 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_with_planning() is 209 lines

- **Category**: long-method
- **Location**: `src/services/llm_router.py:476`
- **Span**: lines 476-684
- **Metric**: function_lines = 209 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_with_planning' in src/services/llm_router.py spans 209 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_gemini_with_tools() is 115 lines

- **Category**: long-method
- **Location**: `src/services/llm_router.py:1461`
- **Span**: lines 1461-1575
- **Metric**: function_lines = 115 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_gemini_with_tools' in src/services/llm_router.py spans 115 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _generate_openai_with_tools() is 102 lines

- **Category**: long-method
- **Location**: `src/services/llm_router.py:1653`
- **Span**: lines 1653-1754
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_generate_openai_with_tools' in src/services/llm_router.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: search() is 178 lines

- **Category**: long-method
- **Location**: `src/services/search.py:104`
- **Span**: lines 104-281
- **Metric**: function_lines = 178 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'search' in src/services/search.py spans 178 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _aggregate_to_documents() is 127 lines

- **Category**: long-method
- **Location**: `src/services/search.py:458`
- **Span**: lines 458-584
- **Metric**: function_lines = 127 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_aggregate_to_documents' in src/services/search.py spans 127 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: export_content_stubs() is 100 lines

- **Category**: long-method
- **Location**: `src/sync/obsidian_exporter.py:500`
- **Span**: lines 500-599
- **Metric**: function_lines = 100 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'export_content_stubs' in src/sync/obsidian_exporter.py spans 100 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: _import_table() is 144 lines

- **Category**: long-method
- **Location**: `src/sync/pg_importer.py:286`
- **Span**: lines 286-429
- **Metric**: function_lines = 144 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function '_import_table' in src/sync/pg_importer.py spans 144 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: register_content_tasks() is 256 lines

- **Category**: long-method
- **Location**: `src/tasks/content.py:50`
- **Span**: lines 50-305
- **Metric**: function_lines = 256 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'register_content_tasks' in src/tasks/content.py spans 256 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: to_markdown() is 156 lines

- **Category**: long-method
- **Location**: `src/utils/digest_formatter.py:10`
- **Span**: lines 10-165
- **Metric**: function_lines = 156 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'to_markdown' in src/utils/digest_formatter.py spans 156 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: to_plain_text() is 118 lines

- **Category**: long-method
- **Location**: `src/utils/digest_formatter.py:168`
- **Span**: lines 168-285
- **Metric**: function_lines = 118 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'to_plain_text' in src/utils/digest_formatter.py spans 118 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: to_html() is 344 lines

- **Category**: long-method
- **Location**: `src/utils/digest_formatter.py:288`
- **Span**: lines 288-631
- **Metric**: function_lines = 344 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'to_html' in src/utils/digest_formatter.py spans 344 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_digest_markdown() is 108 lines

- **Category**: long-method
- **Location**: `src/utils/digest_markdown.py:35`
- **Span**: lines 35-142
- **Metric**: function_lines = 108 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_digest_markdown' in src/utils/digest_markdown.py spans 108 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: generate_summary_markdown() is 102 lines

- **Category**: long-method
- **Location**: `src/utils/summary_markdown.py:16`
- **Span**: lines 16-117
- **Metric**: function_lines = 102 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'generate_summary_markdown' in src/utils/summary_markdown.py spans 102 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: seeded_content() is 120 lines

- **Category**: long-method
- **Location**: `tests/api/test_search_api.py:122`
- **Span**: lines 122-241
- **Metric**: function_lines = 120 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'seeded_content' in tests/api/test_search_api.py spans 120 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: test_create_daily_digest_with_summaries() is 117 lines

- **Category**: long-method
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:50`
- **Span**: lines 50-166
- **Metric**: function_lines = 117 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'test_create_daily_digest_with_summaries' in tests/integration/test_digest_creation_flow_functional.py spans 117 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: test_digest_includes_all_newsletter_sources() is 107 lines

- **Category**: long-method
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:325`
- **Span**: lines 325-431
- **Metric**: function_lines = 107 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'test_digest_includes_all_newsletter_sources' in tests/integration/test_digest_creation_flow_functional.py spans 107 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: summaries_for_digest() is 132 lines

- **Category**: long-method
- **Location**: `tests/integration/test_markdown_outputs.py:71`
- **Span**: lines 71-202
- **Metric**: function_lines = 132 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'summaries_for_digest' in tests/integration/test_markdown_outputs.py spans 132 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: test_full_workflow_approve() is 119 lines

- **Category**: long-method
- **Location**: `tests/integration/test_review_workflow.py:49`
- **Span**: lines 49-167
- **Metric**: function_lines = 119 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'test_full_workflow_approve' in tests/integration/test_review_workflow.py spans 119 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: test_realistic_sources_directory() is 103 lines

- **Category**: long-method
- **Location**: `tests/test_config/test_sources.py:663`
- **Span**: lines 663-765
- **Metric**: function_lines = 103 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'test_realistic_sources_directory' in tests/test_config/test_sources.py spans 103 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Long method: test_branch_context_creates_and_deletes() is 103 lines

- **Category**: long-method
- **Location**: `tests/test_storage/test_neon_branch.py:536`
- **Span**: lines 536-638
- **Metric**: function_lines = 103 (threshold: 50)
- **Smell**: Long Method — Fowler: Extract Method
- **Detail**: Function 'test_branch_context_creates_and_deletes' in tests/test_storage/test_neon_branch.py spans 103 lines (threshold: 50). Long methods are harder to understand, test, and maintain.
- **Recommendation**: Extract Method: break into smaller, well-named functions.

### [HIGH] Duplicated code block (20 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:5`
- **Metric**: duplicate_copies = 20 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 20 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:5, alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:5, alembic/versions/3697508e93f1_add_prompt_overrides_table.py:5, alembic/versions/59fbc6999804_add_theme_analysis_table.py:5, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:8, ...and 15 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:17`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:17, alembic/versions/59fbc6999804_add_theme_analysis_table.py:17, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:17, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:17, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:17, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:7`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:7, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:7, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:7, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:7, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:7
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:8`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:8, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:8, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:8, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:8, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:8
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:10`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:10, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:10, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:10, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:10, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:10
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:11`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:11, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:11, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:11, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:11, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:11
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:15`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:15, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:15, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:15, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:15, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:15
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/02cfa5c75b82_merge_heads.py:16`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/02cfa5c75b82_merge_heads.py:16, alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:16, alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:16, alembic/versions/b8affd253096_merge_add_document_search_with_main.py:16, alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:16
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1455833d558b_add_huggingface_papers_source.py:6`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/1455833d558b_add_huggingface_papers_source.py:6, alembic/versions/22d53edb2933_add_perplexity_content_source.py:7, alembic/versions/a1b2c3d4e5f6_add_arxiv_source_type_and_jsonb.py:6, alembic/versions/add_blog_content_source.py:6, alembic/versions/d364355a18ba_add_xsearch_content_source.py:7
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1455833d558b_add_huggingface_papers_source.py:8`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/1455833d558b_add_huggingface_papers_source.py:8, alembic/versions/22d53edb2933_add_perplexity_content_source.py:9, alembic/versions/a1b2c3d4e5f6_add_arxiv_source_type_and_jsonb.py:8, alembic/versions/add_blog_content_source.py:8, alembic/versions/d364355a18ba_add_xsearch_content_source.py:9
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1455833d558b_add_huggingface_papers_source.py:11`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/1455833d558b_add_huggingface_papers_source.py:11, alembic/versions/22d53edb2933_add_perplexity_content_source.py:12, alembic/versions/a1b2c3d4e5f6_add_arxiv_source_type_and_jsonb.py:11, alembic/versions/add_blog_content_source.py:10, alembic/versions/d364355a18ba_add_xsearch_content_source.py:12
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:7`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:7, alembic/versions/3697508e93f1_add_prompt_overrides_table.py:7, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:9, alembic/versions/59fbc6999804_add_theme_analysis_table.py:7, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:10, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:8`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:8, alembic/versions/3697508e93f1_add_prompt_overrides_table.py:9, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:11, alembic/versions/59fbc6999804_add_theme_analysis_table.py:8, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:11, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:10`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:10, alembic/versions/3697508e93f1_add_prompt_overrides_table.py:11, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:13, alembic/versions/59fbc6999804_add_theme_analysis_table.py:10, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:13, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:11`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:11, alembic/versions/3697508e93f1_add_prompt_overrides_table.py:12, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:14, alembic/versions/59fbc6999804_add_theme_analysis_table.py:11, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:14, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:15`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:15, alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:14, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:18, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:18, alembic/versions/c4d5e6f7a8b9_add_tree_index_columns.py:20
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:16`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/16b8f13de9b6_add_content_hash_for_deduplication.py:16, alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:15, alembic/versions/41d180035213_add_markdown_content_and_theme_tags_.py:19, alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:19, alembic/versions/c4d5e6f7a8b9_add_tree_index_columns.py:21
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:11`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:11, alembic/versions/203a8919b20b_reset_failed_content_from_anthropic_.py:16, alembic/versions/2a0ca52d63c3_add_scholar_source_and_metadata_gin.py:10, alembic/versions/4d78f715c284_add_documents_table.py:12, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:11, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:7`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:7, alembic/versions/4d78f715c284_add_documents_table.py:7, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:6, alembic/versions/7136703eacbc_add_filter_columns_to_contents.py:9, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:11, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:8`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:8, alembic/versions/4d78f715c284_add_documents_table.py:9, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:8, alembic/versions/7136703eacbc_add_filter_columns_to_contents.py:11, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:13, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:10`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:10, alembic/versions/4d78f715c284_add_documents_table.py:11, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:10, alembic/versions/7136703eacbc_add_filter_columns_to_contents.py:13, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:15, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:5`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/1fdacd9de420_add_version_and_description_to_prompt_.py:5, alembic/versions/4d78f715c284_add_documents_table.py:5, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:5, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:9, alembic/versions/d8c7c9b9430a_add_youtube_and_file_upload_source_types.py:5
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/203a8919b20b_reset_failed_content_from_anthropic_.py:13`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/203a8919b20b_reset_failed_content_from_anthropic_.py:13, alembic/versions/2a0ca52d63c3_add_scholar_source_and_metadata_gin.py:7, alembic/versions/7238482da990_move_youtube_metadata_from_links_json_.py:11, alembic/versions/a2b3c4d5e6f7_add_substack_content_source.py:7, alembic/versions/c82a19e5d943_add_filtered_out_status.py:10, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/203a8919b20b_reset_failed_content_from_anthropic_.py:14`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/203a8919b20b_reset_failed_content_from_anthropic_.py:14, alembic/versions/2a0ca52d63c3_add_scholar_source_and_metadata_gin.py:8, alembic/versions/7238482da990_move_youtube_metadata_from_links_json_.py:12, alembic/versions/a2b3c4d5e6f7_add_substack_content_source.py:8, alembic/versions/c82a19e5d943_add_filtered_out_status.py:12, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (15 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/3697508e93f1_add_prompt_overrides_table.py:16`
- **Metric**: duplicate_copies = 15 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 15 times (cross-file). Locations: alembic/versions/3697508e93f1_add_prompt_overrides_table.py:16, alembic/versions/4d78f715c284_add_documents_table.py:15, alembic/versions/76ed931b3444_add_digest_review_fields.py:15, alembic/versions/7852b615ddcc_add_chat_tables.py:17, alembic/versions/8753a5a83a94_drop_newsletter_table_and_fk.py:27, ...and 10 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:40`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: alembic/versions/5a65cf4fe7b6_add_content_id_to_newsletter_summaries.py:40, alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:31, alembic/versions/8753a5a83a94_drop_newsletter_table_and_fk.py:108, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:78, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:97, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:32`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/6b7c8d9e0f1a_refactor_pgqueuer_reliability.py:32, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:79, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:98, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:159, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:178, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (162 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/a1b2c3d4e5f8_add_podcast_tables.py:45`
- **Metric**: duplicate_copies = 162 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 162 times (cross-file). Locations: alembic/versions/a1b2c3d4e5f8_add_podcast_tables.py:45, alembic/versions/b84e1839d132_add_contents_table.py:23, alembic/versions/b84e1839d132_add_contents_table.py:32, alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:284, openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:30, ...and 157 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/a8b9c0d1e2f3_add_images_table.py:99`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/a8b9c0d1e2f3_add_images_table.py:99, alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:62, alembic/versions/b84e1839d132_add_contents_table.py:94, alembic/versions/c1d2e3f4g5h6_add_audio_digests_table.py:97, alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:215
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:20`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:20, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:19, alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:23, alembic/versions/f00ddf1d2b47_add_agent_tables.py:20, alembic/versions/f9a8b7c6d5e5_add_index_to_canonical_id.py:12
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b3c4d5e6f7a8_add_content_references.py:16`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: alembic/versions/b3c4d5e6f7a8_add_content_references.py:16, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:22, alembic/versions/e1f2a3b4c5d6_add_performance_indexes.py:15, alembic/versions/f00ddf1d2b47_add_agent_tables.py:23, alembic/versions/f1a2b3c4d5e6_add_pgqueuer_jobs_table.py:20, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b3c4d5e6f7a8_add_content_references.py:36`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/b3c4d5e6f7a8_add_content_references.py:36, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:65, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:87, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:108, alembic/versions/c9d3e1f5a7b2_add_readwise_source_and_highlights.py:39
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b3c4d5e6f7a8_add_content_references.py:37`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/b3c4d5e6f7a8_add_content_references.py:37, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:66, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:88, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:109, alembic/versions/c9d3e1f5a7b2_add_readwise_source_and_highlights.py:40
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b3c4d5e6f7a8_add_content_references.py:38`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/b3c4d5e6f7a8_add_content_references.py:38, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:67, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:89, alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:110, alembic/versions/c9d3e1f5a7b2_add_readwise_source_and_highlights.py:41
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:31`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:31, alembic/versions/b846f2b0247c_rename_newsletter_summaries_to_summaries.py:112, alembic/versions/c1d2e3f4g5h6_add_audio_digests_table.py:48, alembic/versions/c1d2e3f4g5h6_add_audio_digests_table.py:117, alembic/versions/f1a2b3c4d5e6_add_pgqueuer_jobs_table.py:29
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (26 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `openspec/archive/2026-04-11-add-falkordb-graph-provider/contracts/settings_fields.py:58`
- **Metric**: duplicate_copies = 26 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 26 times (cross-file). Locations: openspec/archive/2026-04-11-add-falkordb-graph-provider/contracts/settings_fields.py:58, src/api/chat_routes.py:526, src/delivery/tts_service.py:536, src/mcp_server.py:1007, src/models/jobs.py:129, ...and 21 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:95`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:95, src/parsers/docling_parser.py:103, src/parsers/kreuzberg_parser.py:144, src/parsers/markitdown_parser.py:84, src/parsers/youtube_parser.py:50
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:96`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:96, src/parsers/docling_parser.py:104, src/parsers/kreuzberg_parser.py:145, src/parsers/markitdown_parser.py:85, src/parsers/youtube_parser.py:51
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:97`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:97, src/parsers/docling_parser.py:105, src/parsers/kreuzberg_parser.py:146, src/parsers/markitdown_parser.py:86, src/parsers/youtube_parser.py:52
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:98`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: openspec/changes/archive/2026-03-27-add-kreuzberg-optional-parser/contracts/generated/kreuzberg_adapter.py:98, src/parsers/docling_parser.py:106, src/parsers/kreuzberg_parser.py:147, src/parsers/markitdown_parser.py:87, src/parsers/youtube_parser.py:53
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (24 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:206`
- **Metric**: duplicate_copies = 24 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 24 times (cross-file). Locations: scripts/analyze_themes.py:206, scripts/analyze_themes.py:216, scripts/analyze_themes.py:223, scripts/bao_seed_newsletter.py:320, scripts/bao_seed_newsletter.py:330, ...and 19 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (21 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:202`
- **Metric**: duplicate_copies = 21 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 21 times (cross-file). Locations: scripts/analyze_themes.py:202, scripts/analyze_themes.py:214, scripts/bao_seed_newsletter.py:323, scripts/generate_daily_digest.py:177, scripts/generate_daily_digest.py:189, ...and 16 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:182`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: scripts/analyze_themes.py:182, scripts/analyze_themes.py:190, scripts/generate_daily_digest.py:157, scripts/generate_daily_digest.py:165, scripts/generate_daily_digest.py:171, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:211`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (cross-file). Locations: scripts/analyze_themes.py:211, scripts/generate_daily_digest.py:154, scripts/generate_daily_digest.py:186, scripts/generate_daily_digest.py:203, scripts/generate_weekly_digest.py:203, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:186`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (cross-file). Locations: scripts/analyze_themes.py:186, scripts/analyze_themes.py:192, scripts/generate_daily_digest.py:161, scripts/generate_daily_digest.py:167, scripts/generate_daily_digest.py:173, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:187`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (cross-file). Locations: scripts/analyze_themes.py:187, scripts/analyze_themes.py:193, scripts/generate_daily_digest.py:162, scripts/generate_daily_digest.py:168, scripts/generate_daily_digest.py:174, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:217`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: scripts/analyze_themes.py:217, scripts/bao_seed_newsletter.py:321, scripts/generate_daily_digest.py:194, scripts/generate_podcast.py:572, scripts/generate_weekly_digest.py:211, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:218`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: scripts/analyze_themes.py:218, scripts/bao_seed_newsletter.py:322, scripts/generate_daily_digest.py:195, scripts/generate_podcast.py:573, scripts/generate_weekly_digest.py:212, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:207`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: scripts/analyze_themes.py:207, scripts/analyze_themes.py:224, scripts/bao_seed_newsletter.py:331, scripts/generate_daily_digest.py:180, scripts/generate_daily_digest.py:199, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:209`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: scripts/analyze_themes.py:209, scripts/generate_daily_digest.py:182, scripts/generate_daily_digest.py:201, scripts/generate_weekly_digest.py:199, scripts/generate_weekly_digest.py:218, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:208`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: scripts/analyze_themes.py:208, scripts/analyze_themes.py:225, scripts/generate_daily_digest.py:181, scripts/generate_daily_digest.py:200, scripts/generate_weekly_digest.py:198, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:188`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: scripts/analyze_themes.py:188, scripts/generate_daily_digest.py:163, scripts/generate_daily_digest.py:169, scripts/generate_weekly_digest.py:180, scripts/generate_weekly_digest.py:186, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:189`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: scripts/analyze_themes.py:189, scripts/generate_daily_digest.py:164, scripts/generate_daily_digest.py:170, scripts/generate_weekly_digest.py:181, scripts/generate_weekly_digest.py:187, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:212`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: scripts/analyze_themes.py:212, scripts/generate_daily_digest.py:187, scripts/generate_weekly_digest.py:204, src/ingestion/youtube.py:1730, src/scripts/migrate_digests_markdown.py:376, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:213`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: scripts/analyze_themes.py:213, scripts/generate_daily_digest.py:188, scripts/generate_weekly_digest.py:205, src/ingestion/youtube.py:1731, src/scripts/migrate_digests_markdown.py:377, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/analyze_themes.py:55`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: scripts/analyze_themes.py:55, scripts/generate_daily_digest.py:52, scripts/generate_podcast.py:296, scripts/generate_weekly_digest.py:60, src/scripts/analyze_markdown_quality.py:141
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/bao_seed_newsletter.py:213`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: scripts/bao_seed_newsletter.py:213, src/ingestion/arxiv.py:551, src/ingestion/substack.py:591, src/processors/digest_creator.py:933, src/utils/token_counter.py:225
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/generate_daily_digest.py:213`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: scripts/generate_daily_digest.py:213, scripts/generate_podcast.py:587, scripts/generate_weekly_digest.py:230, scripts/review_digest.py:439, scripts/validate_docling.py:356, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `scripts/generate_daily_digest.py:212`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: scripts/generate_daily_digest.py:212, scripts/generate_podcast.py:547, scripts/generate_podcast.py:567, scripts/generate_weekly_digest.py:229, scripts/review_digest.py:438
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/scheduler/scheduler.py:23`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/scheduler/scheduler.py:23, src/utils/token_counter.py:174, tests/cli/test_regression_daily_pipeline.py:68, tests/test_services/test_infrastructure_pricing_service.py:274, tests/test_services/test_infrastructure_pricing_service.py:302
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (15 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:50`
- **Metric**: duplicate_copies = 15 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 15 times (cross-file). Locations: src/agents/specialists/analysis.py:50, src/agents/specialists/analysis.py:69, src/agents/specialists/analysis.py:85, src/agents/specialists/analysis.py:101, src/agents/specialists/ingestion.py:44, ...and 10 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:70`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: src/agents/specialists/analysis.py:70, src/agents/specialists/analysis.py:86, src/agents/specialists/analysis.py:102, src/agents/specialists/ingestion.py:88, src/agents/specialists/research.py:48, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:66`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: src/agents/specialists/analysis.py:66, src/agents/specialists/analysis.py:82, src/agents/specialists/analysis.py:98, src/agents/specialists/ingestion.py:70, src/agents/specialists/research.py:60, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:71`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: src/agents/specialists/analysis.py:71, src/agents/specialists/analysis.py:87, src/agents/specialists/analysis.py:103, src/agents/specialists/ingestion.py:89, src/agents/specialists/research.py:49, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:72`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: src/agents/specialists/analysis.py:72, src/agents/specialists/analysis.py:88, src/agents/specialists/analysis.py:104, src/agents/specialists/ingestion.py:90, src/agents/specialists/research.py:50, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:73`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/agents/specialists/analysis.py:73, src/agents/specialists/analysis.py:89, src/agents/specialists/analysis.py:105, src/agents/specialists/research.py:51, src/agents/specialists/research.py:83, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:51`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:51, src/agents/specialists/ingestion.py:45, src/agents/specialists/ingestion.py:74, src/agents/specialists/synthesis.py:68, src/agents/specialists/synthesis.py:87
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:52`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:52, src/agents/specialists/ingestion.py:46, src/agents/specialists/ingestion.py:75, src/agents/specialists/synthesis.py:69, src/agents/specialists/synthesis.py:88
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:76`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:76, src/agents/specialists/analysis.py:92, src/agents/specialists/ingestion.py:64, src/agents/specialists/research.py:54, src/agents/specialists/research.py:86
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:77`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:77, src/agents/specialists/analysis.py:93, src/agents/specialists/ingestion.py:65, src/agents/specialists/research.py:55, src/agents/specialists/research.py:87
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:78`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:78, src/agents/specialists/analysis.py:94, src/agents/specialists/ingestion.py:66, src/agents/specialists/research.py:56, src/agents/specialists/research.py:88
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/analysis.py:79`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/analysis.py:79, src/agents/specialists/analysis.py:95, src/agents/specialists/ingestion.py:67, src/agents/specialists/research.py:57, src/agents/specialists/research.py:89
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/ingestion.py:53`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/ingestion.py:53, tests/e2e/conftest.py:214, tests/e2e/conftest.py:221, tests/e2e/conftest.py:230, tests/e2e/conftest.py:237
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/synthesis.py:114`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: src/agents/specialists/synthesis.py:114, src/api/voice_settings_routes.py:79, src/api/voice_settings_routes.py:89, src/api/voice_settings_routes.py:99, src/api/voice_settings_routes.py:109, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/agents/specialists/synthesis.py:113`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/agents/specialists/synthesis.py:113, src/api/voice_settings_routes.py:78, src/api/voice_settings_routes.py:88, src/api/voice_settings_routes.py:98, src/api/voice_settings_routes.py:108
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/chat_routes.py:1098`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/api/chat_routes.py:1098, src/api/chat_routes.py:1216, src/api/content_routes.py:349, src/api/content_routes.py:992, src/api/pipeline_routes.py:131
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1377 lines

- **Category**: large-file
- **Location**: `src/api/chat_routes.py:1`
- **Metric**: file_lines = 1377 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/api/chat_routes.py has 1377 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (22 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/digest_routes.py:252`
- **Metric**: duplicate_copies = 22 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 22 times (cross-file). Locations: src/api/digest_routes.py:252, tests/api/conftest.py:374, tests/api/conftest.py:390, tests/api/test_markdown_api.py:66, tests/api/test_markdown_api.py:99, ...and 17 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (22 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/digest_routes.py:253`
- **Metric**: duplicate_copies = 22 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 22 times (cross-file). Locations: src/api/digest_routes.py:253, tests/api/conftest.py:375, tests/api/conftest.py:391, tests/api/test_markdown_api.py:67, tests/api/test_markdown_api.py:100, ...and 17 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/digest_routes.py:27`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/api/digest_routes.py:27, src/api/kb_routes.py:28, src/api/pipeline_routes.py:18, src/api/reference_routes.py:19, src/api/search_routes.py:26, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/image_generation_routes.py:18`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/api/image_generation_routes.py:18, src/api/kb_routes.py:27, src/api/podcast_routes.py:26, src/api/reference_routes.py:18, src/api/search_routes.py:25, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/api/voice_settings_routes.py:80`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: src/api/voice_settings_routes.py:80, src/api/voice_settings_routes.py:90, src/api/voice_settings_routes.py:100, src/api/voice_settings_routes.py:110, tests/agents/scheduler/test_scheduler.py:155, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/cli/curate_commands.py:242`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: src/cli/curate_commands.py:242, src/cli/digest_commands.py:148, src/cli/digest_commands.py:251, src/cli/kb_commands.py:409, src/cli/kb_commands.py:470, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (18 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/cli/deploy_commands.py:60`
- **Metric**: duplicate_copies = 18 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 18 times (cross-file). Locations: src/cli/deploy_commands.py:60, src/cli/digest_commands.py:116, src/cli/digest_commands.py:124, src/cli/digest_commands.py:132, src/cli/digest_commands.py:140, ...and 13 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:155`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (same-file). Locations: src/cli/ingest_commands.py:155, src/cli/ingest_commands.py:243, src/cli/ingest_commands.py:341, src/cli/ingest_commands.py:603, src/cli/ingest_commands.py:790, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:156`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (same-file). Locations: src/cli/ingest_commands.py:156, src/cli/ingest_commands.py:244, src/cli/ingest_commands.py:342, src/cli/ingest_commands.py:604, src/cli/ingest_commands.py:791, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:157`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (same-file). Locations: src/cli/ingest_commands.py:157, src/cli/ingest_commands.py:245, src/cli/ingest_commands.py:343, src/cli/ingest_commands.py:605, src/cli/ingest_commands.py:792, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:158`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (same-file). Locations: src/cli/ingest_commands.py:158, src/cli/ingest_commands.py:246, src/cli/ingest_commands.py:344, src/cli/ingest_commands.py:606, src/cli/ingest_commands.py:793, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:159`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (same-file). Locations: src/cli/ingest_commands.py:159, src/cli/ingest_commands.py:247, src/cli/ingest_commands.py:345, src/cli/ingest_commands.py:607, src/cli/ingest_commands.py:794, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:145`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (same-file). Locations: src/cli/ingest_commands.py:145, src/cli/ingest_commands.py:233, src/cli/ingest_commands.py:331, src/cli/ingest_commands.py:780, src/cli/ingest_commands.py:1075, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:146`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (same-file). Locations: src/cli/ingest_commands.py:146, src/cli/ingest_commands.py:234, src/cli/ingest_commands.py:332, src/cli/ingest_commands.py:781, src/cli/ingest_commands.py:1076, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:147`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (same-file). Locations: src/cli/ingest_commands.py:147, src/cli/ingest_commands.py:235, src/cli/ingest_commands.py:333, src/cli/ingest_commands.py:782, src/cli/ingest_commands.py:1077, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:182`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (same-file). Locations: src/cli/ingest_commands.py:182, src/cli/ingest_commands.py:282, src/cli/ingest_commands.py:365, src/cli/ingest_commands.py:440, src/cli/ingest_commands.py:633, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:183`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (same-file). Locations: src/cli/ingest_commands.py:183, src/cli/ingest_commands.py:283, src/cli/ingest_commands.py:366, src/cli/ingest_commands.py:441, src/cli/ingest_commands.py:634, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:148`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (same-file). Locations: src/cli/ingest_commands.py:148, src/cli/ingest_commands.py:236, src/cli/ingest_commands.py:334, src/cli/ingest_commands.py:783, src/cli/ingest_commands.py:1078, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:130`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (same-file). Locations: src/cli/ingest_commands.py:130, src/cli/ingest_commands.py:216, src/cli/ingest_commands.py:314, src/cli/ingest_commands.py:748, src/cli/ingest_commands.py:1139, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:132`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (same-file). Locations: src/cli/ingest_commands.py:132, src/cli/ingest_commands.py:218, src/cli/ingest_commands.py:316, src/cli/ingest_commands.py:750, src/cli/ingest_commands.py:1141, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:150`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:150, src/cli/ingest_commands.py:238, src/cli/ingest_commands.py:336, src/cli/ingest_commands.py:598, src/cli/ingest_commands.py:785, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:151`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:151, src/cli/ingest_commands.py:239, src/cli/ingest_commands.py:337, src/cli/ingest_commands.py:599, src/cli/ingest_commands.py:786, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:152`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:152, src/cli/ingest_commands.py:240, src/cli/ingest_commands.py:338, src/cli/ingest_commands.py:600, src/cli/ingest_commands.py:787, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:153`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:153, src/cli/ingest_commands.py:241, src/cli/ingest_commands.py:339, src/cli/ingest_commands.py:601, src/cli/ingest_commands.py:788, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:181`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:181, src/cli/ingest_commands.py:281, src/cli/ingest_commands.py:364, src/cli/ingest_commands.py:439, src/cli/ingest_commands.py:632, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:278`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:278, src/cli/ingest_commands.py:361, src/cli/ingest_commands.py:436, src/cli/ingest_commands.py:629, src/cli/ingest_commands.py:669, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:279`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: src/cli/ingest_commands.py:279, src/cli/ingest_commands.py:362, src/cli/ingest_commands.py:437, src/cli/ingest_commands.py:630, src/cli/ingest_commands.py:670, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:149`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: src/cli/ingest_commands.py:149, src/cli/ingest_commands.py:237, src/cli/ingest_commands.py:335, src/cli/ingest_commands.py:784, src/cli/ingest_commands.py:1079, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:161`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: src/cli/ingest_commands.py:161, src/cli/ingest_commands.py:249, src/cli/ingest_commands.py:347, src/cli/ingest_commands.py:609, src/cli/ingest_commands.py:796, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:162`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: src/cli/ingest_commands.py:162, src/cli/ingest_commands.py:250, src/cli/ingest_commands.py:348, src/cli/ingest_commands.py:610, src/cli/ingest_commands.py:797, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:277`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: src/cli/ingest_commands.py:277, src/cli/ingest_commands.py:360, src/cli/ingest_commands.py:435, src/cli/ingest_commands.py:628, src/cli/ingest_commands.py:668, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:280`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: src/cli/ingest_commands.py:280, src/cli/ingest_commands.py:363, src/cli/ingest_commands.py:438, src/cli/ingest_commands.py:631, src/cli/ingest_commands.py:671, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:184`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: src/cli/ingest_commands.py:184, src/cli/ingest_commands.py:284, src/cli/ingest_commands.py:367, src/cli/ingest_commands.py:675, src/cli/ingest_commands.py:905, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:185`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: src/cli/ingest_commands.py:185, src/cli/ingest_commands.py:285, src/cli/ingest_commands.py:368, src/cli/ingest_commands.py:676, src/cli/ingest_commands.py:906, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:417`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: src/cli/ingest_commands.py:417, src/cli/ingest_commands.py:612, src/cli/ingest_commands.py:799, src/cli/ingest_commands.py:874, src/cli/ingest_commands.py:961, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:186`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/cli/ingest_commands.py:186, src/cli/ingest_commands.py:286, src/cli/ingest_commands.py:369, src/cli/ingest_commands.py:677, src/cli/ingest_commands.py:1763, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:187`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/cli/ingest_commands.py:187, src/cli/ingest_commands.py:287, src/cli/ingest_commands.py:370, src/cli/ingest_commands.py:678, src/cli/ingest_commands.py:1764
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:268`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/cli/ingest_commands.py:268, src/cli/ingest_commands.py:619, src/cli/ingest_commands.py:806, src/cli/ingest_commands.py:1279, src/cli/ingest_commands.py:1564
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:410`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/cli/ingest_commands.py:410, src/cli/ingest_commands.py:501, src/cli/ingest_commands.py:867, src/cli/ingest_commands.py:954, src/cli/ingest_commands.py:1818
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/ingest_commands.py:411`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/cli/ingest_commands.py:411, src/cli/ingest_commands.py:502, src/cli/ingest_commands.py:868, src/cli/ingest_commands.py:955, src/cli/ingest_commands.py:1819
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1911 lines

- **Category**: large-file
- **Location**: `src/cli/ingest_commands.py:1`
- **Metric**: file_lines = 1911 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/cli/ingest_commands.py has 1911 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/pipeline_commands.py:551`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/cli/pipeline_commands.py:551, src/cli/pipeline_commands.py:570, src/cli/pipeline_commands.py:591, src/cli/pipeline_commands.py:713, src/cli/pipeline_commands.py:732, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/pipeline_commands.py:552`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/cli/pipeline_commands.py:552, src/cli/pipeline_commands.py:571, src/cli/pipeline_commands.py:592, src/cli/pipeline_commands.py:714, src/cli/pipeline_commands.py:733, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/cli/pipeline_commands.py:553`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/cli/pipeline_commands.py:553, src/cli/pipeline_commands.py:572, src/cli/pipeline_commands.py:593, src/cli/pipeline_commands.py:715, src/cli/pipeline_commands.py:734, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/config/__init__.py:32`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: src/config/__init__.py:32, src/ingestion/__init__.py:24, src/models/__init__.py:73, src/parsers/__init__.py:9, src/services/__init__.py:24, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1610 lines

- **Category**: large-file
- **Location**: `src/config/settings.py:1`
- **Metric**: file_lines = 1610 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/config/settings.py has 1610 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/arxiv.py:466`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: src/ingestion/arxiv.py:466, src/ingestion/blog_scraper.py:657, src/ingestion/blog_scraper.py:681, src/ingestion/gmail.py:594, src/ingestion/gmail.py:628, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/arxiv.py:467`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: src/ingestion/arxiv.py:467, src/ingestion/blog_scraper.py:658, src/ingestion/blog_scraper.py:682, src/ingestion/gmail.py:595, src/ingestion/gmail.py:629, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/arxiv.py:468`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: src/ingestion/arxiv.py:468, src/ingestion/blog_scraper.py:659, src/ingestion/blog_scraper.py:683, src/ingestion/gmail.py:596, src/ingestion/gmail.py:630, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (17 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/arxiv.py:469`
- **Metric**: duplicate_copies = 17 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 17 times (cross-file). Locations: src/ingestion/arxiv.py:469, src/ingestion/blog_scraper.py:660, src/ingestion/blog_scraper.py:684, src/ingestion/gmail.py:597, src/ingestion/gmail.py:631, ...and 12 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (14 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:661`
- **Metric**: duplicate_copies = 14 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 14 times (cross-file). Locations: src/ingestion/blog_scraper.py:661, src/ingestion/blog_scraper.py:685, src/ingestion/gmail.py:598, src/ingestion/gmail.py:632, src/ingestion/gmail.py:656, ...and 9 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:686`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: src/ingestion/blog_scraper.py:686, src/ingestion/gmail.py:599, src/ingestion/gmail.py:633, src/ingestion/gmail.py:657, src/ingestion/huggingface_papers.py:662, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:687`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: src/ingestion/blog_scraper.py:687, src/ingestion/gmail.py:600, src/ingestion/gmail.py:634, src/ingestion/gmail.py:658, src/ingestion/huggingface_papers.py:663, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:688`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: src/ingestion/blog_scraper.py:688, src/ingestion/gmail.py:601, src/ingestion/gmail.py:635, src/ingestion/gmail.py:659, src/ingestion/huggingface_papers.py:664, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:689`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: src/ingestion/blog_scraper.py:689, src/ingestion/gmail.py:602, src/ingestion/gmail.py:636, src/ingestion/gmail.py:660, src/ingestion/huggingface_papers.py:665, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:690`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: src/ingestion/blog_scraper.py:690, src/ingestion/gmail.py:603, src/ingestion/gmail.py:637, src/ingestion/gmail.py:661, src/ingestion/huggingface_papers.py:666, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:23`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:23, src/ingestion/huggingface_papers.py:25, src/ingestion/podcast.py:21, src/ingestion/rss.py:22, src/ingestion/substack.py:23, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:631`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:631, src/ingestion/gmail.py:562, src/ingestion/huggingface_papers.py:634, src/ingestion/rss.py:583, src/ingestion/scholar.py:347, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:632`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:632, src/ingestion/gmail.py:563, src/ingestion/huggingface_papers.py:635, src/ingestion/rss.py:584, src/ingestion/scholar.py:348, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:691`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:691, src/ingestion/gmail.py:662, src/ingestion/huggingface_papers.py:720, src/ingestion/rss.py:681, src/ingestion/scholar.py:389, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:692`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:692, src/ingestion/gmail.py:663, src/ingestion/huggingface_papers.py:721, src/ingestion/rss.py:682, src/ingestion/scholar.py:390, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:693`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/ingestion/blog_scraper.py:693, src/ingestion/gmail.py:664, src/ingestion/huggingface_papers.py:722, src/ingestion/rss.py:683, src/ingestion/scholar.py:391, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:604`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:604, src/ingestion/huggingface_papers.py:601, src/ingestion/rss.py:560, src/ingestion/scholar.py:338, src/ingestion/substack.py:310
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:628`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:628, src/ingestion/huggingface_papers.py:631, src/ingestion/rss.py:580, src/ingestion/scholar.py:344, src/ingestion/substack.py:329
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:633`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:633, src/ingestion/gmail.py:565, src/ingestion/huggingface_papers.py:636, src/ingestion/rss.py:585, src/ingestion/substack.py:334
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:667`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:667, src/ingestion/gmail.py:639, src/ingestion/huggingface_papers.py:696, src/ingestion/rss.py:657, src/ingestion/substack.py:392
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:668`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:668, src/ingestion/gmail.py:640, src/ingestion/huggingface_papers.py:697, src/ingestion/rss.py:658, src/ingestion/substack.py:393
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:676`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:676, src/ingestion/gmail.py:647, src/ingestion/huggingface_papers.py:705, src/ingestion/rss.py:666, src/ingestion/substack.py:400
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:677`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:677, src/ingestion/gmail.py:648, src/ingestion/huggingface_papers.py:706, src/ingestion/rss.py:667, src/ingestion/substack.py:401
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/blog_scraper.py:678`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/blog_scraper.py:678, src/ingestion/gmail.py:649, src/ingestion/huggingface_papers.py:707, src/ingestion/rss.py:668, src/ingestion/substack.py:402
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/ingestion/podcast.py:359`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/ingestion/podcast.py:359, src/ingestion/rss.py:545, src/ingestion/substack.py:297, src/ingestion/youtube.py:1142, src/ingestion/youtube.py:1630
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1783 lines

- **Category**: large-file
- **Location**: `src/ingestion/youtube.py:1`
- **Metric**: file_lines = 1783 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/ingestion/youtube.py has 1783 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Large file: 2722 lines

- **Category**: large-file
- **Location**: `src/mcp_server.py:1`
- **Metric**: file_lines = 2722 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/mcp_server.py has 2722 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Too many top-level definitions: 61

- **Category**: large-file
- **Location**: `src/mcp_server.py:1`
- **Metric**: top_level_definitions = 61 (threshold: 20)
- **Smell**: Large Class
- **Detail**: src/mcp_server.py has 61 top-level classes/functions (threshold: 20). This suggests the module has too many responsibilities.
- **Recommendation**: Group related definitions and extract them into focused modules (Single Responsibility Principle).

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/models/agent_task.py:20`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/models/agent_task.py:20, src/models/chunk.py:15, src/models/content_reference.py:24, src/models/evaluation.py:19, src/models/image.py:23, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/parsers/base.py:42`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/parsers/base.py:42, src/parsers/docling_parser.py:186, src/parsers/kreuzberg_parser.py:257, src/parsers/markitdown_parser.py:135, src/parsers/youtube_parser.py:128
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/parsers/base.py:43`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/parsers/base.py:43, src/parsers/docling_parser.py:187, src/parsers/kreuzberg_parser.py:258, src/parsers/markitdown_parser.py:136, src/parsers/youtube_parser.py:129
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/processors/digest_creator.py:49`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/processors/digest_creator.py:49, src/processors/digest_reviser.py:31, src/processors/historical_context.py:25, src/processors/podcast_script_generator.py:110, src/processors/script_reviser.py:36
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1141 lines

- **Category**: large-file
- **Location**: `src/processors/digest_creator.py:1`
- **Metric**: file_lines = 1141 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/processors/digest_creator.py has 1141 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/processors/digest_reviser.py:315`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/processors/digest_reviser.py:315, src/processors/podcast_script_generator.py:70, src/processors/podcast_script_generator.py:88, src/processors/podcast_script_generator.py:453, src/processors/podcast_script_generator.py:476
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1044 lines

- **Category**: large-file
- **Location**: `src/processors/podcast_script_generator.py:1`
- **Metric**: file_lines = 1044 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/processors/podcast_script_generator.py has 1044 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Large file: 1089 lines

- **Category**: large-file
- **Location**: `src/queue/setup.py:1`
- **Metric**: file_lines = 1089 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/queue/setup.py has 1089 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:129`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: src/services/chunking.py:129, src/services/chunking.py:149, src/services/chunking.py:247, src/services/chunking.py:339, src/services/chunking.py:395, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:143`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:143, src/services/chunking.py:241, src/services/chunking.py:333, src/services/chunking.py:389, src/services/chunking.py:474, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:145`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:145, src/services/chunking.py:243, src/services/chunking.py:335, src/services/chunking.py:391, src/services/chunking.py:476, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:146`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:146, src/services/chunking.py:244, src/services/chunking.py:336, src/services/chunking.py:392, src/services/chunking.py:477, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:147`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:147, src/services/chunking.py:245, src/services/chunking.py:337, src/services/chunking.py:393, src/services/chunking.py:478, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:150`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:150, src/services/chunking.py:248, src/services/chunking.py:340, src/services/chunking.py:396, src/services/chunking.py:481, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:151`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:151, src/services/chunking.py:249, src/services/chunking.py:341, src/services/chunking.py:397, src/services/chunking.py:482, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:152`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/chunking.py:152, src/services/chunking.py:250, src/services/chunking.py:342, src/services/chunking.py:398, src/services/chunking.py:483, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/chunking.py:153`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/chunking.py:153, src/services/chunking.py:251, src/services/chunking.py:343, src/services/chunking.py:399, src/services/chunking.py:484
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/connection_checker.py:103`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/connection_checker.py:103, src/services/connection_checker.py:118, src/services/connection_checker.py:133, src/services/connection_checker.py:148, src/services/connection_checker.py:164
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/connection_checker.py:104`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/connection_checker.py:104, src/services/connection_checker.py:119, src/services/connection_checker.py:134, src/services/connection_checker.py:149, src/services/connection_checker.py:165
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/services/infrastructure_pricing_extractor.py:40`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/services/infrastructure_pricing_extractor.py:40, tests/e2e/conftest.py:203, tests/e2e/conftest.py:209, tests/e2e/conftest.py:216, tests/e2e/conftest.py:225, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/services/infrastructure_pricing_extractor.py:41`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/services/infrastructure_pricing_extractor.py:41, tests/e2e/conftest.py:204, tests/e2e/conftest.py:210, tests/e2e/conftest.py:217, tests/e2e/conftest.py:226, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/services/infrastructure_pricing_extractor.py:42`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/services/infrastructure_pricing_extractor.py:42, tests/e2e/conftest.py:205, tests/e2e/conftest.py:211, tests/e2e/conftest.py:218, tests/e2e/conftest.py:227, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:918`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:918, src/services/llm_router.py:954, src/services/llm_router.py:1041, src/services/llm_router.py:1184, src/services/llm_router.py:1324, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:919`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:919, src/services/llm_router.py:955, src/services/llm_router.py:1042, src/services/llm_router.py:1185, src/services/llm_router.py:1325, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:920`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:920, src/services/llm_router.py:956, src/services/llm_router.py:1043, src/services/llm_router.py:1186, src/services/llm_router.py:1326, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:921`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:921, src/services/llm_router.py:957, src/services/llm_router.py:1044, src/services/llm_router.py:1187, src/services/llm_router.py:1327, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:1293`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:1293, src/services/llm_router.py:1310, src/services/llm_router.py:1550, src/services/llm_router.py:1568, src/services/llm_router.py:1734, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:1294`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: src/services/llm_router.py:1294, src/services/llm_router.py:1311, src/services/llm_router.py:1551, src/services/llm_router.py:1569, src/services/llm_router.py:1735, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:298`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/llm_router.py:298, src/services/llm_router.py:433, src/services/llm_router.py:458, src/services/llm_router.py:834, src/services/llm_router.py:904
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:299`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/llm_router.py:299, src/services/llm_router.py:434, src/services/llm_router.py:459, src/services/llm_router.py:835, src/services/llm_router.py:905
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:300`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/llm_router.py:300, src/services/llm_router.py:435, src/services/llm_router.py:460, src/services/llm_router.py:836, src/services/llm_router.py:906
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:301`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/llm_router.py:301, src/services/llm_router.py:436, src/services/llm_router.py:461, src/services/llm_router.py:837, src/services/llm_router.py:907
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/llm_router.py:985`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/llm_router.py:985, src/services/llm_router.py:1355, src/services/llm_router.py:1440, src/services/llm_router.py:1539, src/services/llm_router.py:1561
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1754 lines

- **Category**: large-file
- **Location**: `src/services/llm_router.py:1`
- **Metric**: file_lines = 1754 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/services/llm_router.py has 1754 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/services/reranking.py:32`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/services/reranking.py:32, src/services/reranking.py:61, src/services/reranking.py:91, src/services/reranking.py:144, src/services/reranking.py:177
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/storage/providers/local.py:83`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: src/storage/providers/local.py:83, src/storage/providers/neon.py:168, src/storage/providers/neon.py:227, src/storage/providers/supabase.py:110, src/storage/providers/supabase.py:123, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/storage/providers/local.py:84`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: src/storage/providers/local.py:84, src/storage/providers/neon.py:169, src/storage/providers/neon.py:228, src/storage/providers/supabase.py:111, src/storage/providers/supabase.py:124, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/storage/providers/neon.py:170`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/storage/providers/neon.py:170, src/storage/providers/neon.py:229, src/storage/providers/supabase.py:112, src/storage/providers/supabase.py:125, src/storage/providers/supabase.py:223
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/storage/providers/neon.py:171`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: src/storage/providers/neon.py:171, src/storage/providers/neon.py:230, src/storage/providers/supabase.py:113, src/storage/providers/supabase.py:126, src/storage/providers/supabase.py:224
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `src/sync/obsidian_exporter.py:330`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: src/sync/obsidian_exporter.py:330, src/sync/obsidian_exporter.py:423, src/sync/obsidian_exporter.py:489, src/sync/obsidian_exporter.py:590, src/sync/obsidian_exporter.py:737
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1195 lines

- **Category**: large-file
- **Location**: `src/sync/obsidian_exporter.py:1`
- **Metric**: file_lines = 1195 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: src/sync/obsidian_exporter.py has 1195 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:40`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:40, src/telemetry/providers/braintrust.py:99, src/telemetry/providers/langfuse.py:162, src/telemetry/providers/noop.py:33, src/telemetry/providers/opik.py:164, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:41`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:41, src/telemetry/providers/braintrust.py:100, src/telemetry/providers/langfuse.py:163, src/telemetry/providers/noop.py:34, src/telemetry/providers/opik.py:165, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:43`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:43, src/telemetry/providers/braintrust.py:102, src/telemetry/providers/langfuse.py:165, src/telemetry/providers/noop.py:36, src/telemetry/providers/opik.py:167, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:44`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:44, src/telemetry/providers/braintrust.py:103, src/telemetry/providers/langfuse.py:166, src/telemetry/providers/noop.py:37, src/telemetry/providers/opik.py:168, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:45`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:45, src/telemetry/providers/braintrust.py:104, src/telemetry/providers/langfuse.py:167, src/telemetry/providers/noop.py:38, src/telemetry/providers/opik.py:169, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:46`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:46, src/telemetry/providers/braintrust.py:105, src/telemetry/providers/langfuse.py:168, src/telemetry/providers/noop.py:39, src/telemetry/providers/opik.py:170, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:47`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:47, src/telemetry/providers/braintrust.py:106, src/telemetry/providers/langfuse.py:169, src/telemetry/providers/noop.py:40, src/telemetry/providers/opik.py:171, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `src/telemetry/providers/base.py:48`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: src/telemetry/providers/base.py:48, src/telemetry/providers/braintrust.py:107, src/telemetry/providers/langfuse.py:170, src/telemetry/providers/noop.py:41, src/telemetry/providers/opik.py:172, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/agents/scheduler/test_scheduler.py:156`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/agents/scheduler/test_scheduler.py:156, tests/test_cli/test_profile_commands.py:33, tests/test_config/test_profile_integration.py:61, tests/test_config/test_profile_validation.py:408, tests/test_config/test_profiles.py:53, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (24 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:373`
- **Metric**: duplicate_copies = 24 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 24 times (cross-file). Locations: tests/api/conftest.py:373, tests/api/conftest.py:389, tests/api/test_markdown_api.py:65, tests/api/test_markdown_api.py:98, tests/api/test_markdown_api.py:143, ...and 19 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:371`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: tests/api/conftest.py:371, tests/api/conftest.py:387, tests/api/test_markdown_api.py:63, tests/api/test_markdown_api.py:96, tests/api/test_markdown_api.py:141, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:372`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: tests/api/conftest.py:372, tests/api/conftest.py:388, tests/api/test_markdown_api.py:64, tests/api/test_markdown_api.py:97, tests/api/test_markdown_api.py:142, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:376`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (cross-file). Locations: tests/api/conftest.py:376, tests/api/conftest.py:392, tests/api/test_sorting.py:272, tests/api/test_sorting.py:288, tests/api/test_sorting.py:370, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:377`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (cross-file). Locations: tests/api/conftest.py:377, tests/api/conftest.py:393, tests/api/test_sorting.py:273, tests/api/test_sorting.py:289, tests/api/test_sorting.py:371, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:262`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/conftest.py:262, tests/api/conftest.py:547, tests/integration/conftest.py:258, tests/integration/conftest.py:276, tests/integration/conftest.py:294, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:263`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/conftest.py:263, tests/api/conftest.py:548, tests/integration/conftest.py:259, tests/integration/conftest.py:277, tests/integration/conftest.py:295, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:264`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/conftest.py:264, tests/api/conftest.py:549, tests/integration/conftest.py:260, tests/integration/conftest.py:278, tests/integration/conftest.py:296, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:484`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/conftest.py:484, tests/api/conftest.py:503, tests/api/conftest.py:514, tests/api/conftest.py:527, tests/contract/conftest.py:217, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:485`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/conftest.py:485, tests/api/conftest.py:504, tests/api/conftest.py:515, tests/api/conftest.py:528, tests/contract/conftest.py:218, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:505`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/api/conftest.py:505, tests/api/conftest.py:516, tests/api/test_search_api.py:128, tests/api/test_search_api.py:138, tests/api/test_search_api.py:149, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:265`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/api/conftest.py:265, tests/integration/conftest.py:261, tests/integration/conftest.py:279, tests/integration/conftest.py:297, tests/integration/test_summarization_flow_functional.py:243, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:483`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/api/conftest.py:483, tests/api/conftest.py:502, tests/api/conftest.py:526, tests/contract/conftest.py:216, tests/contract/conftest.py:240, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:260`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: tests/api/conftest.py:260, tests/api/conftest.py:290, tests/api/conftest.py:303, tests/api/conftest.py:545, tests/contract/conftest.py:255, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:386`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/conftest.py:386, tests/api/test_sorting.py:266, tests/api/test_sorting.py:364, tests/api/test_sorting.py:380, tests/api/test_sorting.py:473, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/conftest.py:482`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/conftest.py:482, tests/api/conftest.py:501, tests/contract/conftest.py:215, tests/integration/conftest.py:215, tests/integration/conftest.py:226
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audio_digest_api.py:271`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_audio_digest_api.py:271, tests/api/test_audio_digest_api.py:285, tests/api/test_digest_api.py:88, tests/api/test_podcast_api.py:64, tests/api/test_podcast_api.py:75, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audio_digest_api.py:272`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_audio_digest_api.py:272, tests/api/test_audio_digest_api.py:286, tests/api/test_digest_api.py:89, tests/api/test_podcast_api.py:65, tests/api/test_summary_api.py:202
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (12 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:99`
- **Metric**: duplicate_copies = 12 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 12 times (cross-file). Locations: tests/api/test_audit_ordering.py:99, tests/api/test_audit_routes.py:290, tests/api/test_auth_middleware.py:64, tests/api/test_auth_middleware.py:88, tests/api/test_auth_middleware.py:337, ...and 7 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:97`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/test_audit_ordering.py:97, tests/api/test_audit_routes.py:288, tests/api/test_auth_middleware.py:85, tests/api/test_auth_middleware.py:335, tests/api/test_auth_routes.py:59, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:98`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (cross-file). Locations: tests/api/test_audit_ordering.py:98, tests/api/test_audit_routes.py:289, tests/api/test_auth_middleware.py:87, tests/api/test_auth_middleware.py:336, tests/api/test_auth_routes.py:60, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:96`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/api/test_audit_ordering.py:96, tests/api/test_audit_routes.py:287, tests/api/test_auth_middleware.py:84, tests/api/test_auth_middleware.py:334, tests/api/test_auth_routes.py:58, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:100`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/api/test_audit_ordering.py:100, tests/api/test_audit_routes.py:291, tests/api/test_auth_middleware.py:65, tests/api/test_auth_routes.py:62, tests/api/test_auth_routes.py:128, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:102`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_audit_ordering.py:102, tests/api/test_auth_middleware.py:67, tests/api/test_auth_routes.py:64, tests/api/test_auth_routes.py:87, tests/api/test_auth_routes.py:130, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:104`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_audit_ordering.py:104, tests/api/test_auth_middleware.py:69, tests/api/test_auth_routes.py:66, tests/api/test_auth_routes.py:89, tests/api/test_auth_routes.py:132, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_audit_ordering.py:105`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_audit_ordering.py:105, tests/api/test_auth_middleware.py:71, tests/api/test_auth_routes.py:68, tests/api/test_auth_routes.py:91, tests/api/test_auth_routes.py:134, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_chat_api.py:215`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/api/test_chat_api.py:215, tests/api/test_chat_api.py:247, tests/api/test_chat_api.py:271, tests/api/test_chat_api.py:377, tests/api/test_chat_api.py:414
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_chat_api.py:217`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/api/test_chat_api.py:217, tests/api/test_chat_api.py:249, tests/api/test_chat_api.py:273, tests/api/test_chat_api.py:379, tests/api/test_chat_api.py:416
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_digest_api.py:151`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_digest_api.py:151, tests/api/test_digest_api.py:168, tests/api/test_digest_api.py:183, tests/api/test_digest_api.py:198, tests/api/test_script_api.py:228, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_digest_api.py:113`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_digest_api.py:113, tests/api/test_digest_api.py:125, tests/api/test_query_api.py:50, tests/api/test_query_api.py:75, tests/api/test_query_api.py:111
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_graph_routes.py:67`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_graph_routes.py:67, tests/test_processors/test_podcast_script_generator.py:87, tests/test_processors/test_podcast_script_generator.py:128, tests/test_processors/test_podcast_script_generator.py:147, tests/test_services/test_web_search.py:151, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_graph_routes.py:132`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_graph_routes.py:132, tests/api/test_markdown_api.py:126, tests/test_models/test_content.py:109, tests/test_models/test_content.py:475, tests/test_models/test_content.py:500, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_graph_routes.py:68`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_graph_routes.py:68, tests/test_processors/test_podcast_script_generator.py:88, tests/test_processors/test_podcast_script_generator.py:129, tests/test_processors/test_podcast_script_generator.py:148, tests/test_services/test_web_search.py:152
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_image_generation_api.py:69`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/api/test_image_generation_api.py:69, tests/api/test_image_generation_api.py:115, tests/api/test_image_generation_api.py:135, tests/api/test_image_generation_api.py:164, tests/api/test_image_generation_api.py:191, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_image_generation_api.py:70`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/api/test_image_generation_api.py:70, tests/api/test_image_generation_api.py:136, tests/api/test_image_generation_api.py:165, tests/api/test_image_generation_api.py:192, tests/api/test_image_generation_api.py:211, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_image_generation_api.py:71`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/api/test_image_generation_api.py:71, tests/api/test_image_generation_api.py:166, tests/api/test_image_generation_api.py:193, tests/api/test_image_generation_api.py:212, tests/api/test_image_generation_api.py:228, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_markdown_api.py:61`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_markdown_api.py:61, tests/api/test_markdown_api.py:94, tests/api/test_markdown_api.py:139, tests/integration/test_audio_digest_flow.py:77, tests/integration/test_markdown_outputs.py:392
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_markdown_api.py:76`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_markdown_api.py:76, tests/api/test_markdown_api.py:107, tests/api/test_markdown_api.py:152, tests/integration/test_markdown_outputs.py:405, tests/integration/test_markdown_outputs.py:458
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_prompt_test_api.py:169`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_prompt_test_api.py:169, tests/api/test_settings_api.py:374, tests/api/test_settings_api.py:405, tests/api/test_settings_override_api.py:88, tests/api/test_settings_override_api.py:104
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_save_api.py:54`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_save_api.py:54, tests/api/test_save_api.py:144, tests/api/test_save_api.py:193, tests/api/test_save_api.py:413, tests/services/test_html_processor.py:32
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_script_api.py:140`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_script_api.py:140, tests/integration/test_review_workflow.py:180, tests/integration/test_review_workflow.py:225, tests/integration/test_review_workflow.py:319, tests/integration/test_review_workflow.py:400, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_script_api.py:141`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_script_api.py:141, tests/integration/test_review_workflow.py:181, tests/integration/test_review_workflow.py:226, tests/integration/test_review_workflow.py:320, tests/integration/test_review_workflow.py:401, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_script_api.py:142`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/api/test_script_api.py:142, tests/integration/test_review_workflow.py:182, tests/integration/test_review_workflow.py:227, tests/integration/test_review_workflow.py:321, tests/integration/test_review_workflow.py:402, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_settings_api.py:67`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/api/test_settings_api.py:67, tests/test_agents/test_claude_agent.py:241, tests/test_processors/test_digest_creator.py:395, tests/test_processors/test_podcast_script_generator.py:597, tests/test_processors/test_theme_analyzer.py:253
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_sharing_api.py:145`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/api/test_sharing_api.py:145, tests/api/test_sharing_api.py:163, tests/api/test_sharing_api.py:200, tests/api/test_sharing_api.py:215, tests/api/test_sharing_api.py:228, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_sharing_api.py:147`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/api/test_sharing_api.py:147, tests/api/test_sharing_api.py:164, tests/api/test_sharing_api.py:201, tests/api/test_sharing_api.py:216, tests/api/test_sharing_api.py:229, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/api/test_sorting.py:67`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/api/test_sorting.py:67, tests/api/test_sorting.py:76, tests/api/test_sorting.py:85, tests/api/test_sorting.py:95, tests/api/test_sorting.py:128
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (33 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_analyze_commands.py:46`
- **Metric**: duplicate_copies = 33 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 33 times (cross-file). Locations: tests/cli/test_analyze_commands.py:46, tests/cli/test_analyze_commands.py:65, tests/cli/test_deploy_commands.py:130, tests/cli/test_digest_commands.py:114, tests/cli/test_digest_commands.py:142, ...and 28 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (31 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_analyze_commands.py:47`
- **Metric**: duplicate_copies = 31 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 31 times (cross-file). Locations: tests/cli/test_analyze_commands.py:47, tests/cli/test_analyze_commands.py:66, tests/cli/test_deploy_commands.py:131, tests/cli/test_digest_commands.py:115, tests/cli/test_digest_commands.py:168, ...and 26 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (26 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_analyze_commands.py:50`
- **Metric**: duplicate_copies = 26 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 26 times (cross-file). Locations: tests/cli/test_analyze_commands.py:50, tests/cli/test_analyze_commands.py:69, tests/cli/test_digest_commands.py:118, tests/cli/test_digest_commands.py:170, tests/cli/test_digest_commands.py:212, ...and 21 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_commands_http.py:49`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: tests/cli/test_commands_http.py:49, tests/cli/test_commands_http.py:86, tests/cli/test_kb_commands.py:179, tests/test_services/test_model_pricing_extractor.py:36, tests/test_services/test_model_pricing_extractor.py:46, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_digest_commands.py:171`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: tests/cli/test_digest_commands.py:171, tests/cli/test_podcast_commands.py:28, tests/cli/test_profile_commands.py:149, tests/cli/test_prompt_commands.py:233, tests/cli/test_prompt_commands.py:265, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_ingest_contract.py:114`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_ingest_contract.py:114, tests/cli/test_ingest_contract.py:122, tests/cli/test_ingest_contract.py:132, tests/cli/test_ingest_contract.py:140, tests/cli/test_ingest_contract.py:149
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_ingest_contract.py:115`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_ingest_contract.py:115, tests/cli/test_ingest_contract.py:123, tests/cli/test_ingest_contract.py:133, tests/cli/test_ingest_contract.py:141, tests/cli/test_ingest_contract.py:150
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_ingest_http.py:95`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/cli/test_ingest_http.py:95, tests/cli/test_ingest_http.py:134, tests/cli/test_ingest_http.py:198, tests/cli/test_ingest_http.py:244, tests/cli/test_ingest_http.py:293, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_ingest_http.py:96`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/cli/test_ingest_http.py:96, tests/cli/test_ingest_http.py:135, tests/cli/test_ingest_http.py:199, tests/cli/test_ingest_http.py:245, tests/cli/test_ingest_http.py:294, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_ingest_http.py:106`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_ingest_http.py:106, tests/cli/test_ingest_http.py:209, tests/cli/test_ingest_http.py:258, tests/cli/test_ingest_http.py:306, tests/cli/test_ingest_http.py:345
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_job_commands.py:65`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_job_commands.py:65, tests/cli/test_job_commands.py:112, tests/cli/test_job_commands.py:134, tests/cli/test_job_commands.py:183, tests/cli/test_job_commands.py:204
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_job_commands.py:114`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_job_commands.py:114, tests/cli/test_job_commands.py:136, tests/cli/test_job_commands.py:164, tests/cli/test_job_commands.py:185, tests/cli/test_job_commands.py:206
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_job_commands.py:115`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_job_commands.py:115, tests/cli/test_job_commands.py:137, tests/cli/test_job_commands.py:165, tests/cli/test_job_commands.py:186, tests/cli/test_job_commands.py:207
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_profile_commands.py:163`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/cli/test_profile_commands.py:163, tests/cli/test_prompt_commands.py:228, tests/cli/test_prompt_commands.py:260, tests/cli/test_regression_daily_pipeline.py:186, tests/cli/test_summarize_http.py:61
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_restore_from_cloud.py:161`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/cli/test_restore_from_cloud.py:161, tests/cli/test_restore_from_cloud.py:180, tests/cli/test_restore_from_cloud.py:199, tests/cli/test_restore_from_cloud.py:291, tests/cli/test_restore_from_cloud.py:332, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/cli/test_restore_from_cloud.py:181`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/cli/test_restore_from_cloud.py:181, tests/cli/test_restore_from_cloud.py:200, tests/cli/test_restore_from_cloud.py:292, tests/cli/test_restore_from_cloud.py:333, tests/cli/test_restore_from_cloud.py:357
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/config/test_deploy_secrets.py:21`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/config/test_deploy_secrets.py:21, tests/config/test_deploy_secrets.py:41, tests/config/test_deploy_secrets.py:85, tests/config/test_deploy_secrets.py:102, tests/config/test_deploy_secrets.py:116
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/config/test_production_validation.py:14`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/config/test_production_validation.py:14, tests/config/test_production_validation.py:27, tests/config/test_production_validation.py:40, tests/config/test_production_validation.py:57, tests/config/test_production_validation.py:74, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/config/test_production_validation.py:15`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/config/test_production_validation.py:15, tests/config/test_production_validation.py:28, tests/config/test_production_validation.py:41, tests/config/test_production_validation.py:58, tests/config/test_production_validation.py:75, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/config/test_production_validation.py:16`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/config/test_production_validation.py:16, tests/config/test_production_validation.py:29, tests/config/test_production_validation.py:42, tests/config/test_production_validation.py:59, tests/config/test_production_validation.py:76, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/config/test_production_validation.py:17`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/config/test_production_validation.py:17, tests/config/test_production_validation.py:30, tests/config/test_production_validation.py:43, tests/config/test_production_validation.py:60, tests/config/test_production_validation.py:77, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/e2e/conftest.py:206`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/e2e/conftest.py:206, tests/e2e/conftest.py:212, tests/e2e/conftest.py:219, tests/e2e/conftest.py:228, tests/e2e/conftest.py:235
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/evaluation/test_evaluation_e2e.py:68`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/evaluation/test_evaluation_e2e.py:68, tests/services/test_complexity_router.py:21, tests/services/test_complexity_router.py:36, tests/services/test_complexity_router.py:55, tests/services/test_complexity_router.py:74, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/evaluation/test_judge.py:218`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/evaluation/test_judge.py:218, tests/evaluation/test_judge.py:284, tests/evaluation/test_judge.py:311, tests/evaluation/test_judge.py:331, tests/evaluation/test_judge.py:352
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/evaluation/test_judge.py:219`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/evaluation/test_judge.py:219, tests/evaluation/test_judge.py:285, tests/evaluation/test_judge.py:312, tests/evaluation/test_judge.py:332, tests/evaluation/test_judge.py:353
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/evaluation/test_judge.py:220`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/evaluation/test_judge.py:220, tests/evaluation/test_judge.py:286, tests/evaluation/test_judge.py:313, tests/evaluation/test_judge.py:333, tests/evaluation/test_judge.py:354
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/helpers/simple_mocks.py:122`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/helpers/simple_mocks.py:122, tests/services/test_knowledge_base.py:101, tests/test_services/test_model_pricing_extractor.py:37, tests/test_services/test_model_pricing_extractor.py:47, tests/test_telemetry/test_otel_smoke.py:275, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_audio_digest_flow.py:108`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_audio_digest_flow.py:108, tests/integration/test_audio_digest_flow.py:215, tests/integration/test_audio_digest_flow.py:262, tests/integration/test_audio_digest_flow.py:319, tests/integration/test_audio_digest_flow.py:375
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_audio_digest_flow.py:109`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_audio_digest_flow.py:109, tests/integration/test_audio_digest_flow.py:216, tests/integration/test_audio_digest_flow.py:263, tests/integration/test_audio_digest_flow.py:320, tests/integration/test_audio_digest_flow.py:376
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_audio_digest_flow.py:110`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_audio_digest_flow.py:110, tests/integration/test_audio_digest_flow.py:217, tests/integration/test_audio_digest_flow.py:264, tests/integration/test_audio_digest_flow.py:321, tests/integration/test_audio_digest_flow.py:377
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_audio_digest_flow.py:134`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_audio_digest_flow.py:134, tests/integration/test_audio_digest_flow.py:236, tests/integration/test_audio_digest_flow.py:287, tests/integration/test_audio_digest_flow.py:358, tests/integration/test_audio_digest_flow.py:400
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:79`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:79, tests/integration/test_digest_creation_flow_functional.py:198, tests/integration/test_digest_creation_flow_functional.py:353, tests/integration/test_digest_creation_flow_functional.py:460, tests/integration/test_digest_creation_flow_functional.py:550, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:128`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:128, tests/integration/test_digest_creation_flow_functional.py:242, tests/integration/test_digest_creation_flow_functional.py:296, tests/integration/test_digest_creation_flow_functional.py:396, tests/integration/test_digest_creation_flow_functional.py:499, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:80`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:80, tests/integration/test_digest_creation_flow_functional.py:199, tests/integration/test_digest_creation_flow_functional.py:354, tests/integration/test_digest_creation_flow_functional.py:461, tests/integration/test_digest_creation_flow_functional.py:551, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:126`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:126, tests/integration/test_digest_creation_flow_functional.py:294, tests/integration/test_digest_creation_flow_functional.py:394, tests/integration/test_digest_creation_flow_functional.py:497, tests/integration/test_digest_creation_flow_functional.py:589, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:127`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:127, tests/integration/test_digest_creation_flow_functional.py:295, tests/integration/test_digest_creation_flow_functional.py:395, tests/integration/test_digest_creation_flow_functional.py:498, tests/integration/test_digest_creation_flow_functional.py:590, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:129`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/integration/test_digest_creation_flow_functional.py:129, tests/integration/test_digest_creation_flow_functional.py:243, tests/integration/test_digest_creation_flow_functional.py:397, tests/integration/test_digest_creation_flow_functional.py:500, tests/integration/test_digest_creation_flow_functional.py:592, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:66`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:66, tests/integration/test_digest_creation_flow_functional.py:185, tests/integration/test_digest_creation_flow_functional.py:340, tests/integration/test_digest_creation_flow_functional.py:444, tests/integration/test_digest_creation_flow_functional.py:534
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:75`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:75, tests/integration/test_digest_creation_flow_functional.py:194, tests/integration/test_digest_creation_flow_functional.py:349, tests/integration/test_digest_creation_flow_functional.py:456, tests/integration/test_digest_creation_flow_functional.py:546
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:76`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:76, tests/integration/test_digest_creation_flow_functional.py:195, tests/integration/test_digest_creation_flow_functional.py:350, tests/integration/test_digest_creation_flow_functional.py:457, tests/integration/test_digest_creation_flow_functional.py:547
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:77`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:77, tests/integration/test_digest_creation_flow_functional.py:196, tests/integration/test_digest_creation_flow_functional.py:351, tests/integration/test_digest_creation_flow_functional.py:458, tests/integration/test_digest_creation_flow_functional.py:548
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:78`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:78, tests/integration/test_digest_creation_flow_functional.py:197, tests/integration/test_digest_creation_flow_functional.py:352, tests/integration/test_digest_creation_flow_functional.py:459, tests/integration/test_digest_creation_flow_functional.py:549
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:81`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:81, tests/integration/test_digest_creation_flow_functional.py:200, tests/integration/test_digest_creation_flow_functional.py:355, tests/integration/test_digest_creation_flow_functional.py:462, tests/integration/test_digest_creation_flow_functional.py:552
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:82`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:82, tests/integration/test_digest_creation_flow_functional.py:201, tests/integration/test_digest_creation_flow_functional.py:356, tests/integration/test_digest_creation_flow_functional.py:463, tests/integration/test_digest_creation_flow_functional.py:553
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:101`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:101, tests/integration/test_digest_creation_flow_functional.py:216, tests/integration/test_digest_creation_flow_functional.py:370, tests/integration/test_digest_creation_flow_functional.py:475, tests/integration/test_digest_creation_flow_functional.py:565
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:104`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:104, tests/integration/test_digest_creation_flow_functional.py:218, tests/integration/test_digest_creation_flow_functional.py:372, tests/integration/test_digest_creation_flow_functional.py:477, tests/integration/test_digest_creation_flow_functional.py:567
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:105`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:105, tests/integration/test_digest_creation_flow_functional.py:219, tests/integration/test_digest_creation_flow_functional.py:373, tests/integration/test_digest_creation_flow_functional.py:478, tests/integration/test_digest_creation_flow_functional.py:568
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:106`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:106, tests/integration/test_digest_creation_flow_functional.py:220, tests/integration/test_digest_creation_flow_functional.py:374, tests/integration/test_digest_creation_flow_functional.py:479, tests/integration/test_digest_creation_flow_functional.py:569
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:107`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:107, tests/integration/test_digest_creation_flow_functional.py:221, tests/integration/test_digest_creation_flow_functional.py:375, tests/integration/test_digest_creation_flow_functional.py:480, tests/integration/test_digest_creation_flow_functional.py:570
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:108`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:108, tests/integration/test_digest_creation_flow_functional.py:222, tests/integration/test_digest_creation_flow_functional.py:376, tests/integration/test_digest_creation_flow_functional.py:481, tests/integration/test_digest_creation_flow_functional.py:571
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:109`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:109, tests/integration/test_digest_creation_flow_functional.py:223, tests/integration/test_digest_creation_flow_functional.py:377, tests/integration/test_digest_creation_flow_functional.py:482, tests/integration/test_digest_creation_flow_functional.py:572
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:110`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:110, tests/integration/test_digest_creation_flow_functional.py:224, tests/integration/test_digest_creation_flow_functional.py:378, tests/integration/test_digest_creation_flow_functional.py:483, tests/integration/test_digest_creation_flow_functional.py:573
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:111`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:111, tests/integration/test_digest_creation_flow_functional.py:225, tests/integration/test_digest_creation_flow_functional.py:379, tests/integration/test_digest_creation_flow_functional.py:484, tests/integration/test_digest_creation_flow_functional.py:574
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:113`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:113, tests/integration/test_digest_creation_flow_functional.py:227, tests/integration/test_digest_creation_flow_functional.py:381, tests/integration/test_digest_creation_flow_functional.py:486, tests/integration/test_digest_creation_flow_functional.py:576
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:130`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:130, tests/integration/test_digest_creation_flow_functional.py:244, tests/integration/test_digest_creation_flow_functional.py:398, tests/integration/test_digest_creation_flow_functional.py:501, tests/integration/test_digest_creation_flow_functional.py:593
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:131`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/integration/test_digest_creation_flow_functional.py:131, tests/integration/test_digest_creation_flow_functional.py:245, tests/integration/test_digest_creation_flow_functional.py:399, tests/integration/test_digest_creation_flow_functional.py:502, tests/integration/test_digest_creation_flow_functional.py:594
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (15 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_langfuse_integration.py:46`
- **Metric**: duplicate_copies = 15 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 15 times (cross-file). Locations: tests/integration/test_langfuse_integration.py:46, tests/integration/test_langfuse_integration.py:98, tests/integration/test_opik_integration.py:54, tests/integration/test_opik_integration.py:133, tests/telemetry/test_langfuse_provider.py:225, ...and 10 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (15 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_langfuse_integration.py:47`
- **Metric**: duplicate_copies = 15 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 15 times (cross-file). Locations: tests/integration/test_langfuse_integration.py:47, tests/integration/test_langfuse_integration.py:99, tests/integration/test_opik_integration.py:55, tests/integration/test_opik_integration.py:134, tests/telemetry/test_langfuse_provider.py:226, ...and 10 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (14 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_langfuse_integration.py:45`
- **Metric**: duplicate_copies = 14 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 14 times (cross-file). Locations: tests/integration/test_langfuse_integration.py:45, tests/integration/test_langfuse_integration.py:97, tests/integration/test_opik_integration.py:53, tests/integration/test_opik_integration.py:132, tests/telemetry/test_langfuse_provider.py:224, ...and 9 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_langfuse_integration.py:48`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/integration/test_langfuse_integration.py:48, tests/integration/test_opik_integration.py:56, tests/telemetry/test_langfuse_provider.py:227, tests/test_telemetry/test_llm_integration.py:42, tests/test_telemetry/test_otel_smoke.py:82, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_opik_integration.py:197`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/integration/test_opik_integration.py:197, tests/integration/test_opik_integration.py:217, tests/telemetry/test_langfuse_provider.py:422, tests/telemetry/test_langfuse_provider.py:440, tests/telemetry/test_langfuse_provider.py:460
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_review_workflow.py:56`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/integration/test_review_workflow.py:56, tests/integration/test_review_workflow.py:171, tests/integration/test_review_workflow.py:216, tests/integration/test_review_workflow.py:311, tests/integration/test_review_workflow.py:354, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_review_workflow.py:58`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/integration/test_review_workflow.py:58, tests/integration/test_review_workflow.py:173, tests/integration/test_review_workflow.py:218, tests/integration/test_review_workflow.py:312, tests/integration/test_review_workflow.py:355, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_theme_analysis_workflow.py:27`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/integration/test_theme_analysis_workflow.py:27, tests/integration/test_theme_analysis_workflow.py:45, tests/integration/test_theme_analysis_workflow.py:239, tests/integration/test_theme_analysis_workflow.py:253, tests/test_ingestion/test_scholar.py:68, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_theme_analysis_workflow.py:28`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/integration/test_theme_analysis_workflow.py:28, tests/integration/test_theme_analysis_workflow.py:46, tests/integration/test_theme_analysis_workflow.py:240, tests/integration/test_theme_analysis_workflow.py:254, tests/test_ingestion/test_scholar.py:69, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_theme_analysis_workflow.py:29`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/integration/test_theme_analysis_workflow.py:29, tests/integration/test_theme_analysis_workflow.py:47, tests/integration/test_theme_analysis_workflow.py:241, tests/integration/test_theme_analysis_workflow.py:255, tests/test_processors/test_theme_analyzer.py:101, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_theme_analysis_workflow.py:30`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/integration/test_theme_analysis_workflow.py:30, tests/integration/test_theme_analysis_workflow.py:48, tests/integration/test_theme_analysis_workflow.py:242, tests/integration/test_theme_analysis_workflow.py:256, tests/test_processors/test_theme_analyzer.py:102, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/integration/test_theme_analysis_workflow.py:31`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/integration/test_theme_analysis_workflow.py:31, tests/integration/test_theme_analysis_workflow.py:49, tests/integration/test_theme_analysis_workflow.py:243, tests/integration/test_theme_analysis_workflow.py:257, tests/test_processors/test_theme_analyzer.py:103, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:82`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (same-file). Locations: tests/models/test_evaluation.py:82, tests/models/test_evaluation.py:108, tests/models/test_evaluation.py:143, tests/models/test_evaluation.py:209, tests/models/test_evaluation.py:222, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:83`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (same-file). Locations: tests/models/test_evaluation.py:83, tests/models/test_evaluation.py:109, tests/models/test_evaluation.py:144, tests/models/test_evaluation.py:223, tests/models/test_evaluation.py:283, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:84`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/models/test_evaluation.py:84, tests/models/test_evaluation.py:110, tests/models/test_evaluation.py:145, tests/models/test_evaluation.py:224, tests/models/test_evaluation.py:284, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:85`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/models/test_evaluation.py:85, tests/models/test_evaluation.py:111, tests/models/test_evaluation.py:146, tests/models/test_evaluation.py:225, tests/models/test_evaluation.py:285, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:86`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/models/test_evaluation.py:86, tests/models/test_evaluation.py:112, tests/models/test_evaluation.py:147, tests/models/test_evaluation.py:226, tests/models/test_evaluation.py:286, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:88`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/models/test_evaluation.py:88, tests/models/test_evaluation.py:114, tests/models/test_evaluation.py:149, tests/models/test_evaluation.py:228, tests/models/test_evaluation.py:288, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:115`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/models/test_evaluation.py:115, tests/models/test_evaluation.py:150, tests/models/test_evaluation.py:229, tests/models/test_evaluation.py:289, tests/models/test_evaluation.py:465, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:117`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/models/test_evaluation.py:117, tests/models/test_evaluation.py:152, tests/models/test_evaluation.py:231, tests/models/test_evaluation.py:291, tests/models/test_evaluation.py:467, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:118`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/models/test_evaluation.py:118, tests/models/test_evaluation.py:232, tests/models/test_evaluation.py:292, tests/models/test_evaluation.py:468, tests/models/test_evaluation.py:539
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:119`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/models/test_evaluation.py:119, tests/models/test_evaluation.py:233, tests/models/test_evaluation.py:293, tests/models/test_evaluation.py:469, tests/models/test_evaluation.py:540
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/models/test_evaluation.py:120`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/models/test_evaluation.py:120, tests/models/test_evaluation.py:234, tests/models/test_evaluation.py:294, tests/models/test_evaluation.py:470, tests/models/test_evaluation.py:541
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/security/test_error_sanitization.py:197`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/security/test_error_sanitization.py:197, tests/security/test_error_sanitization.py:210, tests/security/test_error_sanitization.py:225, tests/security/test_error_sanitization.py:241, tests/security/test_error_sanitization.py:255
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/security/test_error_sanitization.py:198`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/security/test_error_sanitization.py:198, tests/security/test_error_sanitization.py:211, tests/security/test_error_sanitization.py:226, tests/security/test_error_sanitization.py:242, tests/security/test_error_sanitization.py:256
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_complexity_router.py:22`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/services/test_complexity_router.py:22, tests/services/test_complexity_router.py:37, tests/services/test_complexity_router.py:56, tests/services/test_complexity_router.py:75, tests/services/test_complexity_router.py:92, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (11 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_content_query.py:333`
- **Metric**: duplicate_copies = 11 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 11 times (same-file). Locations: tests/services/test_content_query.py:333, tests/services/test_content_query.py:353, tests/services/test_content_query.py:378, tests/services/test_content_query.py:402, tests/services/test_content_query.py:422, ...and 6 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_content_query.py:335`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (same-file). Locations: tests/services/test_content_query.py:335, tests/services/test_content_query.py:354, tests/services/test_content_query.py:379, tests/services/test_content_query.py:403, tests/services/test_content_query.py:423, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_content_query.py:331`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/services/test_content_query.py:331, tests/services/test_content_query.py:376, tests/services/test_content_query.py:400, tests/services/test_content_query.py:420, tests/services/test_content_query.py:441, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_html_processor.py:265`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (cross-file). Locations: tests/services/test_html_processor.py:265, tests/services/test_html_processor.py:279, tests/test_models/test_image.py:76, tests/test_models/test_image.py:98, tests/test_models/test_image.py:119, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_knowledge_base.py:96`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/services/test_knowledge_base.py:96, tests/services/test_knowledge_base.py:143, tests/services/test_knowledge_base.py:175, tests/services/test_knowledge_base.py:202, tests/services/test_knowledge_base.py:262
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_knowledge_base.py:97`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/services/test_knowledge_base.py:97, tests/services/test_knowledge_base.py:144, tests/services/test_knowledge_base.py:176, tests/services/test_knowledge_base.py:203, tests/services/test_knowledge_base.py:263
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/services/test_knowledge_base.py:98`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/services/test_knowledge_base.py:98, tests/services/test_knowledge_base.py:145, tests/services/test_knowledge_base.py:177, tests/services/test_knowledge_base.py:204, tests/services/test_knowledge_base.py:264
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/telemetry/test_langfuse_provider.py:223`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (cross-file). Locations: tests/telemetry/test_langfuse_provider.py:223, tests/telemetry/test_langfuse_provider.py:252, tests/telemetry/test_langfuse_provider.py:277, tests/telemetry/test_langfuse_provider.py:295, tests/telemetry/test_langfuse_provider.py:316, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_agents/test_claude_agent.py:61`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/test_agents/test_claude_agent.py:61, tests/test_agents/test_claude_agent.py:69, tests/test_processors/test_digest_creator.py:165, tests/test_utils/test_digest_formatter.py:64, tests/test_utils/test_summary_markdown.py:19, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_agents/test_claude_agent.py:62`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_agents/test_claude_agent.py:62, tests/test_processors/test_digest_creator.py:166, tests/test_utils/test_digest_formatter.py:65, tests/test_utils/test_summary_markdown.py:20, tests/test_utils/test_summary_markdown.py:28
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_profile_validation.py:39`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_config/test_profile_validation.py:39, tests/test_config/test_profile_validation.py:54, tests/test_config/test_profile_validation.py:101, tests/test_config/test_profile_validation.py:127, tests/test_config/test_profile_validation.py:540
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:16`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:16, tests/test_config/test_reference_settings.py:66, tests/test_config/test_settings.py:19, tests/test_config/test_settings.py:165, tests/test_config/test_settings.py:409
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:18`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:18, tests/test_config/test_reference_settings.py:68, tests/test_config/test_settings.py:21, tests/test_config/test_settings.py:166, tests/test_config/test_settings.py:411
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:19`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:19, tests/test_config/test_reference_settings.py:69, tests/test_config/test_settings.py:27, tests/test_config/test_settings.py:168, tests/test_config/test_settings.py:415
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:20`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:20, tests/test_config/test_reference_settings.py:70, tests/test_config/test_settings.py:28, tests/test_config/test_settings.py:169, tests/test_config/test_settings.py:416
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:21`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:21, tests/test_config/test_reference_settings.py:71, tests/test_config/test_settings.py:29, tests/test_config/test_settings.py:170, tests/test_config/test_settings.py:417
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:29`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:29, tests/test_config/test_reference_settings.py:79, tests/test_config/test_settings.py:40, tests/test_config/test_settings.py:180, tests/test_config/test_settings.py:427
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_reference_settings.py:31`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_config/test_reference_settings.py:31, tests/test_config/test_reference_settings.py:81, tests/test_config/test_settings.py:43, tests/test_config/test_settings.py:181, tests/test_config/test_settings.py:429
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_config/test_settings.py:777`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_config/test_settings.py:777, tests/test_config/test_settings.py:789, tests/test_config/test_settings.py:801, tests/test_config/test_settings.py:813, tests/test_config/test_settings.py:825, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_delivery/test_text_chunker.py:115`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_delivery/test_text_chunker.py:115, tests/test_delivery/test_text_chunker.py:149, tests/test_delivery/test_text_chunker.py:162, tests/test_delivery/test_text_chunker.py:409, tests/test_delivery/test_text_chunker.py:433, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_delivery/test_text_chunker.py:116`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_delivery/test_text_chunker.py:116, tests/test_delivery/test_text_chunker.py:150, tests/test_delivery/test_text_chunker.py:163, tests/test_delivery/test_text_chunker.py:434, tests/test_delivery/test_text_chunker.py:449
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_blog_scraper.py:37`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_ingestion/test_blog_scraper.py:37, tests/test_ingestion/test_blog_scraper.py:83, tests/test_ingestion/test_blog_scraper.py:104, tests/test_ingestion/test_blog_scraper.py:130, tests/test_ingestion/test_blog_scraper.py:162, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_blog_scraper.py:38`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_ingestion/test_blog_scraper.py:38, tests/test_ingestion/test_blog_scraper.py:84, tests/test_ingestion/test_blog_scraper.py:105, tests/test_ingestion/test_blog_scraper.py:131, tests/test_ingestion/test_blog_scraper.py:163, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_blog_scraper.py:39`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_ingestion/test_blog_scraper.py:39, tests/test_ingestion/test_blog_scraper.py:85, tests/test_ingestion/test_blog_scraper.py:106, tests/test_ingestion/test_blog_scraper.py:132, tests/test_ingestion/test_blog_scraper.py:182, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_huggingface_papers.py:297`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_ingestion/test_huggingface_papers.py:297, tests/test_ingestion/test_huggingface_papers.py:309, tests/test_ingestion/test_huggingface_papers.py:320, tests/test_ingestion/test_huggingface_papers.py:330, tests/test_ingestion/test_huggingface_papers.py:351
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_podcast.py:286`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_ingestion/test_podcast.py:286, tests/test_ingestion/test_podcast.py:327, tests/test_ingestion/test_podcast.py:366, tests/test_ingestion/test_podcast.py:405, tests/test_ingestion/test_podcast.py:441
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_podcast.py:288`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_ingestion/test_podcast.py:288, tests/test_ingestion/test_podcast.py:328, tests/test_ingestion/test_podcast.py:367, tests/test_ingestion/test_podcast.py:406, tests/test_ingestion/test_podcast.py:442
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_scholar.py:600`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_ingestion/test_scholar.py:600, tests/test_ingestion/test_scholar.py:654, tests/test_ingestion/test_scholar.py:683, tests/test_ingestion/test_scholar.py:701, tests/test_ingestion/test_scholar.py:722
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (16 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_youtube_sources.py:134`
- **Metric**: duplicate_copies = 16 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 16 times (same-file). Locations: tests/test_ingestion/test_youtube_sources.py:134, tests/test_ingestion/test_youtube_sources.py:159, tests/test_ingestion/test_youtube_sources.py:184, tests/test_ingestion/test_youtube_sources.py:209, tests/test_ingestion/test_youtube_sources.py:249, ...and 11 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (16 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_youtube_sources.py:135`
- **Metric**: duplicate_copies = 16 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 16 times (same-file). Locations: tests/test_ingestion/test_youtube_sources.py:135, tests/test_ingestion/test_youtube_sources.py:160, tests/test_ingestion/test_youtube_sources.py:185, tests/test_ingestion/test_youtube_sources.py:210, tests/test_ingestion/test_youtube_sources.py:250, ...and 11 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (16 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_youtube_sources.py:136`
- **Metric**: duplicate_copies = 16 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 16 times (same-file). Locations: tests/test_ingestion/test_youtube_sources.py:136, tests/test_ingestion/test_youtube_sources.py:161, tests/test_ingestion/test_youtube_sources.py:186, tests/test_ingestion/test_youtube_sources.py:211, tests/test_ingestion/test_youtube_sources.py:251, ...and 11 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_ingestion/test_youtube_sources.py:157`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/test_ingestion/test_youtube_sources.py:157, tests/test_ingestion/test_youtube_sources.py:182, tests/test_ingestion/test_youtube_sources.py:207, tests/test_ingestion/test_youtube_sources.py:273, tests/test_ingestion/test_youtube_sources.py:297, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_models/test_image.py:53`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_models/test_image.py:53, tests/test_models/test_image.py:116, tests/test_models/test_image.py:130, tests/test_models/test_image.py:157, tests/test_models/test_image.py:169
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_models/test_image.py:54`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_models/test_image.py:54, tests/test_models/test_image.py:117, tests/test_models/test_image.py:131, tests/test_models/test_image.py:158, tests/test_models/test_image.py:170
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:141`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:141, tests/test_processors/test_audio_digest_generator.py:186, tests/test_processors/test_audio_digest_generator.py:268, tests/test_processors/test_audio_digest_generator.py:346, tests/test_processors/test_audio_digest_generator.py:398, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:142`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:142, tests/test_processors/test_audio_digest_generator.py:187, tests/test_processors/test_audio_digest_generator.py:269, tests/test_processors/test_audio_digest_generator.py:347, tests/test_processors/test_audio_digest_generator.py:399, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:143`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:143, tests/test_processors/test_audio_digest_generator.py:188, tests/test_processors/test_audio_digest_generator.py:270, tests/test_processors/test_audio_digest_generator.py:348, tests/test_processors/test_audio_digest_generator.py:400, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:145`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:145, tests/test_processors/test_audio_digest_generator.py:190, tests/test_processors/test_audio_digest_generator.py:272, tests/test_processors/test_audio_digest_generator.py:350, tests/test_processors/test_audio_digest_generator.py:402, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:146`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:146, tests/test_processors/test_audio_digest_generator.py:191, tests/test_processors/test_audio_digest_generator.py:273, tests/test_processors/test_audio_digest_generator.py:351, tests/test_processors/test_audio_digest_generator.py:403, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:160`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:160, tests/test_processors/test_audio_digest_generator.py:245, tests/test_processors/test_audio_digest_generator.py:285, tests/test_processors/test_audio_digest_generator.py:372, tests/test_processors/test_audio_digest_generator.py:420, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:139`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:139, tests/test_processors/test_audio_digest_generator.py:184, tests/test_processors/test_audio_digest_generator.py:230, tests/test_processors/test_audio_digest_generator.py:266, tests/test_processors/test_audio_digest_generator.py:519, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:147`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:147, tests/test_processors/test_audio_digest_generator.py:192, tests/test_processors/test_audio_digest_generator.py:274, tests/test_processors/test_audio_digest_generator.py:527, tests/test_processors/test_audio_digest_generator.py:712
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:148`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:148, tests/test_processors/test_audio_digest_generator.py:193, tests/test_processors/test_audio_digest_generator.py:275, tests/test_processors/test_audio_digest_generator.py:528, tests/test_processors/test_audio_digest_generator.py:713
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_audio_digest_generator.py:286`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_audio_digest_generator.py:286, tests/test_processors/test_audio_digest_generator.py:373, tests/test_processors/test_audio_digest_generator.py:421, tests/test_processors/test_audio_digest_generator.py:468, tests/test_processors/test_audio_digest_generator.py:724
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_digest_creator.py:125`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (cross-file). Locations: tests/test_processors/test_digest_creator.py:125, tests/test_processors/test_digest_creator.py:138, tests/test_processors/test_digest_creator.py:151, tests/test_processors/test_podcast_script_generator.py:41, tests/test_utils/test_digest_markdown.py:20
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (13 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_digest_text_preparer.py:482`
- **Metric**: duplicate_copies = 13 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 13 times (cross-file). Locations: tests/test_processors/test_digest_text_preparer.py:482, tests/test_processors/test_digest_text_preparer.py:512, tests/test_utils/test_digest_formatter.py:153, tests/test_utils/test_digest_formatter.py:160, tests/test_utils/test_digest_formatter.py:166, ...and 8 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (10 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_digest_text_preparer.py:52`
- **Metric**: duplicate_copies = 10 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 10 times (same-file). Locations: tests/test_processors/test_digest_text_preparer.py:52, tests/test_processors/test_digest_text_preparer.py:123, tests/test_processors/test_digest_text_preparer.py:163, tests/test_processors/test_digest_text_preparer.py:241, tests/test_processors/test_digest_text_preparer.py:250, ...and 5 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_digest_text_preparer.py:153`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_digest_text_preparer.py:153, tests/test_processors/test_digest_text_preparer.py:183, tests/test_processors/test_digest_text_preparer.py:191, tests/test_processors/test_digest_text_preparer.py:211, tests/test_processors/test_digest_text_preparer.py:229, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_digest_text_preparer.py:124`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_digest_text_preparer.py:124, tests/test_processors/test_digest_text_preparer.py:164, tests/test_processors/test_digest_text_preparer.py:242, tests/test_processors/test_digest_text_preparer.py:272, tests/test_processors/test_digest_text_preparer.py:285
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:491`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_historical_context.py:491, tests/test_processors/test_historical_context.py:515, tests/test_processors/test_historical_context.py:540, tests/test_processors/test_historical_context.py:565, tests/test_processors/test_historical_context.py:590, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:494`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_historical_context.py:494, tests/test_processors/test_historical_context.py:518, tests/test_processors/test_historical_context.py:543, tests/test_processors/test_historical_context.py:568, tests/test_processors/test_historical_context.py:593, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:495`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_historical_context.py:495, tests/test_processors/test_historical_context.py:519, tests/test_processors/test_historical_context.py:544, tests/test_processors/test_historical_context.py:569, tests/test_processors/test_historical_context.py:594, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:496`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_processors/test_historical_context.py:496, tests/test_processors/test_historical_context.py:520, tests/test_processors/test_historical_context.py:545, tests/test_processors/test_historical_context.py:570, tests/test_processors/test_historical_context.py:595, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:507`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_historical_context.py:507, tests/test_processors/test_historical_context.py:532, tests/test_processors/test_historical_context.py:557, tests/test_processors/test_historical_context.py:582, tests/test_processors/test_historical_context.py:607
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:508`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_historical_context.py:508, tests/test_processors/test_historical_context.py:533, tests/test_processors/test_historical_context.py:558, tests/test_processors/test_historical_context.py:583, tests/test_processors/test_historical_context.py:608
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_processors/test_historical_context.py:521`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_processors/test_historical_context.py:521, tests/test_processors/test_historical_context.py:546, tests/test_processors/test_historical_context.py:571, tests/test_processors/test_historical_context.py:596, tests/test_processors/test_historical_context.py:621
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_chunking.py:198`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_services/test_chunking.py:198, tests/test_services/test_chunking.py:466, tests/test_services/test_chunking.py:501, tests/test_services/test_chunking.py:524, tests/test_services/test_chunking.py:552
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (8 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_file_storage.py:463`
- **Metric**: duplicate_copies = 8 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 8 times (same-file). Locations: tests/test_services/test_file_storage.py:463, tests/test_services/test_file_storage.py:482, tests/test_services/test_file_storage.py:501, tests/test_services/test_file_storage.py:520, tests/test_services/test_file_storage.py:533, ...and 3 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_file_storage.py:464`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_services/test_file_storage.py:464, tests/test_services/test_file_storage.py:483, tests/test_services/test_file_storage.py:502, tests/test_services/test_file_storage.py:521, tests/test_services/test_file_storage.py:534, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_file_storage.py:637`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_services/test_file_storage.py:637, tests/test_services/test_file_storage.py:685, tests/test_services/test_file_storage.py:704, tests/test_services/test_file_storage.py:722, tests/test_services/test_file_storage.py:735, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_file_storage.py:635`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_services/test_file_storage.py:635, tests/test_services/test_file_storage.py:702, tests/test_services/test_file_storage.py:720, tests/test_services/test_file_storage.py:733, tests/test_services/test_file_storage.py:751
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Large file: 1141 lines

- **Category**: large-file
- **Location**: `tests/test_services/test_file_storage.py:1`
- **Metric**: file_lines = 1141 (threshold: 500)
- **Smell**: Large Class / God File — Fowler: Extract Class, Move Method
- **Detail**: tests/test_services/test_file_storage.py has 1141 lines (threshold: 500). Consider splitting into focused modules.
- **Recommendation**: Extract cohesive groups of functions into separate modules.

### [HIGH] Duplicated code block (6 copies, cross-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_model_pricing_extractor.py:30`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (cross-file). Locations: tests/test_services/test_model_pricing_extractor.py:30, tests/test_services/test_model_pricing_extractor.py:40, tests/test_services/test_model_pricing_extractor.py:50, tests/test_services/test_model_pricing_extractor.py:195, tests/test_telemetry/test_otel_smoke.py:276, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_services/test_review_service.py:120`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_services/test_review_service.py:120, tests/test_services/test_review_service.py:273, tests/test_services/test_review_service.py:298, tests/test_services/test_review_service.py:320, tests/test_services/test_review_service.py:340, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_storage/test_neon_branch.py:245`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_storage/test_neon_branch.py:245, tests/test_storage/test_neon_branch.py:308, tests/test_storage/test_neon_branch.py:550, tests/test_storage/test_neon_branch.py:565, tests/test_storage/test_neon_branch.py:652
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_storage/test_neon_branch.py:247`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_storage/test_neon_branch.py:247, tests/test_storage/test_neon_branch.py:310, tests/test_storage/test_neon_branch.py:552, tests/test_storage/test_neon_branch.py:567, tests/test_storage/test_neon_branch.py:654
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_storage/test_providers.py:27`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_storage/test_providers.py:27, tests/test_storage/test_providers.py:62, tests/test_storage/test_providers.py:80, tests/test_storage/test_providers.py:115, tests/test_storage/test_providers.py:124
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_config.py:76`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_telemetry/test_config.py:76, tests/test_telemetry/test_config.py:86, tests/test_telemetry/test_config.py:96, tests/test_telemetry/test_config.py:119, tests/test_telemetry/test_config.py:141, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_llm_integration.py:28`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_telemetry/test_llm_integration.py:28, tests/test_telemetry/test_llm_integration.py:66, tests/test_telemetry/test_llm_integration.py:96, tests/test_telemetry/test_llm_integration.py:122, tests/test_telemetry/test_llm_integration.py:150
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (5 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_llm_integration.py:29`
- **Metric**: duplicate_copies = 5 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 5 times (same-file). Locations: tests/test_telemetry/test_llm_integration.py:29, tests/test_telemetry/test_llm_integration.py:67, tests/test_telemetry/test_llm_integration.py:97, tests/test_telemetry/test_llm_integration.py:123, tests/test_telemetry/test_llm_integration.py:151
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (9 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_log_correlation.py:19`
- **Metric**: duplicate_copies = 9 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 9 times (same-file). Locations: tests/test_telemetry/test_log_correlation.py:19, tests/test_telemetry/test_log_correlation.py:61, tests/test_telemetry/test_log_correlation.py:82, tests/test_telemetry/test_log_correlation.py:127, tests/test_telemetry/test_log_correlation.py:147, ...and 4 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_log_correlation.py:62`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_telemetry/test_log_correlation.py:62, tests/test_telemetry/test_log_correlation.py:83, tests/test_telemetry/test_log_correlation.py:128, tests/test_telemetry/test_log_correlation.py:167, tests/test_telemetry/test_log_correlation.py:191, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (7 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_log_correlation.py:63`
- **Metric**: duplicate_copies = 7 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 7 times (same-file). Locations: tests/test_telemetry/test_log_correlation.py:63, tests/test_telemetry/test_log_correlation.py:84, tests/test_telemetry/test_log_correlation.py:129, tests/test_telemetry/test_log_correlation.py:168, tests/test_telemetry/test_log_correlation.py:192, ...and 2 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_log_correlation.py:17`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_telemetry/test_log_correlation.py:17, tests/test_telemetry/test_log_correlation.py:59, tests/test_telemetry/test_log_correlation.py:80, tests/test_telemetry/test_log_correlation.py:125, tests/test_telemetry/test_log_correlation.py:145, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] Duplicated code block (6 copies, same-file)

- **Category**: duplicate-code
- **Location**: `tests/test_telemetry/test_log_correlation.py:18`
- **Metric**: duplicate_copies = 6 (threshold: 2)
- **Smell**: Duplicated Code — Fowler: Extract Method, Pull Up Method
- **Detail**: A 6-line code block appears 6 times (same-file). Locations: tests/test_telemetry/test_log_correlation.py:18, tests/test_telemetry/test_log_correlation.py:60, tests/test_telemetry/test_log_correlation.py:81, tests/test_telemetry/test_log_correlation.py:126, tests/test_telemetry/test_log_correlation.py:146, ...and 1 more
- **Recommendation**: Extract Method or Extract Class to share the common logic. If cross-file, consider a shared utility module.

### [HIGH] High fan-out:  depends on 46578 modules

- **Category**: high-coupling
- **Location**: `N/A`
- **Metric**: fan_out = 46578 (threshold: 10)
- **Smell**: Shotgun Surgery / Feature Envy — Fowler: Move Method, Inline Class
- **Detail**: Node '' has 46578 outgoing dependencies (threshold: 10). Changes to its dependencies may require updates here (Shotgun Surgery).
- **Recommendation**: Introduce a facade or mediator to reduce direct dependencies. Consider if this module has Feature Envy for another module's data.

### [HIGH] High fan-in:  depended on by 46578 modules

- **Category**: high-coupling
- **Location**: `N/A`
- **Metric**: fan_in = 46578 (threshold: 10)
- **Smell**: Change Amplifier — Stabilize interfaces, version APIs
- **Detail**: Node '' is depended on by 46578 other nodes (threshold: 10). Any change to this module has a large blast radius.
- **Recommendation**: Stabilize the interface (freeze the API). Consider extracting a stable abstraction layer.

### [HIGH] Hub node:  (fan-in=46578, fan-out=46578)

- **Category**: high-coupling
- **Location**: `N/A`
- **Metric**: hub_score = 93156 (threshold: 16)
- **Smell**: God Object / Blob — Fowler: Extract Class, SRP
- **Detail**: Node '' is a hub with 46578 incoming and 46578 outgoing dependencies. Hub nodes are God Objects — they know too much and do too much.
- **Recommendation**: Split into smaller, focused modules. Apply the Single Responsibility Principle.

### [HIGH] Deep nesting: interactive_script_review() has nesting depth 7

- **Category**: deep-nesting
- **Location**: `scripts/generate_podcast.py:81`
- **Span**: lines 81-232
- **Metric**: nesting_depth = 7 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'interactive_script_review' in scripts/generate_podcast.py has control-flow nesting depth 7 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: interactive_revision_session() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `scripts/review_digest.py:102`
- **Span**: lines 102-330
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'interactive_revision_session' in scripts/review_digest.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: main() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `scripts/review_digest.py:375`
- **Span**: lines 375-477
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'main' in scripts/review_digest.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _plan_task() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/agents/conductor.py:302`
- **Span**: lines 302-368
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_plan_task' in src/agents/conductor.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: get_artifact_content() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/chat_routes.py:225`
- **Span**: lines 225-394
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'get_artifact_content' in src/api/chat_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: apply_action_to_summary() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/chat_routes.py:572`
- **Span**: lines 572-648
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'apply_action_to_summary' in src/api/chat_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: apply_action_to_digest() has nesting depth 7

- **Category**: deep-nesting
- **Location**: `src/api/chat_routes.py:651`
- **Span**: lines 651-722
- **Metric**: nesting_depth = 7 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'apply_action_to_digest' in src/api/chat_routes.py has control-flow nesting depth 7 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: apply_action_to_script() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/chat_routes.py:725`
- **Span**: lines 725-848
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'apply_action_to_script' in src/api/chat_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: trigger_content_summarization() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/content_routes.py:813`
- **Span**: lines 813-907
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'trigger_content_summarization' in src/api/content_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: event_stream() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/notification_routes.py:217`
- **Span**: lines 217-292
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'event_stream' in src/api/notification_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: generate() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/api/notification_routes.py:231`
- **Span**: lines 231-282
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'generate' in src/api/notification_routes.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _stream_sse() has nesting depth 7

- **Category**: deep-nesting
- **Location**: `src/cli/api_client.py:380`
- **Span**: lines 380-409
- **Metric**: nesting_depth = 7 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_stream_sse' in src/cli/api_client.py has control-flow nesting depth 7 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: mask_secrets_in_dict() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/config/secrets.py:232`
- **Span**: lines 232-295
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'mask_secrets_in_dict' in src/config/secrets.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: ingest_from_search() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/ingestion/arxiv.py:492`
- **Span**: lines 492-558
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'ingest_from_search' in src/ingestion/arxiv.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: ingest_content() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/ingestion/gmail.py:490`
- **Span**: lines 490-687
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'ingest_content' in src/ingestion/gmail.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: ingest_content() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/ingestion/rss.py:462`
- **Span**: lines 462-732
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'ingest_content' in src/ingestion/rss.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: get_transcript() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/ingestion/youtube.py:348`
- **Span**: lines 348-442
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'get_transcript' in src/ingestion/youtube.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _process_video() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/ingestion/youtube.py:615`
- **Span**: lines 615-850
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_process_video' in src/ingestion/youtube.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _fetch_transcript() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/parsers/youtube_parser.py:148`
- **Span**: lines 148-201
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_fetch_transcript' in src/parsers/youtube_parser.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: link_source_content_ids() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/scripts/migrate_digests_markdown.py:289`
- **Span**: lines 289-352
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'link_source_content_ids' in src/scripts/migrate_digests_markdown.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: build_curation_plan() has nesting depth 7

- **Category**: deep-nesting
- **Location**: `src/services/source_curator.py:228`
- **Span**: lines 228-263
- **Metric**: nesting_depth = 7 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'build_curation_plan' in src/services/source_curator.py has control-flow nesting depth 7 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: close() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/storage/falkordb_provider.py:139`
- **Span**: lines 139-154
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'close' in src/storage/falkordb_provider.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: import_graph() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/storage/falkordb_provider.py:264`
- **Span**: lines 264-335
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'import_graph' in src/storage/falkordb_provider.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: export_content_stubs() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/sync/obsidian_exporter.py:500`
- **Span**: lines 500-599
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'export_content_stubs' in src/sync/obsidian_exporter.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: export_topics() has nesting depth 7

- **Category**: deep-nesting
- **Location**: `src/sync/obsidian_exporter.py:746`
- **Span**: lines 746-844
- **Metric**: nesting_depth = 7 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'export_topics' in src/sync/obsidian_exporter.py has control-flow nesting depth 7 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _import_table() has nesting depth 8

- **Category**: deep-nesting
- **Location**: `src/sync/pg_importer.py:286`
- **Span**: lines 286-429
- **Metric**: nesting_depth = 8 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_import_table' in src/sync/pg_importer.py has control-flow nesting depth 8 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: extract_digest_theme_tags() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/utils/digest_markdown.py:193`
- **Span**: lines 193-227
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'extract_digest_theme_tags' in src/utils/digest_markdown.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: extract_source_content_ids() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/utils/digest_markdown.py:230`
- **Span**: lines 230-259
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'extract_source_content_ids' in src/utils/digest_markdown.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: extract_relevance_scores() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `src/utils/markdown.py:206`
- **Span**: lines 206-265
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'extract_relevance_scores' in src/utils/markdown.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: _ensure_db_exists() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/e2e/server.py:145`
- **Span**: lines 145-171
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function '_ensure_db_exists' in tests/e2e/server.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: ensure_test_db_exists() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/helpers/test_db.py:81`
- **Span**: lines 81-133
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'ensure_test_db_exists' in tests/helpers/test_db.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: test_create_daily_digest_with_summaries() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:50`
- **Span**: lines 50-166
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'test_create_daily_digest_with_summaries' in tests/integration/test_digest_creation_flow_functional.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: test_create_weekly_digest() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:170`
- **Span**: lines 170-265
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'test_create_weekly_digest' in tests/integration/test_digest_creation_flow_functional.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: test_digest_includes_all_newsletter_sources() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:325`
- **Span**: lines 325-431
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'test_digest_includes_all_newsletter_sources' in tests/integration/test_digest_creation_flow_functional.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: test_digest_processing_time_tracked() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:435`
- **Span**: lines 435-522
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'test_digest_processing_time_tracked' in tests/integration/test_digest_creation_flow_functional.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Deep nesting: test_digest_with_custom_limits() has nesting depth 6

- **Category**: deep-nesting
- **Location**: `tests/integration/test_digest_creation_flow_functional.py:526`
- **Span**: lines 526-615
- **Metric**: nesting_depth = 6 (threshold: 4)
- **Smell**: Deep Nesting — Fowler: Decompose Conditional, Guard Clauses
- **Detail**: Function 'test_digest_with_custom_limits' in tests/integration/test_digest_creation_flow_functional.py has control-flow nesting depth 6 (threshold: 4). Deep nesting hurts readability and increases cognitive load.
- **Recommendation**: Use guard clauses (early returns), Extract Method, or Decompose Conditional.

### [HIGH] Too many parameters: generate_podcast() takes 9 params

- **Category**: parameter-excess
- **Location**: `scripts/generate_podcast.py:251`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'generate_podcast' in scripts/generate_podcast.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: list_contents() takes 13 params

- **Category**: parameter-excess
- **Location**: `src/api/content_routes.py:371`
- **Metric**: parameter_count = 13 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'list_contents' in src/api/content_routes.py accepts 13 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: predict_monthly_costs() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/api/pricing_routes.py:51`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'predict_monthly_costs' in src/api/pricing_routes.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: search_get() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/api/search_routes.py:38`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'search_get' in src/api/search_routes.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: list_summaries() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/api/summary_routes.py:152`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'list_summaries' in src/api/summary_routes.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: curate_rss() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/cli/curate_commands.py:42`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'curate_rss' in src/cli/curate_commands.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: edit_summary() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/cli/edit_commands.py:113`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'edit_summary' in src/cli/edit_commands.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: build_query_from_options() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/cli/query_options.py:15`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'build_query_from_options' in src/cli/query_options.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: summarize_pending() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/cli/summarize_commands.py:78`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'summarize_pending' in src/cli/summarize_commands.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _summarize_pending_direct() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/cli/summarize_commands.py:219`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_summarize_pending_direct' in src/cli/summarize_commands.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: import_cmd() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/cli/sync_commands.py:178`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'import_cmd' in src/cli/sync_commands.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: push_cmd() takes 11 params

- **Category**: parameter-excess
- **Location**: `src/cli/sync_commands.py:328`
- **Metric**: parameter_count = 11 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'push_cmd' in src/cli/sync_commands.py accepts 11 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: obsidian_cmd() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/cli/sync_commands.py:583`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'obsidian_cmd' in src/cli/sync_commands.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: __init__() takes 17 params

- **Category**: parameter-excess
- **Location**: `src/config/models.py:309`
- **Metric**: parameter_count = 17 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '__init__' in src/config/models.py accepts 17 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: synthesize() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/delivery/tts_service.py:214`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'synthesize' in src/delivery/tts_service.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: ingest_feed() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/ingestion/podcast.py:176`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'ingest_feed' in src/ingestion/podcast.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _process_video() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/ingestion/youtube.py:615`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_process_video' in src/ingestion/youtube.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: ingest_playlist() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/ingestion/youtube.py:852`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'ingest_playlist' in src/ingestion/youtube.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: ingest_feed() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/ingestion/youtube.py:1386`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'ingest_feed' in src/ingestion/youtube.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _process_rss_video() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/ingestion/youtube.py:1471`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_process_rss_video' in src/ingestion/youtube.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: list_content() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/mcp_server.py:1043`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'list_content' in src/mcp_server.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: update_digest() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/mcp_server.py:1498`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'update_digest' in src/mcp_server.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _backfill_full() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/scripts/backfill_chunks.py:91`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_backfill_full' in src/scripts/backfill_chunks.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: update_task_status() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/agent_service.py:90`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'update_task_status' in src/services/agent_service.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: create_insight() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/services/agent_service.py:144`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'create_insight' in src/services/agent_service.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: add_sample() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/evaluation_service.py:95`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'add_sample' in src/services/evaluation_service.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: __init__() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/file_storage.py:530`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '__init__' in src/services/file_storage.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: predict_monthly_costs() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/services/infrastructure_pricing_service.py:328`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'predict_monthly_costs' in src/services/infrastructure_pricing_service.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: generate_with_tools() takes 13 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:315`
- **Metric**: parameter_count = 13 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'generate_with_tools' in src/services/llm_router.py accepts 13 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: generate_with_planning() takes 13 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:476`
- **Metric**: parameter_count = 13 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'generate_with_planning' in src/services/llm_router.py accepts 13 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: generate_with_video() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:773`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'generate_with_video' in src/services/llm_router.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _trace_llm_call() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:1109`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_trace_llm_call' in src/services/llm_router.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _generate_anthropic_with_tools() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:1219`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_generate_anthropic_with_tools' in src/services/llm_router.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _generate_gemini_with_video() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:1376`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_generate_gemini_with_video' in src/services/llm_router.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _generate_gemini_with_tools() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:1461`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_generate_gemini_with_tools' in src/services/llm_router.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _generate_openai_with_tools() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/services/llm_router.py:1653`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_generate_openai_with_tools' in src/services/llm_router.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: get_provider() takes 9 params

- **Category**: parameter-excess
- **Location**: `src/storage/providers/factory.py:53`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'get_provider' in src/storage/providers/factory.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _write_note() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/sync/obsidian_exporter.py:1094`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_write_note' in src/sync/obsidian_exporter.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/base.py:40`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/base.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/braintrust.py:99`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/braintrust.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: __init__() takes 8 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/langfuse.py:55`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '__init__' in src/telemetry/providers/langfuse.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/langfuse.py:162`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/langfuse.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/noop.py:33`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/noop.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/opik.py:164`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/opik.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: trace_llm_call() takes 10 params

- **Category**: parameter-excess
- **Location**: `src/telemetry/providers/otel_provider.py:136`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'trace_llm_call' in src/telemetry/providers/otel_provider.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_specialist_result() takes 8 params

- **Category**: parameter-excess
- **Location**: `tests/agents/test_conductor.py:33`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_specialist_result' in tests/agents/test_conductor.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_topic() takes 9 params

- **Category**: parameter-excess
- **Location**: `tests/api/test_kb_lint.py:38`
- **Metric**: parameter_count = 9 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_topic' in tests/api/test_kb_lint.py accepts 9 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_topic() takes 10 params

- **Category**: parameter-excess
- **Location**: `tests/api/test_kb_routes.py:21`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_topic' in tests/api/test_kb_routes.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_topic() takes 8 params

- **Category**: parameter-excess
- **Location**: `tests/api/test_kb_search.py:40`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_topic' in tests/api/test_kb_search.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: test_daily_pipeline_success() takes 10 params

- **Category**: parameter-excess
- **Location**: `tests/cli/test_pipeline_commands.py:93`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'test_daily_pipeline_success' in tests/cli/test_pipeline_commands.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: test_daily_pipeline_emits_pipeline_completion() takes 10 params

- **Category**: parameter-excess
- **Location**: `tests/cli/test_pipeline_commands.py:130`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'test_daily_pipeline_emits_pipeline_completion' in tests/cli/test_pipeline_commands.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: test_weekly_pipeline_success() takes 10 params

- **Category**: parameter-excess
- **Location**: `tests/cli/test_pipeline_commands.py:210`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'test_weekly_pipeline_success' in tests/cli/test_pipeline_commands.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: test_weekly_pipeline_emits_pipeline_completion() takes 10 params

- **Category**: parameter-excess
- **Location**: `tests/cli/test_pipeline_commands.py:247`
- **Metric**: parameter_count = 10 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function 'test_weekly_pipeline_emits_pipeline_completion' in tests/cli/test_pipeline_commands.py accepts 10 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_topic() takes 12 params

- **Category**: parameter-excess
- **Location**: `tests/services/test_kb_qa_health.py:47`
- **Metric**: parameter_count = 12 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_topic' in tests/services/test_kb_qa_health.py accepts 12 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_feedparser_entry() takes 11 params

- **Category**: parameter-excess
- **Location**: `tests/test_ingestion/test_podcast.py:55`
- **Metric**: parameter_count = 11 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_feedparser_entry' in tests/test_ingestion/test_podcast.py accepts 11 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] Too many parameters: _make_ref() takes 8 params

- **Category**: parameter-excess
- **Location**: `tests/test_services/test_reference_resolver.py:32`
- **Metric**: parameter_count = 8 (threshold: 5)
- **Smell**: Long Parameter List — Fowler: Introduce Parameter Object
- **Detail**: Function '_make_ref' in tests/test_services/test_reference_resolver.py accepts 8 parameters (threshold: 5). Long parameter lists make calling code harder to read.
- **Recommendation**: Introduce Parameter Object or use a dataclass/TypedDict.

### [HIGH] High import fan-out: src.api.app imports 60 modules

- **Category**: import-complexity
- **Location**: `src/api/app.py:1`
- **Metric**: import_fan_out = 60 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.api.app' imports 60 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.api.chat_routes imports 25 modules

- **Category**: import-complexity
- **Location**: `src/api/chat_routes.py:1`
- **Metric**: import_fan_out = 25 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.api.chat_routes' imports 25 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.cli.app imports 31 modules

- **Category**: import-complexity
- **Location**: `src/cli/app.py:1`
- **Metric**: import_fan_out = 31 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.cli.app' imports 31 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.cli.manage_commands imports 30 modules

- **Category**: import-complexity
- **Location**: `src/cli/manage_commands.py:1`
- **Metric**: import_fan_out = 30 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.cli.manage_commands' imports 30 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] Circular import: src.config -> src.config.models -> src.storage.database -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 3 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (3 modules): src.config -> src.config.models -> src.storage.database -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.storage.database -> src.utils.logging -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 4 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (4 modules): src.config -> src.config.models -> src.storage.database -> src.utils.logging -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.railway -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 5 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (5 modules): src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.railway -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.neon_branch -> src.utils.logging -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 6 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (6 modules): src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.neon_branch -> src.utils.logging -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.factory -> src.storage.providers.railway -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 6 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (6 modules): src.config -> src.config.models -> src.storage.database -> src.storage.providers -> src.storage.providers.factory -> src.storage.providers.railway -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 4 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (4 modules): src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.utils.logging -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 5 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (5 modules): src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.utils.logging -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.storage.providers -> src.storage.providers.railway -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 6 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (6 modules): src.config -> src.config.models -> src.services.settings_service -> src.storage.database -> src.storage.providers -> src.storage.providers.railway -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.settings -> src.storage.database -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 3 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (3 modules): src.config -> src.config.settings -> src.storage.database -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] Circular import: src.config -> src.config.settings -> src.storage.database -> src.utils.logging -> src.config

- **Category**: import-complexity
- **Location**: `src/config/__init__.py`
- **Metric**: cycle_length = 4 (threshold: 1)
- **Smell**: Circular Dependency — Extract shared types, lazy imports
- **Detail**: Circular dependency detected (4 modules): src.config -> src.config.settings -> src.storage.database -> src.utils.logging -> src.config. Circular imports make initialization order fragile and can cause ImportError at runtime.
- **Recommendation**: Break the cycle by extracting shared types into a separate module, or use lazy imports (import inside function).

### [HIGH] High import fan-out: src.ingestion.youtube imports 33 modules

- **Category**: import-complexity
- **Location**: `src/ingestion/youtube.py:1`
- **Metric**: import_fan_out = 33 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.ingestion.youtube' imports 33 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.mcp_server imports 43 modules

- **Category**: import-complexity
- **Location**: `src/mcp_server.py:1`
- **Metric**: import_fan_out = 43 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.mcp_server' imports 43 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.models imports 26 modules

- **Category**: import-complexity
- **Location**: `src/models/__init__.py:1`
- **Metric**: import_fan_out = 26 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.models' imports 26 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: src.queue.worker imports 26 modules

- **Category**: import-complexity
- **Location**: `src/queue/worker.py:1`
- **Metric**: import_fan_out = 26 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'src.queue.worker' imports 26 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

### [HIGH] High import fan-out: tests.api.conftest imports 29 modules

- **Category**: import-complexity
- **Location**: `tests/api/conftest.py:1`
- **Metric**: import_fan_out = 29 (threshold: 15)
- **Smell**: Divergent Change — Fowler: Extract Class (split responsibilities)
- **Detail**: Module 'tests.api.conftest' imports 29 unique modules (threshold: 15). This suggests the module has too many responsibilities.
- **Recommendation**: Split the module along responsibility boundaries. Each module should import from a focused set of dependencies.

## Recommendations

1. Address 689 high/critical findings first — these indicate active maintainability risks.
2. Refactor 51 complex functions — apply Extract Method and Replace Conditional with Polymorphism.
3. Break down 119 long methods — Fowler: 'The key refactoring is Extract Method.'
4. Split 12 large file(s) — each module should have a single, clear responsibility.
5. Eliminate 393 duplicate code groups — extract shared logic into utility functions or base classes.
6. Prioritize src/cli/ingest_commands.py (34 findings) — it's the top hotspot file.

## Analyzer Performance

| Analyzer | Status | Findings | Duration |
|----------|--------|----------|----------|
| coupling | ok | 3 | 144ms |
| imports | ok | 65 | 7270ms |
| duplication | ok | 5278 | 9005ms |
| complexity | ok | 1688 | 9531ms |
