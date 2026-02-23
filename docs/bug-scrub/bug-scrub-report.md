# Bug Scrub Report

**Timestamp**: 2026-02-22T20:02:07.599610+00:00
**Sources**: pytest, ruff, mypy, openspec, architecture, security, deferred, markers
**Severity filter**: low
**Total findings**: 4224

## Summary

### By Severity

| Severity | Count |
|----------|-------|
| high | 119 |
| medium | 3688 |
| low | 417 |

### By Source

| Source | Count |
|--------|-------|
| deferred:open-tasks | 951 |
| markers | 58 |
| mypy | 3041 |
| openspec | 2 |
| pytest | 87 |
| ruff | 85 |

## Critical / High Findings

### [HIGH] Test failure: test_upload_valid_auth_accepted

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/api/test_upload_auth.py:103
- **Detail**: asser...

### [HIGH] Test failure: TestParallelIngestionPartialFailure::test_pipeline_succeeds_when_two_sources_fail

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestParallelIngestionPartialFailure::test_pipeline_succeeds_when_three_sources_fail

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestParallelIngestionAllFail::test_pipeline_reports_all_source_errors

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestParallelExecution::test_ingestion_uses_asyncio_gather

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestParallelExecution::test_partial_failure_returns_successful_sources_only

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestParallelExecution::test_all_fail_raises_runtime_error

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/cli/test_pipeline_integration.py:302
- **Detail**: Failed: DID NOT RAISE <class 'RuntimeError'>

### [HIGH] Test failure: TestWorkerInitialization::test_run_worker_initializes_queue

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/cli/test_worker_commands.py

### [HIGH] Test failure: TestWorkerInitialization::test_run_worker_registers_signal_handlers

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/cli/test_worker_commands.py

### [HIGH] Test failure: TestWorkerInitialization::test_run_worker_passes_concurrency_to_pgq_run

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/cli/test_worker_commands.py

### [HIGH] Test failure: TestWorkerInitialization::test_run_worker_cleans_up_on_cancelled_error

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/cli/test_worker_commands.py

### [HIGH] Test failure: TestNeonBranchManagerIntegration::test_list_branches

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_neon_integration.py:224
- **Detail**: AssertionError: assert None == 404

### [HIGH] Test failure: TestNeonBranchManagerIntegration::test_create_and_delete_branch

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_neon_integration.py:224
- **Detail**: AssertionError: assert None == 404

### [HIGH] Test failure: TestNeonBranchManagerIntegration::test_get_connection_string

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_neon_integration.py:224
- **Detail**: AssertionError: assert None == 404

### [HIGH] Test failure: TestNeonBranchManagerIntegration::test_branch_context_creates_and_cleans_up

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_neon_integration.py:224
- **Detail**: AssertionError: assert None == 404

### [HIGH] Test failure: TestNeonBranchManagerIntegration::test_delete_nonexistent_branch_raises_error

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_neon_integration.py:224
- **Detail**: AssertionError: assert None == 404

### [HIGH] Test failure: TestSupabaseConnection::test_pooled_connection_works

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnection::test_ssl_connection_required

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnection::test_database_version

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnection::test_health_check_passes

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnection::test_connection_timeout_is_set

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseDirectConnection::test_direct_connection_works

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseDirectConnection::test_direct_connection_ssl

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseDirectConnection::test_can_check_alembic_version_table

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseDirectConnection::test_can_execute_ddl_operations

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnectionPooling::test_multiple_sequential_connections

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnectionPooling::test_concurrent_connections

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnectionPooling::test_connection_pool_exhaustion_recovery

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: TestSupabaseConnectionPooling::test_transaction_mode_isolation

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/integration/test_supabase_provider.py:60
- **Detail**: assert False is True

### [HIGH] Test failure: test_digest_routes_protected_in_production

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/security/test_digest_auth.py

### [HIGH] Test failure: test_content_routes_protected_in_production

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/security/test_digest_auth.py

### [HIGH] Test failure: test_search_routes_protected_in_production

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/security/test_search_auth.py

### [HIGH] Test failure: test_update_prompt_auth

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/security/test_settings_auth.py
- **Detail**: sqlalc...

### [HIGH] Test failure: test_reset_prompt_auth

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/security/test_settings_auth.py
- **Detail**: sqlalch...

### [HIGH] Test failure: TestHealthEndpoints::test_health_returns_200

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestHealthEndpoints::test_ready_returns_200

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestHealthEndpoints::test_system_config_returns_200

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMagicBytes::test_pdf_with_png_header_returns_415

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMagicBytes::test_png_with_jpeg_header_returns_415

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMagicBytes::test_exe_disguised_as_pdf_returns_415

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMagicBytes::test_valid_pdf_magic_bytes_passes_signature_check

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMagicBytes::test_unknown_extension_skips_signature_check

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMimeValidation::test_pdf_with_image_mime_returns_415

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMimeValidation::test_html_with_pdf_mime_returns_415

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMimeValidation::test_octet_stream_bypasses_mime_check

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadMimeValidation::test_matching_mime_and_extension_passes

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestUploadSizeEnforcement::test_small_file_accepted

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestCORSHeaders::test_preflight_returns_cors_headers

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestCORSHeaders::test_cors_allows_configured_origin

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestAdminAuth::test_prompts_without_auth_in_dev_mode

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestAdminAuth::test_prompts_with_wrong_key_returns_403

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestEndpointExistence::test_upload_endpoint_exists

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestEndpointExistence::test_formats_endpoint_exists

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/smoke/test_api_security_smoke.py

### [HIGH] Test failure: TestAudioDigestGeneratorInitialization::test_default_initialization

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_processors/test_audio_digest_generator.py:29
- **Detail**: AssertionError: assert <MagicMock name='settings.get_effective_voice()' id='4767335104'> == 'nova'

### [HIGH] Test failure: test_create_digest_success

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_processors/test_digest_creator.py

### [HIGH] Test failure: test_create_digest_without_historical_context

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_processors/test_digest_creator.py

### [HIGH] Test failure: TestCountTokens::test_counts_tokens

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestCountTokens::test_empty_string

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestMarkdownChunkingStrategy::test_basic_chunking

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestMarkdownChunkingStrategy::test_code_block_preserved

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestMarkdownChunkingStrategy::test_chunk_indexes_sequential

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestMarkdownChunkingStrategy::test_section_path_tracking

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestYouTubeTranscriptStrategy::test_timestamp_parsing

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestYouTubeTranscriptStrategy::test_chunk_type_is_transcript

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestGeminiSummaryStrategy::test_splits_on_topic_sections

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestGeminiSummaryStrategy::test_no_timestamp_metadata

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestChunkingService::test_resolves_defaults

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestChunkingService::test_source_config_override

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_services/test_chunking.py

### [HIGH] Test failure: TestFetchURL::test_fetch_url_success

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestFetchURL::test_fetch_url_follows_redirects

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestFetchURL::test_fetch_url_raises_on_http_error

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestFetchURL::test_fetch_url_rejects_oversized_content_header

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestFetchURL::test_fetch_url_rejects_oversized_content_body

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestFetchURL::test_fetch_url_rejects_non_html_content

- **Source**: pytest
- **Category**: test-failure
- **Location**: /Users/jankneumann/Coding/agentic-newsletter-aggregator/tests/test_services/test_url_extractor.py:209
- **Detail**: AssertionError: Regex pattern did not match.

### [HIGH] Test failure: TestTokenCounter::test_initialization

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_text_tokens_simple

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_text_tokens_empty

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_text_tokens_long

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_newsletter_batch_tokens

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_newsletter_batch_tokens_empty

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_calculate_token_budget_claude

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_calculate_token_budget_custom_percentage

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_calculate_newsletters_that_fit

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_calculate_newsletters_that_fit_zero_budget

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_token_estimation_consistency

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_estimate_with_summaries

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] Test failure: TestTokenCounter::test_model_id_defaults_correctly

- **Source**: pytest
- **Category**: test-failure
- **Location**: tests/test_utils/test_token_counter.py

### [HIGH] E741: Ambiguous variable name: `l`

- **Source**: ruff
- **Category**: lint
- **Location**: .claude/skills/merge-pull-requests/scripts/discover_prs.py:133
- **Detail**: Ambiguous variable name: `l`

### [HIGH] E741: Ambiguous variable name: `l`

- **Source**: ruff
- **Category**: lint
- **Location**: .codex/skills/merge-pull-requests/scripts/discover_prs.py:133
- **Detail**: Ambiguous variable name: `l`

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/analyze_themes.py:53
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/analyze_themes.py:55
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/analyze_themes.py:62
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/analyze_themes.py:145
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/analyze_themes.py:147
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_daily_digest.py:50
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_daily_digest.py:52
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_daily_digest.py:57
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_daily_digest.py:138
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_daily_digest.py:140
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_weekly_digest.py:58
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_weekly_digest.py:60
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_weekly_digest.py:65
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_weekly_digest.py:143
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/generate_weekly_digest.py:145
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/query_knowledge_graph.py:32
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/query_knowledge_graph.py:34
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/query_knowledge_graph.py:69
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/query_knowledge_graph.py:72
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:49
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:51
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:55
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:88
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:90
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E226: Missing whitespace around arithmetic operator

- **Source**: ruff
- **Category**: lint
- **Location**: scripts/summarize_newsletters.py:94
- **Detail**: Missing whitespace around arithmetic operator

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/api/test_upload_security_regression.py:9
- **Detail**: Expected 2 blank lines, found 1

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/api/test_upload_security_regression.py:17
- **Detail**: Expected 2 blank lines, found 1

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/security/test_digest_auth.py:10
- **Detail**: Expected 2 blank lines, found 1

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/security/test_digest_auth.py:28
- **Detail**: Expected 2 blank lines, found 1

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/security/test_search_xss.py:3
- **Detail**: Expected 2 blank lines, found 1

## Medium Findings

| Source | Location | Title |
|--------|----------|-------|
| ruff | .claude/skills/bug-scrub/scripts/collect_deferred.py:271 | SIM113: Use `enumerate()` for index variable `idx` in `for` loop |
| ruff | .claude/skills/bug-scrub/scripts/collect_markers.py:48 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/bug-scrub/scripts/collect_markers.py:63 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/bug-scrub/scripts/collect_mypy.py:60 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/bug-scrub/scripts/collect_openspec.py:110 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/bug-scrub/scripts/collect_ruff.py:57 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/bug-scrub/scripts/collect_ruff.py:75 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/fix-scrub/scripts/execute_auto.py:47 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/fix-scrub/scripts/execute_auto.py:59 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/merge-pull-requests/scripts/check_staleness.py:94 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/merge-pull-requests/scripts/check_staleness.py:196 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:26 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:40 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:57 | RUF005: Consider `["gh", *args]` instead of concatenation |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:65 | RUF005: Consider `['gh', *args]` instead of concatenation |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:77 | RUF005: Consider `["gh", *args]` instead of concatenation |
| ruff | .claude/skills/merge-pull-requests/scripts/shared.py:175 | S607: Starting a process with a partial executable path |
| ruff | .claude/skills/security-review/scripts/detect_profile.py:94 | RUF005: Consider `[*detected, "mixed"]` instead of concatenation |
| ruff | .claude/skills/security-review/scripts/main.py:66 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_deferred.py:271 | SIM113: Use `enumerate()` for index variable `idx` in `for` loop |
| ruff | .codex/skills/bug-scrub/scripts/collect_markers.py:48 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_markers.py:63 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_mypy.py:60 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_openspec.py:110 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_ruff.py:57 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/bug-scrub/scripts/collect_ruff.py:75 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/fix-scrub/scripts/execute_auto.py:47 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/fix-scrub/scripts/execute_auto.py:59 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/merge-pull-requests/scripts/check_staleness.py:94 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/merge-pull-requests/scripts/check_staleness.py:196 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:26 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:40 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:57 | RUF005: Consider `["gh", *args]` instead of concatenation |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:65 | RUF005: Consider `['gh', *args]` instead of concatenation |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:77 | RUF005: Consider `["gh", *args]` instead of concatenation |
| ruff | .codex/skills/merge-pull-requests/scripts/shared.py:175 | S607: Starting a process with a partial executable path |
| ruff | .codex/skills/security-review/scripts/detect_profile.py:94 | RUF005: Consider `[*detected, "mixed"]` instead of concatenation |
| ruff | .codex/skills/security-review/scripts/main.py:66 | S607: Starting a process with a partial executable path |
| ruff | scripts/generate_podcast.py:127 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:145 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:154 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:196 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:163 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:226 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:294 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:299 | ASYNC250: Blocking call to input() in async context |
| ruff | tests/api/test_upload_security.py:202 | RUF059: Unpacked variable `args` is never used |
| ruff | tests/api/test_upload_security_regression.py:1 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/security/test_digest_auth.py:2 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/security/test_digest_auth.py:2 | F401: `pytest` imported but unused |
| ruff | tests/security/test_search_xss.py:1 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/test_models/test_summary_performance.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/test_models/test_summary_performance.py:5 | F401: `src.models.summary.Summary` imported but unused |
| mypy | tests/api/test_system.py:7 | Function is missing a type annotation |
| mypy | tests/api/test_system.py:20 | Function is missing a type annotation |
| mypy | tests/api/test_system.py:29 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:11 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:28 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:43 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:60 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:85 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:107 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:131 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:146 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:162 | Function is missing a type annotation |
| mypy | tests/api/test_prompt_test_api.py:180 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:7 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:15 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:23 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:39 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:48 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:87 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:97 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:112 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:124 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:136 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:150 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:167 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:182 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:197 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:209 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:225 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:262 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:274 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:287 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:298 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:306 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:314 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:321 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:331 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:345 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:354 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:363 | Function is missing a type annotation |
| mypy | tests/helpers/api_mocks.py:35 | Returning Any from function declared to return "dict[Any, Any]" |
| mypy | tests/api/test_voice_settings_api.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:21 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:45 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:53 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:60 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:68 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:75 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:109 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:120 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:19 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:29 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:47 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:72 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:88 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:101 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:112 | Function is missing a type annotation |
| mypy | scripts/setup_test_db.py:145 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:18 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:23 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:31 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:44 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:59 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:69 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:82 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:95 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:106 | Function is missing a type annotation |
| mypy | tests/test_utils/test_markdown.py:119 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:165 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:169 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:181 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:194 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:207 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:224 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:236 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:240 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:252 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:262 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:273 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:283 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:291 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:308 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:313 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:321 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:327 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:333 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:345 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:351 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:357 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:369 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:375 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:389 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:395 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:402 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:410 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:424 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:434 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:440 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:446 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:463 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:476 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:483 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:489 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:505 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:509 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:522 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:537 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:544 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:558 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:568 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:584 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:594 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_markdown.py:611 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:15 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:19 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:23 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:28 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:37 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:43 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:49 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:54 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:63 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:69 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:74 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:81 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:87 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:97 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:101 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:106 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:112 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:118 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:125 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:136 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:143 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:148 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:154 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:160 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:166 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:176 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:183 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:188 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:194 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_content_hash.py:201 | Function is missing a return type annotation |
| mypy | tests/test_models/test_chat.py:9 | Function is missing a return type annotation |
| mypy | tests/test_models/test_chat.py:16 | Function is missing a return type annotation |
| mypy | src/config/sources.py:14 | Library stubs not installed for "yaml" |
| mypy | src/config/profiles.py:19 | Library stubs not installed for "yaml" |
| mypy | src/config/secrets.py:16 | Library stubs not installed for "yaml" |
| mypy | alembic/versions/f9a8b7c6d5e5_add_index_to_canonical_id.py:25 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/f9a8b7c6d5e5_add_index_to_canonical_id.py:41 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/f9a8b7c6d5e4_merge_heads_and_cleanup.py:17 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/f9a8b7c6d5e4_merge_heads_and_cleanup.py:29 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b8affd253096_merge_add_document_search_with_main.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:33 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:83 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:155 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:23 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:26 | Function is missing a type annotation |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:60 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:62 | Function is missing a type annotation |
| mypy | alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/58aa2c7e188c_add_summary_created_at_index.py:24 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/58aa2c7e188c_add_summary_created_at_index.py:40 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | tests/test_parsers/test_youtube_models.py:17 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:21 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:26 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:31 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:35 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:43 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:47 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:52 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:61 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:70 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:75 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:80 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:95 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:107 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:120 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:127 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:152 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:169 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:188 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:209 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:232 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:244 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:255 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_models.py:266 | Function is missing a return type annotation |
| mypy | tests/test_models/test_summary_performance.py:8 | Function is missing a return type annotation |
| mypy | tests/api/test_podcast_api.py:7 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:15 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:72 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:87 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:95 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:110 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:134 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:149 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:194 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:200 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:223 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:15 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:65 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:83 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:101 | Function is missing a type annotation |
| mypy | src/config/migrate_sources.py:17 | Library stubs not installed for "yaml" |
| mypy | src/config/migrate_sources.py:281 | Returning Any from function declared to return "str" |
| mypy | tests/api/test_upload_exception.py:6 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:19 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:24 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:29 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:34 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:39 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:44 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:49 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:58 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:63 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:68 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:73 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:78 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:87 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:93 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:103 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:111 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:119 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:124 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:135 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:140 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:145 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:150 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:159 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:164 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:169 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:175 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:184 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:193 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:200 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:209 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_links.py:221 | Function is missing a return type annotation |
| mypy | tests/api/test_script_api.py:9 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:26 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:35 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:48 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:59 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:69 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:77 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:91 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:103 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:126 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:163 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:172 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:178 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:188 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:197 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:207 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:227 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:242 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:257 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:282 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:312 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:325 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:338 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_document_models.py:14 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:30 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:40 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:49 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:67 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:75 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:96 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:110 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:125 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:145 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:161 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:179 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_document_models.py:186 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:27 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:37 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:43 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:52 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:68 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:93 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:115 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:129 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:141 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:156 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:168 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:185 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:193 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:217 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:243 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:257 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:280 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:288 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:300 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:314 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:342 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:371 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:389 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:406 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:434 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:452 | Function is missing a return type annotation |
| mypy | tests/test_models/test_image.py:468 | Function is missing a return type annotation |
| mypy | tests/api/test_save_api.py:19 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:105 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:119 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:128 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:141 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:166 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:190 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:213 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:224 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:231 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:251 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:264 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:275 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:282 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:290 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:302 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:319 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:335 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:353 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:387 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:398 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:409 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:442 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:471 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:486 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:43 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:92 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:123 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:20 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:28 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:38 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:46 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:56 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:72 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:90 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:98 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:110 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:120 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:126 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:140 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:158 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:171 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:184 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:194 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:210 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:220 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:229 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:237 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:260 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:283 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:288 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:297 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:306 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:320 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:334 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:354 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:372 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:385 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:400 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:419 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:428 | Function is missing a type annotation |
| mypy | tests/api/test_summary_security.py:14 | Function is missing a return type annotation |
| mypy | src/config/models.py:53 | Library stubs not installed for "yaml" |
| mypy | tests/test_telemetry/test_log_correlation.py:14 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:35 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:56 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:77 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:98 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:122 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:142 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:161 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:185 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:205 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:224 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:247 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:290 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:15 | Function is missing a type annotation for one or more arguments |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "bool | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "int | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "bool | list[str] | tuple[str, ...] | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "CliSettingsSource[Any] | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "Literal['all', 'no_enums'] | bool | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "Mapping[str, str | list[str]] | None" |
| mypy | tests/security/test_production_validation.py:31 | Function is missing a type annotation |
| mypy | tests/security/test_production_validation.py:38 | Function is missing a type annotation |
| mypy | tests/security/test_production_validation.py:49 | Function is missing a type annotation |
| mypy | tests/security/test_production_validation.py:62 | Function is missing a type annotation |
| mypy | tests/security/test_production_validation.py:75 | Function is missing a type annotation |
| mypy | tests/security/test_production_validation.py:89 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:98 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:107 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:116 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:124 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:132 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:141 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:150 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:159 | Function is missing a return type annotation |
| mypy | tests/api/test_summary_api.py:16 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:26 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:38 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:62 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:74 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_summary_api.py:110 | Argument "processing_time_seconds" to "Summary" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_summary_api.py:122 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:149 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:160 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:171 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:189 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:200 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:210 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:225 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:236 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:247 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:263 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:280 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:292 | Function is missing a type annotation |
| mypy | src/utils/html_parser.py:74 | Value of type variable "AnyStr" of "urljoin" cannot be "Sequence[str]" |
| mypy | src/utils/html_parser.py:88 | Incompatible return value type (got "list[str | AttributeValueList]", expected "list[str]") |
| mypy | src/cli/profile_commands.py:129 | Library stubs not installed for "yaml" |
| mypy | src/cli/neon_commands.py:23 | Function is missing a return type annotation |
| mypy | src/cli/neon_commands.py:51 | Function is missing a return type annotation |
| mypy | src/cli/neon_commands.py:96 | Function is missing a return type annotation |
| mypy | src/cli/neon_commands.py:138 | Function is missing a return type annotation |
| mypy | src/cli/neon_commands.py:161 | Function is missing a return type annotation |
| mypy | src/cli/neon_commands.py:191 | Function is missing a return type annotation |
| mypy | scripts/performance_test.py:309 | Library stubs not installed for "requests" |
| mypy | src/services/chat_service.py:227 | No overload variant of "create" of "AsyncCompletions" matches argument types "str", "list[dict[str, Any]]", "bool", "dict[str, bool]" |
| mypy | tests/test_utils/test_token_counter.py:10 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:16 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:26 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:32 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:42 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:56 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:62 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:81 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:98 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:118 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:129 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:139 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:149 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_token_counter.py:169 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:11 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:31 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:51 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:65 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:86 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:96 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:103 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:109 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:7 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:11 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:29 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:41 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_api.py:16 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:27 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:43 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:59 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:81 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:97 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:110 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:121 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:128 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:154 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:192 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:216 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:237 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:246 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:259 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:276 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:295 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:304 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:314 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:327 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:344 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:356 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:371 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:402 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:428 | Function is missing a type annotation |
| mypy | tests/api/test_settings_api.py:439 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:11 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:45 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:79 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:96 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:23 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:28 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:33 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:39 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:43 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:52 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:59 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:67 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:71 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:75 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:79 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:83 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:95 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:98 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:105 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:109 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:113 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:121 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:127 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:139 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:142 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:150 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:161 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:164 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:171 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:184 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:199 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:214 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:229 | Function is missing a type annotation |
| mypy | tests/api/test_error_handler.py:22 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:26 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:52 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:78 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:14 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:50 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:56 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:63 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:70 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:77 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:83 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:89 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:95 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:102 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:107 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:119 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:135 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:142 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:149 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:154 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:159 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:170 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:176 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:182 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:188 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:197 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:210 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:217 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:224 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:231 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:238 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:250 | Function is missing a type annotation |
| mypy | tests/test_utils/test_summary_markdown.py:258 | Function is missing a type annotation |
| mypy | tests/test_helpers/test_test_db.py:30 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:37 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:44 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:52 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:59 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:64 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:74 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:90 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:95 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:103 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:111 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:119 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:127 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:140 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:154 | Function is missing a type annotation |
| mypy | tests/test_helpers/test_test_db.py:159 | Function is missing a type annotation |
| mypy | tests/test_helpers/test_test_db.py:170 | Function is missing a type annotation |
| mypy | tests/test_helpers/test_test_db.py:189 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:212 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:230 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:249 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:261 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:287 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:311 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:316 | Function is missing a return type annotation |
| mypy | tests/test_helpers/test_test_db.py:321 | Function is missing a return type annotation |
| mypy | tests/test_config/test_secrets.py:10 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_profiles.py:11 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_profiles.py:557 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/test_config/test_profiles.py:575 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/test_config/test_profile_validation.py:8 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_migrate_sources.py:10 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_migrate_sources.py:95 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:105 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:111 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:122 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:128 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:137 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:147 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:162 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:171 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:181 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:208 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:217 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:223 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:229 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:235 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:245 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:252 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:258 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:264 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:270 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:287 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:297 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:305 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:316 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:326 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:336 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:339 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:344 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:363 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:380 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:400 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:419 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:447 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:463 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:480 | Argument 1 to "write_sources_directory" has incompatible type "dict[str, object]"; expected "list[dict[str, Any]] | dict[str, list[dict[str, Any]]]" |
| mypy | tests/test_config/test_migrate_sources.py:490 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:505 | Argument 1 has incompatible type "dict[str, object]"; expected "list[dict[str, Any]] | dict[str, list[dict[str, Any]]]" |
| mypy | tests/test_config/test_migrate_sources.py:513 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:521 | Argument 1 has incompatible type "dict[str, object]"; expected "list[dict[str, Any]] | dict[str, list[dict[str, Any]]]" |
| mypy | tests/test_config/test_migrate_sources.py:530 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:531 | Need type annotation for "sources" |
| mypy | tests/test_config/test_migrate_sources.py:552 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:575 | Argument 1 to "write_sources_directory" has incompatible type "dict[str, object]"; expected "list[dict[str, Any]] | dict[str, list[dict[str, Any]]]" |
| mypy | tests/test_config/test_migrate_sources.py:593 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:609 | Argument 1 has incompatible type "dict[str, object]"; expected "list[dict[str, Any]] | dict[str, list[dict[str, Any]]]" |
| mypy | tests/test_config/test_migrate_sources.py:625 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:648 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:660 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:687 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:706 | Function is missing a return type annotation |
| mypy | tests/test_config/test_migrate_sources.py:720 | Function is missing a return type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:31 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:38 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:43 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:61 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:69 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:77 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:84 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:95 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:116 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:124 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:131 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:140 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:159 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:175 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:189 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:209 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:215 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:222 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:240 | Function is missing a type annotation |
| mypy | tests/smoke/test_api_security_smoke.py:245 | Function is missing a type annotation |
| mypy | tests/smoke/conftest.py:40 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/smoke/conftest.py:47 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/integration/test_hoverfly_rss.py:29 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:42 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:52 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:61 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:69 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:85 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:89 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:97 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:105 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:114 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:119 | Function is missing a type annotation |
| mypy | tests/integration/test_hoverfly_rss.py:130 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:11 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:41 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:54 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:70 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:90 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:97 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:131 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:139 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:148 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:27 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:33 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:46 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:56 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:62 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:77 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:85 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:104 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:116 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:128 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:152 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:165 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:190 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:194 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:199 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:209 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:218 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiter.py:240 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:245 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:259 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:270 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:292 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:299 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:307 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiter.py:313 | Function is missing a return type annotation |
| mypy | tests/api/test_audio_digest_api.py:14 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_audio_digest_api.py:19 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:23 | Argument "duration_seconds" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:36 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_audio_digest_api.py:42 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:46 | Argument "duration_seconds" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:52 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:59 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:115 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:131 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:141 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:157 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:165 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:174 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:184 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:213 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:221 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:229 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:247 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:255 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:270 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:284 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:302 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:322 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:329 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:346 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:352 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:362 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:382 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:390 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:430 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:449 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:455 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:15 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:83 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:88 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:94 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:101 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:108 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:114 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:122 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:129 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:135 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:140 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:145 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:150 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:165 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:171 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:177 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:182 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:189 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:198 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:203 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:208 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:222 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:227 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:236 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:242 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:248 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:254 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:260 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:273 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:280 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:287 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:294 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:300 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:311 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:331 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:345 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:98 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:146 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:191 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:224 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:256 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:287 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:324 | Function is missing a type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:379 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:412 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_formatter.py:440 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_router.py:15 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_router.py:30 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_router.py:45 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:50 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:57 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:62 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:67 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:71 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:75 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:82 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:88 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:94 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:99 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:104 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:109 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:114 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:119 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:124 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:129 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:134 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:140 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:146 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:154 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:162 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_router.py:179 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_router.py:199 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:15 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:60 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:80 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:135 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:149 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:159 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:187 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:202 | Function is missing a type annotation |
| mypy | tests/test_models/test_revision.py:239 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:255 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:265 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:275 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:292 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:313 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:326 | Function is missing a return type annotation |
| mypy | tests/test_models/test_revision.py:350 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:32 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:48 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:58 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:67 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:80 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:89 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:98 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:117 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:158 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:177 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:185 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:213 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:244 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:256 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:265 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:279 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:293 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:326 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:347 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:365 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:384 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:415 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:429 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:460 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:475 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:480 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:484 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:488 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:519 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:7 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:13 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:29 | Function is missing a return type annotation |
| mypy | tests/helpers/test_hoverfly.py:16 | Function is missing a return type annotation |
| mypy | tests/helpers/test_hoverfly.py:25 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:34 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:42 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:49 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:58 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:66 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:79 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:96 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:100 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:118 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:129 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:138 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:149 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:157 | Function is missing a type annotation |
| mypy | tests/helpers/test_hoverfly.py:162 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:19 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_service.py:25 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:31 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_service.py:47 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_service.py:62 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:72 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:81 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:94 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:106 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:115 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:127 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:137 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:151 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:165 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:173 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:185 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:202 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:210 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:223 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:247 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:255 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:265 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:275 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:288 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:296 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:304 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_service.py:313 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:25 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:100 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:230 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:234 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:241 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:245 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:265 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:280 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:285 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:290 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:299 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:309 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:324 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:330 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:341 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:352 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:367 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:379 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:397 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:410 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:424 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:441 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:449 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:459 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:467 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:477 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:504 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:514 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:528 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:532 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:536 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_config.py:13 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:20 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:27 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:34 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:41 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:49 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:56 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:64 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:75 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:85 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:95 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:108 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:118 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:130 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:140 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:156 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:167 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:178 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:193 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:200 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:207 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:214 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:224 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:235 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_config.py:245 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:26 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:35 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:51 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:61 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:70 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:79 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:88 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:104 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:114 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:123 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:136 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:141 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:147 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:157 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:168 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:181 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:186 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:192 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:207 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:220 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:229 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:240 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:254 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:263 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:270 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:279 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:289 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:295 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:306 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:315 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:328 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:341 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:356 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:363 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:369 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:375 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:389 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:402 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:413 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:419 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:431 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:438 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:445 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:452 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:467 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:473 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:482 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:492 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:500 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:508 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:521 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:530 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:538 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:548 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:557 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:570 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:574 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:581 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:587 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:592 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:599 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:606 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:613 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:24 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:36 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:62 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:71 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:88 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:104 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:116 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:143 | Unpacking a string is disallowed |
| mypy | tests/test_storage/test_neon_branch.py:144 | Cannot determine type of "resp_method" |
| mypy | tests/test_storage/test_neon_branch.py:144 | Cannot determine type of "url_pattern" |
| mypy | tests/test_storage/test_neon_branch.py:145 | Cannot determine type of "resp_method" |
| mypy | tests/test_storage/test_neon_branch.py:145 | Cannot determine type of "url_pattern" |
| mypy | tests/test_storage/test_neon_branch.py:174 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:182 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:236 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:299 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:347 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:388 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:415 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:467 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:528 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_neon_branch.py:536 | Function is missing a type annotation |
| mypy | tests/test_storage/test_neon_branch.py:640 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:4 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_sources.py:25 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:33 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:44 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:52 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:65 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:71 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:75 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:82 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:86 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:93 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:97 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:103 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:112 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:119 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:123 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:136 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:141 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:155 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:160 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:167 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:179 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:193 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:212 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:231 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:252 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:258 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:277 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:281 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:298 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:324 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:350 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:369 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:387 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:407 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:427 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:440 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:456 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:470 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:487 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:500 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:514 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:528 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:547 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:560 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:574 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:592 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:599 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:606 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:614 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:638 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:647 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:663 | Function is missing a type annotation |
| mypy | tests/test_config/test_settings.py:14 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:52 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:63 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:73 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:88 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:101 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:112 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:123 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:136 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:156 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:179 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:191 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:203 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:223 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:238 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:259 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:281 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:297 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:309 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:329 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:361 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:373 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:385 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:397 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:413 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:426 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:438 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:453 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:471 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:485 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:496 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:519 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:531 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:547 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:556 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:565 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:586 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:608 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:619 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:635 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:652 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:671 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:679 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:690 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:700 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:712 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:724 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:736 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:748 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:766 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:779 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:795 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:805 | Function is missing a return type annotation |
| mypy | tests/test_config/test_profile_integration.py:12 | Library stubs not installed for "yaml" |
| mypy | tests/test_config/test_profile_integration.py:17 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:29 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:38 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:59 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:84 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:101 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:112 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:121 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:137 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:142 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:153 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:166 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:186 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:199 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:210 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:220 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:242 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:263 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:303 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:319 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:348 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:358 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:375 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:393 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:414 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:427 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:462 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:485 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:490 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:497 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:529 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:543 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:556 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:572 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:585 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:603 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:15 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:26 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/services/test_settings_service.py:26 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_settings_service.py:41 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:46 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:50 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:61 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:70 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:79 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:86 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:94 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:99 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:104 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:113 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:119 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:123 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:132 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:139 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:149 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:155 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:160 | Function is missing a return type annotation |
| mypy | tests/services/test_settings_service.py:165 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:177 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:185 | Function is missing a type annotation |
| mypy | tests/services/test_settings_service.py:189 | Function is missing a return type annotation |
| mypy | tests/integration/test_markdown_outputs.py:21 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_markdown_outputs.py:71 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_markdown_outputs.py:209 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:236 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:253 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:318 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:363 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:386 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:419 | Function is missing a type annotation |
| mypy | tests/integration/test_markdown_outputs.py:477 | Function is missing a return type annotation |
| mypy | tests/integration/test_markdown_outputs.py:496 | Function is missing a return type annotation |
| mypy | tests/api/test_sorting.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:66 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:75 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:84 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:104 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:114 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:127 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:137 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:166 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:190 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:215 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:225 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:234 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:243 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:261 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:298 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:308 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:317 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:331 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:341 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:359 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:397 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:420 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:430 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:439 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:448 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:466 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:520 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:537 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:546 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:555 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:564 | Function is missing a type annotation |
| mypy | tests/api/test_sorting.py:573 | Function is missing a type annotation |
| mypy | tests/api/test_content_summarization_logic.py:14 | Function is missing a return type annotation |
| mypy | tests/api/test_content_summarization_logic.py:22 | Function is missing a type annotation |
| mypy | tests/api/test_content_summarization_logic.py:107 | Function is missing a type annotation |
| mypy | tests/api/test_content_summarization_logic.py:127 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:13 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:17 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:21 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:26 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:31 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:41 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:47 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:64 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:73 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:80 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:87 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:100 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:118 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:136 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:150 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:156 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:177 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:199 | Function is missing a return type annotation |
| mypy | tests/test_prompt_service.py:205 | Function is missing a type annotation |
| mypy | tests/test_prompt_service.py:211 | Function is missing a type annotation |
| mypy | tests/unit/test_factories.py:24 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:34 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:42 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:52 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:60 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:69 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:77 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:85 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:93 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:106 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:117 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:126 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:133 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:139 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:149 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:160 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:169 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:176 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:182 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:191 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:198 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:206 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:218 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:230 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:239 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:247 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:255 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:265 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:274 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:283 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:296 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:303 | Function is missing a return type annotation |
| mypy | tests/unit/test_factories.py:320 | Function is missing a type annotation |
| mypy | tests/unit/test_factories.py:332 | Function is missing a type annotation |
| mypy | tests/unit/test_factories.py:341 | Function is missing a type annotation |
| mypy | tests/unit/test_factories.py:349 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:13 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:18 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:23 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:32 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:37 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:44 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:51 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:63 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:71 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:77 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:83 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:90 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:98 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:111 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:122 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:131 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:140 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:152 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:162 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:171 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:182 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:190 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:199 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:210 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:220 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:228 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:240 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:249 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:262 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:270 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:283 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:292 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:305 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:311 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:317 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:329 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:335 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:343 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:350 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:361 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:378 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:392 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:412 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:424 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:446 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:496 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:532 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:541 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:549 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:558 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:566 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:575 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:588 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:595 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_text_preparer.py:602 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:15 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:38 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:48 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:55 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:64 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:79 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:100 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:105 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:128 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:139 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:150 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:159 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:169 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:183 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:200 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:217 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:223 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:238 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:325 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:330 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:344 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:363 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:380 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:400 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:420 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:440 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:460 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:477 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:501 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown.py:554 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:16 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:22 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:27 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:33 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:38 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:44 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:54 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:61 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:74 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:84 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:99 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:114 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:132 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:148 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:161 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:178 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:193 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:213 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:220 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:230 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:240 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:250 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:263 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:273 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:278 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:283 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:288 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:293 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:310 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:318 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:335 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:359 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:372 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:396 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:408 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:420 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:432 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:447 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:460 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:478 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:494 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_text_chunker.py:501 | Function is missing a return type annotation |
| mypy | tests/test_cli/test_profile_migrate.py:8 | Library stubs not installed for "yaml" |
| mypy | tests/test_cli/test_profile_migrate.py:385 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_profile_migrate.py:418 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_profile_migrate.py:450 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_profile_commands.py:8 | Library stubs not installed for "yaml" |
| mypy | tests/security/test_storage_traversal.py:18 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:32 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:40 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:48 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:16 | Function is missing a return type annotation |
| mypy | tests/security/test_path_traversal.py:25 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:36 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:44 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:52 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:43 | Function is missing a return type annotation |
| mypy | tests/integration/test_local_supabase.py:78 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:97 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:105 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:115 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:125 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:136 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:180 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:202 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:213 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:222 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:240 | Function is missing a type annotation |
| mypy | tests/integration/test_local_supabase.py:250 | Function is missing a type annotation |
| mypy | tests/api/test_settings_rendering.py:6 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:21 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:38 | Function is missing a return type annotation |
| mypy | tests/test_queue/test_setup.py:21 | Function is missing a return type annotation |
| mypy | tests/test_queue/test_setup.py:49 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:60 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:76 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:83 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:97 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:110 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:124 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:134 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:142 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:152 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:163 | Function is missing a type annotation |
| mypy | tests/test_queue/test_setup.py:173 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:36 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:75 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:86 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:107 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:120 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:133 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:148 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:166 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:182 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:198 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:214 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:236 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:246 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:270 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:293 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:314 | Function is missing a return type annotation |
| mypy | tests/api/test_chat_api.py:317 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:333 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:343 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:353 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:363 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:376 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:413 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:433 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:34 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:46 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:66 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:114 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:142 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:166 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:200 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:235 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:265 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:15 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:19 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:23 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:27 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:31 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:36 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:40 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:45 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:49 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:55 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:84 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:89 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:102 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:122 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:137 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:149 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_youtube_parser.py:162 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:13 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:17 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:21 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:30 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:34 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:40 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:44 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:49 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:54 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:60 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:66 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:71 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:81 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:91 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:101 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:111 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:120 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:134 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:147 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:160 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_markitdown_parser.py:172 | Function is missing a type annotation |
| mypy | tests/security/test_global_error_handler.py:15 | Function is missing a type annotation |
| mypy | tests/security/test_global_error_handler.py:26 | Function is missing a return type annotation |
| mypy | tests/security/test_global_error_handler.py:37 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:27 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:35 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:46 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:71 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:88 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:108 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:126 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:148 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:164 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:177 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:189 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:200 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:217 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:253 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:269 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:289 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:307 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:325 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:337 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:347 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:361 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:398 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:429 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:440 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:469 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:480 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:495 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:522 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:553 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:560 | Function is missing a type annotation |
| mypy | tests/test_services/test_url_extractor.py:583 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:599 | Function is missing a return type annotation |
| mypy | tests/test_services/test_url_extractor.py:607 | Function is missing a type annotation |
| mypy | tests/security/test_ssrf_protection.py:11 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:24 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:36 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:48 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:60 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:68 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:18 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:28 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:61 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:80 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:104 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:114 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:121 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:135 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:154 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:172 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:190 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:214 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:242 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:261 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:278 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:300 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:316 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:331 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:346 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:361 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:369 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:387 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:398 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:419 | Function is missing a return type annotation |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "float | Timeout | NotGiven | None" |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "int" |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "Mapping[str, str] | None" |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "Mapping[str, object] | None" |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "Client | None" |
| mypy | src/agents/claude/summarizer.py:80 | Argument 1 to "AnthropicBedrock" has incompatible type "**dict[str, str]"; expected "bool" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "Credentials | None" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "float | Timeout | NotGiven | None" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "int" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "Mapping[str, str] | None" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "Mapping[str, object] | None" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "Client | None" |
| mypy | src/agents/claude/summarizer.py:92 | Argument 1 to "AnthropicVertex" has incompatible type "**dict[str, str]"; expected "bool" |
| mypy | tests/test_ingestion/test_podcast.py:21 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:39 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:45 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:55 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:117 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:144 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:163 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:185 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:195 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:206 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:219 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:246 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:265 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:275 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:315 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:356 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:392 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:427 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:482 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:501 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:517 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:560 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:578 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:595 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:626 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:638 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:44 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:50 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:55 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:67 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:78 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:90 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:96 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:111 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:117 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:125 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:129 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:138 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:146 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:155 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:165 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:178 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:188 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:196 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:206 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:212 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:225 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:238 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:251 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:266 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:283 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:300 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:317 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:331 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:346 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:357 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:379 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:401 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:416 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:434 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:448 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:462 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:481 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:500 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:519 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:532 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:551 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:574 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:596 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:612 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:634 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:650 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:662 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:676 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:701 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:719 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:732 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:750 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:767 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:788 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:804 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:822 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:833 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:847 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:857 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:866 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:875 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:884 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:900 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:917 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:923 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:928 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:935 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:940 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:948 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:957 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:982 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:991 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:1012 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:1049 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:1078 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:1088 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:1101 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:1113 | Function is missing a return type annotation |
| mypy | tests/test_services/test_file_storage.py:1119 | Function is missing a type annotation |
| mypy | tests/test_services/test_file_storage.py:1132 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:14 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:19 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:24 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:29 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:39 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:47 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:58 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:66 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:74 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:97 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:103 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:111 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:118 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:134 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:143 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:168 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:175 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:196 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:201 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:209 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:226 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:235 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:247 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:252 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:274 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:288 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:293 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:304 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:319 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:330 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:341 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:352 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:365 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:374 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:384 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:388 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:407 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:411 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:422 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:435 | Function is missing a return type annotation |
| mypy | tests/test_delivery/test_tts_service.py:439 | Function is missing a type annotation |
| mypy | tests/test_delivery/test_tts_service.py:449 | Function is missing a type annotation |
| mypy | tests/integration/test_supabase_provider.py:37 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:43 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:50 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:55 | Unsupported right operand type for in ("Any | None") |
| mypy | tests/integration/test_supabase_provider.py:56 | Value of type "Any | None" is not indexable |
| mypy | tests/integration/test_supabase_provider.py:58 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:58 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_supabase_provider.py:62 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:79 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:85 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:92 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:114 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:148 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:158 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:170 | Incompatible return value type (got "tuple[Any | None, float]", expected "tuple[int, float]") |
| mypy | tests/integration/test_supabase_provider.py:188 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:195 | Incompatible return value type (got "Any | None", expected "int") |
| mypy | tests/integration/test_supabase_provider.py:208 | Function is missing a return type annotation |
| mypy | tests/integration/test_supabase_provider.py:254 | Function is missing a type annotation |
| mypy | tests/integration/test_supabase_provider.py:258 | Function is missing a type annotation |
| mypy | tests/integration/test_supabase_provider.py:265 | Function is missing a type annotation |
| mypy | tests/integration/test_supabase_provider.py:273 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:42 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:78 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:102 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:123 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:151 | Function is missing a return type annotation |
| mypy | tests/integration/test_opik_integration.py:168 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:183 | Function is missing a return type annotation |
| mypy | tests/integration/test_opik_integration.py:195 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:215 | Function is missing a type annotation |
| mypy | tests/api/test_script_error_leakage.py:11 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:14 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:39 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:51 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:61 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:74 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:96 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:119 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:134 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:152 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:171 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:195 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:224 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:250 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:272 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:297 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:319 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:339 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:362 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:382 | Function is missing a type annotation |
| mypy | tests/test_services/test_review_service.py:407 | Function is missing a return type annotation |
| mypy | tests/test_services/test_review_service.py:430 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:24 | Function is missing a return type annotation |
| mypy | tests/integration/test_review_workflow.py:49 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:170 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:209 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:310 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:353 | Function is missing a type annotation |
| mypy | tests/integration/test_review_workflow.py:391 | Function is missing a type annotation |
| mypy | scripts/review_digest.py:37 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:38 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:40 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:72 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:73 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:81 | Item "None" of "datetime | None" has no attribute "strftime" |
| mypy | scripts/review_digest.py:90 | Argument 1 to "to_markdown" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:92 | Argument 1 to "to_html" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:94 | Argument 1 to "to_plain_text" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:131 | Need type annotation for "session" |
| mypy | scripts/review_digest.py:145 | Argument 1 to "to_markdown" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:179 | Argument 1 to "to_markdown" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:259 | Item "str" of "list[Any] | str | None" has no attribute "append" |
| mypy | scripts/review_digest.py:259 | Item "None" of "list[Any] | str | None" has no attribute "append" |
| mypy | scripts/review_digest.py:283 | Argument 1 to "to_markdown" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | scripts/review_digest.py:375 | Function is missing a return type annotation |
| mypy | tests/test_agents/test_claude_agent.py:83 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:94 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:106 | Function is missing a return type annotation |
| mypy | tests/test_agents/test_claude_agent.py:115 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:131 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:157 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:191 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:213 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:232 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:245 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:255 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:271 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:287 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:306 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:316 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_gmail.py:13 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:22 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:31 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_gmail.py:38 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:54 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:72 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:101 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:133 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_gmail.py:154 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_gmail.py:171 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_gmail.py:204 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_gmail.py:230 | Function is missing a return type annotation |
| mypy | src/ingestion/substack.py:16 | Library stubs not installed for "yaml" |
| mypy | src/ingestion/substack.py:17 | Library stubs not installed for "dateutil.parser" |
| mypy | src/delivery/email.py:18 | Function is missing a return type annotation |
| mypy | src/delivery/email.py:43 | Argument 1 to "to_html" of "DigestFormatter" has incompatible type "Digest"; expected "DigestData" |
| mypy | src/delivery/email.py:49 | Incompatible types in assignment (expression has type "str | None", target has type "str") |
| mypy | scripts/ingest_gmail.py:6 | Module "src.ingestion.gmail" has no attribute "GmailIngestionService"; maybe "GmailContentIngestionService"? |
| mypy | tests/scripts/test_switch_embeddings.py:20 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:57 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:92 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:112 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:32 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:60 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:76 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_html_processor.py:98 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:125 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:142 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:151 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:164 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:174 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:192 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:202 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:207 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:215 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:232 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:269 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:283 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:289 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:357 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:396 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:433 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:464 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:19 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:35 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:48 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:62 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:77 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:84 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:87 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:90 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:114 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:138 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:183 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:213 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:229 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:265 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:306 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:311 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:314 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:317 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:343 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:395 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:442 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:483 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:488 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:491 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:494 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:518 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:563 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:587 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:608 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:638 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:668 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:673 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:676 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:679 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:703 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:23 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_audio_digest_flow.py:107 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:154 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:191 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:214 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:261 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:318 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:334 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:374 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:435 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:465 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:510 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:527 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:559 | Function is missing a return type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:569 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_audio_digest_flow.py:594 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:622 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:657 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:678 | Function is missing a type annotation |
| mypy | tests/integration/test_audio_digest_flow.py:704 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:15 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:25 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:29 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:40 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:44 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:51 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:55 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:62 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:69 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:74 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:80 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:85 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:92 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:102 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:112 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:123 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:128 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:132 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:138 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:144 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:149 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:159 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:178 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:190 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:197 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:213 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:227 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:249 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_docling_parser.py:262 | Function is missing a type annotation |
| mypy | tests/services/test_embedding_providers.py:25 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:32 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:61 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:78 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:102 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:121 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:146 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:156 | Function is missing a type annotation |
| mypy | tests/services/test_embedding_providers.py:166 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:173 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:185 | Function is missing a type annotation |
| mypy | tests/services/test_embedding_providers.py:217 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:236 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:254 | Function is missing a return type annotation |
| mypy | tests/services/test_embedding_providers.py:279 | Function is missing a type annotation |
| mypy | tests/services/test_embedding_providers.py:298 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:21 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:24 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:36 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:39 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:66 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:92 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:127 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:149 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:164 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:185 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:204 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:227 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:245 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:264 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss_sources.py:280 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:13 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss.py:19 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss.py:37 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss.py:69 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:94 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:129 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:149 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:155 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:168 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:182 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:190 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:195 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_rss.py:207 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:216 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_rss.py:230 | Function is missing a type annotation |
| mypy | scripts/ingest_rss.py:6 | Module "src.ingestion.rss" has no attribute "RSSIngestionService"; maybe "RSSContentIngestionService"? |
| mypy | tests/test_telemetry/test_metrics.py:17 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:20 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:33 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:43 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:46 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:91 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:109 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:12 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:30 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:41 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:56 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:66 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:75 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:85 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:97 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:109 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:130 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:149 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:167 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:181 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:195 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:204 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:15 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:25 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:44 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:60 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:76 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_factory.py:88 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:95 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:103 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:111 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:123 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:128 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:142 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:148 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:154 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:159 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:168 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:185 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:199 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_factory.py:217 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:73 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:78 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:86 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:95 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:103 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:127 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:139 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:168 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:193 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:217 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:237 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:255 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:301 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:339 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:444 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:500 | Function is missing a return type annotation |
| mypy | tests/integration/test_neon_integration.py:514 | Function is missing a return type annotation |
| mypy | tests/integration/conftest.py:75 | Function is missing a return type annotation |
| mypy | tests/integration/conftest.py:98 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/conftest.py:126 | Function is missing a type annotation |
| mypy | tests/integration/conftest.py:135 | Function is missing a return type annotation |
| mypy | tests/integration/conftest.py:143 | Function is missing a return type annotation |
| mypy | tests/integration/conftest.py:187 | Function is missing a type annotation |
| mypy | tests/integration/conftest.py:211 | Function is missing a type annotation |
| mypy | tests/integration/conftest.py:251 | Function is missing a type annotation |
| mypy | tests/integration/conftest.py:312 | Function is missing a return type annotation |
| mypy | tests/integration/conftest.py:354 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:23 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:73 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:80 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:100 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:130 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:163 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_summarizer.py:175 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:205 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:234 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:251 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:268 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:285 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:302 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:308 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:311 | Function is missing a type annotation |
| mypy | tests/test_processors/test_summarizer.py:337 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:21 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:68 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:79 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:104 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:131 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:161 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_workflow.py:186 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:26 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_summarization_flow_functional.py:47 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_summarization_flow_functional.py:60 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:132 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:204 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:295 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:361 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:404 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:436 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:13 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:51 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:79 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:105 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:135 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_video.py:14 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_video.py:24 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:35 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:70 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:105 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:18 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:23 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:30 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:35 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:40 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:45 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:50 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:55 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:60 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:65 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:71 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:76 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:84 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:110 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:117 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:123 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:128 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:132 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:136 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:140 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:144 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:148 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security.py:159 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:174 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:212 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:223 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:234 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:261 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:293 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security.py:304 | Function is missing a type annotation |
| mypy | tests/conftest.py:49 | Function is missing a return type annotation |
| mypy | tests/conftest.py:77 | Function is missing a return type annotation |
| mypy | tests/conftest.py:118 | Function is missing a return type annotation |
| mypy | tests/conftest.py:148 | Function is missing a type annotation |
| mypy | tests/conftest.py:184 | Function is missing a type annotation |
| mypy | tests/conftest.py:193 | Function is missing a type annotation |
| mypy | tests/conftest.py:202 | Function is missing a type annotation |
| mypy | tests/conftest.py:215 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:106 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:204 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:216 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:234 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:241 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:250 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:268 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:283 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:344 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:350 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:361 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:367 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:383 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:398 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:424 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:450 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:478 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:500 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:517 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:533 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:550 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:562 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:573 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:606 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:629 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:638 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:655 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:678 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:706 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:718 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:742 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:751 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:22 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:40 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:53 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:70 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:83 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:94 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:120 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:144 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:168 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:192 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:231 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:256 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:279 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:307 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:345 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:375 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:402 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:420 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:431 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:450 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:482 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:509 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:534 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:560 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:584 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:608 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:22 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:30 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:38 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:42 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:45 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:51 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:63 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:82 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:103 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:121 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:137 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:160 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:183 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:223 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:271 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:301 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:337 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:395 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:418 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:441 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:28 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:31 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:35 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:40 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:45 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:50 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:55 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:59 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:68 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:80 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:86 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:120 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:160 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:182 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_captions.py:188 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:12 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:33 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:48 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:57 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:73 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:92 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:110 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:119 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:139 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_backoff.py:148 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube.py:302 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:312 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:312 | Incompatible types in assignment (expression has type "def mock_ingest_playlist(**kwargs: Any) -> Any", variable has type "def ingest_playlist(self, playlist_id: str, max_videos: int = ..., after_date: datetime | None = ..., force_reprocess: bool = ..., languages: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ..., proofread: bool = ..., hint_terms: list[str] | None = ...) -> Coroutine[Any, Any, int]") |
| mypy | tests/test_ingestion/test_youtube.py:343 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:348 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:348 | Incompatible types in assignment (expression has type "def mock_process(video: Any, playlist_id: Any, **kwargs: Any) -> Any", variable has type "def _process_video(self, video: dict[str, Any], playlist_id: str, force_reprocess: bool = ..., languages: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ..., proofread: bool = ..., hint_terms: list[str] | None = ...) -> Coroutine[Any, Any, bool]") |
| mypy | tests/test_ingestion/test_youtube.py:404 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:414 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:414 | Incompatible types in assignment (expression has type "def mock_ingest_feed(**kwargs: Any) -> Any", variable has type "def ingest_feed(self, feed_url: str, max_entries: int = ..., after_date: datetime | None = ..., force_reprocess: bool = ..., source_name: str | None = ..., source_tags: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ...) -> Coroutine[Any, Any, int]") |
| mypy | tests/integration/test_content_ingestion.py:21 | Function is missing a return type annotation |
| mypy | tests/integration/test_content_ingestion.py:82 | Function is missing a return type annotation |
| mypy | tests/integration/test_content_ingestion.py:86 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:95 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:124 | Function is missing a return type annotation |
| mypy | tests/integration/test_content_ingestion.py:180 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:212 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:226 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:250 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:295 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:307 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:317 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:345 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:379 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:391 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:418 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:448 | Function is missing a type annotation |
| mypy | tests/integration/test_content_ingestion.py:501 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:18 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:22 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:26 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:32 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:35 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:43 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:49 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:55 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:61 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:71 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:90 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:102 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:113 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:138 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:148 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:168 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:194 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:217 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:277 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:292 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:306 | Function is missing a type annotation |
| mypy | tests/security/test_search_xss.py:3 | Function is missing a return type annotation |
| mypy | scripts/generate_podcast.py:44 | Function is missing a return type annotation |
| mypy | scripts/generate_podcast.py:81 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/generate_podcast.py:251 | Function is missing a return type annotation |
| mypy | scripts/generate_podcast.py:322 | Unsupported operand types for // ("None" and "int") |
| mypy | scripts/generate_podcast.py:322 | Unsupported operand types for % ("None" and "int") |
| mypy | scripts/generate_podcast.py:324 | Item "str" of "str | None" has no attribute "value" |
| mypy | scripts/generate_podcast.py:324 | Item "None" of "str | None" has no attribute "value" |
| mypy | scripts/generate_podcast.py:337 | Item "None" of "PodcastScriptRecord | None" has no attribute "status" |
| mypy | scripts/generate_podcast.py:383 | Unsupported operand types for // ("None" and "int") |
| mypy | scripts/generate_podcast.py:383 | Unsupported operand types for % ("None" and "int") |
| mypy | scripts/generate_podcast.py:385 | Item "str" of "str | None" has no attribute "value" |
| mypy | scripts/generate_podcast.py:385 | Item "None" of "str | None" has no attribute "value" |
| mypy | scripts/generate_podcast.py:390 | Item "None" of "PodcastSection | None" has no attribute "title" |
| mypy | scripts/generate_podcast.py:393 | Item "None" of "PodcastSection | None" has no attribute "title" |
| mypy | scripts/generate_podcast.py:414 | Item "None" of "PodcastScriptRecord | None" has no attribute "status" |
| mypy | scripts/generate_podcast.py:422 | Argument 2 to "interactive_script_review" has incompatible type "int | None"; expected "int" |
| mypy | scripts/generate_podcast.py:434 | Function is missing a return type annotation |
| mypy | scripts/generate_podcast.py:441 | Argument "script_id" to "generate_audio" of "PodcastCreator" has incompatible type "int | None"; expected "int" |
| mypy | scripts/generate_podcast.py:454 | Unsupported operand types for // ("None" and "int") |
| mypy | scripts/generate_podcast.py:454 | Unsupported operand types for % ("None" and "int") |
| mypy | scripts/generate_podcast.py:456 | Unsupported operand types for / ("None" and "int") |
| mypy | scripts/generate_podcast.py:460 | Argument 1 to "Path" has incompatible type "str | None"; expected "str | PathLike[str]" |
| mypy | tests/api/test_script_security.py:11 | Function is missing a type annotation |
| mypy | tests/api/test_script_security.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_script_security.py:57 | Function is missing a type annotation |
| mypy | tests/api/test_script_security.py:97 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:19 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:28 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:48 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:57 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:69 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:78 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:104 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:125 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:138 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:151 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:185 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:194 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:213 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:222 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:234 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:247 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:257 | Function is missing a type annotation |
| mypy | src/storage/graphiti_client.py:201 | Incompatible return value type (got "list[EntityEdge]", expected "list[dict[str, Any]]") |
| mypy | src/storage/graphiti_client.py:242 | "EntityEdge" has no attribute "get" |
| mypy | src/storage/graphiti_client.py:248 | Incompatible return value type (got "list[EntityEdge]", expected "list[dict[str, Any]]") |
| mypy | src/storage/graphiti_client.py:333 | Incompatible return value type (got "list[EntityEdge]", expected "list[dict[str, Any]]") |
| mypy | src/storage/graphiti_client.py:364 | Incompatible return value type (got "list[EntityEdge]", expected "list[dict[str, Any]]") |
| mypy | src/storage/graphiti_client.py:430 | Unsupported operand types for in ("str" and "EntityEdge") |
| mypy | src/storage/graphiti_client.py:430 | Value of type "EntityEdge" is not indexable |
| mypy | src/storage/graphiti_client.py:438 | Unsupported operand types for + ("list[dict[str, Any]]" and "list[EntityEdge]") |
| mypy | tests/test_storage/test_graphiti_client.py:15 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:37 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:45 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:55 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:64 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:91 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:122 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:138 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:170 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:186 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:214 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:269 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:301 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:308 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:332 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:392 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:442 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:483 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:123 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:134 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:143 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:183 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:211 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:250 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:277 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:293 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:315 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:325 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:359 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:375 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:399 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:427 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:445 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:454 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:476 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:500 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:525 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:550 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:575 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:600 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:20 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:29 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:37 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:59 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:85 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:109 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:132 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:148 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:47 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_processors/test_theme_analyzer.py:49 | Returning Any from function declared to return "list[dict[Any, Any]]" |
| mypy | tests/test_processors/test_theme_analyzer.py:137 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:150 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:163 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:175 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:207 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:227 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:239 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:260 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:280 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:352 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:16 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:20 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:28 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:34 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:40 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:108 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:108 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_theme_analyzer_fetching.py:148 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analyzer_fetching.py:186 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:22 | Function is missing a return type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:67 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:141 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:196 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:228 | Function is missing a type annotation |
| mypy | tests/integration/test_theme_analysis_workflow.py:304 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:34 | Function is missing a return type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:47 | Function is missing a return type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:60 | Function is missing a return type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:73 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:92 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:112 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:143 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:174 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:228 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:259 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:274 | Function is missing a type annotation |
| mypy | tests/integration/test_e2e_model_combinations.py:284 | Function is missing a return type annotation |
| mypy | scripts/analyze_themes.py:19 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/analyze_themes.py:130 | Argument "processing_time_seconds" to "ThemeAnalysis" has incompatible type "float"; expected "_N | None" |
| mypy | tests/test_scripts/test_digest_generation.py:17 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:87 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_processors/test_digest_creator.py:89 | Returning Any from function declared to return "list[dict[Any, Any]]" |
| mypy | tests/test_processors/test_digest_creator.py:182 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:246 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:286 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:323 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:342 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:354 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:399 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:413 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:433 | Function is missing a return type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:50 | Function is missing a type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:170 | Function is missing a type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:269 | Function is missing a type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:325 | Function is missing a type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:435 | Function is missing a type annotation |
| mypy | tests/integration/test_digest_creation_flow_functional.py:526 | Function is missing a type annotation |
| mypy | scripts/run_pipeline.py:36 | Module "src.ingestion.gmail" has no attribute "GmailIngestionService"; maybe "GmailContentIngestionService"? |
| mypy | scripts/run_pipeline.py:37 | Module "src.ingestion.rss" has no attribute "RSSIngestionService"; maybe "RSSContentIngestionService"? |
| mypy | scripts/run_pipeline.py:51 | Need type annotation for "stats" |
| mypy | scripts/run_pipeline.py:133 | No overload variant of "__add__" of "list" matches argument type "int" |
| mypy | scripts/run_pipeline.py:133 | Unsupported operand types for + ("None" and "int") |
| mypy | scripts/run_pipeline.py:181 | Item "int" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:181 | Item "None" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:199 | Item "int" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:199 | Item "None" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:216 | "ContentSummarizer" has no attribute "summarize_pending_newsletters"; maybe "summarize_pending_contents"? |
| mypy | scripts/run_pipeline.py:218 | Returning Any from function declared to return "int" |
| mypy | scripts/run_pipeline.py:221 | Item "int" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:221 | Item "None" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:281 | Item "int" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:281 | Item "None" of "list[Any] | int | None" has no attribute "append" |
| mypy | scripts/run_pipeline.py:284 | Function is missing a return type annotation |
| mypy | scripts/run_pipeline.py:305 | Function is missing a return type annotation |
| mypy | scripts/generate_weekly_digest.py:19 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/generate_weekly_digest.py:148 | Unsupported operand types for / ("None" and "int") |
| mypy | scripts/generate_daily_digest.py:19 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/generate_daily_digest.py:143 | Unsupported operand types for / ("None" and "int") |
| mypy | tests/cli/test_adapters.py:19 | Function is missing a return type annotation |
| mypy | tests/cli/test_adapters.py:20 | Function is missing a return type annotation |
| mypy | tests/cli/test_adapters.py:26 | Function is missing a return type annotation |
| mypy | tests/cli/test_adapters.py:27 | Function is missing a return type annotation |
| mypy | tests/cli/test_adapters.py:36 | Function is missing a type annotation |
| mypy | tests/cli/test_adapters.py:47 | Function is missing a type annotation |
| mypy | tests/cli/test_adapters.py:58 | Function is missing a type annotation |
| mypy | tests/cli/test_adapters.py:69 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:14 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:24 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:35 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:52 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:59 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:66 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:73 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:80 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:92 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:104 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:116 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:127 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_setup.py:139 | Function is missing a return type annotation |
| mypy | tests/security/test_upload_error_leakage.py:17 | Function is missing a type annotation |
| mypy | tests/security/test_upload_error_leakage.py:35 | Function is missing a return type annotation |
| mypy | tests/security/test_upload_error_leakage.py:43 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:11 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:37 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:64 | Function is missing a type annotation |
| mypy | tests/security/test_search_auth.py:13 | Function is missing a type annotation |
| mypy | tests/security/test_search_auth.py:34 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:42 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:54 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:103 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:111 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:123 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:132 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:140 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:162 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:177 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:186 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:195 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:214 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:223 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:231 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:239 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:245 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:262 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:268 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:274 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:280 | Function is missing a return type annotation |
| mypy | tests/security/test_owner_auth.py:294 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:299 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:304 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:311 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:316 | Function is missing a type annotation |
| mypy | tests/security/test_owner_auth.py:328 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:47 | Function is missing a return type annotation |
| mypy | tests/security/test_error_sanitization.py:59 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:106 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:113 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:123 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:133 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:143 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:154 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:170 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:196 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:209 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:224 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:240 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:254 | Function is missing a type annotation |
| mypy | tests/security/test_digest_auth.py:11 | Function is missing a type annotation |
| mypy | tests/security/test_digest_auth.py:29 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:80 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:93 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/conftest.py:109 | Function is missing a return type annotation |
| mypy | tests/contract/conftest.py:154 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/contract/conftest.py:154 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/conftest.py:202 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:290 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:303 | Function is missing a return type annotation |
| mypy | tests/contract/conftest.py:314 | Function is missing a type annotation |
| mypy | tests/api/test_upload_security_regression.py:10 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_security_regression.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_upload_auth.py:11 | Function is missing a type annotation |
| mypy | tests/api/test_upload_auth.py:21 | Function is missing a return type annotation |
| mypy | tests/api/test_upload_auth.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_upload_auth.py:74 | Function is missing a type annotation |
| mypy | tests/api/test_upload_auth.py:88 | Function is missing a type annotation |
| mypy | tests/api/test_settings_security.py:16 | Function is missing a type annotation |
| mypy | tests/api/test_settings_security.py:20 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_security.py:28 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:32 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_override_api.py:45 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:55 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:63 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:68 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:86 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:123 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:132 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:146 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:150 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:159 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:182 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:193 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:200 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:211 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:224 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:228 | Function is missing a type annotation |
| mypy | tests/api/test_script_auth.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_script_auth.py:16 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:30 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:47 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:56 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:83 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:106 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:116 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:138 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:149 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:171 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:192 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:24 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:48 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:67 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:85 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:94 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:112 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:121 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:154 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:168 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:181 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:195 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:236 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:253 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:271 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:285 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:311 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:326 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:347 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:368 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:397 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:412 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:437 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:466 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:485 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:501 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:519 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:528 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:550 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:565 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:588 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:17 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:48 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:65 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:100 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:120 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:134 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:148 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:174 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:190 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:214 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:239 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:263 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:21 | Function is missing a return type annotation |
| mypy | tests/api/test_files_api.py:27 | Function is missing a return type annotation |
| mypy | tests/api/test_files_api.py:36 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:44 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:98 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:124 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:145 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:165 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:193 | Function is missing a type annotation |
| mypy | tests/api/test_content_security.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_content_security.py:28 | Function is missing a return type annotation |
| mypy | tests/api/test_content_security.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:39 | Function is missing a return type annotation |
| mypy | tests/api/test_auth_routes.py:51 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:79 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:101 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:121 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:176 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:185 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:193 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:198 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:207 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:215 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:221 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:227 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:233 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:244 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:261 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:273 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:287 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:297 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:304 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:313 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:319 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:334 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:340 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:346 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:352 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:47 | Function is missing a return type annotation |
| mypy | tests/api/test_auth_middleware.py:59 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:151 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:162 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:177 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:185 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:195 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:203 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:227 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:240 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:248 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:273 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:297 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:324 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:339 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:355 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:49 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:68 | Function is missing a return type annotation |
| mypy | tests/api/conftest.py:90 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:129 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:137 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:141 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:145 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:149 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:153 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:157 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:161 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:167 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:178 | Function is missing a return type annotation |
| mypy | tests/api/conftest.py:212 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:241 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:276 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:321 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:360 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:405 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:435 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:453 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:497 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:38 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:46 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:52 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:58 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:64 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:70 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:76 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:82 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:97 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:103 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:109 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:115 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:124 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:133 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:143 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:161 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:191 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:202 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:223 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:247 | Function is missing a return type annotation |
| mypy | tests/cli/test_summarize_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:26 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:36 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:44 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:61 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:79 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:89 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:99 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:106 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:116 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:126 | Function is missing a type annotation |
| mypy | tests/cli/test_summarize_commands.py:148 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:16 | Function is missing a return type annotation |
| mypy | tests/cli/test_settings_commands.py:25 | Function is missing a return type annotation |
| mypy | tests/cli/test_settings_commands.py:35 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:41 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:65 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:77 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:92 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:102 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:120 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:151 | Function is missing a type annotation |
| mypy | tests/cli/test_settings_commands.py:157 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:14 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:43 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:51 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:59 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:69 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:76 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:84 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:95 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:109 | Function is missing a type annotation |
| mypy | tests/cli/test_review_commands.py:129 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:19 | Function is missing a return type annotation |
| mypy | tests/cli/test_prompt_commands.py:29 | Function is missing a return type annotation |
| mypy | tests/cli/test_prompt_commands.py:37 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:41 | Function is missing a return type annotation |
| mypy | tests/cli/test_prompt_commands.py:51 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:59 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:68 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:84 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:91 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:98 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:113 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:122 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:134 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:141 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:162 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:175 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:186 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:197 | Library stubs not installed for "yaml" |
| mypy | tests/cli/test_prompt_commands.py:206 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:216 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:227 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:245 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:252 | Function is missing a type annotation |
| mypy | tests/cli/test_prompt_commands.py:259 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:17 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:30 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:42 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:63 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:76 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:86 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:98 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:122 | Function is missing a type annotation |
| mypy | tests/cli/test_profile_commands.py:145 | Function is missing a return type annotation |
| mypy | tests/cli/test_profile_commands.py:158 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:39 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:61 | Function is missing a return type annotation |
| mypy | tests/cli/test_podcast_commands.py:77 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:86 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:108 | Function is missing a type annotation |
| mypy | tests/cli/test_podcast_commands.py:119 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:47 | Variable "unittest.mock.patch" is not valid as a type |
| mypy | tests/cli/test_pipeline_integration.py:96 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:116 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:138 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:164 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_integration.py:179 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_integration.py:206 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:224 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:251 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_integration.py:273 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_integration.py:291 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_integration.py:322 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_integration.py:359 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_commands.py:18 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_commands.py:53 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_commands.py:81 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_commands.py:88 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_commands.py:92 | Function is missing a return type annotation |
| mypy | tests/cli/test_pipeline_commands.py:107 | Function is missing a type annotation |
| mypy | tests/cli/test_pipeline_commands.py:129 | Function is missing a return type annotation |
| mypy | tests/cli/test_manage_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:24 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:36 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:49 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:58 | Function is missing a return type annotation |
| mypy | tests/cli/test_manage_commands.py:66 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:75 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:90 | Function is missing a type annotation |
| mypy | tests/cli/test_job_commands.py:48 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:64 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:83 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:95 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:111 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:126 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:133 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:148 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:175 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:182 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:196 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:203 | Function is missing a return type annotation |
| mypy | tests/cli/test_job_commands.py:217 | Function is missing a return type annotation |
| mypy | tests/cli/test_ingest_commands.py:20 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:29 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:55 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:63 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:74 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:83 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:91 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:105 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:114 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:123 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:133 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:142 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:156 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:165 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:173 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:184 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:193 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:206 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:214 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:223 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:234 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:243 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:253 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:266 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:272 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:297 | Function is missing a return type annotation |
| mypy | tests/cli/test_ingest_commands.py:305 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:316 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:327 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:357 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:365 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:377 | Function is missing a type annotation |
| mypy | tests/cli/test_ingest_commands.py:387 | Function is missing a return type annotation |
| mypy | tests/cli/test_ingest_commands.py:391 | Function is missing a return type annotation |
| mypy | tests/cli/test_graph_commands.py:18 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:44 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:55 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:74 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:85 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:93 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:101 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:31 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:44 | Function is missing a return type annotation |
| mypy | tests/cli/test_digest_commands.py:49 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:59 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:74 | Function is missing a type annotation |
| mypy | tests/cli/test_digest_commands.py:87 | Function is missing a return type annotation |
| mypy | tests/cli/test_digest_commands.py:92 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:16 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:21 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:28 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:36 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:40 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:47 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:53 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:62 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:74 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:78 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:82 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:86 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:90 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:94 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:98 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:102 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:106 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:110 | Function is missing a return type annotation |
| mypy | tests/cli/test_analyze_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_analyze_commands.py:40 | Function is missing a type annotation |
| mypy | tests/cli/test_analyze_commands.py:59 | Function is missing a return type annotation |
| mypy | tests/cli/test_analyze_commands.py:64 | Function is missing a return type annotation |
| mypy | tests/cli/test_analyze_commands.py:79 | Function is missing a type annotation |
| mypy | tests/cli/test_analyze_commands.py:89 | Function is missing a type annotation |
| mypy | tests/cli/conftest.py:13 | Function is missing a return type annotation |
| mypy | tests/cli/conftest.py:19 | Function is missing a return type annotation |
| mypy | tests/cli/conftest.py:25 | Function is missing a return type annotation |
| mypy | tests/contract/test_schema_conformance.py:31 | Function is missing a type annotation |
| mypy | tests/contract/test_schema_conformance.py:71 | Function is missing a type annotation |
| mypy | tests/contract/test_schema_conformance.py:82 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:48 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:64 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:80 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:93 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:106 | Function is missing a type annotation |
| mypy | tests/cli/test_main.py:13 | Function is missing a return type annotation |
| mypy | tests/cli/test_main.py:29 | Function is missing a return type annotation |
| openspec | N/A | TypeError: fetch failed |
| openspec | N/A | TypeError: fetch failed |
| deferred:open-tasks | N/A | 1.1 Create `src/api/versioning.py` |
| deferred:open-tasks | N/A | 1.2 Define `VersionStatus` enum (ACTIVE, DEPRECATED, SUNSET) |
| deferred:open-tasks | N/A | 1.3 Create `API_VERSIONS` configuration dict |
| deferred:open-tasks | N/A | 1.4 Add helper functions: |
| deferred:open-tasks | N/A | 2.1 Create deprecation middleware in `src/api/versioning.py` |
| deferred:open-tasks | N/A | 2.2 Add `Deprecation` header (RFC 8594) |
| deferred:open-tasks | N/A | 2.3 Add `Sunset` header with date |
| deferred:open-tasks | N/A | 2.4 Add `Link` header with successor URL |
| deferred:open-tasks | N/A | 2.5 Add `X-API-Version` header |
| deferred:open-tasks | N/A | 2.6 Add `X-API-Status` header |
| deferred:open-tasks | N/A | 3.1 Create `src/api/v1/` directory |
| deferred:open-tasks | N/A | 3.2 Create `src/api/v1/__init__.py` with v1 router |
| deferred:open-tasks | N/A | 3.3 Move content routes to `src/api/v1/contents.py` |
| deferred:open-tasks | N/A | 3.4 Move summary routes to `src/api/v1/summaries.py` |
| deferred:open-tasks | N/A | 3.5 Move digest routes to `src/api/v1/digests.py` |
| deferred:open-tasks | N/A | 3.6 Update imports in moved files |
| deferred:open-tasks | N/A | 3.7 Update `src/api/app.py` to mount v1 router |
| deferred:open-tasks | N/A | 4.1 Create sunset handler function |
| deferred:open-tasks | N/A | 4.2 Return 410 Gone status |
| deferred:open-tasks | N/A | 4.3 Include migration guide URL in response |
| deferred:open-tasks | N/A | 4.4 Include successor version in response |
| deferred:open-tasks | N/A | 5.1 Update OpenAPI schema to show version |
| deferred:open-tasks | N/A | 5.2 Add deprecation notices to deprecated endpoints |
| deferred:open-tasks | N/A | 5.3 Configure separate OpenAPI docs per version (optional) |
| deferred:open-tasks | N/A | 5.4 Add version info to API description |
| deferred:open-tasks | N/A | 6.1 Add version extraction from request path |
| deferred:open-tasks | N/A | 6.2 Add version to request state for logging |
| deferred:open-tasks | N/A | 6.3 Include version in observability spans (if enabled) |
| deferred:open-tasks | N/A | 7.1 Test deprecation headers are present |
| deferred:open-tasks | N/A | 7.2 Test sunset behavior returns 410 |
| deferred:open-tasks | N/A | 7.3 Test version detection |
| deferred:open-tasks | N/A | 7.4 Verify existing endpoints work after reorganization |
| deferred:open-tasks | N/A | 8.1 Create `docs/api/versioning.md` |
| deferred:open-tasks | N/A | 8.2 Document version lifecycle |
| deferred:open-tasks | N/A | 8.3 Document when to create new versions |
| deferred:open-tasks | N/A | 8.4 Create migration guide template |
| deferred:open-tasks | N/A | 8.5 Update API documentation with version info |
| deferred:open-tasks | N/A | 9.1 Create `src/api/v2/` directory |
| deferred:open-tasks | N/A | 9.2 Implement changed endpoints |
| deferred:open-tasks | N/A | 9.3 Update `API_VERSIONS` to deprecate v1 |
| deferred:open-tasks | N/A | 9.4 Create migration guide |
| deferred:open-tasks | N/A | 9.5 Announce deprecation timeline |
| deferred:open-tasks | N/A | 1.1 Install `@capacitor/core`, `@capacitor/cli` in `web/` |
| deferred:open-tasks | N/A | 1.2 Run `npx cap init` with app ID and name, configure `capacitor.config.ts` |
| deferred:open-tasks | N/A | 1.3 Add iOS platform (`npx cap add ios`) |
| deferred:open-tasks | N/A | 1.4 Add Android platform (`npx cap add android`) — scaffolded only, deployment deferred |
| deferred:open-tasks | N/A | 1.5 Configure `webDir` to point to Vite `dist/` output |
| deferred:open-tasks | N/A | 1.6 Add `ios/` and `android/` to `.gitignore` (or commit — decide convention) |
| deferred:open-tasks | N/A | 2.1 Create `web/src/lib/platform.ts` with `isNative()`, `getPlatform()` utilities |
| deferred:open-tasks | N/A | 2.2 Add `usePlatform` hook for React components that need platform-conditional rendering |
| deferred:open-tasks | N/A | 2.3 Add platform info to telemetry resource attributes |
| deferred:open-tasks | N/A | 3.1 Install `@capacitor/push-notifications`, `@capacitor/haptics`, `@capacitor/status-bar`, `@capacitor/splash-screen` |
| deferred:open-tasks | N/A | 3.2 Install `@capacitor-community/speech-recognition` for native STT |
| deferred:open-tasks | N/A | 3.3 Configure iOS permissions in `Info.plist` (microphone, speech recognition, push notifications) |
| deferred:open-tasks | N/A | 4.1 Create `web/src/lib/push-notifications.ts` with Capacitor Push Notifications plugin wrapper |
| deferred:open-tasks | N/A | 4.2 Implement device token registration via backend API (`POST /api/v1/notifications/devices`) |
| deferred:open-tasks | N/A | 4.3 Handle token refresh (re-register updated token with backend) |
| deferred:open-tasks | N/A | 4.4 Add push notification opt-in toggle to settings UI (native platforms only) |
| deferred:open-tasks | N/A | 4.5 Handle notification tap — navigate to content via event `payload.url` |
| deferred:open-tasks | N/A | 5.1 Create iOS Share Extension target in Xcode project |
| deferred:open-tasks | N/A | 5.3 Implement share handler that extracts URL and calls `save-url` API |
| deferred:open-tasks | N/A | 5.4 Add confirmation toast after successful share save |
| deferred:open-tasks | N/A | 5.5 Add offline queue for shares when device is disconnected |
| deferred:open-tasks | N/A | 6.1 Create `NativeSTTEngine` class implementing the `STTEngine` interface (from `add-on-device-stt`) |
| deferred:open-tasks | N/A | 6.2 Wire `@capacitor-community/speech-recognition` plugin to the engine interface |
| deferred:open-tasks | N/A | 6.3 Update `AutoSTTEngine` to prefer `"native"` when running on Capacitor |
| deferred:open-tasks | N/A | 6.4 Handle native STT permissions (request on first use, handle denial) |
| deferred:open-tasks | N/A | 7.1 Integrate `@capacitor/status-bar` with the existing dark/light theme system |
| deferred:open-tasks | N/A | 7.2 Update status bar style on theme toggle |
| deferred:open-tasks | N/A | 7.3 Configure splash screen with app branding |
| deferred:open-tasks | N/A | 8.1 Create `web/src/lib/haptics.ts` with `triggerHaptic(style)` utility (no-op on web) |
| deferred:open-tasks | N/A | 8.2 Add haptic feedback on voice input toggle |
| deferred:open-tasks | N/A | 8.3 Add haptic feedback on content save confirmation |
| deferred:open-tasks | N/A | 9.1 Add `pnpm cap:dev` script (Vite dev server + live reload) |
| deferred:open-tasks | N/A | 9.2 Add `pnpm cap:build` script (Vite build + cap sync) |
| deferred:open-tasks | N/A | 9.3 Add `pnpm cap:open:ios` script |
| deferred:open-tasks | N/A | 9.4 Document build requirements (Xcode, macOS) in README |
| deferred:open-tasks | N/A | 10.1 Set up Fastlane Match for iOS code signing (private Git repo for profiles + certificates) |
| deferred:open-tasks | N/A | 10.2 Create `ios/fastlane/Fastfile` with `build_app` and `upload_to_testflight` lanes |
| deferred:open-tasks | N/A | 10.3 Create `.github/workflows/ios-build.yml` with macOS runner |
| deferred:open-tasks | N/A | 10.4 Configure CI secrets: Apple Developer credentials, Match passphrase |
| deferred:open-tasks | N/A | 10.5 Implement automatic build versioning — set `CFBundleVersion` from CI run number, `CFBundleShortVersionString` from  |
| deferred:open-tasks | N/A | 10.6 Configure CI trigger on merge to main + manual workflow dispatch |
| deferred:open-tasks | N/A | 10.7 Add TestFlight beta tester group configuration (Apple Developer Console) |
| deferred:open-tasks | N/A | 10.8 Document promotion-to-App-Store steps (manual process) |
| deferred:open-tasks | N/A | 10.9 Add required App Store metadata: privacy policy URL, app description, screenshots, app icon assets |
| deferred:open-tasks | N/A | 11.1 Add E2E tests for platform detection (mock Capacitor context) |
| deferred:open-tasks | N/A | 11.2 Add E2E tests for share target flow (mocked) |
| deferred:open-tasks | N/A | 11.3 Add E2E tests for push notification opt-in flow (mocked) |
| deferred:open-tasks | N/A | 11.4 Manual testing checklist for iOS builds |
| deferred:open-tasks | N/A | 11.5 Verify CI pipeline end-to-end: commit → build → TestFlight upload |
| deferred:open-tasks | N/A | 11.6 Verify build versioning (monotonic build numbers, version from package.json) |
| deferred:open-tasks | N/A | 1.1 Create `src/services/cloud_stt/` package with `CloudSTTProvider` interface (`start_stream`, `send_audio`, `get_resul |
| deferred:open-tasks | N/A | 1.2 Implement `GeminiSTTProvider` (default) — native audio input with built-in cleanup prompt, returns `cleaned: true` |
| deferred:open-tasks | N/A | 1.3 Implement `OpenAIWhisperProvider` — raw transcription, returns `cleaned: false` |
| deferred:open-tasks | N/A | 1.4 Implement `DeepgramProvider` using Deepgram's streaming WebSocket API, returns `cleaned: false` |
| deferred:open-tasks | N/A | 1.5 Create provider factory that resolves adapter from model family: `gemini` → `GeminiSTTProvider`, `whisper` → `Whispe |
| deferred:open-tasks | N/A | 1.6 Define common transcript result model: `{ type: "interim"|"final"|"error", text: str, cleaned: bool, confidence?: fl |
| deferred:open-tasks | N/A | 1.7 Add Gemini transcription+cleanup prompt template (fix grammar, remove filler words, structure text, preserve intent) |
| deferred:open-tasks | N/A | 2.1 Add `CLOUD_STT = "cloud_stt"` to `ModelStep` enum in `src/config/models.py` |
| deferred:open-tasks | N/A | 2.2 Add `supports_audio: bool` field to `ModelInfo` dataclass (analogous to `supports_video`) |
| deferred:open-tasks | N/A | 2.3 Update `load_model_registry()` to parse `supports_audio` from YAML model definitions |
| deferred:open-tasks | N/A | 2.4 Add `supports_audio: true` to Gemini family models (2.0+) in `model_registry.yaml` |
| deferred:open-tasks | N/A | 2.5 Add `supports_audio: false` to Claude, GPT models in `model_registry.yaml` (explicit for clarity) |
| deferred:open-tasks | N/A | 2.6 Add STT-specific model entries to `model_registry.yaml`: `whisper-1` (family: whisper, `supports_audio: true`) and ` |
| deferred:open-tasks | N/A | 2.7 Add `whisper` and `deepgram` to `ModelFamily` enum in `src/config/models.py` |
| deferred:open-tasks | N/A | 2.8 Add `cloud_stt: gemini-2.5-flash` default to `model_registry.yaml` under `default_models` |
| deferred:open-tasks | N/A | 2.9 Add `cloud_stt` parameter to `ModelConfig.__init__()` and wire to `self._models` |
| deferred:open-tasks | N/A | 2.10 Update model settings test step count assertion |
| deferred:open-tasks | N/A | 3.1 Create `src/api/voice_stream_routes.py` with WebSocket endpoint at `/ws/voice/stream` |
| deferred:open-tasks | N/A | 3.2 Implement WebSocket authentication via `X-Admin-Key` query parameter in handshake |
| deferred:open-tasks | N/A | 3.3 Resolve cloud STT provider adapter from `CLOUD_STT` pipeline step model family |
| deferred:open-tasks | N/A | 3.4 Accept binary audio chunks (PCM 16-bit mono 16kHz) and forward to resolved provider |
| deferred:open-tasks | N/A | 3.5 Stream interim/final transcript results back as JSON WebSocket messages (include `cleaned` flag on final results) |
| deferred:open-tasks | N/A | 3.6 Handle provider errors and send error messages to client |
| deferred:open-tasks | N/A | 3.7 Implement clean connection teardown (stop provider stream on WebSocket close) |
| deferred:open-tasks | N/A | 3.8 Register WebSocket route in `src/api/app.py` |
| deferred:open-tasks | N/A | 4.1 Create `CloudSTTEngine` class implementing the `STTEngine` interface |
| deferred:open-tasks | N/A | 4.2 Implement MediaRecorder-based audio capture with AudioContext PCM conversion |
| deferred:open-tasks | N/A | 4.3 Implement WebSocket connection to `/ws/voice/stream` with auth query param |
| deferred:open-tasks | N/A | 4.4 Stream audio chunks at 100-250ms intervals via WebSocket binary messages |
| deferred:open-tasks | N/A | 4.5 Parse incoming JSON messages, emit interim/final transcript events, and propagate `cleaned` flag |
| deferred:open-tasks | N/A | 4.6 Skip automatic `VOICE_CLEANUP` call when `cleaned: true` (Gemini); keep cleanup button available for manual use |
| deferred:open-tasks | N/A | 4.7 Implement WebSocket reconnection with exponential backoff (1s, 2s, 4s, max 3 retries) |
| deferred:open-tasks | N/A | 4.8 Add "Reconnecting..." state to voice input UI during reconnection attempts |
| deferred:open-tasks | N/A | 5.1 Update `AutoSTTEngine` to support configurable preference order (default: cloud → native → browser → on-device) |
| deferred:open-tasks | N/A | 5.2 Add `cloudAvailable` to feature detection (check API key for current CLOUD_STT model's provider via settings API) |
| deferred:open-tasks | N/A | 5.3 Skip unavailable engines in the preference order automatically |
| deferred:open-tasks | N/A | 5.4 Refactor `useVoiceInput` to read engine preference from settings |
| deferred:open-tasks | N/A | 6.1 Extend `voice_settings_routes.py` to include `cloud_stt_language`, `engine_preference_order` (provider/model handled |
| deferred:open-tasks | N/A | 6.2 Add defaults: `cloud_stt_language="auto"`, `engine_preference_order="cloud,native,browser,on-device"` |
| deferred:open-tasks | N/A | 6.3 Add `PUT` endpoints with validation for `cloud_stt_language` and `engine_preference_order` |
| deferred:open-tasks | N/A | 6.4 Add `DELETE` endpoints for reset to defaults |
| deferred:open-tasks | N/A | 6.5 Include `cloud_stt_model` as read-only field in `GET /api/v1/settings/voice` response (referencing current CLOUD_STT |
| deferred:open-tasks | N/A | 6.6 Add cloud STT provider API key status check to connection status API (resolved from CLOUD_STT model family) |
| deferred:open-tasks | N/A | 7.1 Add Cloud STT subsection to `VoiceConfigurator.tsx` (language + engine preference only — model selection is in Model |
| deferred:open-tasks | N/A | 7.2 Show current CLOUD_STT model as a read-only badge linking to Model Configuration dialog |
| deferred:open-tasks | N/A | 7.3 Show API key configuration status for the current model's provider with setup hint if unconfigured |
| deferred:open-tasks | N/A | 7.4 Add language selector (Auto, English US, English UK, Spanish, French, German, Japanese, Chinese) |
| deferred:open-tasks | N/A | 7.5 Add engine preference order list with drag-and-drop reordering |
| deferred:open-tasks | N/A | 7.6 Wire settings to `use-settings.ts` hooks |
| deferred:open-tasks | N/A | 7.7 Add source badges (env/db/default) for cloud STT settings |
| deferred:open-tasks | N/A | 7.8 In Model Configuration dialog, filter CLOUD_STT step selector to only show models with `supports_audio: true` |
| deferred:open-tasks | N/A | 8.1 Add unit tests for cloud STT provider abstraction (mock provider APIs) |
| deferred:open-tasks | N/A | 8.2 Add unit tests for model-family → provider resolution |
| deferred:open-tasks | N/A | 8.3 Add integration tests for WebSocket endpoint (mock provider, verify message flow) |
| deferred:open-tasks | N/A | 8.4 Add unit tests for audio format conversion (PCM 16-bit mono) |
| deferred:open-tasks | N/A | 8.5 Add backend tests for cloud STT settings API endpoints |
| deferred:open-tasks | N/A | 8.6 Add unit tests for `supports_audio` flag parsing in `load_model_registry()` |
| deferred:open-tasks | N/A | 8.7 Add E2E tests for cloud STT settings UI (language, engine preference, model badge link) |
| deferred:open-tasks | N/A | 8.8 Add E2E tests for CLOUD_STT model selector filtering (only `supports_audio: true` models) |
| deferred:open-tasks | N/A | 8.9 Add E2E tests for WebSocket reconnection behavior (mocked) |
| deferred:open-tasks | N/A | 8.10 Update model settings test step count assertion |
| deferred:open-tasks | N/A | 1.1 Add `crawl4ai>=0.7.0` to pyproject.toml as optional dependency |
| deferred:open-tasks | N/A | 1.2 Document `pip install -e ".[crawl4ai]"` installation |
| deferred:open-tasks | N/A | 1.3 Document `crawl4ai-setup` command for browser dependencies |
| deferred:open-tasks | N/A | 1.4 Add verification step using `crawl4ai-doctor` |
| deferred:open-tasks | N/A | 2.1 Add `crawl4ai_enabled: bool = False` to Settings class |
| deferred:open-tasks | N/A | 2.2 Add `crawl4ai_cache_mode: str = "bypass"` setting |
| deferred:open-tasks | N/A | 2.3 Add `crawl4ai_cache_dir: str = "data/crawl4ai_cache"` setting |
| deferred:open-tasks | N/A | 2.4 Update `HtmlMarkdownConverter` to read settings |
| deferred:open-tasks | N/A | 2.5 Update `CRAWL4AI_AVAILABLE` check to include settings flag |
| deferred:open-tasks | N/A | 3.1 Add Crawl4AI service to docker-compose.yml |
| deferred:open-tasks | N/A | 3.2 Add `CRAWL4AI_SERVER_URL` setting for Docker mode |
| deferred:open-tasks | N/A | 3.3 Update converter to support remote Crawl4AI server |
| deferred:open-tasks | N/A | 3.4 Add health check endpoint integration |
| deferred:open-tasks | N/A | 3.5 Document Docker deployment in README or docs |
| deferred:open-tasks | N/A | 4.1 Update `_convert_with_crawl4ai()` to use cache settings |
| deferred:open-tasks | N/A | 4.2 Add support for remote Crawl4AI server (Docker mode) |
| deferred:open-tasks | N/A | 4.3 Add timeout configuration for browser operations |
| deferred:open-tasks | N/A | 4.4 Improve error handling for browser launch failures |
| deferred:open-tasks | N/A | 5.1 Add integration test with JS-heavy page URL |
| deferred:open-tasks | N/A | 5.2 Add test for fallback triggering from Trafilatura to Crawl4AI |
| deferred:open-tasks | N/A | 5.3 Add test for cache mode behavior |
| deferred:open-tasks | N/A | 5.4 Add test for Docker/remote server mode |
| deferred:open-tasks | N/A | 5.5 Mark tests with `@pytest.mark.crawl4ai` for conditional execution |
| deferred:open-tasks | N/A | 6.1 Update ARCHITECTURE.md with Crawl4AI integration diagram |
| deferred:open-tasks | N/A | 6.2 Add Crawl4AI setup section to docs/SETUP.md |
| deferred:open-tasks | N/A | 6.3 Document when Crawl4AI fallback triggers |
| deferred:open-tasks | N/A | 6.4 Add troubleshooting section for browser issues |
| deferred:open-tasks | N/A | 6.5 Update CLAUDE.md with new settings |
| deferred:open-tasks | N/A | 1.1 Create `Dockerfile` with multi-stage build: |
| deferred:open-tasks | N/A | 1.2 Create `.dockerignore`: |
| deferred:open-tasks | N/A | 1.3 Test Docker build locally |
| deferred:open-tasks | N/A | 1.4 Verify image size is reasonable (<500MB) |
| deferred:open-tasks | N/A | 2.1 Create `.github/workflows/ci.yml` |
| deferred:open-tasks | N/A | 2.2 Add lint job (ruff check) |
| deferred:open-tasks | N/A | 2.3 Add typecheck job (mypy) |
| deferred:open-tasks | N/A | 2.4 Add test job with service containers: |
| deferred:open-tasks | N/A | 2.5 Add Docker build verification job |
| deferred:open-tasks | N/A | 2.6 Configure job parallelization |
| deferred:open-tasks | N/A | 2.7 Add coverage reporting (codecov or similar) |
| deferred:open-tasks | N/A | 2.8 Add PR comment with test results |
| deferred:open-tasks | N/A | 3.1 Create `.github/workflows/deploy.yml` |
| deferred:open-tasks | N/A | 3.2 Add Docker build and push job: |
| deferred:open-tasks | N/A | 3.3 Add staging migration job |
| deferred:open-tasks | N/A | 3.4 Add staging deployment job |
| deferred:open-tasks | N/A | 3.5 Add production migration job (manual approval) |
| deferred:open-tasks | N/A | 3.6 Add production deployment job |
| deferred:open-tasks | N/A | 4.1 Create GitHub Environment: `staging` |
| deferred:open-tasks | N/A | 4.2 Create GitHub Environment: `production` |
| deferred:open-tasks | N/A | 4.3 Configure production approval requirement |
| deferred:open-tasks | N/A | 4.4 Add environment secrets: |
| deferred:open-tasks | N/A | 4.5 Document secrets in README |
| deferred:open-tasks | N/A | 5.1 Update `docker-compose.yml` for local dev parity |
| deferred:open-tasks | N/A | 5.2 Create `docker-compose.prod.yml` for production |
| deferred:open-tasks | N/A | 5.3 Add Opik service to docker-compose.yml |
| deferred:open-tasks | N/A | 5.4 Add healthcheck configurations |
| deferred:open-tasks | N/A | 5.5 Document compose file differences |
| deferred:open-tasks | N/A | 6.1 Create `scripts/deploy.sh` for server-side deployment |
| deferred:open-tasks | N/A | 6.2 Add graceful shutdown handling |
| deferred:open-tasks | N/A | 6.3 Add rollback script |
| deferred:open-tasks | N/A | 6.4 Document deployment process |
| deferred:open-tasks | N/A | 7.1 Create `.github/dependabot.yml` |
| deferred:open-tasks | N/A | 7.2 Configure Python dependency updates |
| deferred:open-tasks | N/A | 7.3 Configure GitHub Actions updates |
| deferred:open-tasks | N/A | 7.4 Configure Docker base image updates |
| deferred:open-tasks | N/A | 8.1 Enable branch protection on main |
| deferred:open-tasks | N/A | 8.2 Require CI to pass before merge |
| deferred:open-tasks | N/A | 8.3 Require review approval |
| deferred:open-tasks | N/A | 8.4 Create CODEOWNERS file |
| deferred:open-tasks | N/A | 9.1 Test CI workflow on feature branch |
| deferred:open-tasks | N/A | 9.2 Test Docker build in CI |
| deferred:open-tasks | N/A | 9.3 Test deployment to staging |
| deferred:open-tasks | N/A | 9.4 Verify rollback procedure |
| deferred:open-tasks | N/A | 10.1 Document CI/CD pipeline in docs/ |
| deferred:open-tasks | N/A | 10.2 Document environment setup |
| deferred:open-tasks | N/A | 10.3 Document deployment procedure |
| deferred:open-tasks | N/A | 10.4 Document rollback procedure |
| deferred:open-tasks | N/A | 10.5 Add badges to README (CI status, coverage) |
| deferred:open-tasks | N/A | 1.1 Add `xai-sdk>=1.3.1` to project dependencies (pyproject.toml) |
| deferred:open-tasks | N/A | 1.2 Add configuration settings to `src/config/settings.py`: |
| deferred:open-tasks | N/A | 1.3 Document environment variables in `.env.example` |
| deferred:open-tasks | N/A | 2.1 Add `XSEARCH = "xsearch"` to `ContentSource` enum in `src/models/content.py` |
| deferred:open-tasks | N/A | 2.2 Create Alembic migration to add `xsearch` value to `content_source` enum type in PostgreSQL: |
| deferred:open-tasks | N/A | 2.3 Run migration and verify enum update |
| deferred:open-tasks | N/A | 3.1 Create `src/ingestion/xsearch.py` module |
| deferred:open-tasks | N/A | 3.2 Implement `GrokXClient` class: |
| deferred:open-tasks | N/A | 3.3 Implement `XThreadData` Pydantic model for parsed thread data: |
| deferred:open-tasks | N/A | 3.4 Implement streaming response handling with tool call logging |
| deferred:open-tasks | N/A | 3.5 Add error handling for API failures, rate limits, authentication errors |
| deferred:open-tasks | N/A | 3.6 Add retry logic with exponential backoff |
| deferred:open-tasks | N/A | 3.7 Implement thread fetching: when a post is discovered, fetch its complete thread |
| deferred:open-tasks | N/A | 4.1 Implement `GrokXContentIngestionService` class: |
| deferred:open-tasks | N/A | 4.2 Implement thread-to-ContentData conversion with markdown formatting: |
| deferred:open-tasks | N/A | 4.3 Implement thread-aware deduplication: |
| deferred:open-tasks | N/A | 4.4 Add cost tracking in metadata_json (tool calls made, estimated cost) |
| deferred:open-tasks | N/A | 5.1 Create `src/ingestion/xsearch.py` `__main__` block for CLI usage: |
| deferred:open-tasks | N/A | 5.2 Add argument parsing with argparse |
| deferred:open-tasks | N/A | 5.3 Add progress output and summary statistics |
| deferred:open-tasks | N/A | 6.1 Create `tests/test_ingestion/test_xsearch.py` |
| deferred:open-tasks | N/A | 6.2 Write unit tests for `XThreadData` model validation |
| deferred:open-tasks | N/A | 6.3 Write unit tests for thread markdown content generation (numbered sections) |
| deferred:open-tasks | N/A | 6.4 Write unit tests for thread-aware deduplication: |
| deferred:open-tasks | N/A | 6.5 Write integration tests with mocked xAI SDK responses |
| deferred:open-tasks | N/A | 6.6 Add test fixtures for sample thread data (single post, multi-post threads) |
| deferred:open-tasks | N/A | 7.1 Update `docs/ARCHITECTURE.md` with X search ingestion section |
| deferred:open-tasks | N/A | 7.2 Add X search to ingestion services table |
| deferred:open-tasks | N/A | 7.3 Update `CLAUDE.md` with X search commands |
| deferred:open-tasks | N/A | 7.4 Document prompt templates and best practices |
| deferred:open-tasks | N/A | 8.1 Run end-to-end test with real Grok API (manual, requires API key) |
| deferred:open-tasks | N/A | 8.2 Verify posts appear in Content table with correct structure |
| deferred:open-tasks | N/A | 8.3 Verify posts flow through summarization pipeline |
| deferred:open-tasks | N/A | 8.4 Verify posts appear in digest output |
| deferred:open-tasks | N/A | 1.1 Create `src/services/image_generator.py`: |
| deferred:open-tasks | N/A | 1.2 Implement `generate_for_summary(summary, prompt) -> Image`: |
| deferred:open-tasks | N/A | 1.3 Implement `generate_for_digest(digest, prompt) -> Image`: |
| deferred:open-tasks | N/A | 1.4 Implement `suggest_images(content: str) -> list[ImageSuggestion]`: |
| deferred:open-tasks | N/A | 2.1 Add settings to `src/config/settings.py`: |
| deferred:open-tasks | N/A | 2.2 Add credentials to environment: |
| deferred:open-tasks | N/A | 3.1 Create `ImageSuggestion` schema: |
| deferred:open-tasks | N/A | 3.2 Create `ImageGenerationRequest` schema: |
| deferred:open-tasks | N/A | 3.3 Create `ImageGenerationResponse` schema: |
| deferred:open-tasks | N/A | 4.1 Create `src/api/image_generation_routes.py`: |
| deferred:open-tasks | N/A | 4.2 Add rate limiting for generation endpoints |
| deferred:open-tasks | N/A | 4.3 Register routes in `src/api/app.py` |
| deferred:open-tasks | N/A | 5.1 Update `src/services/review_service.py`: |
| deferred:open-tasks | N/A | 5.2 Update Summary/Digest review UI (future): |
| deferred:open-tasks | N/A | 6.1 Unit tests for ImageGenerator: |
| deferred:open-tasks | N/A | 6.2 Unit tests for suggestion generation: |
| deferred:open-tasks | N/A | 6.3 API endpoint tests: |
| deferred:open-tasks | N/A | 7.1 Document configuration options in SETUP.md |
| deferred:open-tasks | N/A | 7.2 Document API endpoints in ARCHITECTURE.md |
| deferred:open-tasks | N/A | 7.3 Create usage guide for image generation feature |
| deferred:open-tasks | N/A | 1.1 Create `src/api/save_routes.py` with router |
| deferred:open-tasks | N/A | 1.2 Implement `POST /api/v1/content/save-url` endpoint |
| deferred:open-tasks | N/A | 1.3 Add URL validation (valid URL format, https preferred) |
| deferred:open-tasks | N/A | 1.4 Add duplicate detection by source_url |
| deferred:open-tasks | N/A | 1.5 Implement `GET /api/v1/content/{id}/status` endpoint |
| deferred:open-tasks | N/A | 1.6 Configure CORS for mobile clients (allow all origins for API key auth) |
| deferred:open-tasks | N/A | 1.7 Register router in `src/api/app.py` |
| deferred:open-tasks | N/A | 2.1 Create `src/api/auth/api_keys.py` module |
| deferred:open-tasks | N/A | 2.2 Create APIKey model (id, hashed_key, name, rate_limit, created_at) |
| deferred:open-tasks | N/A | 2.3 Implement `verify_api_key()` dependency |
| deferred:open-tasks | N/A | 2.4 Add rate limiting per API key (60 req/min default) |
| deferred:open-tasks | N/A | 2.5 Create Alembic migration for api_keys table |
| deferred:open-tasks | N/A | 2.6 Add API key management CLI commands |
| deferred:open-tasks | N/A | 3.1 Create `src/services/url_extractor.py` |
| deferred:open-tasks | N/A | 3.2 Integrate with existing `ParserRouter` for HTML parsing |
| deferred:open-tasks | N/A | 3.3 Add fallback extraction (title, meta description) if parsing fails |
| deferred:open-tasks | N/A | 3.4 Implement async extraction as background task |
| deferred:open-tasks | N/A | 3.5 Add timeout handling (30s max per URL) |
| deferred:open-tasks | N/A | 3.6 Handle common errors (404, timeout, blocked) |
| deferred:open-tasks | N/A | 4.1 Create `GET /save` endpoint in save_routes.py |
| deferred:open-tasks | N/A | 4.2 Create `src/templates/save.html` (mobile-optimized) |
| deferred:open-tasks | N/A | 4.3 Pre-fill form from URL query parameters |
| deferred:open-tasks | N/A | 4.4 Add JavaScript for async form submission |
| deferred:open-tasks | N/A | 4.5 Show success/error states with clear messaging |
| deferred:open-tasks | N/A | 4.6 Add responsive design (works on phone and desktop) |
| deferred:open-tasks | N/A | 5.1 Create Shortcut in Apple Shortcuts app |
| deferred:open-tasks | N/A | 5.2 Configure to receive URLs from Share Sheet |
| deferred:open-tasks | N/A | 5.3 Add input fields for API URL and API key |
| deferred:open-tasks | N/A | 5.4 Implement HTTP POST action to save-url endpoint |
| deferred:open-tasks | N/A | 5.5 Add success/error notifications |
| deferred:open-tasks | N/A | 5.6 Export as .shortcut file to `shortcuts/` directory |
| deferred:open-tasks | N/A | 5.7 Create `shortcuts/README.md` with installation guide |
| deferred:open-tasks | N/A | 6.1 Write integration tests for save-url with local PostgreSQL |
| deferred:open-tasks | N/A | 6.2 Write integration tests for save-url with Supabase |
| deferred:open-tasks | N/A | 6.3 Write integration tests for save-url with Neon |
| deferred:open-tasks | N/A | 6.4 Verify cold start handling with Neon (test after idle period) |
| deferred:open-tasks | N/A | 6.5 Test duplicate detection across providers |
| deferred:open-tasks | N/A | 7.1 Test save_routes.py endpoint logic |
| deferred:open-tasks | N/A | 7.2 Test URL validation edge cases |
| deferred:open-tasks | N/A | 7.3 Test duplicate detection logic |
| deferred:open-tasks | N/A | 7.4 Test API key authentication |
| deferred:open-tasks | N/A | 7.5 Test rate limiting behavior |
| deferred:open-tasks | N/A | 7.6 Test url_extractor.py with mock responses |
| deferred:open-tasks | N/A | 8.1 Create `docs/MOBILE_CAPTURE.md` user guide |
| deferred:open-tasks | N/A | 8.2 Document iOS Shortcut installation |
| deferred:open-tasks | N/A | 8.3 Document API key setup |
| deferred:open-tasks | N/A | 8.4 Add troubleshooting section |
| deferred:open-tasks | N/A | 8.5 Update CLAUDE.md with new endpoint |
| deferred:open-tasks | N/A | 1.1 Create `neon-branch` skill in `agentic-coding-tools` with create/verify/cleanup actions |
| deferred:open-tasks | N/A | 1.2 Update `openspec-apply-change` skill to invoke `neon-branch create` before implementation |
| deferred:open-tasks | N/A | 1.3 Update `openspec-verify-change` skill to invoke `neon-branch verify` during validation |
| deferred:open-tasks | N/A | 1.4 Update `openspec-archive-change` skill to invoke `neon-branch cleanup` after archiving |
| deferred:open-tasks | N/A | 2.1 Register `neon` pytest marker in `pyproject.toml` |
| deferred:open-tasks | N/A | 2.2 Add `neon_available` session fixture to `tests/integration/conftest.py` |
| deferred:open-tasks | N/A | 2.3 Add `neon_session_branch` session-scoped fixture to `tests/integration/conftest.py` |
| deferred:open-tasks | N/A | 2.4 Add `neon_engine` session-scoped fixture |
| deferred:open-tasks | N/A | 2.5 Verify existing Neon fixtures in `tests/integration/fixtures/neon.py` are importable from conftest |
| deferred:open-tasks | N/A | 3.1 Create `profiles/ci-neon.yaml` profile for CI Neon integration tests |
| deferred:open-tasks | N/A | 3.2 Create `.github/workflows/neon-pr.yml` — full PR-based Neon branch lifecycle |
| deferred:open-tasks | N/A | 3.3 Update `.github/workflows/ci.yml` with profile-aware test job (optional) |
| deferred:open-tasks | N/A | 3.4 Document required GitHub repository configuration |
| deferred:open-tasks | N/A | 4.1 Add unit tests for `aca neon` CLI commands |
| deferred:open-tasks | N/A | 4.2 Add `--json` output validation to CLI tests |
| deferred:open-tasks | N/A | 4.3 Handle edge case: `aca neon create` when branch already exists |
| deferred:open-tasks | N/A | 5.1 Update `CLAUDE.md` "Critical Gotchas" table with Neon branching gotchas |
| deferred:open-tasks | N/A | 5.2 Update `docs/SETUP.md` Neon section with agent workflow instructions |
| deferred:open-tasks | N/A | 5.3 Add Neon branch management to `docs/DEVELOPMENT.md` development workflow section |
| deferred:open-tasks | N/A | 1.1 Create Alembic migration for `notification_events` table (id UUID, event_type varchar indexed, title varchar, summar |
| deferred:open-tasks | N/A | 1.2 Create Alembic migration for `device_registrations` table (id UUID, platform varchar, token varchar unique, delivery |
| deferred:open-tasks | N/A | 1.3 Create SQLAlchemy models for `NotificationEvent` and `DeviceRegistration` |
| deferred:open-tasks | N/A | 2.1 Create `src/services/notification_service.py` with `NotificationEventType` enum (batch_summary, theme_analysis, dige |
| deferred:open-tasks | N/A | 2.2 Implement `NotificationDispatcher` class with `emit(event_type, title, summary, payload)` method |
| deferred:open-tasks | N/A | 2.3 Implement database persistence of events in the dispatcher |
| deferred:open-tasks | N/A | 2.4 Implement in-process pub/sub for pushing events to connected SSE clients |
| deferred:open-tasks | N/A | 2.5 Add notification preference checking — skip delivery (not storage) for disabled event types |
| deferred:open-tasks | N/A | 3.1 Integrate dispatcher into batch summarization completion handler |
| deferred:open-tasks | N/A | 3.2 Integrate dispatcher into theme analysis completion handler |
| deferred:open-tasks | N/A | 3.3 Integrate dispatcher into digest creation completion handler |
| deferred:open-tasks | N/A | 3.4 Integrate dispatcher into podcast script generation completion handler |
| deferred:open-tasks | N/A | 3.5 Integrate dispatcher into audio generation (podcast + audio digest) completion handler |
| deferred:open-tasks | N/A | 3.6 Integrate dispatcher into pipeline completion handler |
| deferred:open-tasks | N/A | 3.7 Integrate dispatcher into job failure handler (all job types) |
| deferred:open-tasks | N/A | 4.1 Create `src/api/notification_routes.py` with route prefix `/api/v1/notifications` |
| deferred:open-tasks | N/A | 4.2 Implement `GET /events` — list recent events (pagination, type filter, since filter) |
| deferred:open-tasks | N/A | 4.3 Implement `GET /unread-count` — return unread event count |
| deferred:open-tasks | N/A | 4.4 Implement `PUT /events/{id}/read` — mark single event as read |
| deferred:open-tasks | N/A | 4.5 Implement `PUT /events/read-all` — mark all events as read |
| deferred:open-tasks | N/A | 4.6 Add `X-Admin-Key` authentication to all notification endpoints |
| deferred:open-tasks | N/A | 4.7 Register notification routes in `src/api/app.py` |
| deferred:open-tasks | N/A | 5.1 Implement `GET /notifications/stream` SSE endpoint with `X-Admin-Key` auth via query param |
| deferred:open-tasks | N/A | 5.2 Wire dispatcher pub/sub to push events to connected SSE clients |
| deferred:open-tasks | N/A | 5.3 Implement `Last-Event-ID` reconnection support (send missed events) |
| deferred:open-tasks | N/A | 5.4 Add 30-second heartbeat (`: ping` comment) to keep connections alive |
| deferred:open-tasks | N/A | 6.1 Implement `POST /notifications/devices` — register device (platform, token, delivery_method) |
| deferred:open-tasks | N/A | 6.2 Implement `DELETE /notifications/devices/{id}` — unregister device |
| deferred:open-tasks | N/A | 6.3 Implement `GET /notifications/devices` — list registered devices |
| deferred:open-tasks | N/A | 6.4 Add upsert logic (update existing registration if platform+token matches) |
| deferred:open-tasks | N/A | 7.1 Add notification preference defaults (all event types enabled) using `notification.*` settings namespace |
| deferred:open-tasks | N/A | 7.2 Extend voice settings routes (or create notification settings routes) with `GET /settings/notifications` returning p |
| deferred:open-tasks | N/A | 7.3 Add `PUT /settings/notifications/{event_type}` to set per-type preference |
| deferred:open-tasks | N/A | 7.4 Add `DELETE /settings/notifications/{event_type}` to reset per-type preference |
| deferred:open-tasks | N/A | 8.1 Add `aca manage cleanup-notifications --older-than <duration>` CLI command |
| deferred:open-tasks | N/A | 8.2 Add auto-cleanup on startup (delete events older than 90 days) |
| deferred:open-tasks | N/A | 9.1 Create `web/src/components/notifications/NotificationBell.tsx` with bell icon and unread badge |
| deferred:open-tasks | N/A | 9.2 Create `web/src/components/notifications/NotificationDropdown.tsx` with recent events list |
| deferred:open-tasks | N/A | 9.3 Add notification bell to app header (`AppShell.tsx`) |
| deferred:open-tasks | N/A | 9.4 Create `web/src/hooks/use-notifications.ts` with React Query hooks for events, unread count, and SSE subscription |
| deferred:open-tasks | N/A | 9.5 Add SSE client (EventSource) for real-time badge updates |
| deferred:open-tasks | N/A | 9.6 Implement click-to-navigate for events in dropdown (route to digest/script/audio/job based on payload URL) |
| deferred:open-tasks | N/A | 9.7 Add "Mark all as read" button in dropdown |
| deferred:open-tasks | N/A | 10.1 Add Notifications section to Settings page with per-event-type toggles |
| deferred:open-tasks | N/A | 10.2 Wire toggles to notification preferences API |
| deferred:open-tasks | N/A | 10.3 Add source badges (env/db/default) for each preference |
| deferred:open-tasks | N/A | 10.4 Add event type descriptions next to each toggle |
| deferred:open-tasks | N/A | 11.1 Add unit tests for `NotificationDispatcher` (emit, preference filtering, pub/sub) |
| deferred:open-tasks | N/A | 11.2 Add API tests for notification event endpoints (list, filter, mark read, unread count) |
| deferred:open-tasks | N/A | 11.3 Add API tests for device registration endpoints (register, unregister, list, upsert) |
| deferred:open-tasks | N/A | 11.4 Add API tests for notification preferences endpoints |
| deferred:open-tasks | N/A | 11.5 Add E2E tests for notification bell rendering and badge count |
| deferred:open-tasks | N/A | 11.6 Add E2E tests for notification dropdown (event list, click navigation, mark all read) |
| deferred:open-tasks | N/A | 11.7 Add E2E tests for notification preferences toggles in settings |
| deferred:open-tasks | N/A | 1.1 Create `web/src/lib/voice/engine.ts` with `STTEngine` interface (`start`, `stop`, `onResult`, `onError`) |
| deferred:open-tasks | N/A | 1.2 Implement `BrowserSTTEngine` class wrapping SpeechRecognition (extract from `useVoiceInput`) |
| deferred:open-tasks | N/A | 1.3 Implement `OnDeviceSTTEngine` class wrapping Whisper Web Worker communication |
| deferred:open-tasks | N/A | 1.4 Implement `AutoSTTEngine` that selects browser or on-device based on availability and connectivity |
| deferred:open-tasks | N/A | 1.5 Refactor `useVoiceInput` hook to accept `engine` option and delegate to the engine abstraction |
| deferred:open-tasks | N/A | 2.1 Add Whisper WASM dependency (`whisper-turbo` or equivalent) to `web/package.json` |
| deferred:open-tasks | N/A | 2.2 Configure Vite to handle WASM file imports and worker bundling |
| deferred:open-tasks | N/A | 2.3 Create `web/src/lib/voice/whisper-worker.ts` Web Worker for model loading and inference |
| deferred:open-tasks | N/A | 2.4 Define typed message protocol between main thread and worker (`load-model`, `transcribe`, `result`, `error`, `progre |
| deferred:open-tasks | N/A | 2.5 Implement model loading in worker (initialize Whisper from cached model bytes) |
| deferred:open-tasks | N/A | 2.6 Implement audio transcription in worker (accept Float32Array, return transcript string) |
| deferred:open-tasks | N/A | 3.1 Create `web/src/lib/voice/model-cache.ts` with Cache API operations (`downloadModel`, `isModelCached`, `deleteModel` |
| deferred:open-tasks | N/A | 3.2 Implement model download with progress tracking via fetch + ReadableStream |
| deferred:open-tasks | N/A | 3.3 Implement persistent model storage in Cache API |
| deferred:open-tasks | N/A | 3.4 Add model size constants (tiny: 39MB, base: 74MB) and CDN URLs |
| deferred:open-tasks | N/A | 3.5 Implement download retry logic with cleanup of partial downloads on failure |
| deferred:open-tasks | N/A | 4.1 Create `web/src/lib/voice/audio-recorder.ts` with `getUserMedia` + `MediaRecorder` wrapper |
| deferred:open-tasks | N/A | 4.2 Implement start/stop recording with audio blob capture |
| deferred:open-tasks | N/A | 4.3 Implement audio format conversion (MediaRecorder blob → Float32Array for Whisper) |
| deferred:open-tasks | N/A | 4.4 Handle microphone permission denial with user-facing error message |
| deferred:open-tasks | N/A | 5.1 Extend `voice_settings_routes.py` to include `stt_engine` and `stt_model_size` fields |
| deferred:open-tasks | N/A | 5.2 Add defaults: `stt_engine="auto"`, `stt_model_size="tiny"` |
| deferred:open-tasks | N/A | 5.3 Add `PUT /api/v1/settings/voice/stt_engine` with validation (`auto`, `browser`, `on-device`) |
| deferred:open-tasks | N/A | 5.4 Add `PUT /api/v1/settings/voice/stt_model_size` with validation (`tiny`, `base`) |
| deferred:open-tasks | N/A | 5.5 Add corresponding `DELETE` endpoints for reset |
| deferred:open-tasks | N/A | 6.1 Add STT Engine subsection to `VoiceConfigurator.tsx` |
| deferred:open-tasks | N/A | 6.2 Add engine selector dropdown (Auto / Browser / On-Device) |
| deferred:open-tasks | N/A | 6.3 Add model size selector (Tiny ~39MB / Base ~74MB) |
| deferred:open-tasks | N/A | 6.4 Add model download button with progress bar |
| deferred:open-tasks | N/A | 6.5 Add model status indicator (cached model name, size, delete button) |
| deferred:open-tasks | N/A | 6.6 Wire settings to `use-settings.ts` hooks |
| deferred:open-tasks | N/A | 7.1 Add "Processing..." state to `VoiceInputButton` (spinner animation during on-device transcription) |
| deferred:open-tasks | N/A | 7.2 Add "Transcribing..." placeholder to input field during on-device processing |
| deferred:open-tasks | N/A | 7.3 Replace indicator with transcript text when processing completes |
| deferred:open-tasks | N/A | 8.1 Add unit tests for engine abstraction (mock SpeechRecognition and Whisper worker) |
| deferred:open-tasks | N/A | 8.2 Add unit tests for model cache operations (mock Cache API) |
| deferred:open-tasks | N/A | 8.3 Add E2E test for STT engine settings UI |
| deferred:open-tasks | N/A | 8.4 Add E2E test for model download/delete flow (mocked) |
| deferred:open-tasks | N/A | 8.5 Add backend tests for STT engine settings API endpoints |
| deferred:open-tasks | N/A | 1.1 Install Tauri v2 CLI and `@tauri-apps/api` in `web/` |
| deferred:open-tasks | N/A | 1.2 Run `npx tauri init` and configure `tauri.conf.json` (app name, identifier, window settings) |
| deferred:open-tasks | N/A | 1.3 Configure `src-tauri/Cargo.toml` with required Tauri plugins |
| deferred:open-tasks | N/A | 1.4 Configure Vite to work with Tauri dev server (dev URL forwarding) |
| deferred:open-tasks | N/A | 1.5 Add `src-tauri/target/` to `.gitignore` |
| deferred:open-tasks | N/A | 2.1 Extend `web/src/lib/platform.ts` to detect Tauri via `window.__TAURI_INTERNALS__` |
| deferred:open-tasks | N/A | 2.2 Add `isTauri()` function returning boolean |
| deferred:open-tasks | N/A | 2.3 Update `getPlatform()` to return `"desktop"` when running in Tauri |
| deferred:open-tasks | N/A | 3.1 Add `tauri-plugin-tray` to Rust dependencies |
| deferred:open-tasks | N/A | 3.2 Create system tray with app icon in `src-tauri/src/tray.rs` |
| deferred:open-tasks | N/A | 3.3 Implement context menu: Open App, Ingest URL, Start Voice Input, Quit |
| deferred:open-tasks | N/A | 3.4 Handle "Open App" action (show and focus main window) |
| deferred:open-tasks | N/A | 3.5 Handle "Ingest URL" action (open small input dialog, call save-url API) |
| deferred:open-tasks | N/A | 3.6 Handle "Start Voice Input" action (launch floating overlay) |
| deferred:open-tasks | N/A | 3.7 Handle "Quit" action (exit app and remove tray) |
| deferred:open-tasks | N/A | 4.1 Add `tauri-plugin-global-shortcut` to Rust dependencies |
| deferred:open-tasks | N/A | 4.2 Register `Cmd+Shift+V` / `Ctrl+Shift+V` as global shortcut on app start |
| deferred:open-tasks | N/A | 4.3 Create floating voice input overlay window (small, always-on-top, transparent background) |
| deferred:open-tasks | N/A | 4.4 Wire shortcut to toggle voice input and show/hide floating overlay |
| deferred:open-tasks | N/A | 4.5 Handle shortcut registration failure gracefully (log warning, no crash) |
| deferred:open-tasks | N/A | 4.6 Add shortcut customization to settings UI |
| deferred:open-tasks | N/A | 5.1 Listen for `tauri://file-drop` events on the main window |
| deferred:open-tasks | N/A | 5.2 Validate dropped files against supported format list (PDF, DOCX, PPTX, XLSX, TXT, MD, HTML) |
| deferred:open-tasks | N/A | 5.3 Upload valid files via `POST /api/v1/documents/upload` |
| deferred:open-tasks | N/A | 5.4 Show drop zone overlay when files are dragged over the window |
| deferred:open-tasks | N/A | 5.5 Display success/error toast for each dropped file |
| deferred:open-tasks | N/A | 5.6 Support multiple file drops with summary notification |
| deferred:open-tasks | N/A | 6.1 Add `tauri-plugin-notification` to Rust dependencies |
| deferred:open-tasks | N/A | 6.2 Request notification permission on first launch |
| deferred:open-tasks | N/A | 6.3 Subscribe to backend SSE endpoint (`GET /api/v1/notifications/stream`) on app start |
| deferred:open-tasks | N/A | 6.4 Convert incoming SSE events to native desktop notifications via Tauri notification plugin |
| deferred:open-tasks | N/A | 6.5 Handle notification click — show/focus window, navigate via event `payload.url` |
| deferred:open-tasks | N/A | 6.6 Implement SSE reconnection with `Last-Event-ID` for missed events |
| deferred:open-tasks | N/A | 7.1 Add `pnpm tauri:dev` script (Tauri dev mode with Vite HMR) |
| deferred:open-tasks | N/A | 7.2 Add `pnpm tauri:build` script (production build for current platform) |
| deferred:open-tasks | N/A | 7.3 Add `pnpm tauri:build:all` script (cross-platform builds via CI) |
| deferred:open-tasks | N/A | 7.4 Document Rust toolchain setup requirements |
| deferred:open-tasks | N/A | 8.1 Add E2E tests for platform detection (mock Tauri context) |
| deferred:open-tasks | N/A | 8.2 Add E2E tests for drag-and-drop file upload (mocked) |
| deferred:open-tasks | N/A | 8.3 Manual testing checklist for macOS, Windows, Linux builds |
| deferred:open-tasks | N/A | 8.4 Test global shortcut registration and voice overlay flow |
| deferred:open-tasks | N/A | 1.1 Create `web/src/hooks/use-voice-input.ts` with `useVoiceInput` hook wrapping SpeechRecognition API |
| deferred:open-tasks | N/A | 1.2 Implement feature detection (`isSupported`) for `SpeechRecognition` / `webkitSpeechRecognition` |
| deferred:open-tasks | N/A | 1.3 Implement `startListening`, `stopListening`, `toggleListening` control methods |
| deferred:open-tasks | N/A | 1.4 Implement interim transcript (`interimTranscript`) and final transcript (`transcript`) state |
| deferred:open-tasks | N/A | 1.5 Implement `continuous` mode and `lang` configuration options |
| deferred:open-tasks | N/A | 1.6 Implement `resetTranscript` method |
| deferred:open-tasks | N/A | 1.7 Handle all SpeechRecognition error events (`not-allowed`, `no-speech`, `network`, `audio-capture`) with user-facing  |
| deferred:open-tasks | N/A | 2.1 Create `web/src/components/voice/VoiceInputButton.tsx` with microphone icon (Lucide `Mic` / `MicOff`) |
| deferred:open-tasks | N/A | 2.2 Implement idle state (mic icon, `aria-label="Start voice input"`) |
| deferred:open-tasks | N/A | 2.3 Implement recording state (pulsing red ring animation, `aria-label="Stop voice input"`) |
| deferred:open-tasks | N/A | 2.4 Implement disabled state (`aria-disabled="true"`, tooltip for unsupported browsers) |
| deferred:open-tasks | N/A | 2.5 Implement error state (brief error indicator + toast notification) |
| deferred:open-tasks | N/A | 2.6 Add keyboard activation (Enter/Space toggle) |
| deferred:open-tasks | N/A | 3.1 Add `VoiceInputButton` to `ChatInput.tsx` adjacent to the send button |
| deferred:open-tasks | N/A | 3.2 Wire `useVoiceInput` to append final transcript to textarea content |
| deferred:open-tasks | N/A | 3.3 Display interim transcript in textarea with reduced opacity styling |
| deferred:open-tasks | N/A | 3.4 Implement auto-submit behavior (when enabled, submit on final result in single-utterance mode) |
| deferred:open-tasks | N/A | 3.5 Auto-resize textarea after voice transcript insertion |
| deferred:open-tasks | N/A | 4.1 Add `VoiceInputButton` inside the main search input (right side) |
| deferred:open-tasks | N/A | 4.2 Wire voice transcript to replace search text and trigger search automatically |
| deferred:open-tasks | N/A | 5.1 Extend `voice_settings_routes.py` to include `input_language`, `input_continuous`, `input_auto_submit` fields |
| deferred:open-tasks | N/A | 5.2 Add defaults: `input_language="en-US"`, `input_continuous="false"`, `input_auto_submit="false"` |
| deferred:open-tasks | N/A | 5.3 Add `PUT /api/v1/settings/voice/input_language` with BCP-47 validation |
| deferred:open-tasks | N/A | 5.4 Add `PUT /api/v1/settings/voice/input_continuous` with boolean validation |
| deferred:open-tasks | N/A | 5.5 Add `PUT /api/v1/settings/voice/input_auto_submit` with boolean validation |
| deferred:open-tasks | N/A | 5.6 Add `DELETE` endpoints for each voice input field (reset to default) |
| deferred:open-tasks | N/A | 6.1 Add Voice Input subsection to `VoiceConfigurator.tsx` below existing TTS settings |
| deferred:open-tasks | N/A | 6.2 Add language selector dropdown (English US, English UK, Spanish, French, German, Japanese, Chinese) |
| deferred:open-tasks | N/A | 6.3 Add continuous mode toggle with description |
| deferred:open-tasks | N/A | 6.4 Add auto-submit toggle with description |
| deferred:open-tasks | N/A | 6.5 Wire settings to `use-settings.ts` hooks (query + mutations for voice input fields) |
| deferred:open-tasks | N/A | 6.6 Add source badges (env/db/default) for voice input settings |
| deferred:open-tasks | N/A | 7.1 Create `POST /api/v1/voice/cleanup` endpoint accepting `{ "text": "..." }` and returning `{ "cleaned_text": "..." }` |
| deferred:open-tasks | N/A | 7.2 Add cleanup prompt template (fix grammar, remove filler words, structure text, preserve intent) |
| deferred:open-tasks | N/A | 7.3 Add `VOICE_CLEANUP = "voice_cleanup"` to `ModelStep` enum in `src/config/models.py` |
| deferred:open-tasks | N/A | 7.4 Add `voice_cleanup: claude-haiku-4-5` to `default_models` in `src/config/model_registry.yaml` |
| deferred:open-tasks | N/A | 7.5 Add `voice_cleanup` parameter to `ModelConfig.__init__()` and wire to `self._models` |
| deferred:open-tasks | N/A | 7.6 Wire cleanup endpoint to use `model_config.get_model_for_step(ModelStep.VOICE_CLEANUP)` |
| deferred:open-tasks | N/A | 7.7 Update model settings test step count assertion in `tests/api/test_model_settings_api.py` |
| deferred:open-tasks | N/A | 8.1 Create `CleanupButton` component (sparkle/wand icon) with loading spinner state |
| deferred:open-tasks | N/A | 8.2 Add `CleanupButton` to `ChatInput.tsx` adjacent to `VoiceInputButton` |
| deferred:open-tasks | N/A | 8.3 Add `POST /api/v1/voice/cleanup` API client function in `web/src/lib/api/` |
| deferred:open-tasks | N/A | 8.4 Wire cleanup button to call API, replace textarea content with cleaned text |
| deferred:open-tasks | N/A | 8.5 Implement voice key phrase detection ("clean up") in continuous mode to auto-trigger cleanup |
| deferred:open-tasks | N/A | 8.6 Add keyboard shortcut `Ctrl+Shift+C` / `Cmd+Shift+C` for cleanup |
| deferred:open-tasks | N/A | 8.7 Handle cleanup errors (preserve original text, show error toast) |
| deferred:open-tasks | N/A | 8.8 Add cleanup key phrase configuration to voice input settings |
| deferred:open-tasks | N/A | 9.1 Add ARIA live region for voice input state announcements ("Recording started", "Recording stopped") |
| deferred:open-tasks | N/A | 9.2 Ensure focus returns to input field when voice input stops |
| deferred:open-tasks | N/A | 9.3 Position cursor at end of inserted text after transcript insertion |
| deferred:open-tasks | N/A | 10.1 Add E2E test for voice input button rendering in ChatInput |
| deferred:open-tasks | N/A | 10.2 Add E2E test for voice input button rendering in search |
| deferred:open-tasks | N/A | 10.3 Add E2E test for voice input settings UI (language, continuous, auto-submit toggles) |
| deferred:open-tasks | N/A | 10.4 Add E2E test for disabled state on unsupported browsers (mock `SpeechRecognition` as undefined) |
| deferred:open-tasks | N/A | 10.5 Add backend tests for voice input settings API endpoints (GET, PUT, DELETE) |
| deferred:open-tasks | N/A | 10.6 Add backend tests for voice cleanup API endpoint |
| deferred:open-tasks | N/A | 10.7 Add E2E test for cleanup button rendering and click flow (mocked API) |
| deferred:open-tasks | N/A | 10.8 Add E2E test for cleanup keyboard shortcut |
| deferred:open-tasks | N/A | 1.1 Create Alembic migration for `contents` table: |
| deferred:open-tasks | N/A | 1.2 Create migration for `newsletter_summaries` table (same fields) |
| deferred:open-tasks | N/A | 1.3 Create migration for `digests` table (same fields) |
| deferred:open-tasks | N/A | 1.4 Test migrations and rollback |
| deferred:open-tasks | N/A | 2.1 Add `is_public` and `share_token` to `Content` model |
| deferred:open-tasks | N/A | 2.2 Add fields to `NewsletterSummary` model |
| deferred:open-tasks | N/A | 2.3 Add fields to `Digest` model |
| deferred:open-tasks | N/A | 2.4 Create Pydantic schemas: `ShareRequest`, `ShareResponse`, `ShareStatus` |
| deferred:open-tasks | N/A | 3.1 Add `POST /api/v1/content/{id}/share` - enable sharing |
| deferred:open-tasks | N/A | 3.2 Add `GET /api/v1/content/{id}/share` - get share status |
| deferred:open-tasks | N/A | 3.3 Add `DELETE /api/v1/content/{id}/share` - disable sharing |
| deferred:open-tasks | N/A | 3.4 Duplicate for `/summaries/{id}/share` |
| deferred:open-tasks | N/A | 3.5 Duplicate for `/digests/{id}/share` |
| deferred:open-tasks | N/A | 4.1 Create `src/api/shared_routes.py` |
| deferred:open-tasks | N/A | 4.2 Implement `GET /shared/content/{token}` |
| deferred:open-tasks | N/A | 4.3 Implement `GET /shared/summary/{token}` |
| deferred:open-tasks | N/A | 4.4 Implement `GET /shared/digest/{token}` |
| deferred:open-tasks | N/A | 4.5 Implement `GET /shared/audio/{token}` (redirect to storage URL) |
| deferred:open-tasks | N/A | 4.6 Add content negotiation (HTML vs JSON) |
| deferred:open-tasks | N/A | 5.1 Create `src/templates/shared/base.html` with OG tags |
| deferred:open-tasks | N/A | 5.2 Create `content.html` template |
| deferred:open-tasks | N/A | 5.3 Create `summary.html` template |
| deferred:open-tasks | N/A | 5.4 Create `digest.html` template with audio player |
| deferred:open-tasks | N/A | 5.5 Add responsive CSS for mobile |
| deferred:open-tasks | N/A | 5.6 Add "Shared via Newsletter Aggregator" attribution |
| deferred:open-tasks | N/A | 6.1 Add rate limiting middleware for `/shared/*` |
| deferred:open-tasks | N/A | 6.2 Configure limits (100/min per IP) |
| deferred:open-tasks | N/A | 6.3 Add `Retry-After` header on 429 |
| deferred:open-tasks | N/A | 7.1 Unit tests for share token generation |
| deferred:open-tasks | N/A | 7.2 API tests for share management endpoints |
| deferred:open-tasks | N/A | 7.3 Tests for public access (valid token, invalid token, disabled share) |
| deferred:open-tasks | N/A | 7.4 Test HTML and JSON response formats |
| deferred:open-tasks | N/A | 7.5 Test rate limiting |
| deferred:open-tasks | N/A | 8.1 Document sharing feature in user guide |
| deferred:open-tasks | N/A | 8.2 Add API documentation for share endpoints |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:130 | FIXME: in b\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:281 | FIXME: no git here\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:130 | FIXME: in b\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:281 | FIXME: no git here\n") |

## Low / Info Findings

- **Low**: 417 findings
- **Info**: 0 findings

_(See JSON report for full details)_

## Recommendations

1. Fix failing tests before other fixes
2. Run /fix-scrub --tier auto for quick lint fixes
3. Consolidate deferred items into a follow-up proposal
4. Consider running /fix-scrub --dry-run to preview remediation plan
