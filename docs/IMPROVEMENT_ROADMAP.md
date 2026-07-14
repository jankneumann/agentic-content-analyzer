# Improvement Roadmap — Ingestion Reliability & Engineering Health

**Date**: 2026-07-04 · **Baseline commit**: `9e4b5fe` · **Status**: PROPOSED

This roadmap answers one question: *why do the ingest pipelines keep failing end-to-end
(or only partially working), and what sequence of changes fixes that durably?* It is based
on four evidence streams gathered on 2026-07-04:

1. A full end-to-end trace of every ingestion execution path (file:line citations below).
2. A testing/CI/observability audit (why breakage is not caught before the owner notices).
3. A macro-architecture and knowledge-management audit.
4. Automated structural analysis (complexity, duplication, imports) — see
   [`docs/tech-debt/tech-debt-report.md`](tech-debt/tech-debt-report.md) (689 high-severity
   findings; finding IDs `td-*` referenced below).

---

## 1. Diagnosis — why the pipeline "sometimes works"

The failures are not random. They are the predictable output of five structural conditions:

### D1. There are three ingestion pipelines, not one

The same user intent (`aca pipeline daily`) is served by **three independently-maintained
drivers that ingest different source sets**:

| Path | Driver | Runs | Missing |
|---|---|---|---|
| CLI direct (backend down) | `src/cli/pipeline_commands.py:143` | gmail, rss, **blog**, youtube×3, podcast, substack, websearch | scholar, arxiv |
| API/queue pipeline (backend up) | `src/pipeline/runner.py:21` | gmail, rss, youtube×3, podcast, substack, websearch, **scholar, arxiv** | blog |
| Queue `ingest_content` job | `src/tasks/content.py:270` | 7 sources only | blog, scholar, arxiv, xsearch, perplexity, files, url |

Which driver runs is decided at runtime by backend reachability
(`pipeline_commands.py:508` falls back on `httpx.ConnectError`). **The same command
silently ingests different content depending on deployment state.** Every new source must
be wired into three places; in practice each got wired into one.

### D2. No adapter contract — every failure policy is bespoke

There is no base class or Protocol for the ~15 `*ContentIngestionService` classes.
Consequences, each verified:

- **Return types diverge**: gmail returns bare `int` (`src/ingestion/gmail.py:496`),
  RSS returns `IngestionResponse` (`rss.py:469`), scholar/arxiv/podcast return three
  further custom shapes. The 1,249-line orchestrator hand-converts each shape
  (`orchestrator.py:127,602,847`) — a mapping bug in one source is invisible to the others.
- **Silent per-item failure**: gmail catches persistence errors with
  `db.rollback(); continue` — no count change, no error recorded, envelope says `ok`
  (`gmail.py:681-684`). RSS, by contrast, tracks `items_failed` + `item_errors`
  (`rss.py:136-149`). Same event, opposite visibility.
- **84 broad `except Exception` blocks across 18 files in `src/ingestion/`** (top:
  youtube 10, substack 9, orchestrator 9, scholar 7).
- **Copy-paste persistence**: the `Content(...)` construct + `add/flush/commit` block is
  duplicated at **17 sites** across adapters (`td-*` duplication findings, e.g.
  `arxiv.py:466`, `blog_scraper.py:657`, `gmail.py:598`). Every adapter also re-implements
  the 3-layer dedup (`rss.py:559-581` ≈ `gmail.py:547-560`). Each adapter's
  `ingest_content()` is 100–270 lines (`rss.py:462` is 271 lines, complexity 26).
- **Downstream hooks are inconsistently wired**: `index_content` is called by 8 adapters
  but **missing from podcast, perplexity, xsearch, arxiv, readwise** — their content is
  persisted but never searchable. The reference hook `on_content_ingested`
  (`src/services/reference_hook.py:42`) has **zero production callers** — reference
  extraction documented as automatic is actually backfill-only. The filter hook reads
  `persona_id` from kwargs that no `ingest_*` function accepts (`orchestrator.py:53`), so
  persona-aware filtering always runs as `"default"`.

### D3. Failures are structurally invisible

- Both pipeline drivers read only `result.items_ingested` and **discard
  `status`/`errors`/`warnings`** (`runner.py:123`, `pipeline_commands.py:136`). A run
  where 10 of 50 feeds died reports success. Only if *every* source fails does the stage
  fail (`runner.py:145`).
- A broken `sources.d/*.yaml` aborts loading of **all** sources
  (`src/config/sources.py:349,368` — no per-file isolation), and the error is then handled
  inconsistently: RSS fails loudly, while gmail/scholar/arxiv orchestrator wrappers catch
  it and return `items_ingested=0, status="ok"` (`orchestrator.py:113,559,789`).
- **Stuck states with no recovery**: `PROCESSING` is set before the LLM call
  (`src/processors/summarizer.py:90`) but the selector only picks
  `PENDING`/`PARSED` (`summarizer.py:276,331`) — a crash strands rows forever. Same for
  `PARSING` (`url_extractor.py:79`). `FAILED` has no retry except one manual API endpoint
  (`api/content_routes.py:884`). The queue's stale-job sweeper (`queue/setup.py:590`)
  fails the *job* but never resets `Content.status`.
- `content_hash` is indexed but **not unique** (`models/content.py:143`); gmail's
  in-memory hash-dedup dict is built once and never updated in-loop (`gmail.py:539`), so
  intra-batch duplicates double-insert.

### D4. Nothing verifies or watches the real pipeline

- The one test targeting the exact reported symptom — *"orchestrator returns 0, CLI
  reports success"* — exists and is **skipped**
  (`tests/cli/test_ingest_contract.py:383` `test_ingest_actually_writes_to_db`).
- CI deselects every real-behavior marker: `-m "not hoverfly and not contract and not
  smoke and not integration and not live_api"` (`.github/workflows/ci.yml:152`), and
  `pyproject.toml:285` bakes the same exclusion into local defaults. The 41 integration
  tests are collected and dropped. **No workflow has a `schedule:`** — upstream
  API/feed-format changes are invisible until a digest is empty.
- The flagship regression suite (`tests/cli/test_regression_daily_pipeline.py:58-96`)
  mocks all ingestion, summarization, and digest creation, then asserts CLI strings.
- Production (scheduler→worker) ingestion emits **no metrics** —
  `record_ingestion()` is called only from the CLI path (`src/cli/pipeline_commands.py`),
  not from `src/tasks/content.py` or the worker.
- Failure notifications are SSE-to-open-browser only
  (`src/services/notification_service.py:141-154`); a 3 a.m. failure alerts nobody.
  Health checks (`connection_checker`, `kb_health`, `/ready`) are pull-only and don't
  cover source liveness.
- Adapters `arxiv.py`, `files.py`, `substack.py` run in the nightly pipeline with **no
  dedicated unit tests**.

### D5. Breadth is outrunning depth, and knowledge is drifting

- Feature surfaces: 13+ ingestion sources, 3 LLM SDKs, 3 observability backends,
  3 DB providers, 2 graph backends, 4 parsing engines, web + desktop + mobile +
  extension + MCP + CLI + API. Meanwhile the two largest docs in the repo are unfixed-issue
  backlogs (`docs/bug-scrub/` 4,516 + 3,779 lines).
- `docs/ARCHITECTURE.md:12-20` and `README.md:101-105` still headline a multi-framework
  agent comparison (`agents/openai/`, `agents/google/`, `agents/microsoft/`) that
  **does not exist** — only `src/agents/claude/` is real.
- Configuration resolves through **~11 precedence layers** (6 Pydantic sources in
  `src/config/settings.py:251-283`, plus profiles `extends`, `settings/*.yaml` registry,
  DB overrides, `sources.d/`, `.secrets.yaml` interpolation). GOTCHAS devotes 17 entries
  to config footguns — documentation standing in for validation.
- Circular imports at the foundation: `src.config → src.config.models →
  src.services.settings_service → src.storage.database → src.config` (10 cycles found).
- OpenSpec queue rot: 5 of 8 active changes frozen at 0/N tasks since 2026-04-25; one
  change 38/38 complete but never archived. `src/services/` is a flat 54-file, 18.3k-LOC
  grab-bag; god files: `mcp_server.py` 2,722, `cli/ingest_commands.py` 1,911 (business
  logic in the CLI layer), `youtube.py` 1,783, `llm_router.py` 1,754,
  `config/settings.py` 1,610.

**Summary**: content enters through one of three divergent drivers, flows through 15
hand-rolled adapters with inconsistent error semantics, can strand in unrecoverable
states, and no test, metric, or alert observes any of it. "Often doesn't work end-to-end"
is the expected steady state of this structure — not bad luck.

---

## 2. Guiding principles

1. **One path to production.** A source is either registered in the single pipeline or it
   doesn't exist. No behavior may depend on backend reachability.
2. **Contract first.** Adapters implement a narrow, typed interface; the framework owns
   fetch-loop orchestration, dedup, persistence, hooks, and error accounting. Adapters
   only fetch and normalize.
3. **Loud failures, cheap recovery.** Partial failure is a first-class, persisted result.
   Every non-terminal state has a timeout and a re-entry path.
4. **Test the seam that hurts.** The highest-value test is adapter→parse→persist→filter
   against a real database with replayed HTTP — exactly the tier currently switched off.
5. **Detect drift mechanically.** Docs, specs, and config claims that can rot must be
   checked by CI or converted into runtime validation. A gotcha written down twice is a
   missing validator.
6. **Depth gates before breadth.** New surfaces (sources, providers, backends) require
   conformance tests + fixtures + a named owner-path. Until Phases 0–2 land, new feature
   surfaces are frozen.

---

## 3. Roadmap

Effort scale: **S** ≤ ½ day · **M** 1–3 days · **L** ~1 week · **XL** multi-week.
Each item lists acceptance criteria (AC). Phases 0–1 are sequenced; later phases can
overlap. Recommended vehicle: one OpenSpec change per phase-item cluster.

### Phase 0 — Make failure visible (week 1) · *stop flying blind*

The cheapest, highest-leverage work. Nothing here refactors; it only surfaces truth.

| # | Item | Effort | Evidence |
|---|---|---|---|
| 0.1 | **Un-skip and implement `test_ingest_actually_writes_to_db`** using the existing Hoverfly RSS simulation + CI Postgres service. AC: test fails if claimed `items_ingested` ≠ DB row delta. | S | `tests/cli/test_ingest_contract.py:383` |
| 0.2 | **Add a CI integration job**: `pytest -m "integration or hoverfly"` against the Postgres service already provisioned in `ci.yml`. AC: the 41 currently-dropped integration tests execute on every PR. | M | `ci.yml:152`, `pyproject.toml:285` |
| 0.3 | **Add a nightly scheduled workflow** (`schedule:` cron) running the Hoverfly-replayed pipeline plus a small `live_api` smoke set (1 feed per source type). AC: upstream format breakage produces a red nightly run within 24h. | M | no `schedule:` in any workflow |
| 0.4 | **Stop discarding source results**: pipeline drivers persist the full `IngestionResponse` (status, errors, warnings, per-source counts) instead of only `items_ingested`. Introduce an `IngestionRun` + `SourceRunResult` table (run id, source, ok/partial/failed, counts, error strings). AC: `aca pipeline daily` exits non-zero (or prints WARN summary) when any source is partial/failed; results queryable via CLI/API. | M | `runner.py:123`, `pipeline_commands.py:136` |
| 0.5 | **Instrument the production path**: call `record_ingestion` / `record_pipeline_stage_*` from `src/tasks/content.py` and the worker, not just the CLI. AC: scheduled runs emit per-source counters. | S | `src/telemetry/metrics.py:72`, call sites only in `pipeline_commands.py` |
| 0.6 | **Real alerting for `job_failure` and zero-item runs**: add one out-of-band channel (email via existing SendGrid dep, or ntfy/webhook) to `notification_service.emit()` for severity ≥ warning. AC: a 3 a.m. failed or empty run produces a push/email by morning. | M | `notification_service.py:141-154` |
| 0.7 | **Stuck-row sweeper**: a periodic job (reuse pgqueuer cron) that resets `PROCESSING`/`PARSING` rows older than N minutes back to `PARSED`/`PENDING` and re-queues `FAILED` rows up to a retry budget; `aca manage requeue-stuck` CLI. AC: `SELECT count(*) FROM contents WHERE status IN ('processing','parsing') AND updated_at < now()-'1h'` trends to zero. | M | `summarizer.py:90,276`, `queue/setup.py:590` |

**Exit criterion for Phase 0**: you find out about every pipeline failure from a machine,
not from noticing an empty digest.

### Phase 1 — One pipeline (weeks 2–4) · *eliminate the three-driver split*

| # | Item | Effort | Evidence |
|---|---|---|---|
| 1.1 | **Single source registry**: one declarative registry (`SOURCES: dict[str, SourceSpec]` — ingest callable, config section, default kwargs, enabled flag) consumed by all three drivers. Delete the per-driver hardcoded lists. AC: adding a source = one registry entry; `pipeline daily` runs the identical source set in CLI-direct, runner, and queue modes; a parity test asserts the three drivers resolve the same set. | L | `pipeline_commands.py:174`, `runner.py:88-109`, `tasks/content.py:270` |
| 1.2 | **Per-file isolation in `sources.d` loading**: one malformed YAML disables that file only, recorded as a source-level error in the run result (per 0.4), never silently defaulted. Kill the catch-and-return-ok paths. AC: broken `podcasts.yaml` → rss/gmail unaffected, run marked partial with a pointed error; scholar can no longer report `ok, 0 items` on config failure. | M | `config/sources.py:349,368`, `orchestrator.py:113,559,789` |
| 1.3 | **Canonical result type end-to-end**: every orchestrator function returns `IngestionResponse`; retire the bare-`int` returns (gmail, readwise, arxiv `ingest_content`). AC: mypy-enforced uniform signature; orchestrator conversion shims deleted. | M | `gmail.py:496`, `orchestrator.py:964`, `arxiv.py:613` |
| 1.4 | **Fail-loud per-item accounting**: replace swallow-and-continue blocks with `items_failed++` + structured `item_errors` (RSS pattern as the template). Budget: reduce the 84 broad `except Exception` in `src/ingestion/` to <20, each with a comment stating what it intentionally tolerates. | M | `gmail.py:681-684`, RSS pattern `rss.py:136-149` |
| 1.5 | **Deprecate divergence** (per deprecation-and-migration practice): mark `runner.py`/`tasks/content.py` bespoke source lists as strangled once 1.1 lands; delete after two green weeks. | S | — |

**Exit criterion**: the sentence "it depends which path ran" can no longer be true.

### Phase 2 — Adapter framework (weeks 5–8) · *one implementation of the loop*

| # | Item | Effort | Evidence |
|---|---|---|---|
| 2.1 | **`BaseIngestionAdapter` (template method)**: framework owns iterate → dedupe → persist → index → hooks → error accounting; adapters implement `fetch_items()` and `to_content_data()` only. Extract `ContentRepository.upsert()` to kill the 17× persist block and the copied 3-layer dedup. Migrate adapters strangler-style: RSS first (best current shape), then gmail, then the rest, one PR each with before/after row-count parity checks. | XL | dup findings (17 sites), `rss.py:559-581` ≈ `gmail.py:547-560` |
| 2.2 | **Uniform hook wiring**: `index_content` and `on_content_ingested` invoked by the base class for every adapter (fail-safe, after commit). AC: podcast/xsearch/perplexity/arxiv/readwise content appears in search; reference extraction actually runs at ingest time (or the docs/claims are changed to say backfill-only — pick one). | M | missing `index_content` in 5 adapters; `reference_hook.py:42` zero callers |
| 2.3 | **Kill dead configuration**: either implement or remove `content_filter_*` per-source options for non-blog sources (currently silently ignored) and the `persona_id` filter-hook parameter (currently always `"default"`). Silently-ignored config is worse than no config. | M | `content_filter.py:240` only used in `blog_scraper.py:509`; `orchestrator.py:53` |
| 2.4 | **Dedup correctness**: add a partial unique index on `content_hash` (or maintain the in-batch hash set in-loop); regression test for intra-batch duplicates. | S/M | `models/content.py:143`, `gmail.py:539` |
| 2.5 | **Adapter conformance suite**: one parametrized test class run against every registered adapter (contract: response shape, error accounting, dedup idempotency — second run ingests 0, force_reprocess updates in place, malformed item → items_failed not crash). Hoverfly fixture required per adapter; add fixtures for the 3 untested adapters (`arxiv.py`, `files.py`, `substack.py`). AC: a new adapter cannot register without passing conformance. | L | test-coverage matrix; adapters with no tests |

**Exit criterion**: a bug fixed in the ingestion loop is fixed for all sources at once.

### Phase 3 — Structural debt (weeks 9–12, overlappable)

| # | Item | Effort | Evidence |
|---|---|---|---|
| 3.1 | **Break the config/storage/services import cycle**: extract the `Settings` model from anything importing `storage.database`; `settings_service` (DB overrides) becomes a consumer, not a dependency, of `src.config`. AC: import-analyzer reports 0 cycles. | L | 10 cycles through `src.config ↔ src.storage.database ↔ src.services.settings_service` |
| 3.2 | **Move business logic out of the CLI layer**: `cli/ingest_commands.py` (1,911 lines, top-2 hotspot) shrinks to argument parsing + calls into services/pipeline. Ditto `pipeline_commands.py` once 1.1 lands. | L | tech-debt hotspots #1–2 |
| 3.3 | **Partition `src/services/`** into subpackages by domain (`llm/`, `search/`, `references/` (5 modules), `pricing/` (3), `filters/`, `kb/`); split `llm_router.py` (1,754) by provider and `mcp_server.py` (2,722) by tool group. Mechanical moves + re-export shims, then shim removal on a dated schedule (also delete the existing `src/ingestion/reference_extractor.py` shim). | XL | 54-file flat dir, god-file list |
| 3.4 | **Rename the filter twins** to encode the pre/post-persist distinction (`content_filter` → e.g. `adapter_relevance_filter`, `ingestion_filter` → `post_persist_priority_filter`), with deprecation aliases. | S | near-twin confusion documented in `ingestion_filter.py:9-18` |
| 3.5 | **Config-layer reduction**: publish one authoritative precedence diagram, then remove at least two layers (candidates: `.secrets.yaml` interpolation folded into profiles; DB `SettingsOverride` scoped to an allowlist of genuinely-runtime keys). Convert the 17 GOTCHAS config entries into startup validations that fail fast with the gotcha text as the error message. | L | `settings.py:251-283`, GOTCHAS Profiles/DB sections |

### Phase 4 — Knowledge management (continuous, start immediately)

| # | Item | Effort | Evidence |
|---|---|---|---|
| 4.1 | **Make docs true**: delete the multi-framework agent thesis from `README.md` and `docs/ARCHITECTURE.md`; document the real `src/agents/` structure (scheduler/persona/specialists/approval/memory). Record the abandonment as an ADR in `docs/decisions/` so the "why" survives. | S | `ARCHITECTURE.md:12-20`, `README.md:101-105`; only `agents/claude/` exists |
| 4.2 | **Doc-drift check in CI**: a small script that verifies file paths referenced in `ARCHITECTURE.md`/`CLAUDE.md` exist (the `src/config/model_registry.yaml` claim is already false). Run in the lint job. | S/M | stale path claims found in spot-check |
| 4.3 | **Groom the OpenSpec queue**: archive `add-ingestion-filtering-prioritization` (38/38 done); explicitly close or re-scope the 5 changes at 0/N since 2026-04-25; adopt a WIP limit (e.g. ≤3 active changes) and a staleness rule (no commit in 30 days → close or re-justify). | S | `openspec/changes/` audit |
| 4.4 | **One planning system**: fold `docs/plans/` (9 parallel plan docs) into OpenSpec or mark them historical; the bug-scrub/fix-scrub backlogs (8,295 lines) get triaged into ≤20 tracked items, rest archived — a backlog nobody reads is documentation debt, not a plan. | M | `docs/plans/`, `docs/bug-scrub/` |
| 4.5 | **Gotcha-to-validator pipeline**: standing rule — a new GOTCHAS entry must ship with either a runtime validation, a lint rule, or a test that encodes it; the prose is the fallback, not the fix. Retrofit the top 10 (config precedence, enum/StrEnum, autoflush, admin-key header). | M (ongoing) | ~110 gotcha rows across 15 categories |
| 4.6 | **Depth gate policy** (documented in CLAUDE.md): new ingestion source ⇒ registry entry + conformance suite pass + Hoverfly fixture + sources.d schema entry. New provider/backend ⇒ ADR justifying why an existing one can't serve. Consolidation targets: pick 1 primary + 1 fallback among the 3 observability backends and 4 parsing engines; demote the rest to optional extras with explicit "unsupported" status. | S policy / M execution | breadth inventory (§D5) |

---

## 4. Sequencing rationale

- **Phase 0 before everything**: refactoring an unobserved system is how regressions ship
  unnoticed. Every later phase relies on 0.2/0.3 (real tests in CI) as its safety net and
  0.4 (persisted run results) as its success metric.
- **Phase 1 before Phase 2**: unifying *which* code runs must precede unifying *how* it
  runs, otherwise the adapter framework gets built three times.
- **Phase 2 is the payoff**: it converts your recurring symptom class ("this one source
  broke again, differently") into a single-fix domain.
- **Phase 3 is deliberately after 0–2**: import cycles and god files are a velocity tax,
  not the acute reliability problem; they're safe to defer but not to skip — 3.1 in
  particular is a latent "works in CLI, breaks in worker" generator.
- **Phase 4 runs in parallel** because it's mostly editorial and policy work that
  prevents the debt from re-accumulating while the code phases execute.

## 5. Measuring success

Track weekly (Phase 0 makes all of these queryable):

| Metric | Now | Target (12 weeks) |
|---|---|---|
| Pipeline runs with silent partial failure | unknown (invisible) | 0 — all partials reported + alerted |
| Sources runnable from all drivers | 7–9 of 15, path-dependent | 15 of 15, one driver |
| Content rows stuck >24h in PARSING/PROCESSING/FAILED | unknown | 0 (swept automatically) |
| Integration tests executed in CI | 0 of 41 | all, on every PR + nightly live smoke |
| Adapters with conformance coverage | 0 | all registered adapters |
| Broad `except Exception` in `src/ingestion/` | 84 | <20, each justified |
| Duplicated persist blocks | 17 | 1 (`ContentRepository`) |
| Import cycles | 10 | 0 |
| Active OpenSpec changes stale >30 days | 6 of 8 | 0 (WIP limit enforced) |
| MTTD for a broken source | days–weeks (human notices) | <24h (nightly run / alert) |

Re-run `/tech-debt-analysis` and the architecture refresh at each phase boundary and diff
the JSON reports — addressed findings should disappear; new-code findings should not grow.

## 6. Appendix — analysis provenance

- Structural report: `docs/tech-debt/tech-debt-report.md` (high-severity subset; generated
  by `.claude/skills/tech-debt-analysis`, analyzers: complexity, duplication, imports;
  the coupling analyzer's graph input was malformed and its 3 findings were discarded).
- Full-severity counts: 3,293 findings (689 high) — 636 long methods, 424 complex
  functions, 137 large files, 1,537 duplicate groups, 10 import cycles.
- The `refresh-architecture` pipeline itself fails in a fresh checkout (4 analyzer
  errors); artifacts for this analysis were produced by invoking
  `analyze_python.py`/`compile_architecture_graph.py` manually — fixing that script is a
  small candidate for Phase 4 tooling hygiene.
- All file:line citations in this document were verified against commit `9e4b5fe`; the
  four highest-impact claims (three-driver divergence, PROCESSING black hole, uncalled
  reference hook, dead `persona_id`) were independently re-verified by direct inspection.
