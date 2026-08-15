# Bug Scrub Report

**Timestamp**: 2026-08-02T00:42:43.700448+00:00
**Sources**: pytest, ruff, mypy, openspec, architecture, security, deferred, markers
**Severity filter**: low
**Total findings**: 7351

## Summary

### By Severity

| Severity | Count |
|----------|-------|
| high | 2 |
| medium | 6158 |
| low | 1191 |

### By Source

| Source | Count |
|--------|-------|
| deferred:open-tasks | 696 |
| markers | 882 |
| mypy | 5705 |
| ruff | 68 |

## Critical / High Findings

### [HIGH] E741: Ambiguous variable name: `l`

- **Source**: ruff
- **Category**: lint
- **Location**: tests/agents/test_agent_models.py:85
- **Detail**: Ambiguous variable name: `l`

### [HIGH] E302: Expected 2 blank lines, found 1

- **Source**: ruff
- **Category**: lint
- **Location**: tests/security/test_agent_error_leakage.py:12
- **Detail**: Expected 2 blank lines, found 1

## Medium Findings

| Source | Location | Title |
|--------|----------|-------|
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| ruff | scripts/generate_podcast.py:127 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:145 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:154 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/generate_podcast.py:196 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:163 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:226 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:294 | ASYNC250: Blocking call to input() in async context |
| ruff | scripts/review_digest.py:299 | ASYNC250: Blocking call to input() in async context |
| ruff | tests/agents/memory/test_memory_models.py:40 | B017: Do not assert blind exception: `Exception` |
| ruff | tests/agents/memory/test_memory_models.py:44 | B017: Do not assert blind exception: `Exception` |
| ruff | tests/agents/memory/test_provider.py:7 | F401: `unittest.mock.MagicMock` imported but unused |
| ruff | tests/agents/memory/test_provider.py:11 | F401: `src.agents.memory.models.MemoryFilter` imported but unused |
| ruff | tests/agents/memory/test_strategies.py:7 | F401: `unittest.mock.patch` imported but unused |
| ruff | tests/agents/memory/test_strategies.py:11 | F401: `src.agents.memory.models.MemoryFilter` imported but unused |
| ruff | tests/agents/persona/test_loader.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/agents/persona/test_models.py:150 | B017: Do not assert blind exception: `Exception` |
| ruff | tests/agents/persona/test_models.py:152 | B017: Do not assert blind exception: `Exception` |
| ruff | tests/agents/specialists/test_registry.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/agents/specialists/test_registry.py:6 | F401: `pytest` imported but unused |
| ruff | tests/agents/test_agent_models.py:10 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/agents/test_agent_models.py:10 | F401: `uuid` imported but unused |
| ruff | tests/agents/test_agent_models.py:11 | F401: `datetime.datetime` imported but unused |
| ruff | tests/agents/test_agent_models.py:13 | F401: `pytest` imported but unused |
| ruff | tests/agents/test_conductor.py:6 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/agents/test_conductor.py:7 | F401: `unittest.mock.patch` imported but unused |
| ruff | tests/config/test_huggingface_papers_sources.py:86 | F821: Undefined name `pytest` |
| ruff | tests/config/test_routing_config.py:11 | F401: `os` imported but unused |
| ruff | tests/config/test_routing_config.py:13 | F401: `pytest` imported but unused |
| ruff | tests/evaluation/test_consensus.py:13 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/evaluation/test_consensus.py:13 | F401: `json` imported but unused |
| ruff | tests/evaluation/test_consensus.py:20 | F401: `src.evaluation.consensus.ConsensusResult` imported but unused |
| ruff | tests/evaluation/test_criteria.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/evaluation/test_criteria.py:5 | F401: `pathlib.Path` imported but unused |
| ruff | tests/evaluation/test_criteria.py:8 | F401: `src.evaluation.criteria.JudgeConfig` imported but unused |
| ruff | tests/evaluation/test_judge.py:11 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/evaluation/test_judge.py:12 | F401: `unittest.mock.patch` imported but unused |
| ruff | tests/evaluation/test_judge.py:22 | F401: `src.evaluation.judge.DimensionCritique` imported but unused |
| ruff | tests/ingestion/test_filter_hook.py:32 | UP037: Remove quotes from type annotation |
| ruff | tests/integration/conftest.py:389 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/models/test_evaluation.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/models/test_evaluation.py:355 | RUF059: Unpacked variable `samples` is never used |
| ruff | tests/models/test_evaluation.py:363 | RUF059: Unpacked variable `dataset` is never used |
| ruff | tests/models/test_evaluation.py:370 | RUF059: Unpacked variable `dataset` is never used |
| ruff | tests/models/test_evaluation.py:396 | RUF059: Unpacked variable `dataset` is never used |
| ruff | tests/models/test_evaluation.py:412 | RUF059: Unpacked variable `dataset` is never used |
| ruff | tests/security/test_agent_error_leakage.py:7 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/services/test_evaluation_report.py:9 | F401: `unittest.mock.patch` imported but unused |
| ruff | tests/services/test_evaluation_service.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/services/test_evaluation_service.py:4 | F401: `unittest.mock.AsyncMock` imported but unused |
| ruff | tests/services/test_evaluation_service.py:4 | F401: `unittest.mock.patch` imported but unused |
| ruff | tests/services/test_evaluation_service.py:8 | F401: `src.services.evaluation_service.EvaluationReport` imported but unused |
| ruff | tests/services/test_ingestion_filter.py:8 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/services/test_ingestion_filter.py:10 | F401: `asyncio` imported but unused |
| ruff | tests/test_services/test_chunking.py:3 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/test_services/test_chunking.py:197 | C408: Unnecessary `dict()` call (rewrite as a literal) |
| ruff | tests/test_services/test_content_filter.py:7 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/test_services/test_content_filter.py:15 | F401: `src.services.content_filter.FilterResult` imported but unused |
| ruff | tests/test_services/test_indexing.py:5 | F401: `pytest` imported but unused |
| ruff | tests/test_services/test_indexing.py:7 | F401: `src.models.chunk.ChunkType` imported but unused |
| ruff | tests/test_services/test_model_pricing_extractor.py:7 | I001: Import block is un-sorted or un-formatted |
| ruff | tests/test_storage/test_falkordb_provider.py:5 | F401: `unittest.mock.AsyncMock` imported but unused |
| ruff | tests/test_sync/test_obsidian_frontmatter.py:9 | F401: `pytest` imported but unused |
| ruff | tests/test_sync/test_obsidian_frontmatter.py:57 | UP017: Use `datetime.UTC` alias |
| ruff | tests/test_sync/test_obsidian_frontmatter.py:100 | UP017: Use `datetime.UTC` alias |
| ruff | tests/test_sync/test_obsidian_frontmatter.py:121 | UP017: Use `datetime.UTC` alias |
| ruff | tests/test_sync/test_obsidian_manifest.py:12 | F401: `src.sync.obsidian_manifest.ManifestEntry` imported but unused |
| mypy | tests/helpers/api_mocks.py:35 | Returning Any from function declared to return "dict[Any, Any]" |
| mypy | tests/api/test_shortcut_page.py:7 | Function is missing a type annotation |
| mypy | tests/api/test_shortcut_page.py:13 | Function is missing a type annotation |
| mypy | tests/api/test_shortcut_page.py:19 | Function is missing a type annotation |
| mypy | tests/api/test_shortcut_page.py:26 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:13 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:35 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:47 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:72 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:85 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:92 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:100 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:108 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:119 | Function is missing a type annotation |
| mypy | tests/api/test_query_api.py:127 | Function is missing a type annotation |
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
| mypy | tests/api/test_digest_api.py:129 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:144 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:159 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:171 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:187 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:200 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:211 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:224 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:236 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:260 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:268 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:276 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:283 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:293 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:307 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:316 | Function is missing a type annotation |
| mypy | tests/api/test_digest_api.py:325 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:26 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:42 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:66 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:74 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:81 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:103 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:110 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:118 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:126 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:133 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:141 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:148 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:155 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:163 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:171 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:179 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:187 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:195 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:203 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:210 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:223 | Function is missing a type annotation |
| mypy | tests/api/test_voice_settings_api.py:234 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:21 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:39 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:49 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:57 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:73 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:90 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:98 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:106 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:114 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:127 | Function is missing a type annotation |
| mypy | tests/api/test_model_settings_api.py:138 | Function is missing a type annotation |
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
| mypy | tests/test_models/test_summary_performance.py:6 | Function is missing a return type annotation |
| mypy | tests/test_models/test_chat.py:9 | Function is missing a return type annotation |
| mypy | tests/test_models/test_chat.py:16 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:13 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:25 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:39 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:48 | Function is missing a return type annotation |
| mypy | tests/api/test_save_rate_limiter.py:58 | Function is missing a return type annotation |
| mypy | alembic/versions/f9a8b7c6d5e5_add_index_to_canonical_id.py:25 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/f9a8b7c6d5e5_add_index_to_canonical_id.py:41 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/f9a8b7c6d5e4_merge_heads_and_cleanup.py:17 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/f9a8b7c6d5e4_merge_heads_and_cleanup.py:29 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b8affd253096_merge_add_document_search_with_main.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:23 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:26 | Function is missing a type annotation |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:60 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b017a1a2b3c4_bolt_performance_chat_indexes.py:62 | Function is missing a type annotation |
| mypy | alembic/versions/8f6faaa1bce9_merge_substack_enum_and_summary_index_.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/718414e9009f_merge_main_and_pgqueuer_reliability_.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/58aa2c7e188c_add_summary_created_at_index.py:24 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/58aa2c7e188c_add_summary_created_at_index.py:40 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
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
| mypy | tests/migrations/test_batch_processing.py:41 | Function is missing a return type annotation |
| mypy | tests/migrations/test_batch_processing.py:47 | Function is missing a return type annotation |
| mypy | tests/migrations/test_batch_processing.py:54 | Function is missing a type annotation |
| mypy | alembic/versions/f00ddf1d2b47_add_agent_tables.py:31 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:35 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:159 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:183 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:228 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/c5f6a7b8d9e0_add_topic_tables.py:267 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/bc56c4b2e94d_add_evaluation_tables.py:30 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/ba489b85c5a3_merge_perplexity_and_notification_heads.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
| mypy | alembic/versions/b7a1c9d5e2f0_add_audit_log_table.py:42 | Function is missing a type annotation for one or more arguments |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:33 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:83 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/b2c3d4e5f6a7_add_document_chunks_table.py:166 | Argument 1 to "from_engine" of "Inspector" has incompatible type "Connection"; expected "Engine" |
| mypy | alembic/versions/02cfa5c75b82_merge_heads.py:16 | Incompatible types in assignment (expression has type "tuple[str, str]", variable has type "str | None") |
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
| mypy | tests/test_services/test_model_promotion.py:17 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:20 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:26 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:32 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:36 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:40 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:44 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:49 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:57 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:66 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:75 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:84 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_promotion.py:94 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:35 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:40 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:43 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:46 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:49 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:53 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:58 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:61 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:66 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:69 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:72 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:85 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:90 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:94 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:104 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:109 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_routing.py:112 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:18 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:31 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:47 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:50 | Function is missing a type annotation |
| mypy | tests/services/test_complexity_router.py:67 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:84 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:101 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:117 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:135 | Function is missing a return type annotation |
| mypy | tests/services/test_complexity_router.py:151 | Function is missing a type annotation |
| mypy | tests/services/test_complexity_router.py:175 | Function is missing a type annotation |
| mypy | tests/services/test_complexity_router.py:180 | Function is missing a type annotation |
| mypy | tests/regression/conftest.py:32 | Function is missing a type annotation |
| mypy | tests/real_ingestion/test_failure_evidence.py:144 | Function is missing a type annotation for one or more arguments |
| mypy | tests/models/test_topic.py:14 | Function is missing a return type annotation |
| mypy | tests/models/test_topic.py:21 | Function is missing a return type annotation |
| mypy | tests/models/test_topic.py:32 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:51 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:84 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:97 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:118 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:141 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:161 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:183 | Function is missing a type annotation |
| mypy | tests/models/test_topic.py:196 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:18 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiters.py:21 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:33 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:42 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_rate_limiters.py:50 | Returning Any from function declared to return "bool" |
| mypy | tests/api/test_rate_limiters.py:52 | Function is missing a return type annotation |
| mypy | tests/api/test_rate_limiters.py:52 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_rate_limiters.py:62 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:66 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:87 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:113 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:129 | Function is missing a type annotation |
| mypy | tests/api/test_rate_limiters.py:133 | Function is missing a return type annotation |
| mypy | tests/api/test_nul_byte_query_params.py:45 | Function is missing a type annotation |
| mypy | tests/api/test_nul_byte_query_params.py:66 | Function is missing a type annotation |
| mypy | tests/api/test_nul_byte_query_params.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_nul_byte_query_params.py:85 | Function is missing a type annotation |
| mypy | tests/api/test_audit_retention.py:48 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_retention.py:88 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_retention.py:98 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_retention.py:109 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_retention.py:117 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_retention.py:133 | Function is missing a type annotation |
| mypy | tests/api/test_audit_retention.py:160 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:28 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:38 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:79 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:121 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:155 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:161 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:190 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:205 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:211 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:254 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:276 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:283 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:298 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:342 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:359 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:380 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:388 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:424 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:454 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:460 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:484 | Function is missing a type annotation |
| mypy | tests/api/test_notification_api.py:491 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:24 | Function is missing a return type annotation |
| mypy | tests/models/test_evaluation.py:28 | Function is missing a return type annotation |
| mypy | tests/models/test_evaluation.py:33 | Function is missing a return type annotation |
| mypy | tests/models/test_evaluation.py:37 | Function is missing a return type annotation |
| mypy | tests/models/test_evaluation.py:47 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:65 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:81 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:107 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:142 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:173 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:198 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:208 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:221 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:256 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:262 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:272 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:281 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:310 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:329 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:354 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:362 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:369 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:395 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:411 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:431 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:457 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:493 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:527 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:573 | Function is missing a type annotation |
| mypy | tests/models/test_evaluation.py:583 | Function is missing a type annotation |
| mypy | tests/agents/test_agent_models.py:29 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:43 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:48 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:54 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:61 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:68 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:75 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:80 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:89 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:103 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:106 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:115 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:121 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:138 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:147 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:150 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:155 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:165 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:172 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:175 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:180 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:185 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:189 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:196 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:199 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:204 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:218 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:221 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:224 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:227 | Function is missing a return type annotation |
| mypy | tests/agents/test_agent_models.py:230 | Function is missing a return type annotation |
| mypy | scripts/setup_test_db.py:145 | Function is missing a return type annotation |
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
| mypy | scripts/bao_seed_newsletter.py:99 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/bao_seed_newsletter.py:142 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/bao_seed_newsletter.py:202 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/bao_seed_newsletter.py:250 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_report.py:64 | Returning Any from function declared to return "dict[str, Any]" |
| mypy | tests/cli_gen_eval/test_report.py:74 | Returning Any from function declared to return "dict[str, Any]" |
| mypy | tests/config/test_deploy_secrets.py:14 | Function is missing a return type annotation |
| mypy | tests/config/test_deploy_secrets.py:14 | Function is missing a type annotation for one or more arguments |
| mypy | tests/config/test_deploy_secrets.py:20 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:40 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:59 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:64 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:70 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:84 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:101 | Function is missing a type annotation |
| mypy | tests/config/test_deploy_secrets.py:115 | Function is missing a type annotation |
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
| mypy | tests/services/test_persona_profile_cache.py:35 | Argument 1 to "PersonaProfileCache" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_persona_profile_cache.py:41 | Argument 1 to "PersonaProfileCache" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_persona_profile_cache.py:54 | Argument 1 to "PersonaProfileCache" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_persona_profile_cache.py:67 | Argument 1 to "PersonaProfileCache" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/evaluation/test_calibrator.py:9 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:18 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:27 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:39 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:49 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:61 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:71 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:76 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:87 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_calibrator.py:97 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:17 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:29 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:39 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:45 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:53 | Function is missing a type annotation |
| mypy | tests/evaluation/test_criteria.py:59 | Function is missing a type annotation |
| mypy | tests/evaluation/test_criteria.py:89 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:100 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:108 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:116 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:123 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:129 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_criteria.py:134 | Function is missing a return type annotation |
| mypy | tests/api/test_podcast_api.py:9 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:26 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:39 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:52 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:63 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:74 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:97 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:112 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:118 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:139 | Function is missing a type annotation |
| mypy | tests/api/test_podcast_api.py:154 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:40 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:65 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:70 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:79 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:129 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:144 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:162 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:176 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:185 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:193 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:207 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:222 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:235 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:250 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:269 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:281 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:291 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:331 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:373 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:424 | Function is missing a return type annotation |
| mypy | tests/api/test_sharing_api.py:432 | Function is missing a return type annotation |
| mypy | tests/api/test_sharing_api.py:442 | Function is missing a return type annotation |
| mypy | tests/api/test_sharing_api.py:453 | Function is missing a return type annotation |
| mypy | tests/api/test_sharing_api.py:465 | Function is missing a return type annotation |
| mypy | tests/api/test_sharing_api.py:481 | Function is missing a type annotation |
| mypy | tests/api/test_sharing_api.py:490 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:14 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_audio_digest_api.py:19 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:23 | Argument "duration_seconds" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:36 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_audio_digest_api.py:42 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:46 | Argument "duration_seconds" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:52 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:59 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_audio_digest_api.py:80 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:88 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:97 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:107 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:136 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:144 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:152 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:161 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:170 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:178 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:193 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:207 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:225 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:245 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:252 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:269 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:275 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:285 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:305 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:313 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:353 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:372 | Function is missing a type annotation |
| mypy | tests/api/test_audio_digest_api.py:378 | Function is missing a type annotation |
| mypy | tests/ingestion/test_response_builder.py:33 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:55 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:73 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:88 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:100 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:112 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_response_builder.py:133 | Function is missing a return type annotation |
| mypy | tests/test_config/test_profiles.py:557 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/test_config/test_profiles.py:575 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/test_config/test_langfuse_profile_defaults.py:75 | "ObservabilitySettings" has no attribute "langfuse_base_url" |
| mypy | tests/test_config/test_langfuse_profile_defaults.py:102 | "APIKeySettings" has no attribute "langfuse_public_key" |
| mypy | tests/test_config/test_langfuse_profile_defaults.py:105 | "APIKeySettings" has no attribute "langfuse_secret_key" |
| mypy | tests/test_config/test_bao_settings_integration.py:19 | Function is missing a return type annotation |
| mypy | tests/test_config/test_bao_settings_integration.py:26 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:24 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:29 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:33 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:37 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:44 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:51 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:58 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:67 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:73 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:79 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:86 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:91 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:96 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:110 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:119 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:178 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:186 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:191 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:201 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:217 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:227 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:243 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:255 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:263 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:279 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:302 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:311 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_scheduler.py:324 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_refresh_models_schedule.py:15 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/scheduler/test_refresh_models_schedule.py:21 | Function is missing a return type annotation |
| mypy | tests/agents/scheduler/test_refresh_models_schedule.py:32 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:14 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:23 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:39 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:43 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:47 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:55 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:63 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:67 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_memory_models.py:80 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:35 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:46 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:61 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:68 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:81 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:85 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:92 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:97 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:105 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:119 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:136 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:148 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:163 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:167 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:176 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:194 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:198 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:201 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:204 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:207 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_judge.py:217 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:243 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:268 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:282 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:310 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:329 | Function is missing a type annotation |
| mypy | tests/evaluation/test_judge.py:351 | Function is missing a type annotation |
| mypy | tests/release_smoke/test_browser_smoke.py:98 | Function is missing a type annotation |
| mypy | tests/release_smoke/test_browser_smoke.py:209 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/test_models/test_content_reference.py:31 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:37 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:42 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:54 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:60 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:69 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:75 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:84 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:104 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:117 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:137 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:150 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:154 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:176 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:187 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:197 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:209 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:220 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:231 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:242 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:256 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:260 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:264 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:268 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:272 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:276 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:280 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:293 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:301 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:309 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:329 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:352 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:374 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content_reference.py:402 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:32 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:56 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:66 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:75 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:89 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:98 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:107 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:126 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:167 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:186 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:194 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:222 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:253 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:265 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:274 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:288 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:302 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:335 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:356 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:374 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:393 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:424 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:438 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:469 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:484 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:489 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:493 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:497 | Function is missing a return type annotation |
| mypy | tests/test_models/test_content.py:528 | Function is missing a return type annotation |
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
| mypy | tests/api/test_script_api.py:222 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:237 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:262 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:292 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:305 | Function is missing a type annotation |
| mypy | tests/api/test_script_api.py:318 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:31 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:43 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:92 | Function is missing a type annotation |
| mypy | tests/api/test_markdown_api.py:123 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:34 | Function is missing a return type annotation |
| mypy | tests/api/test_graph_routes.py:41 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:95 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:106 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:110 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:111 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:131 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_graph_routes.py:159 | Incompatible return value type (got "int | None", expected "int") |
| mypy | tests/api/test_graph_routes.py:163 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:179 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:186 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:194 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:209 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:213 | Function is missing a type annotation |
| mypy | tests/api/test_graph_routes.py:234 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:19 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:27 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:45 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:55 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:63 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:71 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:114 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:124 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:130 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:144 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:162 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:175 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:188 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:198 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:206 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:222 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:232 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:241 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:272 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:295 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:300 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:309 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:318 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:332 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:346 | Function is missing a type annotation |
| mypy | tests/api/test_content_api.py:355 | Function is missing a type annotation |
| mypy | tests/real_ingestion/test_live_tier.py:51 | Function is missing a type annotation for one or more arguments |
| mypy | tests/real_ingestion/test_live_tier.py:68 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/persona/test_loader.py:140 | "object" has no attribute "return_value" |
| mypy | tests/evaluation/test_consensus.py:62 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:68 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:74 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:80 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:90 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:100 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:106 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:117 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:132 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:142 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:146 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:152 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:163 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:175 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:186 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:199 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:212 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:223 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_consensus.py:243 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:7 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:13 | Function is missing a return type annotation |
| mypy | tests/security/test_youtube_input_validation.py:29 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:21 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:63 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:84 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:90 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:101 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:107 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:115 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:126 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:138 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:148 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:157 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:179 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:197 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:211 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:224 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:240 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:250 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:255 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:265 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:281 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:289 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:293 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:297 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:302 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:308 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:312 | Function is missing a type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:334 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:338 | Function is missing a return type annotation |
| mypy | tests/parsers/test_kreuzberg_parser.py:342 | Function is missing a return type annotation |
| mypy | tests/api/test_search_api.py:25 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:122 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:252 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:256 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:263 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:267 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:271 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:287 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:302 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:307 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:312 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:321 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:331 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:346 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:352 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:363 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:374 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:389 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:401 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:419 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:432 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:446 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:463 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:471 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:481 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:489 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:499 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:526 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:536 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:550 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:554 | Function is missing a type annotation |
| mypy | tests/api/test_search_api.py:558 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:29 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:40 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:59 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:92 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:100 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:118 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:133 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:165 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:177 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:185 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:199 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:219 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:257 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:279 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:283 | Function is missing a return type annotation |
| mypy | tests/api/test_reference_routes.py:290 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_reference_routes.py:308 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:335 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:363 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:382 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:392 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:399 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:403 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:410 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:411 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:429 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:440 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:463 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:481 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:499 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:506 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:513 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:520 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:534 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:535 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:549 | Function is missing a type annotation |
| mypy | tests/api/test_reference_routes.py:557 | Function is missing a type annotation |
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
| mypy | tests/migrations/test_workflow_provenance.py:102 | Module has no attribute "op" |
| mypy | tests/api/test_theme_api.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:29 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:38 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:47 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_theme_api.py:120 | Function is missing a type annotation |
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
| mypy | tests/cli/test_query_options.py:13 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:19 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:30 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:41 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:52 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:63 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:69 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:75 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:83 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:89 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:100 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:111 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:122 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:134 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:148 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:158 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:165 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:176 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:186 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:197 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:208 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:217 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:223 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:234 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:246 | Function is missing a return type annotation |
| mypy | tests/cli/test_query_options.py:264 | Function is missing a return type annotation |
| mypy | tests/release_smoke/test_evidence.py:290 | Function is missing a type annotation for one or more arguments |
| mypy | tests/release_smoke/test_evidence.py:344 | Function is missing a type annotation for one or more arguments |
| mypy | tests/release_smoke/test_evidence.py:399 | Function is missing a type annotation for one or more arguments |
| mypy | tests/release_smoke/test_evidence.py:415 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/memory/test_provider.py:18 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_provider.py:32 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:47 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:61 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:75 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:87 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:96 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:103 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:109 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:114 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:126 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:137 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:151 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_provider.py:165 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_provider.py:173 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:187 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:203 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_provider.py:224 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_provider.py:241 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:18 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:22 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:24 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:30 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:32 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:35 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:38 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:41 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:52 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:57 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:64 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:73 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:82 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:89 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:100 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:110 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:117 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:126 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:132 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:138 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:146 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:156 | Function is missing a return type annotation |
| mypy | tests/agents/memory/test_strategies.py:164 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:170 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:176 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:181 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:186 | Function is missing a type annotation |
| mypy | tests/agents/memory/test_strategies.py:191 | Function is missing a type annotation |
| mypy | tests/services/test_evaluation_report.py:15 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_report.py:20 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_report.py:29 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_report.py:45 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:14 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:28 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:35 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:48 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:55 | Function is missing a return type annotation |
| mypy | tests/services/test_evaluation_service.py:61 | Function is missing a return type annotation |
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
| mypy | tests/test_sync/test_obsidian_topic_export.py:18 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:22 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:25 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:42 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:55 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:62 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:70 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:99 | Function is missing a return type annotation |
| mypy | tests/test_sync/test_obsidian_topic_export.py:112 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:11 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:28 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:39 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:44 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:50 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:70 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:86 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:89 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:93 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:104 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:114 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:124 | Function is missing a return type annotation |
| mypy | tests/test_models/test_batch.py:141 | Function is missing a return type annotation |
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
| mypy | tests/test_utils/test_html_parser.py:11 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:31 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:51 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:65 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:86 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:96 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:103 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_html_parser.py:109 | Function is missing a return type annotation |
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
| mypy | tests/security/test_ssrf_protection.py:11 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:24 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:36 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:48 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:60 | Function is missing a return type annotation |
| mypy | tests/security/test_ssrf_protection.py:68 | Function is missing a return type annotation |
| mypy | tests/security/test_path_traversal.py:16 | Function is missing a return type annotation |
| mypy | tests/security/test_path_traversal.py:25 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:36 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:44 | Function is missing a type annotation |
| mypy | tests/security/test_path_traversal.py:52 | Function is missing a type annotation |
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
| mypy | tests/conftest.py:42 | Cannot assign to a type |
| mypy | tests/conftest.py:42 | Incompatible types in assignment (expression has type "type[JSON]", variable has type "type[JSONB]") |
| mypy | tests/conftest.py:56 | Function is missing a return type annotation |
| mypy | tests/conftest.py:84 | Function is missing a return type annotation |
| mypy | tests/conftest.py:125 | Function is missing a return type annotation |
| mypy | tests/conftest.py:150 | Function is missing a type annotation |
| mypy | tests/conftest.py:186 | Function is missing a type annotation |
| mypy | tests/conftest.py:195 | Function is missing a type annotation |
| mypy | tests/conftest.py:204 | Function is missing a type annotation |
| mypy | tests/conftest.py:217 | Function is missing a type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:7 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:11 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:29 | Function is missing a return type annotation |
| mypy | tests/unit/test_prompt_service_unit.py:41 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:9 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:18 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:25 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:32 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:40 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:47 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:58 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:63 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:72 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:77 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:91 | Function is missing a return type annotation |
| mypy | tests/unit/test_model_audio_capability.py:95 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:34 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:46 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:66 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:114 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:142 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:166 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:200 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:235 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_otel_smoke.py:265 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:12 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:30 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:41 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:56 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:66 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:75 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:85 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:97 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:109 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:142 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:161 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:179 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:193 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:207 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_setup.py:216 | Function is missing a type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:16 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:37 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:58 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:79 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:100 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:124 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:144 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:163 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:187 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:207 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:226 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:262 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_log_correlation.py:324 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:13 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:51 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:79 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:105 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_llm_integration.py:135 | Function is missing a return type annotation |
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
| mypy | tests/test_storage/test_providers.py:391 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:404 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:415 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:421 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:433 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:440 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:447 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:454 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:469 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:475 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:484 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:494 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:502 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:510 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:523 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:532 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:540 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:550 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:559 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:572 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:576 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:583 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:589 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_providers.py:594 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:601 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:608 | Function is missing a type annotation |
| mypy | tests/test_storage/test_providers.py:615 | Function is missing a type annotation |
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
| mypy | tests/test_services/test_reference_extractor.py:31 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:35 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:39 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:43 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:47 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:51 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:55 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:59 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:63 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:70 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:74 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:86 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:89 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:92 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:95 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:98 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:102 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:112 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:120 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:125 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:131 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:138 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:141 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:151 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:160 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:168 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:175 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:190 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:197 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:205 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:212 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:219 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:228 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:238 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:241 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:244 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:248 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:258 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:261 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:265 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:269 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:274 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:282 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:284 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_extractor.py:291 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:301 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:304 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_extractor.py:310 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:314 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:318 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:322 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:325 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:337 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:340 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_extractor.py:348 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_extractor.py:355 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_extractor.py:361 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:378 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:394 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:407 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:433 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:436 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:452 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:467 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:490 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:504 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:517 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:533 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:543 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:563 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_extractor.py:572 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_video.py:14 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_video.py:24 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:35 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:70 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:105 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:138 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:164 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_video.py:172 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:200 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:223 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_video.py:232 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:39 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:57 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:67 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:72 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:82 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:108 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:124 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:141 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:156 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:171 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:186 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:208 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:221 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:238 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:253 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:267 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:280 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:287 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:303 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:318 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:347 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router_batch.py:350 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router.py:19 | Function is missing a return type annotation |
| mypy | tests/test_services/test_llm_router.py:28 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:53 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:86 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:106 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:153 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:173 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:198 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:205 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:208 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:225 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:249 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:275 | Function is missing a type annotation |
| mypy | tests/test_services/test_llm_router.py:289 | Function is missing a type annotation |
| mypy | tests/test_services/test_indexing.py:12 | Function is missing a return type annotation |
| mypy | tests/test_services/test_indexing.py:17 | Function is missing a return type annotation |
| mypy | tests/test_services/test_indexing.py:48 | Function is missing a type annotation |
| mypy | tests/test_services/test_indexing.py:65 | Function is missing a type annotation |
| mypy | tests/test_services/test_indexing.py:100 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:31 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:36 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:41 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:51 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:54 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:58 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:62 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:73 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:79 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:87 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:95 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:103 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:107 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:112 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:120 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:124 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:137 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:144 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:144 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_services/test_content_filter.py:172 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:181 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:188 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:195 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:208 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:217 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:251 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:257 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:270 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:281 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:287 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:298 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:301 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:304 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:308 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:312 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:315 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:318 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:328 | Function is missing a type annotation |
| mypy | tests/test_services/test_content_filter.py:338 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:345 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:356 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:362 | Function is missing a return type annotation |
| mypy | tests/test_services/test_content_filter.py:373 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:27 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:32 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:37 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:43 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:47 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:56 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:64 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:72 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:76 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:80 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:84 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:88 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:100 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:108 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:111 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:118 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:122 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:126 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:134 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:140 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:152 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:155 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:163 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:174 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:177 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:184 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:195 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:211 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:223 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:235 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:247 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:278 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:287 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:297 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:302 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:308 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:315 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:327 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:336 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:345 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:359 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:363 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:367 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:371 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:380 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:384 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:396 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:412 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:422 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:433 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:442 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:448 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:455 | Function is missing a return type annotation |
| mypy | tests/test_services/test_chunking.py:464 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:499 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:522 | Function is missing a type annotation |
| mypy | tests/test_services/test_chunking.py:550 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_disabled_regression.py:19 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_disabled_regression.py:26 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_disabled_regression.py:41 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:24 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:36 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:45 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:61 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:80 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:88 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:99 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:105 | Function is missing a return type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:127 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:139 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:155 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:185 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:207 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:226 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:245 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:272 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:289 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:310 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:325 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:351 | Function is missing a type annotation |
| mypy | tests/test_parsers/test_html_markdown_crawl4ai.py:376 | Function is missing a type annotation |
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
| mypy | tests/test_ingestion/test_youtube_sources.py:31 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:39 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:48 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:68 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:81 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:98 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:111 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:122 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:148 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:173 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:198 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:223 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:263 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:289 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:313 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:342 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:367 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:406 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:436 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:464 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:482 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:493 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:512 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:544 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:572 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:598 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:625 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:649 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_sources.py:673 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_segments.py:11 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_youtube_segments.py:15 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_segments.py:36 | Function is missing a return type annotation |
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
| mypy | tests/test_ingestion/test_youtube_rss.py:399 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:433 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube_rss.py:465 | Function is missing a type annotation |
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
| mypy | tests/test_ingestion/test_youtube.py:327 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:341 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:341 | Incompatible types in assignment (expression has type "def mock_ingest_playlist(**kwargs: Any) -> Any", variable has type "def ingest_playlist(self, playlist_id: str, max_videos: int = ..., after_date: datetime | None = ..., force_reprocess: bool = ..., languages: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ..., proofread: bool = ..., hint_terms: list[str] | None = ..., video_fps: float | None = ..., long_video_threshold_seconds: int = ..., long_video_strategy: str = ..., segment_overlap_seconds: int = ..., unknown_duration_strategy: str = ..., min_duration_seconds: int | None = ..., max_duration_seconds: int | None = ..., content_filter: Any = ...) -> Coroutine[Any, Any, SourceFetchResult]") |
| mypy | tests/test_ingestion/test_youtube.py:373 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:378 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:378 | Incompatible types in assignment (expression has type "def mock_process(video: Any, playlist_id: Any, **kwargs: Any) -> Any", variable has type "def _process_video(self, video: dict[str, Any], playlist_id: str, force_reprocess: bool = ..., languages: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ..., proofread: bool = ..., hint_terms: list[str] | None = ..., video_fps: float | None = ..., long_video_threshold_seconds: int = ..., long_video_strategy: str = ..., segment_overlap_seconds: int = ..., unknown_duration_strategy: str = ..., min_duration_seconds: int | None = ..., max_duration_seconds: int | None = ..., content_filter: Any = ...) -> Coroutine[Any, Any, bool]") |
| mypy | tests/test_ingestion/test_youtube.py:441 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_youtube.py:454 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_youtube.py:454 | Incompatible types in assignment (expression has type "def mock_ingest_feed(**kwargs: Any) -> Any", variable has type "def ingest_feed(self, feed_url: str, max_entries: int = ..., after_date: datetime | None = ..., force_reprocess: bool = ..., source_name: str | None = ..., source_tags: list[str] | None = ..., *, gemini_summary: bool = ..., gemini_resolution: str = ..., video_fps: float | None = ..., long_video_threshold_seconds: int = ..., long_video_strategy: str = ..., segment_overlap_seconds: int = ..., unknown_duration_strategy: str = ..., min_duration_seconds: int | None = ..., max_duration_seconds: int | None = ..., content_filter: Any = ...) -> Coroutine[Any, Any, SourceFetchResult]") |
| mypy | tests/test_ingestion/test_xsearch.py:106 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:112 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:118 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:135 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:145 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:156 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:161 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:172 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:180 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:187 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:197 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:201 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:219 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:225 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:230 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:234 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:250 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:259 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:277 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:282 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:288 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:318 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:338 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:357 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:376 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:405 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:438 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:474 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:508 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:531 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_xsearch.py:550 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_url_routing_dispatch.py:75 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_url_routing_dispatch.py:77 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_url_routing_dispatch.py:117 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_url_routing_dispatch.py:155 | Cannot assign to a method |
| mypy | tests/test_ingestion/test_scholar.py:67 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "str" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "str | None" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "int | None" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "int" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "list[str]" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "list[FakeS2Author]" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "dict[str, str]" |
| mypy | tests/test_ingestion/test_scholar.py:88 | Argument 1 to "FakeS2Paper" has incompatible type "**dict[str, object]"; expected "dict[str, str] | None" |
| mypy | tests/test_ingestion/test_scholar.py:91 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_ingestion/test_scholar.py:112 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:124 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:137 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:146 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:163 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:166 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:184 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:201 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:218 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:221 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:235 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:255 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:258 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:272 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:277 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:282 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:287 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:292 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:297 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:302 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:317 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:320 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:325 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:334 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:343 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:352 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:382 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:393 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:396 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:403 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:410 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:417 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:423 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:434 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:451 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:455 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:468 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:481 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:500 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:506 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:530 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:555 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:566 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:577 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:602 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:608 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:626 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:642 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:651 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:660 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:685 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:691 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:709 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:727 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:748 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:757 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_scholar.py:772 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:787 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:801 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_scholar.py:808 | Function is missing a return type annotation |
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
| mypy | tests/test_ingestion/test_reference_extractor.py:10 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:13 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:17 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:21 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:25 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:29 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:33 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:39 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:42 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:46 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:50 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:55 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:60 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:63 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:68 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:73 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:76 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:86 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:93 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:96 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:98 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:111 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:115 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:117 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:129 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_reference_extractor.py:138 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:37 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:40 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:45 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:58 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:72 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:84 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:91 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:97 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:101 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:107 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:112 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:117 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:121 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:126 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:130 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:135 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:145 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:154 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:158 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:172 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:179 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:186 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:192 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:201 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:211 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:221 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:246 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:262 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:273 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:286 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:300 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:322 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_ingestion/test_readwise.py:341 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_ingestion/test_readwise.py:357 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_readwise.py:364 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:374 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:395 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:406 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:421 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:445 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:461 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:485 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:514 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:549 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:586 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_readwise.py:610 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:22 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:40 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:46 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:56 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:118 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:145 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:164 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:186 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:196 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:207 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:220 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:247 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:266 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:276 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:317 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:358 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:396 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:439 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:495 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:514 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:530 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_podcast.py:573 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:579 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:604 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:608 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:629 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:633 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:668 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_podcast.py:680 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:39 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:47 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:67 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:71 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:77 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:82 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:88 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:95 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:100 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:106 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:110 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:116 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:144 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:153 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:162 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:169 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:178 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:212 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:242 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:273 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:284 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:317 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:339 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:355 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:361 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:397 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:427 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:447 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:468 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:496 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_perplexity_search.py:534 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:20 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:31 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:48 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:60 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:75 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:85 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:97 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:104 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:111 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:117 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:124 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:138 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:147 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:156 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:165 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:174 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:190 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:204 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:213 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:227 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:236 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:258 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:269 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:280 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:296 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:308 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:319 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:329 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:341 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:350 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:368 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:410 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:430 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:452 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:461 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:481 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:526 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:548 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:560 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_huggingface_papers.py:583 | Function is missing a type annotation |
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
| mypy | tests/test_ingestion/test_blog_scraper.py:19 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:30 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:50 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:64 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:76 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:94 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:115 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:122 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:140 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:155 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:174 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:190 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:216 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:225 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:233 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:240 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:254 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:260 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:273 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:293 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:302 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:311 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:327 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:336 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:351 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:367 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:370 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:373 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:376 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:388 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:416 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:431 | Function is missing a return type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:452 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:499 | Function is missing a type annotation |
| mypy | tests/test_ingestion/test_blog_scraper.py:521 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:14 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:24 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:34 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:49 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:56 | Function is missing a return type annotation |
| mypy | tests/test_config/test_youtube_routing_config.py:61 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:31 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:43 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:52 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:66 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:74 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:78 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:93 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:105 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:121 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:125 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:140 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:165 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:198 | Function is missing a return type annotation |
| mypy | tests/test_config/test_websearch_sources.py:228 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:27 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:35 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:46 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:54 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:57 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:70 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:76 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:80 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:87 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:91 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:98 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:102 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:108 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:117 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:124 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:128 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:141 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:146 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:160 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:165 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:172 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:184 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:198 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:217 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:236 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:257 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:263 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:282 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:286 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:303 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:329 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:355 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:374 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:392 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:412 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:432 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:445 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:461 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:475 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:492 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:505 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:519 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:533 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:552 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:565 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:579 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:597 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:604 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:611 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:619 | Function is missing a type annotation |
| mypy | tests/test_config/test_sources.py:643 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:652 | Function is missing a return type annotation |
| mypy | tests/test_config/test_sources.py:668 | Function is missing a type annotation |
| mypy | tests/test_config/test_settings.py:14 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:52 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:63 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:73 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:88 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:101 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:112 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:123 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:136 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:162 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:188 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:204 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:215 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:232 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:255 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:267 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:279 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:299 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:314 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:335 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:357 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:373 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:385 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:405 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:437 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:449 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:461 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:473 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:489 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:502 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:514 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:529 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:547 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:561 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:572 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:595 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:607 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:623 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:632 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:641 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:662 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:684 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:695 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:711 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:728 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:747 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:755 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:766 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:776 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:788 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:800 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:812 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:824 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:842 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:855 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:871 | Function is missing a return type annotation |
| mypy | tests/test_config/test_settings.py:881 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:14 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:39 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:43 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:47 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:51 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:55 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:64 | Function is missing a return type annotation |
| mypy | tests/test_config/test_reference_settings.py:89 | Function is missing a type annotation |
| mypy | tests/test_config/test_reference_settings.py:94 | Function is missing a type annotation |
| mypy | tests/test_config/test_reference_settings.py:99 | Function is missing a type annotation |
| mypy | tests/test_config/test_reference_settings.py:104 | Function is missing a type annotation |
| mypy | tests/test_config/test_reference_settings.py:109 | Function is missing a type annotation |
| mypy | tests/test_config/test_profile_integration.py:17 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:29 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:38 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:59 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:84 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:101 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:112 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:121 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:138 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:143 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:154 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:167 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:187 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:200 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:211 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:221 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:243 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:264 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:304 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:320 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:349 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:359 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:376 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:394 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:415 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:428 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:463 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:486 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:491 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:498 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:530 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:544 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:557 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:573 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:586 | Function is missing a return type annotation |
| mypy | tests/test_config/test_models.py:604 | Function is missing a return type annotation |
| mypy | tests/test_config/test_bao_secrets.py:31 | Function is missing a return type annotation |
| mypy | tests/test_config/test_bao_secrets.py:333 | Function is missing a type annotation |
| mypy | tests/test_config/test_bao_secrets.py:346 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:21 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:24 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:27 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:31 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:35 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:41 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:46 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:59 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:72 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:92 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:105 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:134 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:149 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:155 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:173 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:190 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:210 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:242 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:267 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:292 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:306 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:341 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:362 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:376 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:382 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:388 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:392 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:404 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:421 | Function is missing a type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:439 | Function is missing a type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:459 | Function is missing a type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:483 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:493 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:501 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:511 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:521 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:540 | Function is missing a return type annotation |
| mypy | tests/telemetry/test_langfuse_provider.py:546 | Function is missing a return type annotation |
| mypy | tests/services/test_source_override_service.py:17 | Function is missing a return type annotation |
| mypy | tests/services/test_source_override_service.py:26 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/services/test_source_override_service.py:26 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_source_override_service.py:40 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:44 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:48 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:52 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:58 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:67 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:76 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:80 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:87 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:94 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:100 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:110 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:117 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:128 | Function is missing a type annotation |
| mypy | tests/services/test_source_override_service.py:132 | Function is missing a type annotation |
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
| mypy | tests/services/test_llm_router_routing.py:19 | Function is missing a return type annotation |
| mypy | tests/services/test_llm_router_routing.py:24 | Function is missing a return type annotation |
| mypy | tests/services/test_llm_router_routing.py:42 | Function is missing a type annotation |
| mypy | tests/services/test_llm_router_routing.py:61 | Function is missing a type annotation |
| mypy | tests/services/test_llm_router_routing.py:84 | Function is missing a type annotation |
| mypy | tests/services/test_llm_router_routing.py:116 | Function is missing a type annotation |
| mypy | tests/services/test_llm_router_routing.py:134 | Function is missing a type annotation |
| mypy | tests/services/test_llm_router_routing.py:166 | Function is missing a type annotation |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "bool" |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "int" |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "tuple[str, ...]" |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "str | None" |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "BorderlineBand" |
| mypy | tests/services/test_ingestion_filter.py:115 | Argument 1 to "FilterConfig" has incompatible type "**dict[str, object]"; expected "float" |
| mypy | tests/services/test_ingestion_filter.py:154 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:167 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:180 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:200 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:214 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:228 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:241 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:257 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_ingestion_filter.py:268 | Argument 1 to "IngestionFilterService" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_image_generation_prompts.py:17 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:22 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:27 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:34 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:39 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:47 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:63 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:75 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generation_prompts.py:85 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:15 | Function is missing a type annotation for one or more arguments |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "bool | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "int | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "bool | list[str] | tuple[str, ...] | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "CliSettingsSource[Any] | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "Literal['all', 'no_enums'] | bool | None" |
| mypy | tests/security/test_production_validation.py:25 | Argument 2 to "Settings" has incompatible type "**dict[str, str]"; expected "Mapping[str, str | list[str]] | None" |
| mypy | tests/security/test_production_validation.py:28 | Function is missing a type annotation for one or more arguments |
| mypy | tests/security/test_production_validation.py:44 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:51 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:62 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:76 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:90 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:103 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:112 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:121 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:130 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:139 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:147 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:156 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:165 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:174 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:187 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:193 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:199 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:206 | Function is missing a return type annotation |
| mypy | tests/security/test_production_validation.py:215 | Function is missing a return type annotation |
| mypy | tests/real_ingestion/test_scheduled_tier.py:31 | Function is missing a type annotation for one or more arguments |
| mypy | tests/real_ingestion/test_scheduled_tier.py:52 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/integration/test_arxiv_live.py:29 | Function is missing a type annotation |
| mypy | tests/integration/test_arxiv_live.py:33 | Function is missing a type annotation |
| mypy | tests/integration/test_arxiv_live.py:47 | Function is missing a return type annotation |
| mypy | tests/integration/test_arxiv_live.py:58 | Function is missing a return type annotation |
| mypy | tests/integration/test_arxiv_live.py:72 | Function is missing a return type annotation |
| mypy | tests/integration/test_arxiv_live.py:82 | Function is missing a return type annotation |
| mypy | tests/integration/test_arxiv_live.py:103 | Function is missing a return type annotation |
| mypy | tests/integration/test_arxiv_live.py:103 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_arxiv_live.py:138 | Function is missing a return type annotation |
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
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "str" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "type[StrictModel]" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[StrictModel], IngestionResponse | int]" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "frozenset[ContentSource]" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "bool" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[tuple[SourceBase, ...], datetime, datetime], tuple[StrictModel, ...]] | None" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "frozenset[str]" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Mapping[str, str]" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[SourceBase], bool] | None" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[SourcesConfig], list[SourceBase]] | None" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[StrictModel], str | RouteKind] | None" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "Callable[[StrictModel], frozenset[ContentSource]] | None" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "SourceOptions" |
| mypy | tests/ingestion/test_source_registry.py:87 | Argument 2 to "replace" of "SourceDescriptor" has incompatible type "**dict[str, str | frozenset[str]]"; expected "SourceRetryPolicy" |
| mypy | tests/ingestion/test_source_registry.py:177 | "StrictModel" has no attribute "kind" |
| mypy | tests/ingestion/test_source_registry.py:188 | "StrictModel" has no attribute "prompt" |
| mypy | tests/ingestion/test_source_registry.py:207 | "StrictModel" has no attribute "after_date" |
| mypy | tests/ingestion/test_source_registry.py:225 | "StrictModel" has no attribute "query" |
| mypy | tests/ingestion/test_source_registry.py:226 | "StrictModel" has no attribute "max_items" |
| mypy | tests/ingestion/test_source_registry.py:227 | "StrictModel" has no attribute "configured_sources" |
| mypy | tests/ingestion/test_source_registry.py:239 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "SourcesConfig" |
| mypy | tests/ingestion/test_source_registry.py:239 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "datetime" |
| mypy | tests/ingestion/test_source_registry.py:241 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "SourcesConfig" |
| mypy | tests/ingestion/test_source_registry.py:241 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "datetime" |
| mypy | tests/ingestion/test_source_registry.py:243 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "SourcesConfig" |
| mypy | tests/ingestion/test_source_registry.py:243 | Argument 2 to "plan_scheduled_commands" of "SourceRegistry" has incompatible type "**dict[str, object]"; expected "datetime" |
| mypy | tests/ingestion/test_source_registry.py:246 | Function is missing a type annotation for one or more arguments |
| mypy | tests/ingestion/test_orchestrator.py:32 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:44 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:66 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:81 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:93 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:105 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:114 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:152 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:182 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:202 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:221 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:260 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:315 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:327 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:355 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:365 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:377 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:390 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:400 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:425 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:449 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:482 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:503 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:514 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:536 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:558 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:575 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:599 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:640 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:667 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:694 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:717 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:734 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:756 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:775 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:796 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:812 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:818 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:823 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:849 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:867 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:902 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_orchestrator.py:902 | Function is missing a type annotation for one or more arguments |
| mypy | tests/ingestion/test_orchestrator.py:914 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:943 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:958 | Function is missing a type annotation |
| mypy | tests/ingestion/test_orchestrator.py:979 | Function is missing a type annotation |
| mypy | tests/ingestion/test_filter_hook.py:95 | Argument "db" to "apply_filter_to_recent" has incompatible type "_FakeSession"; expected "Session | None" |
| mypy | tests/ingestion/test_filter_hook.py:123 | Argument "db" to "apply_filter_to_recent" has incompatible type "_FakeSession"; expected "Session | None" |
| mypy | tests/ingestion/test_filter_hook.py:150 | Argument "db" to "apply_filter_to_recent" has incompatible type "_FakeSession"; expected "Session | None" |
| mypy | tests/ingestion/test_file_identity.py:31 | Value of type "Any | None" is not indexable |
| mypy | tests/ingestion/test_file_identity.py:35 | Function is missing a type annotation for one or more arguments |
| mypy | tests/ingestion/test_file_identity.py:61 | Value of type "Any | None" is not indexable |
| mypy | tests/ingestion/test_arxiv_client.py:14 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:17 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:20 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:23 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:26 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:29 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:32 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:35 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:38 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:41 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:44 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:48 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:52 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:57 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:60 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:63 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:66 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:73 | Function is missing a return type annotation |
| mypy | tests/ingestion/test_arxiv_client.py:117 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:21 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:42 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:78 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:106 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:123 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_e2e.py:141 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:34 | Function is missing a type annotation |
| mypy | tests/config/test_source_overrides_merge.py:37 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:40 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:44 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:56 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:62 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:77 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_merge.py:91 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:22 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:36 | Function is missing a type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:38 | Function is missing a return type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:48 | Function is missing a type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:63 | Function is missing a type annotation |
| mypy | tests/config/test_source_overrides_e2e.py:78 | Function is missing a type annotation |
| mypy | tests/config/test_routing_config.py:24 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:27 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:32 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:40 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:57 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:68 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:77 | Function is missing a return type annotation |
| mypy | tests/config/test_routing_config.py:81 | Function is missing a type annotation |
| mypy | tests/config/test_routing_config.py:88 | Function is missing a type annotation |
| mypy | tests/config/test_routing_config.py:95 | Function is missing a type annotation |
| mypy | tests/config/test_routing_config.py:102 | Function is missing a return type annotation |
| mypy | tests/config/test_production_validation.py:13 | Function is missing a type annotation |
| mypy | tests/config/test_production_validation.py:26 | Function is missing a type annotation |
| mypy | tests/config/test_production_validation.py:39 | Function is missing a type annotation |
| mypy | tests/config/test_production_validation.py:56 | Function is missing a type annotation |
| mypy | tests/config/test_production_validation.py:73 | Function is missing a type annotation |
| mypy | tests/config/test_production_validation.py:91 | Function is missing a type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:9 | Function is missing a return type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:15 | Function is missing a return type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:30 | Function is missing a return type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:51 | Function is missing a return type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:64 | Function is missing a return type annotation |
| mypy | tests/config/test_huggingface_papers_sources.py:78 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_settings.py:6 | Function is missing a type annotation |
| mypy | tests/config/test_batch_settings.py:14 | Function is missing a type annotation |
| mypy | tests/config/test_batch_config.py:18 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:29 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:35 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:42 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:49 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:55 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:60 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:67 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:75 | Function is missing a return type annotation |
| mypy | tests/config/test_batch_config.py:81 | Function is missing a return type annotation |
| mypy | tests/config/test_arxiv_sources.py:9 | Function is missing a return type annotation |
| mypy | tests/config/test_arxiv_sources.py:18 | Function is missing a return type annotation |
| mypy | tests/config/test_arxiv_sources.py:37 | Function is missing a return type annotation |
| mypy | tests/config/test_arxiv_sources.py:49 | Function is missing a return type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:9 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:27 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:34 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:41 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:65 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:78 | Function is missing a type annotation |
| mypy | tests/api/test_voice_cleanup_api.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:28 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:40 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:52 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:83 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:88 | Function is missing a return type annotation |
| mypy | tests/api/test_summary_api.py:97 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_summary_api.py:133 | Argument "processing_time_seconds" to "Summary" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_summary_api.py:145 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:161 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:172 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:183 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:194 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:212 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:223 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:233 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:248 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:264 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:281 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:293 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:306 | Function is missing a type annotation |
| mypy | tests/api/test_summary_api.py:311 | Function is missing a return type annotation |
| mypy | tests/api/test_source_api.py:21 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:36 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:71 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:107 | Function is missing a type annotation |
| mypy | tests/api/test_source_api.py:120 | Function is missing a type annotation |
| mypy | tests/api/test_settings_rendering.py:6 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:21 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_settings_rendering.py:38 | Function is missing a return type annotation |
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
| mypy | tests/api/test_notification_preferences_api.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:44 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:68 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:121 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:134 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:154 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:163 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:176 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:191 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:204 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:221 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:237 | Function is missing a type annotation |
| mypy | tests/api/test_notification_preferences_api.py:243 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:21 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:30 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:35 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:46 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:51 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:68 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:90 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:108 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:134 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:157 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:186 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:225 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:254 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:259 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:263 | Function is missing a return type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:275 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:310 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:313 | Function is missing a type annotation |
| mypy | tests/agents/test_llm_router_extensions.py:335 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:17 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:20 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:33 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:43 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:46 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:91 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_metrics.py:109 | Function is missing a return type annotation |
| mypy | tests/security/test_storage_traversal.py:18 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:32 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:40 | Function is missing a type annotation |
| mypy | tests/security/test_storage_traversal.py:48 | Function is missing a type annotation |
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
| mypy | tests/integration/test_opik_integration.py:42 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:78 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:102 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:123 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:151 | Function is missing a return type annotation |
| mypy | tests/integration/test_opik_integration.py:168 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:183 | Function is missing a return type annotation |
| mypy | tests/integration/test_opik_integration.py:195 | Function is missing a type annotation |
| mypy | tests/integration/test_opik_integration.py:215 | Function is missing a type annotation |
| mypy | tests/integration/test_langfuse_integration.py:41 | Function is missing a type annotation |
| mypy | tests/integration/test_langfuse_integration.py:60 | Function is missing a type annotation |
| mypy | tests/integration/test_langfuse_integration.py:79 | Function is missing a type annotation |
| mypy | tests/integration/test_langfuse_integration.py:91 | Function is missing a type annotation |
| mypy | tests/integration/test_langfuse_integration.py:115 | Function is missing a return type annotation |
| mypy | tests/integration/test_langfuse_integration.py:129 | Function is missing a return type annotation |
| mypy | tests/integration/test_langfuse_integration.py:148 | Function is missing a return type annotation |
| mypy | tests/integration/test_langfuse_integration.py:160 | Function is missing a type annotation |
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
| mypy | tests/test_telemetry/test_agent_metrics.py:29 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:32 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:35 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:48 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:57 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:61 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:69 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:72 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:75 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:111 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:133 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:147 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:165 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:195 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:198 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:201 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:208 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:213 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:218 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:223 | Function is missing a return type annotation |
| mypy | tests/test_telemetry/test_agent_metrics.py:233 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:39 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:46 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:54 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:61 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:70 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:79 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:87 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:97 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:108 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:133 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:149 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:167 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:193 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:210 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:229 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:246 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:257 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:273 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:297 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:322 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_auto_ingest.py:334 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:18 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:27 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:37 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:46 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:55 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_cleanup.py:65 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:81 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:103 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:132 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:151 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:169 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:192 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:209 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:239 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:267 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:295 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:329 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:371 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:418 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:422 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_pricing_extractor.py:428 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:12 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:15 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:20 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:37 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:44 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:61 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_catalog_discovery.py:74 | Function is missing a type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:37 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:51 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:59 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:67 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:75 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:89 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:102 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:115 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:129 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:143 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:162 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:167 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:188 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:199 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:206 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:214 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:225 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:234 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:241 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:250 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:257 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:271 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:299 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:341 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:358 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:371 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:382 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:388 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:400 | Function is missing a return type annotation |
| mypy | tests/test_services/test_infrastructure_pricing_service.py:412 | Function is missing a return type annotation |
| mypy | tests/services/test_filter_feedback.py:47 | Argument 1 to "emit_feedback" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_filter_feedback.py:66 | Argument 1 to "emit_feedback" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_filter_feedback.py:78 | Argument 1 to "emit_feedback" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_filter_feedback.py:91 | Argument 1 to "emit_feedback" has incompatible type "_FakeSession"; expected "Session" |
| mypy | tests/services/test_filter_feedback.py:110 | Argument 1 to "emit_feedback" has incompatible type "_FakeSession"; expected "Session" |
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
| mypy | tests/services/test_content_set_resolver.py:26 | Function is missing a type annotation |
| mypy | tests/services/test_content_set_resolver.py:30 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:49 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:57 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:64 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:70 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:71 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:74 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:86 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:114 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:118 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:132 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:133 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:134 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:136 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:139 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:153 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:154 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:159 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:196 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:199 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:202 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:236 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:259 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:278 | Function is missing a type annotation |
| mypy | tests/services/test_content_set_resolver.py:285 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:286 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:287 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:291 | "ContentFactory" has no attribute "id" |
| mypy | tests/services/test_content_set_resolver.py:296 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:315 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_content_set_resolver.py:321 | Property "fingerprint" defined in "ResolvedContentSet" is read-only |
| mypy | tests/services/test_content_set_resolver.py:323 | Property "limit" defined in "SelectionPolicy" is read-only |
| mypy | tests/services/test_content_query.py:25 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:33 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:37 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:41 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:45 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:50 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:54 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:58 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:62 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:66 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:78 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:82 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:109 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:119 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:131 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:142 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:154 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:165 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:177 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:188 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:199 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:210 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:219 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:233 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:245 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:254 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:264 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:293 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:305 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:317 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:339 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:360 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:373 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:379 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:391 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:404 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:412 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:428 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:437 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:448 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:457 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:469 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:477 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:483 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:501 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:512 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:520 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:529 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:537 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:543 | Function is missing a return type annotation |
| mypy | tests/services/test_content_query.py:551 | Function is missing a type annotation |
| mypy | tests/services/test_content_query.py:565 | Function is missing a return type annotation |
| mypy | tests/api/test_connection_status_api.py:16 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:66 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:84 | Function is missing a type annotation |
| mypy | tests/api/test_connection_status_api.py:101 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:20 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:38 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:52 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:63 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:77 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:88 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:109 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:122 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:135 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:150 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:168 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:184 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:200 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:216 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:244 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:253 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:277 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:300 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:321 | Function is missing a return type annotation |
| mypy | tests/api/test_chat_api.py:324 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:340 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:350 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:360 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:370 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:383 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:420 | Function is missing a type annotation |
| mypy | tests/api/test_chat_api.py:440 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_savings.py:13 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_savings.py:19 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_savings.py:31 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_savings.py:42 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_savings.py:49 | Function is missing a return type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:20 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:57 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:92 | Function is missing a type annotation |
| mypy | tests/scripts/test_switch_embeddings.py:112 | Function is missing a type annotation |
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
| mypy | tests/cli_gen_eval/test_selection.py:376 | Function is missing a return type annotation |
| mypy | tests/test_cli/test_profile_migrate.py:385 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_profile_migrate.py:418 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_profile_migrate.py:450 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_cli/test_auth_commands.py:32 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:39 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:44 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:53 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:58 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:68 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:72 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:83 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:93 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:97 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:116 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:132 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:168 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:182 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:206 | Function is missing a type annotation |
| mypy | tests/test_cli/test_auth_commands.py:220 | Function is missing a type annotation |
| mypy | tests/e2e/conftest.py:70 | Function is missing a return type annotation |
| mypy | tests/e2e/conftest.py:88 | Function is missing a type annotation for one or more arguments |
| mypy | tests/e2e/conftest.py:91 | Returning Any from function declared to return "str" |
| mypy | tests/e2e/conftest.py:100 | Function is missing a return type annotation |
| mypy | tests/e2e/conftest.py:117 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/e2e/conftest.py:131 | Function is missing a return type annotation |
| mypy | tests/e2e/conftest.py:541 | Returning Any from function declared to return "str | None" |
| mypy | tests/e2e/conftest.py:583 | Returning Any from function declared to return "dict[Any, Any]" |
| mypy | tests/config/test_settings_api_url.py:8 | Function is missing a return type annotation |
| mypy | tests/config/test_settings_api_url.py:15 | Function is missing a type annotation |
| mypy | tests/config/test_settings_api_url.py:24 | Function is missing a type annotation |
| mypy | tests/cli/test_api_client_retry.py:25 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:36 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:47 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:61 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:73 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:85 | Function is missing a type annotation |
| mypy | tests/cli/test_api_client_retry.py:92 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:98 | Function is missing a return type annotation |
| mypy | tests/cli/test_api_client_retry.py:104 | Function is missing a return type annotation |
| mypy | tests/unit/test_audit_decorator.py:18 | Function is missing a return type annotation |
| mypy | tests/unit/test_audit_decorator.py:20 | Function is missing a type annotation |
| mypy | tests/unit/test_audit_decorator.py:30 | Function is missing a return type annotation |
| mypy | tests/unit/test_audit_decorator.py:32 | Function is missing a type annotation |
| mypy | tests/unit/test_audit_decorator.py:40 | Function is missing a return type annotation |
| mypy | tests/unit/test_audit_decorator.py:42 | Function is missing a type annotation |
| mypy | tests/unit/test_audit_decorator.py:46 | Function is missing a type annotation |
| mypy | tests/unit/test_audit_decorator.py:58 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_observability.py:46 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_observability.py:63 | Function is missing a type annotation |
| mypy | tests/api/test_audit_observability.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_audit_observability.py:87 | Function is missing a type annotation |
| mypy | tests/api/test_audit_observability.py:99 | Function is missing a type annotation |
| mypy | tests/api/test_audit_observability.py:108 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_observability.py:123 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:52 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_middleware.py:57 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:90 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_middleware.py:108 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:123 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:137 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:145 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:157 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:168 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:177 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:184 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:191 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:223 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:241 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:256 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:263 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:271 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:284 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:294 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:302 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:309 | Function is missing a type annotation |
| mypy | tests/api/test_audit_middleware.py:323 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_middleware.py:329 | Function is missing a type annotation |
| mypy | tests/agents/specialists/test_base.py:11 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:24 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:37 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:52 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:65 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:77 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:85 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:102 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:106 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:121 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:123 | Function is missing a type annotation |
| mypy | tests/agents/specialists/test_base.py:136 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:138 | Function is missing a type annotation |
| mypy | tests/agents/specialists/test_base.py:151 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:153 | Function is missing a type annotation |
| mypy | tests/agents/specialists/test_base.py:165 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_base.py:167 | Function is missing a type annotation |
| mypy | tests/integration/fixtures/falkordb.py:35 | Function is missing a return type annotation |
| mypy | tests/integration/fixtures/falkordb.py:52 | Function is missing a type annotation |
| mypy | tests/integration/fixtures/falkordb.py:62 | Function is missing a type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:17 | Function is missing a type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:27 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:49 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:64 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:71 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:81 | Function is missing a type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:98 | Function is missing a type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:116 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:136 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:151 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:169 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:189 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:210 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:228 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:240 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:252 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:265 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:276 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:290 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:301 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_falkordb_provider.py:308 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:35 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:51 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:61 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:75 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:81 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:88 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:94 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:100 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:116 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:121 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:128 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:142 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:147 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:176 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:190 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:200 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:214 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:219 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:236 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:243 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:248 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:274 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:293 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:298 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:304 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:323 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:334 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:349 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:359 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:373 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:383 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:394 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:401 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:406 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:429 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:441 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:457 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:462 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:468 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:479 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:490 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:501 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:521 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:533 | Function is missing a type annotation |
| mypy | tests/test_services/test_web_search.py:545 | Function is missing a return type annotation |
| mypy | tests/test_services/test_web_search.py:561 | Function is missing a return type annotation |
| mypy | tests/test_services/test_scholar_web_search.py:172 | Argument 1 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_scholar_web_search.py:172 | Argument 2 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_scholar_web_search.py:207 | Argument 1 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_scholar_web_search.py:207 | Argument 2 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_scholar_web_search.py:238 | Argument 1 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_scholar_web_search.py:238 | Argument 2 to "_setup_mock_client" has incompatible type Module; expected "MagicMock" |
| mypy | tests/test_services/test_search.py:17 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:23 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:27 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:31 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:37 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:40 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:48 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:54 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:60 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:66 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:76 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:95 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:107 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:118 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:143 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:153 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:173 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:199 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:222 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:284 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:299 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:313 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:331 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:343 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:363 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:386 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:398 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:403 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:412 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:422 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:467 | Function is missing a return type annotation |
| mypy | tests/test_services/test_search.py:473 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:497 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:534 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:575 | Function is missing a type annotation |
| mypy | tests/test_services/test_search.py:599 | Function is missing a type annotation |
| mypy | tests/security/test_search_xss.py:4 | Function is missing a return type annotation |
| mypy | tests/test_services/test_registry_writeback.py:12 | Function is missing a return type annotation |
| mypy | tests/test_services/test_registry_writeback.py:17 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:22 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:27 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:33 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:42 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:61 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:72 | Function is missing a type annotation |
| mypy | tests/test_services/test_registry_writeback.py:88 | Function is missing a type annotation |
| mypy | tests/services/test_image_generator.py:39 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:45 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:50 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:67 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:119 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:146 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:184 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:217 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:257 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:300 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:312 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:316 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:320 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:324 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:330 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:344 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:354 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:364 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:375 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:392 | Function is missing a return type annotation |
| mypy | tests/services/test_image_generator.py:398 | Function is missing a return type annotation |
| mypy | tests/api/test_image_generation_api.py:24 | Function is missing a return type annotation |
| mypy | tests/api/test_image_generation_api.py:68 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:89 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:101 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:113 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:129 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:156 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:183 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:209 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:225 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:241 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:262 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:300 | Function is missing a type annotation |
| mypy | tests/api/test_image_generation_api.py:320 | Function is missing a type annotation |
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
| mypy | tests/security/test_markdown_xss.py:4 | Function is missing a return type annotation |
| mypy | tests/security/test_markdown_xss.py:15 | Function is missing a return type annotation |
| mypy | tests/security/test_markdown_xss.py:26 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:16 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:27 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:38 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:46 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:55 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:73 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:82 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:91 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:102 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:113 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:124 | Function is missing a return type annotation |
| mypy | tests/unit/test_cloud_stt_service.py:132 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:48 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:64 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:77 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:91 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:97 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:113 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:128 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:137 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:151 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:155 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:165 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:170 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:174 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:177 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_collector.py:184 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:188 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_collector.py:192 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:67 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:92 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:105 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:122 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:150 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:174 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:205 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:231 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:246 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:261 | Function is missing a type annotation |
| mypy | tests/test_services/test_reference_hook.py:281 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_hook.py:293 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_hook.py:305 | Function is missing a return type annotation |
| mypy | tests/test_services/test_reference_hook.py:317 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:23 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:33 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:66 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:85 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:109 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:120 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:127 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:141 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:167 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:180 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:203 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:230 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:249 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:266 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:288 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:330 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:360 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:397 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:413 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:428 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:443 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:458 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:466 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:482 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:493 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_reviser.py:514 | Function is missing a return type annotation |
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
| mypy | tests/cli_gen_eval/test_mutation_guard.py:92 | Function is missing a return type annotation |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:107 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:114 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:126 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:146 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:158 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:166 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:175 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:189 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:198 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:205 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:211 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:219 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:299 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:312 | Need type annotation for "overrides" |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:330 | Function is missing a type annotation |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:385 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:423 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli_gen_eval/test_mutation_guard.py:445 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli/test_evaluate_commands.py:23 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:30 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:45 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:54 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:73 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:80 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:100 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:105 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:114 | Function is missing a return type annotation |
| mypy | tests/cli/test_evaluate_commands.py:121 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:29 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:42 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:58 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:67 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:83 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:100 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:112 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:120 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:128 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:149 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:158 | Function is missing a return type annotation |
| mypy | tests/cli/test_deploy_commands.py:172 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:22 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:40 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:61 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:75 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:92 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:109 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:125 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:150 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:162 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:185 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:197 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:209 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:229 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:242 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:246 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:250 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:254 | Function is missing a return type annotation |
| mypy | tests/agents/test_cli_commands.py:269 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:285 | Function is missing a type annotation |
| mypy | tests/agents/test_cli_commands.py:300 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:79 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:99 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:128 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:152 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:169 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:194 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:215 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:236 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:267 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:284 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:303 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:345 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:375 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:398 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:419 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:452 | Function is missing a return type annotation |
| mypy | tests/e2e/test_daily_pipeline_live.py:489 | Function is missing a return type annotation |
| mypy | tests/test_agents/test_claude_agent.py:90 | Function is missing a return type annotation |
| mypy | tests/test_agents/test_claude_agent.py:100 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:110 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:121 | Function is missing a return type annotation |
| mypy | tests/test_agents/test_claude_agent.py:135 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:160 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:182 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:193 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:213 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:236 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:251 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:276 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:311 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:332 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:351 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:368 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:378 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:394 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:410 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:429 | Function is missing a type annotation |
| mypy | tests/test_agents/test_claude_agent.py:439 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:22 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:27 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:34 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:47 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:60 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:69 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:83 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:105 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:122 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:137 | Function is missing a return type annotation |
| mypy | tests/integration/test_falkordb_provider.py:155 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:197 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:218 | Function is missing a type annotation |
| mypy | tests/integration/test_falkordb_provider.py:232 | Function is missing a type annotation |
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
| mypy | tests/test_storage/test_graphiti_client.py:15 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:39 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:46 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:58 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:64 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:73 | Function is missing a return type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:100 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:110 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:122 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:149 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:165 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:187 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:231 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:274 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:300 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:307 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:325 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:372 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:411 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:446 | Function is missing a type annotation |
| mypy | tests/test_storage/test_graphiti_client.py:459 | Function is missing a type annotation |
| mypy | scripts/query_knowledge_graph.py:24 | Missing positional arguments "provider", "graphiti" in call to "GraphitiClient" |
| mypy | scripts/query_knowledge_graph.py:54 | Missing positional arguments "provider", "graphiti" in call to "GraphitiClient" |
| mypy | scripts/extract_entities.py:57 | Missing positional arguments "provider", "graphiti" in call to "GraphitiClient" |
| mypy | scripts/extract_entities.py:92 | Missing positional arguments "provider", "graphiti" in call to "GraphitiClient" |
| mypy | tests/test_services/test_reference_graph_sync.py:161 | Cannot assign to a method |
| mypy | tests/services/test_source_curator.py:33 | Function is missing a type annotation |
| mypy | tests/services/test_source_curator.py:40 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:50 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:57 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:68 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:78 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:85 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:90 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:97 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:103 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:114 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:124 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:137 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:146 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:161 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:171 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:179 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:191 | Function is missing a type annotation |
| mypy | tests/services/test_source_curator.py:196 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:205 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:215 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:225 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:237 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:243 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:249 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:260 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:271 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:280 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:293 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:301 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:311 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:323 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:340 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:358 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:371 | Function is missing a type annotation |
| mypy | tests/services/test_source_curator.py:375 | Function is missing a type annotation |
| mypy | tests/services/test_source_curator.py:382 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:394 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:402 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:412 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:423 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:434 | Function is missing a return type annotation |
| mypy | tests/services/test_source_curator.py:447 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:106 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:204 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:216 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:234 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:241 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:250 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:268 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:279 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:324 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:330 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:341 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:347 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:363 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:379 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:406 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:428 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:443 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:470 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:501 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:524 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:542 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:558 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:575 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:587 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:598 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:631 | Function is missing a type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:654 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:663 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:680 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:703 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:731 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:743 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:767 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_podcast_script_generator.py:776 | Function is missing a return type annotation |
| mypy | tests/services/test_capability_service.py:103 | Need type annotation for "parsed" |
| mypy | tests/ingestion/test_ingestion_service.py:137 | Function is missing a type annotation |
| mypy | tests/ingestion/test_ingestion_service.py:263 | Function is missing a type annotation for one or more arguments |
| mypy | tests/ingestion/test_ingestion_service.py:390 | "_publish_content" does not return a value (it only ever returns None) |
| mypy | tests/ingestion/test_ingestion_service.py:402 | "_record_loaded_content_reference" does not return a value (it only ever returns None) |
| mypy | tests/ingestion/test_ingestion_service.py:428 | "_publish_content" does not return a value (it only ever returns None) |
| mypy | tests/ingestion/test_ingestion_service.py:464 | "_publish_content" does not return a value (it only ever returns None) |
| mypy | tests/ingestion/test_ingestion_service.py:471 | "_publish_content" does not return a value (it only ever returns None) |
| mypy | tests/ingestion/test_ingestion_service.py:489 | "_publish_content" does not return a value (it only ever returns None) |
| mypy | tests/fixtures/sources/harness.py:63 | Function is missing a return type annotation |
| mypy | tests/fixtures/sources/harness.py:121 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:122 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:150 | Incompatible types in assignment (expression has type "_SessionDigestLoader", variable has type "ExactContentSetLoader") |
| mypy | tests/fixtures/sources/harness.py:154 | "DigestFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:160 | Argument "digest" to "VerticalWorkflowResult" has incompatible type "DigestFactory"; expected "Digest" |
| mypy | tests/fixtures/sources/harness.py:167 | "StrictModel" has no attribute "kind" |
| mypy | tests/fixtures/sources/harness.py:190 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:193 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:194 | Incompatible types in assignment (expression has type "tuple[ContentFactory, SummaryFactory, ContentSource]", variable has type "tuple[Content, Summary, ContentSource] | None") |
| mypy | tests/fixtures/sources/harness.py:201 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:202 | "ContentFactory" has no attribute "id" |
| mypy | tests/fixtures/sources/harness.py:208 | Argument "upload_service" to "IngestionService" has incompatible type "_FixtureUploadService | None"; expected "UploadService | None" |
| mypy | tests/fixtures/sources/harness.py:216 | "StrictModel" has no attribute "upload_ids" |
| mypy | tests/fixtures/sources/harness.py:233 | Argument "content_id" to "PersistedFixture" has incompatible type "int | None"; expected "int" |
| mypy | tests/fixtures/sources/harness.py:234 | Argument "summary_id" to "PersistedFixture" has incompatible type "int | None"; expected "int" |
| mypy | tests/services/test_html_processor.py:29 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_html_processor.py:51 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:78 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:95 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:104 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:117 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:127 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:145 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:155 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:160 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:168 | Function is missing a return type annotation |
| mypy | tests/services/test_html_processor.py:185 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:222 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:236 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:242 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:310 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:349 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:386 | Function is missing a type annotation |
| mypy | tests/services/test_html_processor.py:417 | Function is missing a type annotation |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:31 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:71 | Function is missing a return type annotation |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:71 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:89 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:100 | "ContentFactory" has no attribute "id" |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:139 | "ContentFactory" has no attribute "id" |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:140 | "ContentFactory" has no attribute "id" |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:148 | "ContentFactory" has no attribute "id" |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:149 | "ContentFactory" has no attribute "id" |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:156 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_canonical_workflow_edge_cases.py:210 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_service.py:302 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_service.py:343 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_service.py:354 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_service.py:391 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_service.py:432 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_service.py:447 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/test_processors/test_audio_digest_generator.py:19 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:36 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:50 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:65 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:81 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:88 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:91 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:94 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:118 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:143 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:189 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:220 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:236 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:273 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:315 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:320 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:323 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:326 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:352 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:405 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:453 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:495 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:500 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:503 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:506 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:530 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:576 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:601 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:623 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:654 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:685 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:690 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:693 | Function is missing a type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:696 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_audio_digest_generator.py:720 | Function is missing a type annotation |
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
| mypy | tests/evaluation/test_evaluation_api.py:30 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:36 | Function is missing a return type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:55 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:62 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:69 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:75 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:100 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:109 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:120 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:127 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:134 | Function is missing a type annotation |
| mypy | tests/evaluation/test_evaluation_api.py:141 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:23 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:36 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:48 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:58 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:70 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:74 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:78 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:82 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:86 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:97 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:105 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:109 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:113 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:117 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:121 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:125 | Function is missing a return type annotation |
| mypy | tests/api/test_ingest_extended.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:153 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:166 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:186 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:206 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:217 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:229 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:240 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:252 | Function is missing a type annotation |
| mypy | tests/api/test_ingest_extended.py:271 | Function is missing a type annotation |
| mypy | tests/agents/test_api_routes.py:41 | Function is missing a type annotation |
| mypy | tests/agents/test_api_routes.py:69 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:69 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:90 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:90 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:114 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:121 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:128 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:133 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:133 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:145 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:145 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:157 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:157 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:171 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:175 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:189 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:189 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:201 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:201 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:213 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:213 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:224 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:228 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:242 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:242 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:257 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:257 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_api_routes.py:271 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:284 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:289 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:293 | Function is missing a return type annotation |
| mypy | tests/agents/test_api_routes.py:306 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:28 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:31 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:34 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:37 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:41 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:46 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:49 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:52 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:56 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:59 | Function is missing a return type annotation |
| mypy | tests/services/test_knowledge_base.py:67 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:84 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:92 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:128 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:170 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:199 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:234 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:244 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:253 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:307 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:328 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:346 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:373 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:401 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:423 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:436 | Function is missing a type annotation |
| mypy | tests/services/test_knowledge_base.py:457 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:23 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_kb_routes.py:45 | Argument "relevance_score" to "Topic" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_kb_routes.py:60 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:65 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:90 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:104 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:116 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:129 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:143 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:147 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:166 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:179 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:183 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:195 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:205 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:214 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:218 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:229 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:240 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:256 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:264 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:278 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:287 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:298 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:305 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:316 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:322 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:326 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:343 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:350 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:360 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:382 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:403 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:417 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:434 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:450 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:457 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:471 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:482 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:508 | Function is missing a type annotation |
| mypy | tests/api/test_kb_routes.py:518 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:123 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:134 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:143 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:190 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:220 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:262 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:289 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:305 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:327 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:337 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:374 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:390 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:417 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:448 | Function is missing a type annotation |
| mypy | tests/test_processors/test_historical_context.py:466 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:475 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:497 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:521 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:546 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:571 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:596 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_historical_context.py:621 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:99 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:106 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:110 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:119 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:127 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:133 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:144 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:151 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:155 | Function is missing a type annotation |
| mypy | tests/agents/specialists/test_registry.py:177 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:181 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:190 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:205 | Function is missing a return type annotation |
| mypy | tests/agents/specialists/test_registry.py:210 | Function is missing a type annotation |
| mypy | tests/contract/test_source_workflow_matrix.py:45 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/test_source_workflow_matrix.py:78 | "StrictModel" has no attribute "kind" |
| mypy | tests/contract/test_source_workflow_matrix.py:81 | "StrictModel" has no attribute "kind" |
| mypy | tests/contract/test_source_workflow_matrix.py:93 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/test_source_workflow_matrix.py:111 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_save_api.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:23 | Function is missing a return type annotation |
| mypy | tests/api/test_save_api.py:33 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:73 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:119 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:144 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:168 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:191 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:202 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:210 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:228 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:235 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:243 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:253 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:270 | Function is missing a type annotation |
| mypy | tests/api/test_save_api.py:281 | Function is missing a type annotation |
| mypy | tests/workflows/test_podcast_script_workflow.py:20 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_podcast_script_workflow.py:47 | Function is missing a return type annotation |
| mypy | tests/security/test_global_error_handler.py:15 | Function is missing a type annotation |
| mypy | tests/security/test_global_error_handler.py:26 | Function is missing a return type annotation |
| mypy | tests/security/test_global_error_handler.py:37 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:22 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:26 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:52 | Function is missing a return type annotation |
| mypy | tests/api/test_error_handler.py:78 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_registry_service.py:26 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_registry_service.py:36 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:42 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:51 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:57 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:63 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:68 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:74 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:91 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:100 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:108 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:121 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:126 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:133 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:149 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:174 | Function is missing a type annotation |
| mypy | tests/test_services/test_model_registry_service.py:203 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_registry_service.py:223 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_registry_service.py:235 | Function is missing a return type annotation |
| mypy | tests/test_services/test_model_registry_service.py:250 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:28 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:44 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:51 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:59 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:70 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:84 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:98 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:120 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:133 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:146 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:159 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:177 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:183 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:209 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:214 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:239 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:269 | Function is missing a return type annotation |
| mypy | tests/services/test_notification_service.py:283 | Function is missing a return type annotation |
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
| mypy | tests/api/test_model_registry_routes.py:17 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:27 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:46 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:71 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:76 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:105 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:150 | Function is missing a type annotation |
| mypy | tests/api/test_model_registry_routes.py:171 | Function is missing a type annotation |
| mypy | tests/workflows/test_audio_digest_workflow.py:15 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_audio_digest_workflow.py:35 | Function is missing a return type annotation |
| mypy | tests/services/test_public_audio_services.py:42 | Function is missing a return type annotation |
| mypy | tests/services/test_public_audio_services.py:42 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/integration/test_summarization_flow_functional.py:38 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_summarization_flow_functional.py:59 | Function is missing a type annotation for one or more arguments |
| mypy | tests/integration/test_summarization_flow_functional.py:72 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:144 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:216 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:307 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:373 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:416 | Function is missing a type annotation |
| mypy | tests/integration/test_summarization_flow_functional.py:448 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:24 | Function is missing a return type annotation |
| mypy | tests/services/test_kb_qa_health.py:34 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:42 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:47 | Function is missing a type annotation for one or more arguments |
| mypy | tests/services/test_kb_qa_health.py:73 | Argument "relevance_score" to "Topic" has incompatible type "float"; expected "_N | None" |
| mypy | tests/services/test_kb_qa_health.py:90 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:108 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:118 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:126 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:140 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:165 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:183 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:203 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:231 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:252 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:267 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:280 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:296 | Function is missing a type annotation |
| mypy | tests/services/test_kb_qa_health.py:315 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:20 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:29 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:37 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:59 | Function is missing a return type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:85 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:109 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:132 | Function is missing a type annotation |
| mypy | tests/unit/test_theme_analyzer_providers.py:148 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:48 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_processors/test_theme_analyzer.py:50 | Returning Any from function declared to return "list[dict[Any, Any]]" |
| mypy | tests/test_processors/test_theme_analyzer.py:140 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:153 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:166 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:178 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:207 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:228 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:240 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:262 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:282 | Function is missing a type annotation |
| mypy | tests/test_processors/test_theme_analyzer.py:354 | Function is missing a type annotation |
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
| mypy | scripts/analyze_themes.py:47 | Missing positional argument "resolved_set" in call to "analyze_themes" of "ThemeAnalyzer" |
| mypy | scripts/analyze_themes.py:57 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | scripts/analyze_themes.py:119 | Unexpected keyword argument "newsletter_count" for "ThemeAnalysis" |
| mypy | scripts/analyze_themes.py:119 | Unexpected keyword argument "newsletter_ids" for "ThemeAnalysis" |
| mypy | scripts/analyze_themes.py:122 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | scripts/analyze_themes.py:123 | "ThemeAnalysisResult" has no attribute "newsletter_ids" |
| mypy | scripts/analyze_themes.py:130 | Argument "processing_time_seconds" to "ThemeAnalysis" has incompatible type "float"; expected "_N | None" |
| mypy | scripts/analyze_themes.py:149 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | scripts/analyze_themes.py:151 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | scripts/analyze_themes.py:160 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | scripts/analyze_themes.py:161 | "ThemeAnalysisResult" has no attribute "newsletter_count" |
| mypy | tests/integration/test_agent_integration.py:226 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:246 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:261 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:275 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:310 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:343 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:356 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:365 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:401 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:435 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/integration/test_agent_integration.py:436 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/integration/test_agent_integration.py:440 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/integration/test_agent_integration.py:441 | Item "None" of "dict[str, Any] | None" has no attribute "get" |
| mypy | tests/integration/test_agent_integration.py:445 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:475 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:500 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/integration/test_agent_integration.py:513 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:577 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:623 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:683 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:709 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:733 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:746 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:765 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:797 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:822 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:850 | Function is missing a return type annotation |
| mypy | tests/integration/test_agent_integration.py:883 | Function is missing a return type annotation |
| mypy | tests/agents/test_conductor.py:22 | Function is missing a type annotation for one or more arguments |
| mypy | tests/agents/test_conductor.py:56 | Function is missing a return type annotation |
| mypy | tests/agents/test_conductor.py:69 | Function is missing a return type annotation |
| mypy | tests/agents/test_conductor.py:77 | Function is missing a return type annotation |
| mypy | tests/agents/test_conductor.py:84 | Function is missing a return type annotation |
| mypy | tests/agents/test_conductor.py:91 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:110 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:121 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:130 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:145 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:158 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:180 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:189 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:198 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:212 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:224 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:239 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:253 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:268 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:282 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:301 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:313 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:324 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:335 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:350 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:369 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:390 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:407 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:418 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:441 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:453 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:473 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:486 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:498 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:521 | Function is missing a type annotation |
| mypy | tests/agents/test_conductor.py:569 | Function is missing a type annotation |
| mypy | tests/workflows/test_podcast_audio_workflow.py:15 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_podcast_audio_workflow.py:20 | Function is missing a return type annotation |
| mypy | tests/workflows/test_podcast_audio_workflow.py:36 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_podcast_audio_workflow.py:66 | Function is missing a return type annotation |
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
| mypy | tests/workflows/test_theme_analysis_workflow.py:27 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_theme_analysis_workflow.py:51 | Function is missing a return type annotation |
| mypy | tests/workflows/test_theme_analysis_workflow.py:107 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_theme_analysis_workflow.py:123 | Function is missing a return type annotation |
| mypy | tests/workflows/test_theme_analysis_workflow.py:150 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_theme_analysis_workflow.py:176 | Function is missing a return type annotation |
| mypy | tests/test_scripts/test_digest_generation.py:17 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:96 | Function is missing a type annotation for one or more arguments |
| mypy | tests/test_processors/test_digest_creator.py:98 | Returning Any from function declared to return "list[dict[Any, Any]]" |
| mypy | tests/test_processors/test_digest_creator.py:125 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:244 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:295 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:318 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:378 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:397 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:409 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:454 | Function is missing a type annotation |
| mypy | tests/test_processors/test_digest_creator.py:468 | Function is missing a return type annotation |
| mypy | tests/test_processors/test_digest_creator.py:488 | Function is missing a return type annotation |
| mypy | tests/processors/test_provider_boundaries.py:99 | Need type annotation for "context" |
| mypy | tests/processors/test_provider_boundaries.py:209 | Cannot assign to a method |
| mypy | tests/processors/test_provider_boundaries.py:237 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:179 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:180 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:183 | Argument "request" to "analyze_themes" of "ThemeAnalyzer" has incompatible type "SimpleNamespace"; expected "ThemeAnalysisRequest" |
| mypy | tests/processors/test_processor_workflow_provenance.py:195 | Item "None" of "_Call | None" has no attribute "kwargs" |
| mypy | tests/processors/test_processor_workflow_provenance.py:210 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:211 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:214 | Argument "request" to "analyze_themes" of "ThemeAnalyzer" has incompatible type "SimpleNamespace"; expected "ThemeAnalysisRequest" |
| mypy | tests/processors/test_processor_workflow_provenance.py:261 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:262 | Cannot assign to a method |
| mypy | tests/processors/test_processor_workflow_provenance.py:428 | Argument 1 to "_ordered_cited_ids" of "PodcastScriptReviser" has incompatible type "SimpleNamespace"; expected "PodcastScript" |
| mypy | scripts/generate_weekly_digest.py:19 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/generate_weekly_digest.py:55 | Missing positional argument "resolved_set" in call to "create_digest" of "DigestCreator" |
| mypy | scripts/generate_weekly_digest.py:148 | Unsupported operand types for / ("None" and "int") |
| mypy | scripts/generate_daily_digest.py:19 | Function is missing a type annotation for one or more arguments |
| mypy | scripts/generate_daily_digest.py:47 | Missing positional argument "resolved_set" in call to "create_digest" of "DigestCreator" |
| mypy | scripts/generate_daily_digest.py:143 | Unsupported operand types for / ("None" and "int") |
| mypy | tests/workflows/test_resource.py:21 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_resource.py:32 | Function is missing a return type annotation |
| mypy | tests/workflows/test_resource.py:52 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_resource.py:62 | Function is missing a return type annotation |
| mypy | tests/workflows/test_resource.py:77 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_resource.py:86 | Function is missing a return type annotation |
| mypy | tests/workflows/test_resource.py:97 | Item "None" of "Any | None" has no attribute "operation_id" |
| mypy | tests/workflows/test_resource.py:113 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_resource.py:134 | Argument "speed" to "AudioDigest" has incompatible type "float"; expected "_N | None" |
| mypy | tests/workflows/test_resource.py:149 | Function is missing a return type annotation |
| mypy | tests/workflows/test_resource.py:205 | Item "None" of "Digest | ThemeAnalysis | PodcastScriptRecord | Podcast | AudioDigest | None" has no attribute "id" |
| mypy | tests/workflows/test_digest_workflow.py:23 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_digest_workflow.py:68 | Function is missing a return type annotation |
| mypy | tests/workflows/test_digest_workflow.py:154 | Argument 1 to "_apply" of "DigestWorkflow" has incompatible type "SimpleNamespace"; expected "Digest" |
| mypy | tests/workflows/test_digest_workflow.py:164 | Function is missing a type annotation for one or more arguments |
| mypy | tests/workflows/test_digest_workflow.py:194 | Function is missing a return type annotation |
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
| mypy | tests/test_utils/test_digest_markdown.py:351 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:374 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:388 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:406 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:418 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:432 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:444 | Function is missing a return type annotation |
| mypy | tests/test_utils/test_digest_markdown.py:467 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:31 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_api_contract_consistency.py:134 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:151 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:167 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:183 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:199 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:223 | Function is missing a type annotation for one or more arguments |
| mypy | tests/regression/test_api_contract_consistency.py:231 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:243 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:253 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:263 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:286 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:297 | Function is missing a return type annotation |
| mypy | tests/regression/test_api_contract_consistency.py:306 | Function is missing a return type annotation |
| mypy | tests/mcp/test_workflow_conformance.py:74 | Argument 1 to "signature" has incompatible type "function"; expected "Callable[..., Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:98 | Argument 1 to "ingest_url" has incompatible type "str"; expected "AnyUrl" |
| mypy | tests/mcp/test_workflow_conformance.py:153 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:154 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:155 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:156 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:168 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:231 | Function is missing a type annotation for one or more arguments |
| mypy | tests/mcp/test_workflow_conformance.py:446 | Function is missing a type annotation for one or more arguments |
| mypy | tests/mcp/test_workflow_conformance.py:512 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:513 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:514 | Value of type "dict[str, Any] | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:536 | Value of type "TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource | str" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:536 | Invalid index type "str" for "str"; expected type "SupportsIndex | slice[Any, Any, Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:537 | Value of type "TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource | str" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:537 | Invalid index type "str" for "str"; expected type "SupportsIndex | slice[Any, Any, Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:538 | Value of type "TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource | str" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:538 | Invalid index type "str" for "str"; expected type "SupportsIndex | slice[Any, Any, Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:539 | Value of type "TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource | str" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:539 | Invalid index type "str" for "str"; expected type "SupportsIndex | slice[Any, Any, Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:540 | Value of type "TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource | str" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:540 | Invalid index type "str" for "str"; expected type "SupportsIndex | slice[Any, Any, Any]" |
| mypy | tests/mcp/test_workflow_conformance.py:563 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:571 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:627 | Function is missing a type annotation for one or more arguments |
| mypy | tests/mcp/test_workflow_conformance.py:648 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:649 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:677 | Value of type "Any | None" is not indexable |
| mypy | tests/mcp/test_workflow_conformance.py:678 | Value of type "Any | None" is not indexable |
| mypy | tests/workflows/test_pipeline_workflow.py:115 | Function is missing a return type annotation |
| mypy | tests/workflows/test_pipeline_workflow.py:350 | "Callable[[int], Digest | Any | None]" has no attribute "assert_not_called" |
| mypy | tests/workflows/test_pipeline_workflow.py:465 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/workflows/test_pipeline_workflow.py:466 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/workflows/test_pipeline_workflow.py:495 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/workflows/test_pipeline_workflow.py:523 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/workflows/test_pipeline_workflow.py:598 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/test_services/test_batch_workers.py:49 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:58 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:64 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:69 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:75 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:88 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:105 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:111 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:119 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:125 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:144 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:147 | Function is missing a return type annotation |
| mypy | tests/test_services/test_batch_workers.py:160 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:179 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:199 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:218 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:252 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:284 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:298 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:313 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:348 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:384 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:411 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:435 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:467 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:499 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:538 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:563 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:582 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:592 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:597 | Function is missing a type annotation |
| mypy | tests/test_services/test_batch_workers.py:623 | Function is missing a return type annotation |
| mypy | tests/security/test_agent_error_leakage.py:16 | Function is missing a return type annotation |
| mypy | tests/queue/test_workflow_handlers.py:26 | Function is missing a return type annotation |
| mypy | tests/queue/test_workflow_handlers.py:29 | Function is missing a return type annotation |
| mypy | tests/queue/test_workflow_handlers.py:29 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:60 | Item "None" of "_Call | None" has no attribute "kwargs" |
| mypy | tests/queue/test_workflow_handlers.py:65 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:117 | Function is missing a type annotation |
| mypy | tests/queue/test_workflow_handlers.py:144 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:269 | Function is missing a type annotation |
| mypy | tests/queue/test_workflow_handlers.py:354 | Function is missing a type annotation |
| mypy | tests/queue/test_workflow_handlers.py:377 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:402 | Item "None" of "_Call | None" has no attribute "kwargs" |
| mypy | tests/queue/test_workflow_handlers.py:406 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:415 | Function is missing a return type annotation |
| mypy | tests/queue/test_workflow_handlers.py:415 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_workflow_handlers.py:419 | Function is missing a return type annotation |
| mypy | tests/queue/test_workflow_handlers.py:419 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_worker_extended.py:17 | Function is missing a return type annotation |
| mypy | tests/queue/test_worker_extended.py:23 | Function is missing a return type annotation |
| mypy | tests/queue/test_worker_extended.py:36 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:47 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:68 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:91 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:100 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:110 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:121 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:131 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:140 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:150 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:165 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:193 | Function is missing a type annotation |
| mypy | tests/queue/test_worker_extended.py:204 | Function is missing a return type annotation |
| mypy | tests/queue/test_worker_extended.py:217 | Function is missing a type annotation |
| mypy | tests/queue/test_operation_controls.py:54 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:95 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:108 | Item "None" of "_Call | None" has no attribute "kwargs" |
| mypy | tests/queue/test_operation_controls.py:117 | Function is missing a return type annotation |
| mypy | tests/queue/test_operation_controls.py:117 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:147 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_controls.py:163 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_controls.py:172 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:185 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:197 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:218 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_controls.py:252 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_controls.py:266 | Function is missing a return type annotation |
| mypy | tests/queue/test_operation_controls.py:266 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:274 | Function is missing a return type annotation |
| mypy | tests/queue/test_operation_controls.py:274 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:299 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:322 | Item "None" of "_Call | None" has no attribute "args" |
| mypy | tests/queue/test_operation_controls.py:361 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:368 | Function is missing a type annotation |
| mypy | tests/queue/test_operation_controls.py:380 | Function is missing a type annotation for one or more arguments |
| mypy | tests/queue/test_operation_controls.py:416 | Function is missing a type annotation |
| mypy | tests/queue/test_batch_maintenance.py:19 | Function is missing a return type annotation |
| mypy | tests/queue/test_batch_maintenance.py:30 | Function is missing a type annotation |
| mypy | tests/queue/test_batch_maintenance.py:32 | Function is missing a return type annotation |
| mypy | tests/queue/test_batch_maintenance.py:39 | Function is missing a type annotation |
| mypy | tests/queue/test_batch_maintenance.py:52 | Function is missing a type annotation |
| mypy | tests/queue/test_batch_maintenance.py:68 | Function is missing a type annotation |
| mypy | tests/real_ingestion/test_pr_tier.py:26 | Function is missing a type annotation for one or more arguments |
| mypy | tests/real_ingestion/test_pr_tier.py:37 | Function is missing a type annotation for one or more arguments |
| mypy | tests/real_ingestion/conftest.py:34 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/security/test_upload_signature_bypass.py:14 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:32 | Function is missing a return type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:43 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:51 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:59 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:67 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:75 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:83 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:92 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:100 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:108 | Function is missing a type annotation |
| mypy | tests/security/test_upload_signature_bypass.py:116 | Function is missing a type annotation |
| mypy | tests/security/test_upload_error_leakage.py:18 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:11 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:37 | Function is missing a type annotation |
| mypy | tests/security/test_settings_auth.py:64 | Function is missing a type annotation |
| mypy | tests/security/test_search_auth.py:28 | Function is missing a type annotation |
| mypy | tests/security/test_search_auth.py:46 | Function is missing a type annotation |
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
| mypy | tests/security/test_error_sanitization.py:198 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:211 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:226 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:242 | Function is missing a type annotation |
| mypy | tests/security/test_error_sanitization.py:256 | Function is missing a type annotation |
| mypy | tests/security/test_digest_auth.py:29 | Function is missing a type annotation |
| mypy | tests/security/test_digest_auth.py:47 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:29 | Function is missing a return type annotation |
| mypy | tests/contract/test_openapi_drift.py:50 | Function is missing a return type annotation |
| mypy | tests/contract/test_openapi_drift.py:81 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:96 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:115 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:149 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:182 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:204 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:212 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:219 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:229 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:235 | Function is missing a type annotation |
| mypy | tests/contract/test_openapi_drift.py:241 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:80 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:95 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/conftest.py:111 | Function is missing a return type annotation |
| mypy | tests/contract/conftest.py:156 | The return type of a generator function should be "Generator" or one of its supertypes |
| mypy | tests/contract/conftest.py:156 | Function is missing a type annotation for one or more arguments |
| mypy | tests/contract/conftest.py:186 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:274 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:285 | Function is missing a return type annotation |
| mypy | tests/contract/conftest.py:295 | Function is missing a type annotation |
| mypy | tests/contract/conftest.py:301 | Function is missing a return type annotation |
| mypy | tests/contract/conftest.py:309 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:22 | Function is missing a return type annotation |
| mypy | tests/api/test_source_write_api.py:41 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:50 | Function is missing a return type annotation |
| mypy | tests/api/test_source_write_api.py:64 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:73 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:78 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:84 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:90 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:100 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:108 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:125 | Function is missing a return type annotation |
| mypy | tests/api/test_source_write_api.py:135 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:139 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:143 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:149 | Function is missing a type annotation |
| mypy | tests/api/test_source_write_api.py:161 | Function is missing a return type annotation |
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
| mypy | tests/api/test_settings_override_api.py:128 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:136 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:150 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:154 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:163 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:174 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:186 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:197 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:204 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:215 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:228 | Function is missing a type annotation |
| mypy | tests/api/test_settings_override_api.py:232 | Function is missing a type annotation |
| mypy | tests/api/test_security_headers.py:15 | Function is missing a return type annotation |
| mypy | tests/api/test_security_headers.py:26 | Function is missing a return type annotation |
| mypy | tests/api/test_security_headers.py:35 | Function is missing a return type annotation |
| mypy | tests/api/test_security_headers.py:42 | Function is missing a type annotation |
| mypy | tests/api/test_security_headers.py:59 | Function is missing a return type annotation |
| mypy | tests/api/test_security_headers.py:68 | Function is missing a return type annotation |
| mypy | tests/api/test_security_headers.py:84 | Function is missing a return type annotation |
| mypy | tests/api/test_script_auth.py:10 | Function is missing a type annotation |
| mypy | tests/api/test_script_auth.py:16 | Function is missing a return type annotation |
| mypy | tests/api/test_pricing_security.py:12 | Function is missing a return type annotation |
| mypy | tests/api/test_pricing_security.py:16 | Function is missing a type annotation |
| mypy | tests/api/test_pricing_security.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_pricing_security.py:41 | Function is missing a type annotation |
| mypy | tests/api/test_pricing_security.py:54 | Function is missing a type annotation |
| mypy | tests/api/test_otel_proxy.py:29 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:60 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:69 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:96 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:119 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:129 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:151 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:162 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:184 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:205 | Function is missing a return type annotation |
| mypy | tests/api/test_otel_proxy.py:217 | Function is missing a return type annotation |
| mypy | tests/api/test_kb_search.py:24 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:33 | Function is missing a return type annotation |
| mypy | tests/api/test_kb_search.py:40 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_kb_search.py:59 | Argument "relevance_score" to "Topic" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_kb_search.py:69 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:93 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:113 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:137 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:152 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:168 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:172 | Function is missing a type annotation |
| mypy | tests/api/test_kb_search.py:178 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:27 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:31 | Function is missing a return type annotation |
| mypy | tests/api/test_kb_lint.py:38 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_kb_lint.py:56 | Argument "relevance_score" to "Topic" has incompatible type "float"; expected "_N | None" |
| mypy | tests/api/test_kb_lint.py:73 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:102 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:128 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:141 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:158 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:179 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:192 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:209 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:226 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:235 | Function is missing a type annotation |
| mypy | tests/api/test_kb_lint.py:249 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:22 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:67 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:86 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:104 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:113 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:131 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:140 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:157 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:173 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:187 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:200 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:214 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:255 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:272 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:290 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:304 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:330 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:345 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:366 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:387 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:416 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:431 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:456 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:485 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:504 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:520 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:538 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:547 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:569 | Function is missing a return type annotation |
| mypy | tests/api/test_job_routes.py:584 | Function is missing a type annotation |
| mypy | tests/api/test_job_routes.py:607 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:19 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:40 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:48 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:60 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:68 | Function is missing a return type annotation |
| mypy | tests/api/test_health_routes.py:79 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:96 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:113 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:130 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:148 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:168 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:182 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:196 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:222 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:262 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:287 | Function is missing a type annotation |
| mypy | tests/api/test_health_routes.py:311 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:22 | Function is missing a return type annotation |
| mypy | tests/api/test_files_api.py:41 | Function is missing a return type annotation |
| mypy | tests/api/test_files_api.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:58 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:72 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:94 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:112 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:138 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:159 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:179 | Function is missing a type annotation |
| mypy | tests/api/test_files_api.py:207 | Function is missing a type annotation |
| mypy | tests/api/test_content_security.py:18 | Function is missing a type annotation |
| mypy | tests/api/test_content_security.py:28 | Function is missing a return type annotation |
| mypy | tests/api/test_content_security.py:37 | Function is missing a type annotation |
| mypy | tests/api/test_chat_routes_mock.py:24 | Function is missing a return type annotation |
| mypy | tests/api/test_chat_routes_mock.py:43 | Function is missing a return type annotation |
| mypy | tests/api/test_chat_routes_mock.py:63 | Function is missing a return type annotation |
| mypy | tests/api/test_chat_routes_mock.py:78 | Function is missing a return type annotation |
| mypy | tests/api/test_canonical_workflow_api.py:21 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:62 | Function is missing a return type annotation |
| mypy | tests/api/test_canonical_workflow_api.py:62 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:110 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:121 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:158 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:176 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:215 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:225 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:271 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:294 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:323 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/test_canonical_workflow_api.py:363 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/api/test_auth_routes.py:330 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:351 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:357 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:363 | Function is missing a type annotation |
| mypy | tests/api/test_auth_routes.py:369 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:47 | Function is missing a return type annotation |
| mypy | tests/api/test_auth_middleware.py:59 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:82 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:153 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:164 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:172 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:180 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:188 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:198 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:206 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:230 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:243 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:251 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:276 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:300 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:327 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:333 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:365 | Function is missing a type annotation |
| mypy | tests/api/test_auth_middleware.py:381 | Function is missing a type annotation |
| mypy | tests/api/test_auth_bypass.py:12 | Function is missing a return type annotation |
| mypy | tests/api/test_auth_bypass.py:19 | Function is missing a type annotation |
| mypy | tests/api/test_auth_bypass.py:23 | Function is missing a return type annotation |
| mypy | tests/api/test_auth_bypass.py:32 | Function is missing a type annotation |
| mypy | tests/api/test_auth_bypass.py:50 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:30 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:40 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_routes.py:61 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:116 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:204 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:212 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:221 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:230 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:238 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:246 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:255 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:263 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:271 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:277 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:283 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:310 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_routes.py:318 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:348 | Function is missing a type annotation |
| mypy | tests/api/test_audit_routes.py:360 | Function is missing a type annotation |
| mypy | tests/api/test_audit_ordering.py:42 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_ordering.py:49 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_ordering.py:65 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_ordering.py:74 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_ordering.py:93 | Function is missing a return type annotation |
| mypy | tests/api/test_audit_ordering.py:117 | Function is missing a type annotation |
| mypy | tests/api/test_audit_ordering.py:137 | Function is missing a type annotation |
| mypy | tests/api/test_audit_ordering.py:143 | Function is missing a type annotation |
| mypy | tests/api/test_audit_ordering.py:161 | Function is missing a type annotation |
| mypy | tests/api/test_audit_ordering.py:167 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:25 | Cannot assign to a type |
| mypy | tests/api/conftest.py:25 | Incompatible types in assignment (expression has type "type[JSON]", variable has type "type[JSONB]") |
| mypy | tests/api/conftest.py:68 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:87 | Function is missing a return type annotation |
| mypy | tests/api/conftest.py:112 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:151 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:159 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:163 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:167 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:171 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:175 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:179 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:188 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:194 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:208 | Function is missing a return type annotation |
| mypy | tests/api/conftest.py:255 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:284 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:319 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:364 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:403 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:448 | Function is missing a type annotation for one or more arguments |
| mypy | tests/api/conftest.py:478 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:496 | Function is missing a type annotation |
| mypy | tests/api/conftest.py:540 | Function is missing a type annotation |
| mypy | tests/contract/test_cross_interface_workflows.py:117 | Function is missing a return type annotation |
| mypy | tests/contract/test_cross_interface_workflows.py:199 | List item 6 has incompatible type "object"; expected "str" |
| mypy | tests/contract/test_cross_interface_workflows.py:201 | List item 8 has incompatible type "object"; expected "str" |
| mypy | tests/contract/test_cross_interface_workflows.py:230 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "Literal['daily', 'weekly']" |
| mypy | tests/contract/test_cross_interface_workflows.py:230 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "str" |
| mypy | tests/contract/test_cross_interface_workflows.py:230 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "ContentQuery | None" |
| mypy | tests/contract/test_cross_interface_workflows.py:230 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "bool" |
| mypy | tests/contract/test_cross_interface_workflows.py:240 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "Literal['daily', 'weekly']" |
| mypy | tests/contract/test_cross_interface_workflows.py:240 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "str" |
| mypy | tests/contract/test_cross_interface_workflows.py:240 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "ContentQuery | None" |
| mypy | tests/contract/test_cross_interface_workflows.py:240 | Argument 1 to "create_digest" has incompatible type "**dict[str, object]"; expected "bool" |
| mypy | tests/contract/test_cross_interface_workflows.py:297 | Need type annotation for "typed_command" |
| mypy | tests/contract/test_cross_interface_workflows.py:299 | Argument 1 to "_error_signature" has incompatible type "ErrorDetails"; expected "dict[str, Any]" |
| mypy | tests/contract/test_cross_interface_workflows.py:338 | Value of type "Any | None" is not indexable |
| mypy | tests/contract/test_cross_interface_workflows.py:349 | Value of type "Any | None" is not indexable |
| mypy | tests/cli_gen_eval/test_descriptor_drift.py:148 | Returning Any from function declared to return "dict[str, Any]" |
| mypy | tests/cli_gen_eval/test_descriptor_drift.py:155 | Returning Any from function declared to return "dict[str, Any]" |
| mypy | tests/cli_gen_eval/test_descriptor_drift.py:196 | Returning Any from function declared to return "dict[str, Any]" |
| mypy | tests/cli_gen_eval/test_descriptor_drift.py:416 | Function is missing a return type annotation |
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
| mypy | tests/cli/test_worker_commands.py:170 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:189 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:197 | Function is missing a type annotation |
| mypy | tests/cli/test_worker_commands.py:217 | Function is missing a return type annotation |
| mypy | tests/cli/test_worker_commands.py:234 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:23 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:28 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:47 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:72 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:87 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:98 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:132 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:160 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:168 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:177 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:186 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:196 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:210 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:224 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:238 | Function is missing a type annotation |
| mypy | tests/cli/test_source_commands.py:255 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:267 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:282 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:293 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:301 | Function is missing a return type annotation |
| mypy | tests/cli/test_source_commands.py:309 | Function is missing a return type annotation |
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
| mypy | tests/cli/test_restore_from_cloud.py:30 | Function is missing a return type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:47 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:80 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:109 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:123 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:138 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:159 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:178 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:197 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:223 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:242 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:262 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:283 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:308 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:325 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:354 | Function is missing a type annotation |
| mypy | tests/cli/test_restore_from_cloud.py:393 | Function is missing a return type annotation |
| mypy | tests/cli/test_remote_backend_guard.py:66 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli/test_remote_backend_guard.py:85 | Function is missing a type annotation for one or more arguments |
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
| mypy | tests/cli/test_neon_commands.py:44 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli/test_neon_commands.py:72 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:88 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:98 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:117 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:132 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:145 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:156 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:174 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:186 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:203 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:217 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:228 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:245 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:256 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:266 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:276 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:287 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:299 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:314 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:329 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:344 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:359 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:404 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:419 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:432 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:446 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:481 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:497 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:512 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:524 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:558 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:573 | Function is missing a return type annotation |
| mypy | tests/cli/test_neon_commands.py:589 | Function is missing a return type annotation |
| mypy | tests/cli/test_manage_refs.py:17 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:44 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:67 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:89 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:110 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:132 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:150 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:169 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_refs.py:186 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:24 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:36 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:49 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:58 | Function is missing a return type annotation |
| mypy | tests/cli/test_manage_commands.py:66 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:75 | Function is missing a type annotation |
| mypy | tests/cli/test_manage_commands.py:90 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:23 | Function is missing a return type annotation |
| mypy | tests/cli/test_kb_commands.py:28 | Function is missing a return type annotation |
| mypy | tests/cli/test_kb_commands.py:38 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:64 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:88 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:110 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:116 | Function is missing a return type annotation |
| mypy | tests/cli/test_kb_commands.py:129 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:135 | Function is missing a return type annotation |
| mypy | tests/cli/test_kb_commands.py:145 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:151 | Function is missing a return type annotation |
| mypy | tests/cli/test_kb_commands.py:174 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:201 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:230 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:246 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:263 | Function is missing a type annotation |
| mypy | tests/cli/test_kb_commands.py:275 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:18 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:46 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:57 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:76 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:87 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:95 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:103 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:118 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:136 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:156 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:174 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:200 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:217 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:232 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:253 | Function is missing a type annotation |
| mypy | tests/cli/test_graph_commands.py:271 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:35 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:45 | Function is missing a return type annotation |
| mypy | tests/cli/test_curate_commands.py:55 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:76 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:94 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:104 | Function is missing a type annotation |
| mypy | tests/cli/test_curate_commands.py:123 | Function is missing a type annotation |
| mypy | tests/cli/test_canonical_workflows.py:110 | Function is missing a return type annotation |
| mypy | tests/cli/test_canonical_workflows.py:375 | Need type annotation for "command" |
| mypy | tests/cli/test_batch_commands.py:24 | Function is missing a type annotation |
| mypy | tests/cli/test_batch_commands.py:26 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:32 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:38 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:60 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:75 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:94 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:134 | Function is missing a return type annotation |
| mypy | tests/cli/test_batch_commands.py:146 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:22 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:27 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:34 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:42 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:46 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:55 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:62 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:68 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:77 | Function is missing a type annotation |
| mypy | tests/cli/test_app.py:89 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:93 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:97 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:101 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:105 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:109 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:113 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:117 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:121 | Function is missing a return type annotation |
| mypy | tests/cli/test_app.py:125 | Function is missing a return type annotation |
| mypy | tests/cli/conftest.py:13 | Function is missing a return type annotation |
| mypy | tests/cli/conftest.py:19 | Function is missing a return type annotation |
| mypy | tests/cli/conftest.py:25 | Function is missing a return type annotation |
| mypy | tests/contract/test_schema_conformance.py:32 | Function is missing a return type annotation |
| mypy | tests/contract/test_schema_conformance.py:59 | Function is missing a type annotation |
| mypy | tests/contract/test_schema_conformance.py:103 | Function is missing a type annotation |
| mypy | tests/contract/test_schema_conformance.py:114 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:66 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:82 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:106 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:123 | Function is missing a type annotation |
| mypy | tests/contract/test_fuzz.py:144 | Function is missing a type annotation |
| mypy | tests/cli/test_main.py:13 | Function is missing a return type annotation |
| mypy | tests/cli/test_main.py:29 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:16 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:39 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:49 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:69 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:77 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:89 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:104 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:112 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:123 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:136 | Function is missing a return type annotation |
| mypy | tests/regression/test_agent_regression.py:148 | Function is missing a return type annotation |
| mypy | tests/cli/test_railway.py:16 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:23 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:27 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:36 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:39 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:50 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:54 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:66 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:69 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:81 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:86 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:98 | Function is missing a type annotation |
| mypy | tests/cli/test_railway.py:113 | Function is missing a type annotation |
| mypy | tests/cli/test_auth_commands.py:52 | Function is missing a type annotation for one or more arguments |
| mypy | tests/cli/test_auth_commands.py:73 | Function is missing a type annotation for one or more arguments |
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
| deferred:open-tasks | N/A | 1.1 Finalize Obsidian clip frontmatter contract (`source_url`, `captured_at`, optional fields) |
| deferred:open-tasks | N/A | 1.2 Publish ACA-recommended Web Clipper template |
| deferred:open-tasks | N/A | 1.3 Define compatibility behavior for missing/extra fields |
| deferred:open-tasks | N/A | 2.1 Add settings for vault path + ingest folder + settle/poll controls |
| deferred:open-tasks | N/A | 2.2 Enforce allowed-root validation and path traversal protection |
| deferred:open-tasks | N/A | 2.3 Add runtime support for `type: obsidian_ingest` in source loader |
| deferred:open-tasks | N/A | 3.1 Add migration for `obsidian_ingest_state` table |
| deferred:open-tasks | N/A | 3.2 Add indexes for `status` and `canonical_url_hash` |
| deferred:open-tasks | N/A | 3.3 Add data access methods for upsert/read transitions |
| deferred:open-tasks | N/A | 4.1 Implement poller for markdown files in ingest folder |
| deferred:open-tasks | N/A | 4.2 Add file settle-window stabilization checks |
| deferred:open-tasks | N/A | 4.3 Skip temp/lock/partial files safely |
| deferred:open-tasks | N/A | 4.4 Add optional watcher trigger with poller fallback |
| deferred:open-tasks | N/A | 5.1 Parse frontmatter and validate required fields |
| deferred:open-tasks | N/A | 5.2 Normalize Obsidian constructs (wikilinks/embeds/callouts) |
| deferred:open-tasks | N/A | 5.3 Extract canonical URL + compute dedupe hashes |
| deferred:open-tasks | N/A | 5.4 Map normalized payload to existing ingestion contract |
| deferred:open-tasks | N/A | 6.1 Deduplicate by canonical URL hash (primary), file hash (fallback) |
| deferred:open-tasks | N/A | 6.2 Record failure classes and actionable error messages |
| deferred:open-tasks | N/A | 6.3 Auto-retry on file changes |
| deferred:open-tasks | N/A | 6.4 Add manual reprocess operation for failed notes |
| deferred:open-tasks | N/A | 7.1 Add optional move-to-processed-folder behavior |
| deferred:open-tasks | N/A | 7.2 Handle filename collisions deterministically |
| deferred:open-tasks | N/A | 7.3 Keep state-table idempotency when move is disabled |
| deferred:open-tasks | N/A | 8.1 Unit: frontmatter parsing, URL canonicalization, hash strategy |
| deferred:open-tasks | N/A | 8.2 Integration: poller + settle behavior under partial-write simulation |
| deferred:open-tasks | N/A | 8.3 Integration: duplicate clip replay and content linking behavior |
| deferred:open-tasks | N/A | 8.4 Migration: `obsidian_ingest_state` create/rollback coverage |
| deferred:open-tasks | N/A | 8.5 Negative-path: path traversal, malformed YAML, invalid URL |
| deferred:open-tasks | N/A | 9.1 Add setup docs for Obsidian Sync/iCloud/Dropbox variants |
| deferred:open-tasks | N/A | 9.2 Add security/privacy and trust-boundary guidance |
| deferred:open-tasks | N/A | 9.3 Add troubleshooting for sync lag, lock files, malformed clips |
| deferred:open-tasks | N/A | 9.4 Maintain `sources.d/obsidian-ingest.yaml.example` |
| deferred:open-tasks | N/A | 9.5 Promote to active `.yaml` only after 2.3 lands |
| deferred:open-tasks | N/A | Align OpenAPI, server, and generated client request/response shapes. |
| deferred:open-tasks | N/A | Document canonical PATCH behavior in current durable design docs or an |
| deferred:open-tasks | N/A | Add component and browser tests for source settings operations. |
| deferred:open-tasks | N/A | Add migration upgrade evidence against a disposable PostgreSQL database. |
| deferred:open-tasks | N/A | Document database source override setup, precedence, and recovery. |
| deferred:open-tasks | N/A | Run contract drift, backend, frontend, migration, and strict OpenSpec |
| deferred:open-tasks | N/A | Done |
| deferred:open-tasks | N/A | Refine effective configuration and router-factory contracts. |
| deferred:open-tasks | N/A | Define a non-executable classifier format, dependency, immutable |
| deferred:open-tasks | N/A | Implement real paired-dataset generation or import. |
| deferred:open-tasks | N/A | Close the training/calibration/enablement bootstrap loop. |
| deferred:open-tasks | N/A | Align configured judges, optional human verdicts, failures, and cost data. |
| deferred:open-tasks | N/A | Align CLI, API, durable operation behavior, and documentation. |
| deferred:open-tasks | N/A | Prove fresh-runtime config consumption, weak-model selection, decision |
| deferred:open-tasks | N/A | Prove tampered, malformed, traversal, symlink-escape, and legacy-pickle |
| deferred:open-tasks | N/A | Planning |
| deferred:open-tasks | N/A | Implementation |
| deferred:open-tasks | N/A | Testing |
| deferred:open-tasks | N/A | Review |
| deferred:open-tasks | N/A | Done |
| deferred:open-tasks | N/A | Define detailed requirements |
| deferred:open-tasks | N/A | Implement core functionality |
| deferred:open-tasks | N/A | Write tests |
| deferred:open-tasks | N/A | Update documentation |
| deferred:open-tasks | N/A | Review and merge |
| deferred:open-tasks | N/A | Planning |
| deferred:open-tasks | N/A | Implementation |
| deferred:open-tasks | N/A | Testing |
| deferred:open-tasks | N/A | Review |
| deferred:open-tasks | N/A | Done |
| deferred:open-tasks | N/A | Define detailed requirements |
| deferred:open-tasks | N/A | Implement core functionality |
| deferred:open-tasks | N/A | Write tests |
| deferred:open-tasks | N/A | Update documentation |
| deferred:open-tasks | N/A | Review and merge |
| deferred:open-tasks | N/A | Inventory current filtering behavior and select retained historical |
| deferred:open-tasks | N/A | Define global/persona/source/command control precedence in typed contracts. |
| deferred:open-tasks | N/A | Retain and implement the language gate with detector/fail-open tests, or |
| deferred:open-tasks | N/A | Align dry-run, rerun, explain, content projection, feedback, and |
| deferred:open-tasks | N/A | Create a reviewed implementation plan and work-package graph. |
| deferred:open-tasks | N/A | Implement retained gaps test-first without restoring legacy execution. |
| deferred:open-tasks | N/A | Validate cross-surface contracts, behavior, documentation, and migration |
| deferred:open-tasks | N/A | Planning |
| deferred:open-tasks | N/A | Implementation |
| deferred:open-tasks | N/A | Testing |
| deferred:open-tasks | N/A | Review |
| deferred:open-tasks | N/A | Done |
| deferred:open-tasks | N/A | Define detailed requirements |
| deferred:open-tasks | N/A | Implement core functionality |
| deferred:open-tasks | N/A | Write tests |
| deferred:open-tasks | N/A | Update documentation |
| deferred:open-tasks | N/A | Review and merge |
| deferred:open-tasks | N/A | Align all image names and version documentation to the canonical build. |
| deferred:open-tasks | N/A | Capture production topology, active revisions/digests, backup, rollback, |
| deferred:open-tasks | N/A | Obtain explicit production deployment authority. |
| deferred:open-tasks | N/A | Deploy or verify the immutable ParadeDB image digest. |
| deferred:open-tasks | N/A | Capture extension/version and `paradedb_bm25` evidence. |
| deferred:open-tasks | N/A | Capture one revision-correlated Langfuse trace round trip. |
| deferred:open-tasks | N/A | Validate health, restore/rollback readiness, documentation, and evidence. |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/roadmap-workflow-surface-reliability/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-reconciliation/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-retry/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-contracts/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-surfaces/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-schema/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-integration/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.codex/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.claude/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/refresh-architecture/scripts/tests/test_enrich_with_treesitter.py:92 | FIXME: broken") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.agents/skills/refresh-architecture/scripts/tests/test_comment_linker.py:39 | FIXME: broken", "language": "python", |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:60 | FIXME: race condition\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:69 | HACK: fragile workaround\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:105 | FIXME: second item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:106 | HACK: third item\n" |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:135 | FIXME: in b\n") |
| markers | .git-worktrees/stuck-content-sweeper-and-requeue-cli/wp-fence/.gemini/skills/bug-scrub/tests/test_collect_markers.py:292 | FIXME: no git here\n") |

## Low / Info Findings

- **Low**: 1191 findings
- **Info**: 0 findings

_(See JSON report for full details)_

## Recommendations

1. Run /fix-scrub --tier auto for quick lint fixes
2. Consolidate deferred items into a follow-up proposal
3. Consider running /fix-scrub --dry-run to preview remediation plan
