# Design: CLI as Thin HTTP Client

## Architecture

### Current Architecture

```
┌─────────┐     ┌──────────────┐     ┌──────────┐
│  CLI    │────▶│  Orchestrator │────▶│ Services │  (inline, no tracking)
└─────────┘     └──────────────┘     └──────────┘

┌─────────┐     ┌─────┐     ┌────────────┐     ┌──────────────┐     ┌──────────┐
│ Web UI  │────▶│ API │────▶│ Job Queue  │────▶│  Worker      │────▶│ Services │
└─────────┘     └─────┘     └────────────┘     └──────────────┘     └──────────┘
```

### Target Architecture

```
┌─────────┐
│  CLI    │──┐
└─────────┘  │  httpx     ┌─────┐     ┌────────────┐     ┌────────┐     ┌──────────┐
             ├──────────▶│ API │────▶│ Job Queue  │────▶│ Worker │────▶│ Services │
┌─────────┐  │           └─────┘     └────────────┘     └────────┘     └──────────┘
│ Web UI  │──┘
└─────────┘

┌─────────┐  --direct    ┌──────────────┐     ┌──────────┐
│  CLI    │─────────────▶│  Orchestrator │────▶│ Services │  (fallback)
└─────────┘              └──────────────┘     └──────────┘
```

## Component Design

### 1. Settings Extension

Add `api_base_url` to `src/config/settings.py`:

```python
# New field in Settings class
api_base_url: str = "http://localhost:8000"
api_timeout: int = 300  # 5 minutes for long-running ingestion
```

Profile wiring in `profiles/base.yaml`:
```yaml
settings:
  api:
    api_base_url: "http://localhost:8000"
    api_timeout: 300
```

Profile override in `profiles/railway.yaml`:
```yaml
settings:
  api:
    api_base_url: "${API_BASE_URL:-https://your-app.up.railway.app}"
    api_timeout: 300
```

### 2. API Client (`src/cli/api_client.py`)

Sync httpx client with profile-aware configuration:

```python
class ApiClient:
    """Thin HTTP client for CLI → API communication."""

    def __init__(self, base_url: str, admin_key: str | None, timeout: float = 300):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"X-Admin-Key": admin_key} if admin_key else {},
        )

    # Ingestion
    def ingest(self, source: str, **params) -> IngestResponse: ...
    def stream_ingest_status(self, task_id: str) -> Iterator[SSEEvent]: ...

    # Summarization
    def summarize(self, **params) -> SummarizeResponse: ...
    def stream_summarize_status(self, task_id: str) -> Iterator[SSEEvent]: ...

    # Pipeline
    def run_pipeline(self, pipeline_type: str, **params) -> PipelineResponse: ...
    def stream_pipeline_status(self, task_id: str) -> Iterator[SSEEvent]: ...

    # Digest
    def create_digest(self, **params) -> dict: ...

    # Jobs
    def list_jobs(self, **params) -> JobListResponse: ...
    def get_job(self, job_id: int) -> JobRecord: ...
    def retry_job(self, job_id: int) -> dict: ...

    # Health
    def health_check(self) -> bool: ...

    def close(self): self._client.close()
```

Factory function:
```python
def get_api_client() -> ApiClient:
    from src.config.settings import get_settings
    settings = get_settings()
    return ApiClient(
        base_url=settings.api_base_url,
        admin_key=settings.admin_api_key,
        timeout=settings.api_timeout,
    )
```

### 3. Direct Mode (`src/cli/output.py`)

Add alongside existing `_json_mode`:

```python
_direct_mode: bool = False

def is_direct_mode() -> bool:
    return _direct_mode

def _set_direct_mode(value: bool) -> None:
    global _direct_mode
    _direct_mode = value
```

Global callback in `src/cli/app.py`:
```python
direct: bool = typer.Option(False, "--direct", help="Run directly without backend API")
```

### 4. SSE Progress Display (`src/cli/progress.py`)

```python
def stream_job_progress(
    client: ApiClient,
    task_id: str,
    label: str,
    json_mode: bool = False,
) -> dict:
    """Stream SSE events and display Rich progress. Returns final result."""
```

- Rich mode: `Status` spinner with progress message updates
- JSON mode: Final JSON result only (no intermediate output)
- Returns the terminal SSE event data as dict

### 5. Extended IngestRequest

Extend `src/api/content_routes.py` `IngestRequest`:

```python
class IngestRequest(BaseModel):
    source: str = Field(default="gmail")  # Accept string, not just ContentSource enum
    max_results: int | None = Field(default=None, ge=1, le=200)  # None = use source config
    days_back: int = Field(default=7, ge=1, le=90)
    force_reprocess: bool = Field(default=False)
    # Source-specific optional fields
    query: str | None = None           # gmail: label query
    prompt: str | None = None          # xsearch/perplexity: search prompt
    max_threads: int | None = None     # xsearch: max threads
    recency_filter: str | None = None  # perplexity: day/week/month
    context_size: str | None = None    # perplexity: low/medium/high
    transcribe: bool = True            # podcast: enable transcription
    session_cookie: str | None = None  # substack: session cookie override
    public_only: bool = False          # youtube: skip private playlists
    url: str | None = None             # url ingestion: target URL
    title: str | None = None           # url/file: content title override
    tags: list[str] | None = None      # url: content tags
    notes: str | None = None           # url: content notes
```

### 6. Extended Worker Source Map

Extend `src/queue/worker.py` `ingest_content` handler:

```python
source_map = {
    # Existing
    "gmail": (ingest_gmail, {"max_results": max_results, "query": query}),
    "rss": (ingest_rss, {"max_entries_per_feed": max_results}),
    "youtube": (ingest_youtube, {"max_videos": max_results, "use_oauth": not public_only}),
    "youtube-playlist": (ingest_youtube_playlist, {"max_videos": max_results}),
    "youtube-rss": (ingest_youtube_rss, {"max_videos": max_results}),
    "podcast": (ingest_podcast, {"max_entries_per_feed": max_results}),
    "substack": (ingest_substack, {"max_entries_per_source": max_results}),
    # New
    "xsearch": (ingest_xsearch, {"prompt": prompt, "max_threads": max_threads}),
    "perplexity": (ingest_perplexity_search, {"prompt": prompt, "max_results": max_results, ...}),
    "url": (ingest_url, {"url": url, "title": title, "tags": tags, "notes": notes}),
}
```

### 7. Pipeline API

New `src/api/pipeline_routes.py`:

```python
router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

class PipelineRequest(BaseModel):
    pipeline_type: str = "daily"  # daily | weekly
    date: str | None = None       # Override date (YYYY-MM-DD)
    use_queue: bool = True        # Enqueue summarization or run inline

class PipelineResponse(BaseModel):
    job_id: int
    message: str
    pipeline_type: str

@router.post("/run")
async def run_pipeline(request: PipelineRequest) -> PipelineResponse: ...

@router.get("/status/{job_id}")
async def pipeline_status(job_id: int) -> StreamingResponse: ...
```

Pipeline runner extracted to `src/pipeline/runner.py` (shared between worker and `--direct` CLI).

### 8. Gmail Config Fix

In `src/ingestion/orchestrator.py`:

```python
def ingest_gmail(*, query=None, max_results=None, after_date=None, force_reprocess=False):
    from src.config.sources import load_sources_config
    config = load_sources_config()
    gmail_sources = config.get_gmail_sources()
    if gmail_sources:
        source = gmail_sources[0]
        query = query or source.query
        max_results = max_results or source.max_results  # Uses sources.d/gmail.yaml value
    else:
        max_results = max_results or 10  # Fallback default
    ...
```

## CLI Command Pattern

Each converted command follows this pattern:

```python
@app.command("gmail")
def gmail(query: str = ..., max: int = ..., days: int = ..., force: bool = False):
    if is_direct_mode():
        return _gmail_direct(query, max, days, force)

    client = get_api_client()
    try:
        response = client.ingest(source="gmail", query=query, max_results=max, ...)
    except httpx.ConnectError:
        if not is_json_mode():
            console.print("[yellow]Backend unavailable, running directly...[/yellow]")
        return _gmail_direct(query, max, days, force)

    result = stream_job_progress(client, response.task_id, label="Gmail ingestion")
    _display_result(result, source="gmail")
```

## Alternatives Considered

### 1. gRPC instead of HTTP/REST
Rejected — REST is already the API's protocol, adding gRPC doubles the surface area.

### 2. CLI calls orchestrator but enqueues jobs itself
Rejected — requires CLI to have DB access, which defeats the goal of a thin client that can target remote backends.

### 3. WebSocket instead of SSE for progress
Rejected — SSE is simpler, already implemented, and sufficient for unidirectional progress updates.

## Risks

| Risk | Mitigation |
|------|-----------|
| Backend unavailable breaks CLI | Auto-fallback to direct mode with warning |
| SSE connection drops | Reconnect with `Last-Event-ID`, or fall back to polling `/api/v1/jobs/{id}` |
| Latency increase (network hop) | Acceptable for cloud; `--direct` available for local dev |
| Auth complexity | CLI reads `admin_api_key` from same Settings/profile — no new credential flow |
| Breaking existing scripts | CLI output format unchanged; only execution path changes |

## Phase Dependencies

```
Phase 1: Foundation (Settings, ApiClient, --direct flag)
    ↓
Phase 2: API extensions (IngestRequest, worker source map, Gmail config)
    ↓
Phase 3: CLI ingestion conversion ──┬── Phase 4: Pipeline API
                                    ├── Phase 5: Summarize/Digest CLI
                                    └── Phase 6: Remaining CLI commands
```
