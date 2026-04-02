# Spec: LLM Router Evaluation

**Capability**: `llm-router-evaluation`
**Status**: Draft
**Depends on**: `llm-provider-routing`

## Scenarios

### Routing Configuration

#### llm-router-evaluation.1 — Per-step routing mode configuration
**Given** a `routing:` section in `settings/models.yaml` with per-step entries
**When** `ModelConfig` loads the registry
**Then** each `ModelStep` SHALL have a `RoutingConfig` with:
  - `mode`: `fixed` (default) or `dynamic`
  - `strong_model`: model ID for high-complexity prompts
  - `weak_model`: model ID for low-complexity prompts
  - `threshold`: float 0.0–1.0 (default 0.5)
  - `enabled`: bool (default false — dynamic routing is opt-in)

#### llm-router-evaluation.2 — Fixed mode preserves current behavior
**Given** a step configured with `mode: fixed`
**When** `LLMRouter.generate()` is called with `step=ModelStep.SUMMARIZATION`
**Then** the router SHALL use `get_model_for_step(step)` exactly as today
**And** no complexity classification SHALL occur

#### llm-router-evaluation.3 — Dynamic mode routes by complexity
**Given** a step configured with `mode: dynamic`, `strong_model: claude-sonnet-4-5`, `weak_model: claude-haiku-4-5`, `threshold: 0.6`, `enabled: true`
**When** `LLMRouter.generate()` is called with `step=ModelStep.SUMMARIZATION`
**Then** the router SHALL:
  1. Embed the user prompt using the configured embedding provider
  2. Compute a complexity score via the trained classifier (0.0–1.0)
  3. If score >= threshold → select `strong_model`
  4. If score < threshold → select `weak_model`
  5. Log the routing decision to `routing_decisions` table
  6. Proceed with generation using the selected model

#### llm-router-evaluation.4 — Dynamic routing disabled falls back to fixed
**Given** a step with `mode: dynamic` but `enabled: false`
**When** `LLMRouter.generate()` is called with that step
**Then** it SHALL behave identically to `mode: fixed`

#### llm-router-evaluation.5 — Step parameter is optional (backward compatibility)
**Given** existing callers that do not pass `step` to `generate()`
**When** `generate(model="claude-sonnet-4-5", ...)` is called without `step`
**Then** the router SHALL use the explicitly provided model (no routing logic)
**And** no routing decision SHALL be logged

### Complexity Classification

#### llm-router-evaluation.6 — Embedding-based complexity scoring
**Given** a trained complexity classifier for a pipeline step
**When** a prompt is submitted for classification
**Then** the classifier SHALL:
  1. Embed the prompt using the existing `embedding_provider`
  2. Pass the embedding through a lightweight classifier (logistic regression or small MLP)
  3. Return a score between 0.0 (simple) and 1.0 (complex)

#### llm-router-evaluation.7 — Classifier cold start
**Given** no trained classifier exists for a step
**When** dynamic routing is enabled for that step
**Then** the router SHALL fall back to `fixed` mode
**And** log a warning: "No trained classifier for step {step}, falling back to fixed mode"

### LLM-as-Judge Evaluation

#### llm-router-evaluation.8 — Single judge evaluation
**Given** 1 judge model configured
**When** an evaluation is run on a prompt with strong and weak model outputs
**Then** the judge SHALL:
  1. Produce a binary preference decision: `strong_wins` | `weak_wins` | `tie`
  2. Provide structured text critiques for each quality dimension (e.g., accuracy, completeness, conciseness, clarity)
  3. Each critique SHALL be a pass/fail assessment with a brief text explanation of the deficiency (if fail) or strength (if pass)
  4. Store the preference, per-dimension pass/fail verdicts, and critique text in `evaluation_results` table

#### llm-router-evaluation.9 — Multi-judge consensus
**Given** N judge models configured (2 ≤ N ≤ 3)
**When** an evaluation is run
**Then** each judge SHALL independently evaluate the outputs
**And** the final preference SHALL be determined by majority vote
**And** individual and consensus results SHALL be stored
**And** inter-judge agreement rate SHALL be tracked

#### llm-router-evaluation.10 — Step-specific quality dimensions with pass/fail critiques
**Given** quality dimensions defined per `ModelStep`
**When** a judge evaluates outputs for `SUMMARIZATION`
**Then** it SHALL critique on: `accuracy`, `completeness`, `conciseness`, `key_insight_capture`
**When** a judge evaluates outputs for `DIGEST_CREATION`
**Then** it SHALL critique on: `narrative_flow`, `theme_coherence`, `actionability`, `depth`
**When** a judge evaluates outputs for `PODCAST_SCRIPT`
**Then** it SHALL critique on: `conversational_tone`, `engagement`, `technical_accuracy`, `pacing`
**And** each dimension SHALL produce a binary `pass`/`fail` verdict with a text critique explaining the assessment

#### llm-router-evaluation.11 — Human review integration
**Given** the `ReviewService` is configured with structured scoring
**When** a human reviewer approves/rejects a digest with quality scores
**Then** those scores SHALL be stored in `evaluation_results` with `judge_type: human`
**And** human scores SHALL be weighted higher than LLM judges in calibration

### Threshold Calibration

#### llm-router-evaluation.12 — Automated threshold discovery
**Given** an evaluation dataset for a step with N evaluated prompt pairs
**When** `calibrate_threshold(step, target_quality=0.95)` is called
**Then** the engine SHALL:
  1. For each prompt, retrieve the router's complexity score
  2. Sort prompts by complexity score
  3. Find the threshold where the weak model achieves >= target% of strong model quality (measured by judge scores)
  4. Store the calibrated threshold in `routing_configs`
  5. Return the threshold and estimated cost savings

#### llm-router-evaluation.13 — Minimum sample requirement
**Given** fewer than 30 evaluated prompt pairs for a step
**When** calibration is attempted
**Then** the engine SHALL refuse with: "Insufficient evaluation data ({N}/30 minimum)"

### Evaluation Dataset Management

#### llm-router-evaluation.14 — Dataset creation from pipeline
**Given** real pipeline inputs for a step
**When** `aca evaluate create-dataset --step summarization --samples 100` is run
**Then** the system SHALL:
  1. Sample N recent inputs for that step from pipeline history
  2. Generate outputs from both the strong and weak model
  3. Store the prompt + both outputs in `evaluation_datasets`
  4. Mark the dataset as `pending_evaluation`

#### llm-router-evaluation.15 — Evaluation execution
**Given** a dataset with `pending_evaluation` status
**When** `aca evaluate run --step summarization` is executed
**Then** the system SHALL:
  1. Run each configured judge on each prompt pair
  2. Compute consensus preferences
  3. Store all results in `evaluation_results`
  4. Update dataset status to `evaluated`

### Routing Decision Tracking

#### llm-router-evaluation.16 — Decision logging
**Given** dynamic routing is active for a step
**When** a routing decision is made
**Then** the system SHALL log to `routing_decisions`:
  - `step`, `prompt_hash`, `complexity_score`, `threshold`
  - `model_selected`, `strong_model`, `weak_model`
  - `cost_actual` (populated after generation completes)
  - `timestamp`

#### llm-router-evaluation.17 — Cost savings reporting
**Given** routing decisions have been logged over a time period
**When** `aca evaluate report` is run
**Then** it SHALL display:
  - Per-step: total calls, % routed to weak, cost savings vs. all-strong
  - Aggregate: total cost savings, quality score distribution
  - Recommendation: steps where dynamic routing should be enabled/disabled

### CLI Interface

#### llm-router-evaluation.18 — Evaluation CLI commands
The following CLI commands SHALL be available under `aca evaluate`:

| Command | Purpose |
|---------|---------|
| `aca evaluate create-dataset --step <step> --samples N` | Create evaluation dataset |
| `aca evaluate run --step <step>` | Run judges on pending dataset |
| `aca evaluate calibrate --step <step> --target-quality <pct>` | Calibrate routing threshold |
| `aca evaluate compare --step <step>` | Compare routed vs. fixed performance |
| `aca evaluate report` | Cost savings and quality dashboard |
| `aca evaluate list-datasets` | List evaluation datasets |

### API Endpoints

#### llm-router-evaluation.19 — Evaluation API
The following API endpoints SHALL be available (authenticated with `X-Admin-Key`):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/evaluation/configs` | List routing configs for all steps |
| `PUT` | `/api/evaluation/configs/{step}` | Update routing config for a step |
| `POST` | `/api/evaluation/datasets` | Create evaluation dataset |
| `GET` | `/api/evaluation/datasets` | List datasets |
| `POST` | `/api/evaluation/run/{dataset_id}` | Run evaluation on dataset |
| `POST` | `/api/evaluation/calibrate/{step}` | Calibrate threshold |
| `GET` | `/api/evaluation/report` | Cost savings report |
| `GET` | `/api/evaluation/decisions` | Query routing decisions |
