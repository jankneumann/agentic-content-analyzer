# Fix Scrub Report

**Branch**: `fix-scrub/2026-08-03`
**Worktree**: `.git-worktrees/fix-scrub/2026-08-03/fix-1785794658`
**Timestamp**: 2026-08-03T22:13:50.495870+00:00
**Source report**: `docs/bug-scrub/bug-scrub-report.json` (2026-08-02 scrub)

## Fixes Applied

- **Auto-fixes**: 54 via `ruff check --fix` (imports, formatting, unused vars where fixable)
- **Follow-up fixes**: 12 remaining auto-tier findings fixed manually after ruff could not auto-apply
  - E741 ambiguous `l` → `level`
  - F821 missing `pytest` import
  - B017 blind `Exception` → `pydantic.ValidationError` (4 sites)
  - RUF059 unused unpacks → `_samples` / `_dataset` (5 sites)
  - C408 `dict()` → dict literal
- **Agent-fixes**: 0 applied
  - Orchestrator selected 10 marker findings in skill fixture files (`.claude`/`.codex` bug-scrub tests)
  - These are intentional fixtures for the markers collector — dispatching would break skill tests
  - Skipped deliberately
- **Manual-only remaining**: ~6080 (mostly mypy missing annotations in tests, deferred OpenSpec tasks, worktree marker noise, ASYNC250 in scripts)

## Files Changed (code)

- `tests/agents/memory/test_memory_models.py`
- `tests/agents/memory/test_provider.py`
- `tests/agents/memory/test_strategies.py`
- `tests/agents/persona/test_loader.py`
- `tests/agents/persona/test_models.py`
- `tests/agents/specialists/test_registry.py`
- `tests/agents/test_agent_models.py`
- `tests/agents/test_conductor.py`
- `tests/config/test_huggingface_papers_sources.py`
- `tests/config/test_routing_config.py`
- `tests/evaluation/test_consensus.py`
- `tests/evaluation/test_criteria.py`
- `tests/evaluation/test_judge.py`
- `tests/ingestion/test_filter_hook.py`
- `tests/integration/conftest.py`
- `tests/models/test_evaluation.py`
- `tests/security/test_agent_error_leakage.py`
- `tests/services/test_evaluation_report.py`
- `tests/services/test_evaluation_service.py`
- `tests/services/test_ingestion_filter.py`
- `tests/test_services/test_chunking.py`
- `tests/test_services/test_content_filter.py`
- `tests/test_services/test_indexing.py`
- `tests/test_services/test_model_pricing_extractor.py`
- `tests/test_storage/test_falkordb_provider.py`
- `tests/test_sync/test_obsidian_frontmatter.py`
- `tests/test_sync/test_obsidian_manifest.py`

## Quality Checks

| Tool | Result | Notes |
|------|--------|-------|
| ruff (touched files) | PASS | All auto-target files clean |
| pytest (targeted suite) | PASS | 176 tests across changed areas |
| full pytest | FAIL/timeout | Pre-existing suite length (300s collector timeout) |
| full mypy | FAIL | Pre-existing ~5705 test annotation findings |
| openspec validate | FAIL | Pre-existing exit code 1 |

## High-severity from scrub

- [x] E741 `tests/agents/test_agent_models.py`
- [x] E302 `tests/security/test_agent_error_leakage.py` (auto)

## Notable manual leftovers

- ASYNC250 blocking `input()` in `scripts/generate_podcast.py` and `scripts/review_digest.py` (8)
- Deferred OpenSpec open tasks (active medium)
- Marker noise under `.git-worktrees/` and skill fixtures
- Mass mypy missing annotations in tests

## Recommendations

1. Re-run `/bug-scrub` after pruning or ignoring `.git-worktrees` in markers collector
2. Follow-up for ASYNC250 CLI scripts (use `asyncio.to_thread` / sync wrappers)
3. Consider excluding `tests/` from default mypy in bug-scrub or raise max-agent-fixes for real `src/` issues only
