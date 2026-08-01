# Ingestion Reliability & Engineering Health

Source analysis: [`docs/IMPROVEMENT_ROADMAP.md`](../../../docs/IMPROVEMENT_ROADMAP.md)
(diagnosis D1–D5, evidence verified at commit `9e4b5fe`).

## Motivation

The ingest pipelines routinely fail end-to-end or work only partially. The 2026-07-04
analysis traced this to five structural conditions: three divergent pipeline drivers that
each run a different source set; no shared adapter contract (bespoke error policies, 17×
copy-pasted persistence, 84 broad exception swallows); failures that are structurally
invisible (partial results discarded, unrecoverable PROCESSING/PARSING states); zero real
ingestion coverage in CI and no alerting; and breadth-over-depth accretion with drifting
documentation. This epic converts that diagnosis into a dependency-ordered set of
OpenSpec changes: first make failure visible, then unify the pipeline, then extract a
shared adapter framework, then pay down structural debt and install knowledge-management
guardrails so the debt does not re-accumulate.

## Capabilities

### Capability: Real ingestion test tiers in CI

Un-skip and implement `test_ingest_actually_writes_to_db`
(`tests/cli/test_ingest_contract.py:383`) using the existing Hoverfly RSS simulation and
the Postgres service already provisioned in CI. Add a PR-blocking integration job running
`pytest -m "integration or hoverfly"` (the 41 integration tests currently collected and
deselected by `ci.yml:152` / `pyproject.toml:285`). Add a nightly `schedule:` workflow
running the Hoverfly-replayed pipeline plus a minimal `live_api` smoke set (one feed per
source type).

**Acceptance Outcomes:**
- A pipeline run whose claimed `items_ingested` does not match the DB row delta fails CI.
- All integration-marked tests execute on every PR.
- Upstream feed/API format breakage produces a red nightly run within 24 hours.

### Pipeline: Persisted ingestion run results

Stop discarding source-level outcomes: pipeline drivers currently read only
`items_ingested` and drop `status`/`errors`/`warnings` (`src/pipeline/runner.py:123`,
`src/cli/pipeline_commands.py:136`). Introduce `IngestionRun` and `SourceRunResult`
tables (run id, source, ok/partial/failed, counts, error strings) written by every
driver, with CLI/API queries.

**Acceptance Outcomes:**
- `aca pipeline daily` exits non-zero or prints a WARN summary when any source is partial or failed.
- Per-source run history is queryable via CLI and API.
- A 1-of-N feed failure is visible in the run record, not only in logs.

### Service: Production telemetry and out-of-band alerting

Instrument the scheduler→queue→worker path: call `record_ingestion` /
`record_pipeline_stage_*` from `src/tasks/content.py` and the worker (today only the CLI
path is instrumented). Add one out-of-band notification channel (email via the existing
SendGrid dependency, or webhook/ntfy) to `notification_service.emit()` for severity ≥
warning, covering `job_failure` and zero-item runs — today delivery is SSE to a
currently-open browser only (`src/services/notification_service.py:141-154`).

**Acceptance Outcomes:**
- Scheduled runs emit per-source ingestion counters.
- A failed or empty overnight run produces an email/push notification by morning.

### Job: Stuck-content sweeper and requeue

This original age-based direct-reset design is superseded by RI-08 in
`openspec/roadmaps/workflow-surface-reliability/roadmap.yaml` and
`openspec/changes/stuck-content-sweeper-and-requeue-cli/design.md`. Reconciliation
must use persisted transition ownership, claim generations, guarded domain writes,
canonical retry budgets, dry-run, and protocol-gated apply. Do not implement
`aca manage requeue-stuck` or direct time-based resets from this proposal.

**Acceptance Outcomes:**
- Replan only from the authoritative workflow-surface-reliability RI-08 artifacts.
- Periodic automatic apply is deferred until telemetry consumes stable outcomes.

### Registry: Unified source registry for all pipeline drivers

One declarative registry (source name → ingest callable, config section, defaults,
enabled flag) consumed by all three drivers, replacing the divergent hardcoded lists in
`pipeline_commands.py:174`, `runner.py:88-109`, and `tasks/content.py:270`. Strangle and
delete the bespoke lists after two green weeks.

**Acceptance Outcomes:**
- Adding a source is one registry entry; all drivers run the identical source set.
- A parity test asserts the three drivers resolve the same sources.
- `aca pipeline daily` behavior no longer depends on backend reachability.

### Component: Per-file isolation for sources.d config loading

A malformed `sources.d/*.yaml` currently aborts loading of all sources
(`src/config/sources.py:349,368`) and is then handled inconsistently (RSS fails loudly;
gmail/scholar/arxiv return `ok, 0 items` via `orchestrator.py:113,559,789`). Isolate
failures per file, record them as source-level errors in the run result, and remove the
catch-and-return-ok paths.

**Acceptance Outcomes:**
- A broken `podcasts.yaml` leaves rss/gmail ingestion unaffected and marks the run partial with a pointed error.
- No source can report success-with-zero-items on a config load failure.

### Adapter: Canonical ingestion result and fail-loud accounting

Every orchestrator function returns `IngestionResponse`; retire bare-`int` returns
(gmail `gmail.py:496`, readwise `orchestrator.py:964`, arxiv `arxiv.py:613`) and delete
the hand-maintained per-source conversion shims. Replace swallow-and-continue per-item
handlers (e.g. `gmail.py:681-684`) with `items_failed` + structured `item_errors`,
using the RSS pattern (`rss.py:136-149`) as the template. Reduce the 84 broad
`except Exception` blocks in `src/ingestion/` to <20, each with a stated tolerance.

**Acceptance Outcomes:**
- Uniform, mypy-enforced return signature across all orchestrator ingest functions.
- Per-item persistence failures increment `items_failed` and carry structured errors.
- Broad exception handlers in `src/ingestion/` reduced below 20, each justified.

### Adapter: Shared ingestion adapter framework

Template-method `BaseIngestionAdapter`: the framework owns iterate → dedupe → persist →
index → hooks → error accounting; adapters implement `fetch_items()` and
`to_content_data()` only. Extract `ContentRepository.upsert()` to eliminate the 17×
duplicated persist block and the per-adapter copies of 3-layer dedup
(`rss.py:559-581` ≈ `gmail.py:547-560`). Migrate adapters strangler-style (RSS first,
then gmail, then the rest), one PR each with row-count parity checks.

**Acceptance Outcomes:**
- One implementation of the ingest loop; adapters contain only fetch/normalize logic.
- The duplicated persist block count drops from 17 to 1.
- A bug fixed in the loop is fixed for every source simultaneously.

### Handler: Uniform downstream hook wiring

The base framework invokes `index_content` and reference extraction for every adapter,
fail-safe after commit. Today `index_content` is missing from podcast, xsearch,
perplexity, arxiv, and readwise (content never searchable), and
`reference_hook.on_content_ingested` has zero production callers despite being
documented as automatic.

**Acceptance Outcomes:**
- Content from all adapters appears in hybrid search.
- Reference extraction runs at ingest time, or docs are corrected to state backfill-only — one or the other, explicitly.

### Component: Remove dead filter configuration

Per-source `content_filter_*` options are silently ignored for every source except blog
(`services/content_filter.py:240` used only by `blog_scraper.py:509`), and the filter
hook's `persona_id` is always `"default"` because no `ingest_*` function accepts it
(`orchestrator.py:53`). Implement both or remove both — silently-ignored configuration
is worse than none.

**Acceptance Outcomes:**
- Every documented per-source filter option either takes effect or fails validation.
- Persona-aware filtering receives a real `persona_id` or the parameter is removed.

### Store: Content-hash dedup correctness

Add a partial unique index on `content_hash` (or maintain the in-batch hash set
in-loop — gmail builds its dedup dict once at `gmail.py:539` and never updates it), with
a regression test for intra-batch duplicates that currently double-insert.

**Acceptance Outcomes:**
- Two same-hash items in one batch produce one canonical row plus one duplicate link.

### Capability: Adapter conformance suite

One parametrized test class run against every registered adapter: response shape, error
accounting, dedup idempotency (second run ingests 0; `force_reprocess` updates in
place), malformed-item tolerance. Hoverfly fixture required per adapter, including the
three currently untested adapters (`arxiv.py`, `files.py`, `substack.py`).

**Acceptance Outcomes:**
- A new adapter cannot register without passing the conformance suite.
- All registered adapters have replayable HTTP fixtures.

### Module: Break the config/storage/services import cycles

Ten import cycles run through `src.config → src.config.models →
src.services.settings_service → src.storage.database → src.config`. Extract the
`Settings` model from anything importing `storage.database`; make the DB-override
service a consumer, not a dependency, of `src.config`.

**Acceptance Outcomes:**
- The import analyzer reports zero cycles.

### CLI: Slim the CLI layer to argument parsing

`src/cli/ingest_commands.py` (1,911 lines, top-2 tech-debt hotspot) and
`pipeline_commands.py` shrink to argument parsing plus calls into services/pipeline;
business logic moves behind the unified registry and pipeline modules.

**Acceptance Outcomes:**
- No ingestion business logic remains in `src/cli/`; CLI files drop below ~500 lines each.

### Module: Partition the services package

Split the flat 54-file, 18.3k-LOC `src/services/` into domain subpackages (`llm/`,
`search/`, `references/`, `pricing/`, `filters/`, `kb/`); split `llm_router.py` (1,754
lines) by provider and `mcp_server.py` (2,722 lines) by tool group. Mechanical moves with
re-export shims, then shim removal on a dated schedule (including the existing
`src/ingestion/reference_extractor.py` shim).

**Acceptance Outcomes:**
- No flat module dump: every service lives in a domain subpackage.
- No src file exceeds ~1,000 lines except by documented exception.

### Component: Rename the filter twins

`content_filter.py` vs `ingestion_filter.py` encode a pre-persist vs post-persist
distinction their names do not carry. Rename with deprecation aliases so a developer
cannot edit the wrong one unknowingly.

**Acceptance Outcomes:**
- Names state the pre/post-persist distinction; old imports warn.

### Capability: Configuration layer reduction and gotcha validators

Publish one authoritative precedence diagram for the ~11 config layers
(`settings.py:251-283` plus profiles, registry YAML, DB overrides, sources.d,
`.secrets.yaml`), then remove at least two layers. Convert the 17 GOTCHAS config
entries — and the top-10 gotchas overall — into startup validations that fail fast with
the gotcha text as the error message.

**Acceptance Outcomes:**
- Documented precedence matches implementation; at least two layers eliminated.
- Top config gotchas are enforced by validators, not prose.

### Capability: Documentation reality sync and drift check

Delete the never-built multi-framework agent thesis from `README.md:101-105` and
`docs/ARCHITECTURE.md:12-20`; document the real `src/agents/` structure; record the
abandonment as an ADR. Add a CI script verifying that file paths referenced in
`ARCHITECTURE.md`/`CLAUDE.md` exist (the `src/config/model_registry.yaml` claim is
already false).

**Acceptance Outcomes:**
- ARCHITECTURE.md describes only code that exists; drift check runs in the lint job.

### Workflow: OpenSpec queue grooming and WIP limits

Archive `add-ingestion-filtering-prioritization` (38/38 tasks done); explicitly close or
re-scope the five changes frozen at 0/N tasks since 2026-04-25; adopt a WIP limit (≤3
active changes) and a 30-day staleness rule.

**Acceptance Outcomes:**
- Zero active changes stale >30 days; completed changes archived within a week.

### Workflow: Single planning system

Fold `docs/plans/` (9 parallel plan docs) into OpenSpec or mark them historical; triage
the 8,295-line bug-scrub/fix-scrub backlogs into ≤20 tracked items and archive the rest.

**Acceptance Outcomes:**
- One live planning surface; backlogs are tracked items, not documents.

### Workflow: Depth gates for new surfaces

Document in CLAUDE.md: a new ingestion source requires a registry entry + conformance
pass + Hoverfly fixture + sources.d schema entry; a new provider/backend requires an ADR
justifying why an existing one cannot serve. Consolidate to one primary + one fallback
among the 3 observability backends and 4 parsing engines.

**Acceptance Outcomes:**
- The gate policy is documented and referenced in review; consolidation targets named with owners.

## Constraints

- Changes must land strangler-style: no big-bang rewrite of the ingestion layer; each
  adapter migration must ship with row-count parity verification against the previous
  implementation.
- Phase 0 observability items must land before any refactoring item starts — refactoring
  an unobserved system is prohibited.
- All new tables require Alembic migrations with single-head verification.
- New feature surfaces (sources, providers, backends) are frozen until the adapter
  framework and conformance suite are complete.
- Existing CLI command names and flags must remain backward compatible.

## Phases

### Phase 0 — Make failure visible

Real ingestion test tiers in CI; persisted ingestion run results; production telemetry
and out-of-band alerting; stuck-content sweeper.

### Phase 1 — One pipeline

Unified source registry; per-file sources.d isolation; canonical ingestion result.

### Phase 2 — Adapter framework

Shared adapter framework; uniform hook wiring; dead filter config removal; content-hash
dedup; adapter conformance suite.

### Phase 3 — Structural debt

Config import cycles; CLI slimming; services partition; filter twins rename; config
layer reduction.

### Phase 4 — Knowledge management

Documentation reality sync; OpenSpec queue grooming; single planning system; depth
gates.

## Out of Scope

- New ingestion sources, providers, or feature surfaces (explicitly frozen).
- Frontend/web work beyond what run-result surfacing requires.
- Knowledge-graph, search-quality, or digest-content improvements.
- Rewriting the agents subsystem; only its documentation is corrected here.
