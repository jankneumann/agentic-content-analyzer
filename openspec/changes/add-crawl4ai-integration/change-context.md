# Change Context: add-crawl4ai-integration

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Test(s) | Files Changed | Evidence |
|--------|-------------|-------------|---------|---------------|----------|
| wce.1 | specs/web-content-extraction/spec.md | Crawl4AI fallback when Trafilatura insufficient | `test_fallback_triggered_on_low_quality` | `src/parsers/html_markdown.py:395-411` | pass 4091670 |
| wce.2 | specs/web-content-extraction/spec.md | Crawl4AI disabled by default | `test_disabled_by_default`, `test_no_fallback_when_disabled` | `src/config/settings.py:673` | pass 4091670 |
| wce.3 | specs/web-content-extraction/spec.md | Enable via settings | `test_defaults_from_settings` | `src/config/settings.py:673`, `src/parsers/html_markdown.py:165-168` | pass 4091670 |
| wce.4 | specs/web-content-extraction/spec.md | CacheMode string mapping | `test_build_cache_mode_map_with_crawl4ai`, `test_valid_cache_mode_resolves` | `src/parsers/html_markdown.py:109-127` | pass 4091670 |
| wce.5 | specs/web-content-extraction/spec.md | Invalid cache mode raises ValueError | `test_invalid_cache_mode_raises` | `src/parsers/html_markdown.py:198-202` | pass 4091670 |
| wce.6 | specs/web-content-extraction/spec.md | Page timeout configuration | `test_constructor_overrides_settings` | `src/parsers/html_markdown.py:174-176` | pass 4091670 |
| wce.7 | specs/web-content-extraction/spec.md | Excluded tags configuration | `test_constructor_overrides_settings` | `src/parsers/html_markdown.py:177-179` | pass 4091670 |
| wce.8 | specs/web-content-extraction/spec.md | Constructor override for testing | `test_constructor_overrides_settings` | `src/parsers/html_markdown.py:140-159` | pass 4091670 |
| wce.9 | specs/web-content-extraction/spec.md | Remote extraction via HTTP POST /md | `test_remote_extraction_success` | `src/parsers/html_markdown.py:318-357` | pass 4091670 |
| wce.10 | specs/web-content-extraction/spec.md | Remote server unavailable — fail-safe | `test_remote_extraction_connection_refused` | `src/parsers/html_markdown.py:345-350` | pass 4091670 |
| wce.11 | specs/web-content-extraction/spec.md | Remote server error — fail-safe | `test_remote_extraction_server_error` | `src/parsers/html_markdown.py:340-344` | pass 4091670 |
| wce.12 | specs/web-content-extraction/spec.md | Local mode when no server URL | `test_dispatches_to_local_when_no_server_url` | `src/parsers/html_markdown.py:314-316` | pass 4091670 |
| wce.13 | specs/web-content-extraction/spec.md | Docker service with port 11235, shm_size 1g | (infra) | `docker-compose.yml:75-88` | pass 4091670 |
| wce.14 | specs/web-content-extraction/spec.md | Health check in /ready endpoint | (infra) | `src/api/health_routes.py:129-136` | pass 4091670 |
| wce.15 | specs/web-content-extraction/spec.md | Fail-safe: import unavailable | `test_build_cache_mode_map_without_crawl4ai` | `src/parsers/html_markdown.py:362-402` | pass 4091670 |
| wce.16 | specs/web-content-extraction/spec.md | Graceful degradation chain | `test_fallback_failure_returns_trafilatura_result` | `src/parsers/html_markdown.py:395-460` | pass 4091670 |

## Design Decision Trace

| Decision | Rationale | Implementation |
|----------|-----------|----------------|
| Support both local and remote modes | Memory isolation + horizontal scaling for production | `_convert_with_crawl4ai()` dispatches based on `server_url` |
| Settings with None sentinel pattern | Constructor overrides for testing without patching Settings | `__init__()` accepts `None` defaults, falls back to `get_settings()` |
| Lazy CacheMode mapping | crawl4ai is optional dep, can't import at module level | `_build_cache_mode_map()` called on first `_resolve_cache_mode()` |
| Docker service under `crawl4ai` profile | Opt-in (like Hoverfly), ~2GB image shouldn't be default | `profiles: [crawl4ai]` in docker-compose.yml |
| httpx for remote mode | Already a project dependency, async-native | `httpx.AsyncClient` in `_convert_with_crawl4ai_remote()` |

## Coverage Summary

- **Requirements traced**: 16
- **Tests mapped**: 16 (14 unit tests + 2 infrastructure verifications)
- **Evidence collected**: 16/16
- **Gaps**: 0
- **Deferred**: 0
