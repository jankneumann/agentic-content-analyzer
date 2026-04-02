# Proposal: LLM Router Evaluation & Dynamic Routing

**Change ID**: `llm-router-evaluation`
**Status**: Proposed
**Created**: 2026-04-02

## Why

The current `LLMRouter` assigns a **single fixed model** to each of the 19 pipeline steps (e.g., Claude Haiku for all summarizations, Claude Sonnet for all digests). This static approach leaves cost savings on the table — not every summarization prompt requires the same model capability. A simple product announcement summary could use a lightweight model, while a nuanced technical analysis might need a stronger one.

The system also has **no automated quality assessment**. Content guidelines exist as prose in `docs/CONTENT_GUIDELINES.md`, the human review system tracks revision history, and telemetry captures operational metrics — but there's no way to:
- Automatically score output quality across pipeline steps
- Compare model performance on the same inputs
- Make data-driven model selection decisions
- Know whether Haiku's summary of a particular article is "good enough" vs. when Sonnet would materially improve quality

Open-source solutions like [RouteLLM](https://github.com/lm-sys/RouteLLM) demonstrate that ML-based routing between a "strong" and "weak" model can achieve **85% cost reduction at 95% quality retention** on general chat benchmarks. However, RouteLLM has significant limitations for our use case:
- Binary routing only (strong/weak), no multi-tier support
- Pre-trained on Chatbot Arena chat data — poor transfer to newsletter summarization/digest creation
- Hard dependency on OpenAI `text-embedding-3-small` for prompt embeddings
- Fixed vocabulary of 64 models — new models require retraining
- No built-in judge pipeline for generating domain-specific training data

We need a **custom routing and evaluation system** inspired by RouteLLM's architecture but purpose-built for our domain, using our existing embedding infrastructure and quality criteria.

## What Changes

### New Components

1. **Complexity Router** — A prompt complexity classifier that sits between `ModelStep` config and `LLMRouter.generate()`:
   - Uses existing embedding infrastructure (same `embedding_provider` as `DocumentChunk`) to embed prompts
   - Trained on domain-specific evaluation data from the LLM-as-judge framework
   - Returns a complexity score (0.0–1.0) compared against a per-step configurable threshold
   - Every `ModelStep` is independently configurable: `fixed` (current behavior) or `dynamic` (router-driven)
   - Strong/weak model pair configurable per step

2. **LLM-as-Judge Evaluation Framework** — Multi-judge quality assessment system:
   - 1–3 configurable judge models (e.g., Claude Sonnet + Gemini Flash + GPT)
   - Majority-vote consensus for preference decisions (strong vs. weak vs. tie)
   - Per-step quality criteria derived from `docs/CONTENT_GUIDELINES.md` (accuracy, completeness, conciseness, clarity, etc.)
   - Binary pass/fail verdicts per quality dimension with structured text critiques, plus overall binary preference (strong_wins | weak_wins | tie)
   - Optional human review integration — pass/fail verdicts collected during existing `ReviewService` workflow feed into calibration as high-weight ground truth

3. **Evaluation Dataset & Results Storage** — PostgreSQL tables for:
   - `evaluation_datasets`: Curated prompt sets per pipeline step (sampled from real pipeline inputs)
   - `evaluation_results`: Judge preferences, per-dimension pass/fail critiques, and reasoning per prompt/model pair
   - `routing_decisions`: Runtime routing choices with outcome tracking (model selected, threshold used, cost saved)
   - `routing_configs`: Per-step routing configuration (mode, strong/weak models, threshold, active/inactive)

4. **Threshold Calibration Engine** — Automated threshold discovery:
   - Generates outputs from both strong and weak models for a sample dataset
   - Runs multi-judge evaluation on each pair
   - Computes the threshold where the weak model achieves a target win-or-tie rate (e.g., 95%) against the strong model in judge consensus
   - Stores calibrated thresholds in `routing_configs` table
   - CLI command: `aca evaluate calibrate --step summarization --target-quality 0.95`

5. **Evaluation CLI & API** — Management interface:
   - `aca evaluate run --step <step> --samples N` — Run evaluation on N samples
   - `aca evaluate calibrate --step <step> --target-quality <pct>` — Calibrate routing threshold
   - `aca evaluate compare --step <step>` — Compare routed vs. fixed model performance
   - `aca evaluate report` — Cost savings and quality metrics dashboard
   - API endpoints for programmatic access

### Modified Components

1. **`LLMRouter`** (`src/services/llm_router.py`):
   - New `generate()` parameter: `step: ModelStep | None` — enables routing-aware generation
   - Before dispatch, checks if the step has dynamic routing enabled
   - If dynamic: runs complexity classifier, selects strong or weak model, logs routing decision
   - If fixed (or step=None): current behavior, fully backward-compatible

2. **`ModelConfig`** (`src/config/models.py`):
   - New `RoutingMode` enum: `FIXED | DYNAMIC`
   - New `RoutingConfig` dataclass per step: mode, strong_model, weak_model, threshold, router_type
   - New YAML section in `settings/models.yaml`: `routing:` with per-step configuration

3. **`settings/models.yaml`**:
   - New `routing:` section alongside existing `default_models:`
   - Per-step routing configuration with sensible defaults (all steps start as `fixed`)

4. **Review System** (optional integration):
   - `ReviewService` extended with per-dimension pass/fail verdict collection (matching LLM judge format)
   - Human verdicts feed into evaluation dataset as high-weight ground truth for calibration

## Approaches Considered

### Approach A: Adopt RouteLLM as Library Dependency

**Description**: Install `routellm` package, use its MF (Matrix Factorization) classifier directly, wrap in our LLMRouter.

**Pros**:
- Fastest to ship (pre-trained model, proven architecture)
- Battle-tested on Chatbot Arena data (55K conversations)
- Built-in calibration tooling

**Cons**:
- Hard dependency on OpenAI `text-embedding-3-small` (even when routing non-OpenAI models)
- Fixed vocabulary of 64 models — Claude 4.5, Gemini 2.5, GPT-5 may not be in the trained set
- Trained on general chat, not newsletter/digest domain — thresholds won't transfer
- Binary only (strong/weak), no future multi-tier extension path
- PyTorch + Transformers dependency adds significant install weight

**Effort**: S

### Approach B: Custom Router with Domain-Trained LLM-as-Judge (Recommended)

**Description**: Build a custom complexity classifier using our existing embedding provider, trained on evaluation data generated by a configurable multi-judge framework. Inspired by RouteLLM's architecture (prompt embedding → classifier → threshold → strong/weak) but purpose-built for our domain.

**Pros**:
- No new embedding dependencies — uses existing infrastructure
- Domain-specific — trained on actual newsletter/digest evaluation data
- Multi-judge consensus reduces single-model bias
- Per-step configurable — every ModelStep can independently opt in/out
- Human review integration provides ground-truth calibration signal
- Extensible to multi-tier routing (strong/medium/weak) in the future
- PostgreSQL storage integrates with existing settings override pattern

**Cons**:
- More upfront implementation work
- Requires evaluation data collection before routing becomes effective (cold start)
- Custom classifier needs training pipeline and maintenance

**Effort**: L

### Approach C: Heuristic Router (No ML)

**Description**: Route based on simple heuristics — input token count, source type, content category — without embedding-based complexity estimation. E.g., "if input < 2000 tokens, use weak model."

**Pros**:
- Zero latency overhead (no embedding call)
- No training data required — works immediately
- Easy to understand and debug

**Cons**:
- Crude — token count is a poor proxy for reasoning difficulty
- No quality feedback loop — can't learn from evaluation results
- RouteLLM's research shows ML classifiers significantly outperform heuristics
- No path to improvement without replacing the approach entirely

**Effort**: S

### Selected Approach: B — Custom Router with Domain-Trained LLM-as-Judge

Approach B was selected because it balances domain specificity with extensibility. The multi-judge framework provides the evaluation data needed to train a custom classifier, while per-step configuration ensures zero risk to quality-critical steps. The cold-start problem is addressed by starting all steps in `fixed` mode and only enabling `dynamic` routing after calibration data proves quality parity.

The LLM-as-judge framework is independently valuable even without dynamic routing — it gives us automated quality assessment, model comparison capabilities, and data-driven model selection for the static `default_models` configuration.

**User modifications to approach:**
- All 19 `ModelStep` values must be independently configurable (dynamic vs. fixed)
- Multi-judge supports 1–3 judges (configurable) with optional human review integration
- Evaluation results and routing decisions stored in PostgreSQL
- No RouteLLM library dependency — custom router uses existing embedding infrastructure

## Out of Scope

- **N-way routing** (3+ model tiers) — future extension once binary routing is validated
- **Provider-level routing** (choosing between Anthropic vs. Bedrock for the same model) — handled by existing `resolve_provider()`
- **Real-time A/B testing in production** — evaluation runs are batch operations, not live traffic splitting
- **Fine-tuning models** based on evaluation data — we select between existing models, not train new ones
- **Frontend UI for evaluation results** — CLI and API only; dashboards can be added later
