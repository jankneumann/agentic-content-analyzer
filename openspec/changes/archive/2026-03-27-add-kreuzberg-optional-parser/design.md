## Architecture Decisions

### AD-1: Async-Native Adapter Without Executor Wrapping

**Decision**: Implement `KreuzbergParser` using Kreuzberg's native `extract_file()` / `extract_bytes()` async API directly, without `asyncio.run_in_executor()`.

**Alternatives considered**:
- A. Sync wrapper with executor (how Docling works) — unnecessary overhead since Kreuzberg is async-first
- B. Sync-only adapter — would block the event loop during parsing

**Trade-offs**: Direct async reduces latency (~1 fewer thread hop per parse). Requires Kreuzberg >= 4.0 which guarantees stable async API.

**Consequences**: `KreuzbergParser.parse()` is a true coroutine. Testing requires `@pytest.mark.asyncio` + `AsyncMock` for the underlying `extract_file` call.

---

### AD-2: Lazy Import with Graceful Degradation

**Decision**: Follow the Docling pattern — lazy-import Kreuzberg inside the parser class, catch `ImportError`, and log a warning. The router skips Kreuzberg when unavailable.

**Alternatives considered**:
- A. Eager import at module level — crashes the app when Kreuzberg isn't installed
- B. Sentinel stub class — over-engineered; the router already handles `None` parsers

**Trade-offs**: Lazy import adds ~5ms on first parse (Rust native module load). Zero cost when disabled.

**Consequences**: `get_parser_router()` wraps Kreuzberg construction in `try/except ImportError`, identical to the Docling pattern. No startup penalty when `enable_kreuzberg=False`.

---

### AD-3: Markdown as Primary Output Format

**Decision**: Configure Kreuzberg with `OutputFormat.MARKDOWN` and map directly to `DocumentContent.markdown_content`. Extract tables, metadata, and links from the `ExtractionResult` fields.

**Alternatives considered**:
- A. Plain text output + post-processing — loses structure
- B. HTML output + Trafilatura conversion — unnecessary double conversion

**Trade-offs**: Markdown is the codebase's canonical format and what downstream LLM consumers expect. Kreuzberg's Markdown output includes heading hierarchy, list structure, and inline links.

**Consequences**: `KreuzbergParser` sets `parser_used="kreuzberg"` and populates `DocumentContent` identically to existing parsers. No downstream changes needed in summarization or digest creation.

---

### AD-4: Router Extension with Preference Map

**Decision**: Add an optional `kreuzberg_parser` parameter to `ParserRouter.__init__()` and a `kreuzberg_preferred_formats` setting that overrides `ROUTING_TABLE` entries per format. OCR routing to Docling takes absolute precedence.

**Alternatives considered**:
- A. Replace ROUTING_TABLE entries statically — too coarse, loses ability to A/B test per format
- B. Priority-ranked parser list per format — over-engineered for 3 parsers

**Trade-offs**: The preference map is additive — formats not in the map use existing routing. This makes rollout incremental (promote one format at a time).

**Routing precedence** (highest to lowest):
1. OCR override → Docling (unchanged)
2. `prefer_structured=True` for PDF → Docling (unchanged)
3. `kreuzberg_preferred_formats` set membership → Kreuzberg
4. `ROUTING_TABLE` default → existing parser
5. Fallback → MarkItDown (unchanged)

**Consequences**: Router gains `_has_kreuzberg` flag and `_kreuzberg_preferred` set. Fallback from Kreuzberg goes to the `ROUTING_TABLE` default for that format (usually MarkItDown), not to Docling.

---

### AD-5: Shadow Evaluation as Parallel Parse with Telemetry

**Decision**: When `kreuzberg_shadow_formats` is non-empty and contains the document's format, run Kreuzberg as a fire-and-forget `asyncio.create_task()` alongside the canonical parser. Emit structured comparison telemetry (latency delta, content length delta, warning counts) via the existing observability provider.

**Alternatives considered**:
- A. Sequential shadow parse after canonical — doubles latency
- B. Separate batch job for shadow evaluation — too complex for initial rollout
- C. Log-only comparison — loses structured metrics for promotion decisions

**Trade-offs**: Parallel shadow adds resource overhead proportional to shadow format volume. The fire-and-forget pattern means shadow failures don't block canonical ingestion.

**Consequences**: Shadow telemetry uses existing `src/telemetry` infrastructure — no new observability dependencies. Shadow results are logged and metered but never persisted to the `Content` table.

---

### AD-6: Optional Dependency Group

**Decision**: Add `kreuzberg` as an optional dependency group in `pyproject.toml` (like `ocr` and `crawl4ai`). Pin to `>=4.0.0,<5.0.0` for API stability.

**Alternatives considered**:
- A. Always-installed dependency — bloats base install for users who don't need it
- B. Unpinned version — Kreuzberg's Rust core has breaking changes across majors

**Trade-offs**: Users opt in with `uv sync --extra kreuzberg`. Docker builds can include/exclude via build arg.

**Consequences**: CI needs a test matrix entry with `--extra kreuzberg` for parser-specific tests. The `Dockerfile` gains an optional `--extra kreuzberg` flag alongside the existing `--extra braintrust` pattern.

---

## Component Interaction

```
┌──────────────────────────────────────────────────────────┐
│  upload_routes.py / files.py                             │
│  get_parser_router()                                     │
│    ├─ MarkItDownParser()          (always)               │
│    ├─ DoclingParser()             (if enable_docling)     │
│    ├─ KreuzbergParser()           (if enable_kreuzberg)   │
│    └─ YouTubeParser()             (always)               │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  ParserRouter.route()                                    │
│                                                          │
│  1. OCR override?        → Docling                       │
│  2. prefer_structured?   → Docling                       │
│  3. kreuzberg_preferred? → Kreuzberg (fallback: table)   │
│  4. ROUTING_TABLE        → default parser                │
│  5. fallback             → MarkItDown                    │
│                                                          │
│  Shadow mode: if format in kreuzberg_shadow_formats      │
│    → fire-and-forget Kreuzberg parse + emit telemetry    │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  KreuzbergParser.parse()                                 │
│                                                          │
│  kreuzberg.extract_file(path, config=ExtractionConfig(   │
│    output_format=OutputFormat.MARKDOWN                   │
│  ))                                                      │
│  → ExtractionResult                                      │
│    .content      → markdown_content                      │
│    .metadata     → DocumentMetadata                      │
│    .tables       → list[TableData]                       │
│    .quality_score → logged for evaluation                │
└──────────────────────────────────────────────────────────┘
```

## Settings Additions

```python
# src/config/settings.py — new fields
enable_kreuzberg: bool = False                    # Disabled by default
kreuzberg_preferred_formats: str = ""             # Comma-separated, e.g. "docx,epub,html"
kreuzberg_shadow_formats: str = ""                # Formats for shadow comparison
kreuzberg_max_file_size_mb: int = 100             # Size limit (matches Docling default)
kreuzberg_timeout_seconds: int = 120              # Lower than Docling (Kreuzberg is faster)
```

## File Impact Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | modify | Add `kreuzberg` optional dependency group |
| `src/config/settings.py` | modify | Add Kreuzberg settings fields |
| `src/parsers/kreuzberg_parser.py` | **new** | KreuzbergParser implementation |
| `src/parsers/router.py` | modify | Add kreuzberg_parser param, preference routing |
| `src/api/upload_routes.py` | modify | Wire Kreuzberg into `get_parser_router()` |
| `src/ingestion/files.py` | none | No changes (uses router abstraction) |
| `tests/parsers/test_kreuzberg_parser.py` | **new** | Unit tests for adapter |
| `tests/parsers/test_router.py` | modify | Add Kreuzberg routing/fallback tests |
| `tests/api/test_upload_routes.py` | modify | Add Kreuzberg-enabled format tests |
