# Design: LLM Router Evaluation & Dynamic Routing

**Change ID**: `llm-router-evaluation`

## Architecture Overview

```
Pipeline Processor (e.g., SummarizationAgent)
    │
    │  step = ModelStep.SUMMARIZATION
    ▼
LLMRouter.generate(model, step=step, ...)
    │
    ├── step is None or mode=fixed? ──► Use model as-is (current behavior)
    │
    └── mode=dynamic and enabled?
        │
        ▼
    ComplexityRouter.classify(prompt, step)
        │
        ├── Embed prompt (existing embedding_provider)
        ├── Run classifier → score (0.0–1.0)
        └── score >= threshold? → strong_model : weak_model
            │
            ▼
    LLMRouter._dispatch_to_provider(selected_model, ...)
        │
        ▼
    Log routing decision → routing_decisions table
```

## Key Design Decisions

### D1: Complexity Router as Separate Service (not inline in LLMRouter)

**Decision**: The complexity classification logic lives in a new `ComplexityRouter` class (`src/services/complexity_router.py`), not directly in `LLMRouter`.

**Rationale**: The `LLMRouter` is already 1245 lines with provider dispatch, agentic loops, planning, and reflection. Adding ML classification logic would violate single responsibility. The `ComplexityRouter` is injected into `LLMRouter` via constructor (optional dependency, default None).

**Trade-off**: Extra indirection vs. clean separation. The `LLMRouter` calls `self.complexity_router.classify(prompt, step)` only when dynamic routing is active — zero overhead for fixed-mode steps.

### D2: Embedding Reuse via Existing Provider

**Decision**: Use the same embedding infrastructure as `DocumentChunk` (configured via `EMBEDDING_PROVIDER` env var) rather than adding a RouteLLM-specific OpenAI embedding dependency.

**Rationale**: The codebase already supports embedding providers. Reusing this avoids a new dependency, keeps embedding costs consolidated, and ensures the classifier operates on the same embedding space as semantic search.

**Implementation**: `ComplexityRouter.__init__()` accepts an `embed_fn: Callable[[str], list[float]]` that wraps the configured embedding provider. The classifier is trained on embeddings from this provider.

### D3: Logistic Regression Classifier (not Neural Network)

**Decision**: Use scikit-learn `LogisticRegression` (or small MLP with 1 hidden layer) as the complexity classifier, not a deep neural network or transformer.

**Rationale**: 
- Training data is small (hundreds to low thousands of labeled examples from evaluation runs)
- Inference must be fast (< 10ms) — no GPU required
- Scikit-learn is already a transitive dependency via other packages
- RouteLLM research shows simple classifiers perform well when trained on good evaluation data
- Easy to retrain as evaluation data grows

**Trade-off**: Less expressive than a fine-tuned BERT or causal LLM router, but appropriate for our data scale and latency requirements.

### D4: Multi-Judge with Configurable Count

**Decision**: Support 1–3 judge models, configurable in `settings/models.yaml`, with majority-vote consensus.

**Rationale**: Single-judge evaluation risks systematic bias (e.g., Claude judges may prefer Claude outputs). Multi-judge consensus is more robust. Making it configurable (1–3) allows cost-conscious users to start with 1 judge and add more as budget allows.

**Implementation**:
```yaml
# settings/models.yaml
evaluation:
  judges:
    - model: claude-sonnet-4-5
      weight: 1.0
    - model: gemini-2.5-flash
      weight: 1.0
    # Optional third judge:
    # - model: gpt-5-mini
    #   weight: 1.0
  human_review_weight: 2.0  # Human pass/fail verdicts weighted 2x vs. LLM judges in consensus
```

### D5: Quality Criteria from CONTENT_GUIDELINES.md

**Decision**: Encode the prose quality criteria from `docs/CONTENT_GUIDELINES.md` as structured evaluation rubrics per `ModelStep`, stored in `settings/evaluation.yaml`.

**Rationale**: The content guidelines define excellent quality criteria (accuracy, relevance, actionability, clarity, multi-audience awareness) but only as human-readable prose. Encoding them as structured rubrics makes them machine-executable for the judge framework.

**Example rubric** (summarization):
```yaml
evaluation_criteria:
  summarization:
    accuracy:
      description: "Key facts and claims are faithfully represented from the source"
      fail_when: "Misrepresents facts, hallucinates claims, or introduces information not in the source"
    completeness:
      description: "All important points from the source are captured"
      fail_when: "Omits a major theme, key finding, or critical nuance from the source"
    conciseness:
      description: "No unnecessary repetition or filler"
      fail_when: "Contains redundant sentences, padding phrases, or information that adds no value"
    key_insight_capture:
      description: "Novel, surprising, or strategically important insights are highlighted"
      fail_when: "Buries or omits the most noteworthy insight in favor of routine information"
    clarity:
      description: "Written in clear, accessible language for the target audience"
      fail_when: "Uses ambiguous phrasing, undefined jargon, or convoluted sentence structure"
```

**Judge output format** (per evaluation):
```json
{
  "preference": "weak_wins",
  "critiques": {
    "accuracy": {"verdict": "pass", "explanation": "Both outputs are factually faithful."},
    "completeness": {"verdict": "pass", "explanation": "Both capture the main claims."},
    "conciseness": {"verdict": "fail", "explanation": "Output A (strong) is 40% longer with redundant framing paragraphs."},
    "key_insight_capture": {"verdict": "pass", "explanation": "Both highlight the novel architecture finding."},
    "clarity": {"verdict": "pass", "explanation": "Both are well-structured."}
  },
  "reasoning": "Both outputs are accurate and complete, but the weak model's output is significantly more concise without losing substance."
}
```

This binary pass/fail + text critique approach is more reliable than Likert scales because it forces judges to commit to a concrete deficiency rather than hedging with middle scores. The text critiques provide actionable feedback for understanding routing quality.

### D5a: Position Bias Mitigation

**Decision**: Randomize which output (strong vs. weak) is presented as "Output A" vs "Output B" in every judge evaluation. Track the mapping to correctly interpret the judge's preference.

**Rationale**: LLMs exhibit well-documented position bias — a tendency to prefer whichever output appears first. Without randomization, evaluation data would be systematically biased toward whichever model's output is always presented first. This is standard practice in Chatbot Arena, LMSYS, and RouteLLM evaluation pipelines.

### D5b: Judge Prompt Template

**Decision**: Judge prompts are constructed programmatically by `LLMJudge` using criteria from `settings/evaluation.yaml`, not stored as raw prompt templates in `settings/prompts.yaml`.

**Rationale**: Judge prompts must dynamically include the quality dimensions, their descriptions, fail_when criteria, and concrete fail examples — all of which vary per `ModelStep`. A template string would need so many variables that a programmatic builder is cleaner. The builder outputs a prompt structured as:

```
You are evaluating two outputs for a {step_name} task.

## Quality Dimensions
For each dimension, assess BOTH outputs and give a binary verdict (pass/fail) with a brief explanation.

1. **{dim_name}**: {description}
   - FAIL when: {fail_when}

[...repeat for each dimension...]

## Outputs
**Output A:**
{output_a}

**Output B:**
{output_b}

## Instructions
Return a JSON object with this exact structure:
{
  "preference": "A_wins" | "B_wins" | "tie",
  "critiques": {
    "{dim_name}": {"verdict": "pass" | "fail", "explanation": "..."},
    ...
  },
  "reasoning": "Overall comparison explanation"
}
```

### D5c: Consensus Tie-Breaking

**Decision**: When judges cannot reach majority, the consensus result is `tie`.

**Rules**:
- 1 judge: judge's preference is the consensus
- 2 judges, same preference: that preference wins (agreement_rate = 1.0)
- 2 judges, split preference: consensus = `tie` (agreement_rate = 0.0)
- 3 judges, 2+ agree: majority preference wins
- 3 judges, 3-way split: consensus = `tie` (agreement_rate = 0.33)

**Rationale**: Defaulting to `tie` on disagreement is conservative — it means the calibration engine treats the sample as "inconclusive" rather than guessing. For routing purposes, `tie` means the weak model is considered acceptable (it didn't lose), which aligns with cost-optimization goals.

### D6: PostgreSQL for All Persistence (not Observability Provider)

**Decision**: Store evaluation results and routing decisions in PostgreSQL tables, not in Langfuse/Braintrust.

**Rationale**: 
- Consistent with existing settings override pattern
- Queryable by calibration engine without external API calls
- No dependency on optional observability provider being configured
- Routing decisions are queried at runtime for cost reporting
- Future: can export to observability provider as a separate step

### D7: Routing Config Override Hierarchy

**Decision**: Routing configuration follows the same override pattern as model selection: env var > DB override > YAML default.

**Hierarchy**:
1. `ROUTING_<STEP>_MODE=dynamic|fixed` env var (highest)
2. DB override in `routing_configs` table (set by calibration or API)
3. `settings/models.yaml` `routing:` section (default)

This ensures ops teams can enable/disable routing via env vars without code changes.

## Database Schema

### New Tables

```sql
-- Routing configuration per step
CREATE TABLE routing_configs (
    id SERIAL PRIMARY KEY,
    step VARCHAR(50) NOT NULL UNIQUE,     -- ModelStep value
    mode VARCHAR(10) NOT NULL DEFAULT 'fixed',  -- 'fixed' or 'dynamic'
    strong_model VARCHAR(100),
    weak_model VARCHAR(100),
    threshold FLOAT DEFAULT 0.5,
    enabled BOOLEAN DEFAULT FALSE,
    classifier_version VARCHAR(50),        -- Trained classifier identifier
    calibrated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evaluation datasets (collections of prompt pairs)
CREATE TABLE evaluation_datasets (
    id SERIAL PRIMARY KEY,
    step VARCHAR(50) NOT NULL,
    name VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'pending_evaluation',
    -- 'pending_evaluation', 'evaluated', 'calibrated'
    sample_count INTEGER NOT NULL,
    strong_model VARCHAR(100) NOT NULL,
    weak_model VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual evaluation samples within a dataset
CREATE TABLE evaluation_samples (
    id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    prompt_text TEXT NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,      -- SHA-256 for dedup
    strong_output TEXT,
    weak_output TEXT,
    strong_tokens INTEGER,
    weak_tokens INTEGER,
    strong_cost FLOAT,
    weak_cost FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Judge evaluation results
CREATE TABLE evaluation_results (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER NOT NULL REFERENCES evaluation_samples(id) ON DELETE CASCADE,
    judge_model VARCHAR(100) NOT NULL,     -- Model ID or 'human'
    judge_type VARCHAR(10) NOT NULL,       -- 'llm' or 'human'
    preference VARCHAR(20) NOT NULL,       -- 'strong_wins', 'weak_wins', 'tie'
    critiques JSONB NOT NULL,              -- {"accuracy": {"verdict": "pass", "explanation": "..."}, ...}
    reasoning TEXT,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Consensus results per sample
CREATE TABLE evaluation_consensus (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER NOT NULL REFERENCES evaluation_samples(id) ON DELETE CASCADE,
    consensus_preference VARCHAR(20) NOT NULL,
    agreement_rate FLOAT,                  -- 0.0–1.0
    dimension_verdicts JSONB,              -- {"accuracy": {"pass": 2, "fail": 1}, ...} per-dimension vote tally
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sample_id)
);

-- Runtime routing decisions
CREATE TABLE routing_decisions (
    id SERIAL PRIMARY KEY,
    step VARCHAR(50) NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    complexity_score FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    model_selected VARCHAR(100) NOT NULL,
    strong_model VARCHAR(100) NOT NULL,
    weak_model VARCHAR(100) NOT NULL,
    cost_actual FLOAT,                     -- Populated after generation
    tokens_input INTEGER,
    tokens_output INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_routing_decisions_step_created ON routing_decisions(step, created_at);
CREATE INDEX idx_evaluation_results_sample ON evaluation_results(sample_id);
CREATE INDEX idx_evaluation_samples_dataset ON evaluation_samples(dataset_id);
```

## Module Structure

```
src/
├── services/
│   ├── llm_router.py              # Modified: add step parameter, complexity routing hook
│   ├── complexity_router.py       # NEW: ComplexityRouter — classify, train, load models
│   └── evaluation_service.py      # NEW: EvaluationService — datasets, judges, calibration
├── config/
│   ├── models.py                  # Modified: RoutingConfig, RoutingMode, routing config loading
│   └── evaluation.py              # NEW: Evaluation criteria, judge configs
├── evaluation/
│   ├── __init__.py
│   ├── judge.py                   # NEW: LLMJudge — single judge evaluation
│   ├── consensus.py               # NEW: ConsensusEngine — multi-judge aggregation
│   ├── calibrator.py              # NEW: ThresholdCalibrator — calibration engine
│   └── criteria.py                # NEW: QualityCriteria — per-step rubrics
├── cli/
│   └── evaluate_commands.py       # NEW: CLI commands for aca evaluate
├── api/
│   └── evaluation.py              # NEW: API endpoints
├── models/
│   └── evaluation.py              # NEW: SQLAlchemy models for new tables
settings/
├── models.yaml                    # Modified: routing section
└── evaluation.yaml                # NEW: Judge configs, criteria per step
```

## Integration with Agentic Analysis Agent

The `agentic-analysis-agent` change (Phase 2) extends `LLMRouter` with reflection, planning, and memory. This feature composes cleanly:

- **Reflection + routing**: If dynamic routing selects the weak model and the reflection phase scores low, a future enhancement could re-run with the strong model. For now, reflection operates on whichever model was selected.
- **Planning + routing**: `generate_with_planning()` calls `generate_with_tools()` internally. Adding `step` to the top-level call propagates routing to individual plan steps.
- **Cost limits + routing**: Dynamic routing reduces per-call cost, which means cost_limit budgets stretch further — complementary, not conflicting.

No code in the agentic-analysis-agent change needs modification for this feature. The integration is additive.

## Performance Considerations

| Operation | Latency | Notes |
|-----------|---------|-------|
| Prompt embedding | ~50ms | One embedding API call; cached for identical prompts |
| Classifier inference | < 5ms | Logistic regression / small MLP on CPU |
| Routing decision logging | ~2ms | Async PostgreSQL insert, non-blocking |
| Total overhead | ~57ms | Negligible vs. LLM generation (500ms–10s) |

## Security

- Evaluation API endpoints require `X-Admin-Key` authentication (consistent with existing admin APIs)
- Judge model API keys use the same provider credentials as generation
- Evaluation datasets may contain sensitive content from newsletters — same access controls as existing content tables
- Prompt hashes (SHA-256) used for dedup; full prompts stored only in evaluation tables, not routing decisions
