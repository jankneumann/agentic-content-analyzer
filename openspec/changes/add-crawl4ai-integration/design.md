# Design: Add Crawl4AI Integration

## Architecture Decision: Local vs Remote Extraction Mode

### Context

Crawl4AI supports two deployment modes:
1. **Local mode**: Embed `AsyncWebCrawler` in-process with Playwright-managed Chromium
2. **Remote mode**: Delegate to a Docker-hosted Crawl4AI server via REST API (port 11235)

### Decision

**Support both modes, selected by settings.** Remote mode is preferred for production (memory isolation, horizontal scaling). Local mode is available for development and environments where Docker isn't available.

### Selection Logic

```
if crawl4ai_enabled == False:
    → no fallback (existing behavior)
elif crawl4ai_server_url is set:
    → remote mode (HTTP POST /md)
else:
    → local mode (AsyncWebCrawler in-process)
```

### Rationale

- Local mode requires ~500MB RAM for Chromium per concurrent page
- Remote mode isolates browser memory from the Python process
- Docker image manages browser pool (permanent/hot/cold tiers) automatically
- REST API is simpler to mock for testing than browser lifecycle

---

## Architecture Decision: Settings Integration Pattern

### Context

The existing `HtmlMarkdownConverter` accepts configuration via constructor kwargs:
```python
def __init__(self, use_crawl4ai_fallback=False, min_length_threshold=200):
```

Callers (RSS, Gmail services, URL extractor) construct it directly. No settings injection exists.

### Decision

**Read settings in `__init__` via `get_settings()` with constructor override.**

```python
def __init__(self, use_crawl4ai_fallback=None, min_length_threshold=None, ...):
    settings = get_settings()
    self.use_crawl4ai_fallback = use_crawl4ai_fallback if use_crawl4ai_fallback is not None else settings.crawl4ai_enabled
    self.min_length_threshold = min_length_threshold if min_length_threshold is not None else settings.crawl4ai_min_length_threshold
    self.server_url = settings.crawl4ai_server_url
    self.cache_mode = self._parse_cache_mode(settings.crawl4ai_cache_mode)
    self.page_timeout = settings.crawl4ai_page_timeout
    self.excluded_tags = settings.crawl4ai_excluded_tags
```

### Rationale

- Constructor overrides enable testing without patching settings
- `get_settings()` provides profile/env/secrets precedence chain
- No changes needed in caller code (RSS, Gmail, URL extractor)
- Default `None` sentinel distinguishes "not passed" from "explicitly False"

---

## Architecture Decision: Remote Server HTTP Client

### Context

Crawl4AI Docker server exposes REST endpoints. The most relevant:
- `POST /md` — extract content as markdown (accepts `url`, optional `f` filter, `q` query, `c` cache mode)
- `POST /crawl` — full crawl with all options (accepts `urls` array + config)

### Decision

**Use `POST /md` for simple extraction, `POST /crawl` for advanced use cases.**

Implementation:
```python
async def _convert_with_crawl4ai_remote(self, url: str) -> str | None:
    async with httpx.AsyncClient(timeout=self.page_timeout / 1000 + 5) as client:
        response = await client.post(
            f"{self.server_url}/md",
            json={"url": url, "c": self.cache_mode.name.lower()},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("result", {}).get("markdown", None)
        return None
```

### Rationale

- `httpx` is already a project dependency (used by URL extractor, CLI API calls)
- `/md` endpoint is minimal — returns markdown directly without full CrawlResult overhead
- Cache mode string maps cleanly to API parameter
- Timeout = page_timeout + 5s network buffer

---

## Architecture Decision: CacheMode Mapping

### Context

Crawl4AI's `CacheMode` enum has 5 values. Our settings use a string for profile/env compatibility.

### Decision

**Map string setting to enum at converter init time:**

```python
CACHE_MODE_MAP = {
    "bypass": CacheMode.BYPASS,
    "enabled": CacheMode.ENABLED,
    "disabled": CacheMode.DISABLED,
    "read_only": CacheMode.READ_ONLY,
    "write_only": CacheMode.WRITE_ONLY,
}
```

For remote mode, the string is passed directly to the REST API (no enum needed).

### Rationale

- Strings are profile/env-friendly (no enum import in YAML)
- Mapping at init catches invalid values early
- Remote mode uses the string as-is (API accepts same values)

---

## Architecture Decision: Docker Service Configuration

### Context

Crawl4AI Docker image (`unclecode/crawl4ai:latest`) requires:
- Port 11235 for REST API
- `--shm-size=1g` for Chromium stability
- ~2GB disk for browser downloads on first start

### Decision

**Add to `docker-compose.yml` under `test` profile (opt-in, like Hoverfly):**

```yaml
crawl4ai:
  image: unclecode/crawl4ai:latest
  container_name: newsletter-crawl4ai
  ports:
    - "11235:11235"
  shm_size: '1g'
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:11235/health || exit 1"]
    interval: 15s
    timeout: 10s
    retries: 5
    start_period: 30s
  profiles:
    - crawl4ai
```

**Makefile targets:**
```makefile
crawl4ai-up:
    docker compose --profile crawl4ai up -d crawl4ai
    @echo "Waiting for Crawl4AI health..."
    @timeout 60 bash -c 'until curl -sf http://localhost:11235/health; do sleep 2; done'

crawl4ai-down:
    docker compose --profile crawl4ai stop crawl4ai

crawl4ai-logs:
    docker compose --profile crawl4ai logs -f crawl4ai
```

### Rationale

- `test` profile keeps it opt-in (matches Hoverfly pattern)
- `start_period: 30s` allows browser download on first start
- Health check ensures service is ready before tests run
- Separate Makefile targets follow existing pattern (opik-up, langfuse-up, hoverfly-up)

---

## Architecture Decision: Error Handling and Fallback Chain

### Context

The extraction pipeline has a fail-safe design: extraction failures never block content ingestion.

### Decision

**Preserve the existing fail-safe pattern. Add remote-specific error handling:**

```
Extraction flow:
1. Trafilatura (primary) → success? → return
2. Quality check → pass? → return
3. Crawl4AI fallback:
   a. If remote mode → HTTP POST /md → success? → return
   b. If local mode → AsyncWebCrawler → success? → return
4. Both fail → return Trafilatura result (even if short) → log warning
```

Remote mode errors (connection refused, timeout, 5xx) are caught and logged — they do NOT propagate as exceptions to ingestion services.

### Rationale

- Content ingestion must always succeed (fail-safe design principle)
- Remote mode adds a new failure class (network errors) not present in local mode
- Returning short Trafilatura output is better than returning None for downstream summarization
- Health check in `/ready` endpoint can report Crawl4AI server status

---

## Component Interaction

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ RSS/Gmail/   │────>│ HtmlMarkdownConverter │────>│ Trafilatura     │
│ URL Ingest   │     │                      │     │ (primary, sync) │
└─────────────┘     │                      │     └─────────────────┘
                    │                      │              │
                    │  quality < threshold │              │ quality check
                    │                      │              ▼
                    │                      │     ┌─────────────────┐
                    │  crawl4ai_enabled?   │────>│ Crawl4AI        │
                    │                      │     │ (fallback)      │
                    └──────────────────────┘     └────┬───────┬────┘
                                                      │       │
                                        server_url?   │       │ no server_url
                                                      ▼       ▼
                                               ┌──────────┐ ┌──────────────┐
                                               │ HTTP API  │ │ Local Browser│
                                               │ :11235/md │ │ AsyncWebCrawl│
                                               └──────────┘ └──────────────┘
```

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Add `crawl4ai` optional dependency group |
| `src/config/settings.py` | Add 5 new `crawl4ai_*` settings fields |
| `src/parsers/html_markdown.py` | Settings integration, remote mode, CacheMode mapping |
| `docker-compose.yml` | Add crawl4ai service under `crawl4ai` profile |
| `Makefile` | Add `crawl4ai-up`, `crawl4ai-down`, `crawl4ai-logs` targets |
| `profiles/base.yaml` | Add `${CRAWL4AI_*}` interpolation references |
| `docs/SETUP.md` | Crawl4AI setup section |
| `docs/ARCHITECTURE.md` | Updated extraction pipeline diagram |
| `CLAUDE.md` | New gotchas and settings |
| `tests/parsers/test_html_markdown.py` | Unit tests for settings + remote mode |
| `tests/integration/fixtures/simulations/crawl4ai_*.json` | Hoverfly simulations |

## Risks

| Risk | Mitigation |
|------|------------|
| Crawl4AI Docker image is large (~2GB) | Use `crawl4ai` profile so it's opt-in |
| Browser memory leaks in local mode | Prefer remote mode for production; Docker manages pool |
| REST API changes in Crawl4AI updates | Pin version in docker-compose; `/md` is stable endpoint |
| Network latency in remote mode | Add 5s buffer to page_timeout for HTTP overhead |
| First request slow (browser cold start) | Docker health check ensures readiness before use |
