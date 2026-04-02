# Tasks: LLM Router Evaluation & Dynamic Routing

**Change ID**: `llm-router-evaluation`

## Parallelizability Notes

Phases 1-2 and Phase 4 have **no cross-dependencies** and can run in parallel:
- **Stream A**: Phase 1 → Phase 2 → Phase 3 (database → config → complexity router)
- **Stream B**: Phase 4 (judge framework — depends only on itself)
- **Merge point**: Phase 5 (requires both streams complete)

**Max parallel width**: 4 tasks (1.1, 4.1, 4.2, 4.3 can all start simultaneously)

**File overlap warnings**:
- `src/config/models.py`: Tasks 2.2 + 2.4 (merged into single task)
- `src/services/llm_router.py`: Tasks 3.4, 3.6 (sequenced explicitly)

---

## Phase 1: Database Schema & Models

- [ ] 1.1 Write tests for evaluation database models — CRUD, constraints, cascading deletes, status transitions
  **Spec scenarios**: llm-router-evaluation.16 (decision logging), llm-router-evaluation.14 (dataset creation)
  **Design decisions**: D6 (PostgreSQL for all persistence)
  **Files**: `tests/models/test_evaluation.py` (new)
  **Dependencies**: None

- [ ] 1.2 Create Alembic migration for new tables (`routing_configs`, `evaluation_datasets`, `evaluation_samples`, `evaluation_results`, `evaluation_consensus`, `routing_decisions`)
  **Files**: `alembic/versions/xxx_add_evaluation_tables.py` (new)
  **Dependencies**: 1.1

- [ ] 1.3 Create SQLAlchemy models in `src/models/evaluation.py`
  **Files**: `src/models/evaluation.py` (new), `src/models/__init__.py` (import)
  **Dependencies**: 1.1

- [ ] 1.4 Run migration and verify all models against database schema
  **Dependencies**: 1.2, 1.3

## Phase 2: Routing Configuration

- [ ] 2.1 Write tests for `RoutingConfig` loading — YAML parsing, env var overrides (`ROUTING_<STEP>_MODE`), DB overrides, default fallbacks
  **Spec scenarios**: llm-router-evaluation.1 (per-step config), llm-router-evaluation.2 (fixed mode), llm-router-evaluation.4 (disabled fallback)
  **Design decisions**: D7 (override hierarchy)
  **Files**: `tests/config/test_routing_config.py` (new)
  **Dependencies**: 1.3

- [ ] 2.2 Add `RoutingMode` enum, `RoutingConfig` dataclass, and routing config loading to `src/config/models.py`. Add `routing:` section to `settings/models.yaml` with per-step defaults (all `fixed`, `enabled: false`)
  **Spec scenarios**: llm-router-evaluation.1
  **Files**: `src/config/models.py` (modify), `settings/models.yaml` (modify)
  **Dependencies**: 2.1
  **Note**: Merged former tasks 2.2 + 2.3 + 2.4 — all modify the same config subsystem

## Phase 3: Complexity Router

- [ ] 3.1 Write tests for `ComplexityRouter` — classify (with/without trained model), cold start fallback, embedding failure fallback, model persistence
  **Spec scenarios**: llm-router-evaluation.6 (embedding-based scoring), llm-router-evaluation.7 (cold start fallback), llm-router-evaluation.15a (embedding failure)
  **Design decisions**: D1 (separate service), D2 (embedding reuse), D3 (logistic regression)
  **Files**: `tests/services/test_complexity_router.py` (new)
  **Dependencies**: 2.2

- [ ] 3.2 Create `src/services/complexity_router.py` — `ComplexityRouter` class with `classify()`, `train()`, `load_model()`, `save_model()`. On embedding failure: fall back to fixed mode and log warning
  **Files**: `src/services/complexity_router.py` (new)
  **Dependencies**: 3.1

- [ ] 3.3 Write tests for `LLMRouter` integration — step parameter routing, dynamic dispatch, backward compat (no step → no routing_configs query, no routing_decisions row)
  **Spec scenarios**: llm-router-evaluation.3 (dynamic routing), llm-router-evaluation.5 (backward compat — verify no routing_configs query and no routing_decisions insert)
  **Files**: `tests/services/test_llm_router_routing.py` (new)
  **Dependencies**: 3.2

- [ ] 3.4 Modify `LLMRouter.generate()` and `generate_with_tools()` — add optional `step` parameter, integrate `ComplexityRouter` for dynamic mode, add async routing decision logging to `routing_decisions` table
  **Spec scenarios**: llm-router-evaluation.3, llm-router-evaluation.5, llm-router-evaluation.16
  **Files**: `src/services/llm_router.py` (modify)
  **Dependencies**: 3.3
  **Note**: Merged former tasks 3.4 + 3.5 + 3.6 — all modify `llm_router.py`, avoids churn

## Phase 4: Evaluation Criteria & Judge Framework *(parallel with Phases 1-3)*

- [ ] 4.1 Write tests for quality criteria loading — per-step rubrics from YAML, default fallback dimensions, dimension validation
  **Spec scenarios**: llm-router-evaluation.10 (step-specific criteria), llm-router-evaluation.15g (default dimensions)
  **Design decisions**: D5 (criteria from CONTENT_GUIDELINES.md)
  **Files**: `tests/evaluation/test_criteria.py` (new)
  **Dependencies**: None

- [ ] 4.2 Create `settings/evaluation.yaml` with quality criteria per step (summarization, digest_creation, podcast_script) and `_default` fallback (accuracy, completeness, conciseness, clarity). Include `description` and `fail_when` with concrete examples per dimension
  **Spec scenarios**: llm-router-evaluation.10, llm-router-evaluation.15g
  **Files**: `settings/evaluation.yaml` (new)
  **Dependencies**: None (can parallel with 4.1)

- [ ] 4.3 Create `src/evaluation/criteria.py` — `QualityCriteria` class, per-step rubric loading with `_default` fallback
  **Files**: `src/evaluation/criteria.py` (new)
  **Dependencies**: 4.1, 4.2

- [ ] 4.4 Write tests for `LLMJudge` — prompt construction (blinded A/B, criteria from YAML, structured JSON output format), binary preference parsing, pass/fail per-dimension critique validation, judge response parse failure retry
  **Spec scenarios**: llm-router-evaluation.8 (single judge), llm-router-evaluation.10a (position bias), llm-router-evaluation.15c (parse failure), llm-router-evaluation.15d (prompt template)
  **Files**: `tests/evaluation/test_judge.py` (new)
  **Dependencies**: 4.3

- [ ] 4.5 Create `src/evaluation/judge.py` — `LLMJudge` class with `evaluate_pair()`: construct blinded judge prompt with criteria + fail examples, randomize A/B presentation order, parse structured JSON response, retry on parse failure, map A/B preference back to strong/weak
  **Spec scenarios**: llm-router-evaluation.8, llm-router-evaluation.10a, llm-router-evaluation.15c, llm-router-evaluation.15d
  **Files**: `src/evaluation/judge.py` (new)
  **Dependencies**: 4.4
  **Note**: Merged former 4.5 + 4.5a + 4.5b — position bias is integral to judge, not separable

- [ ] 4.6 Write tests for `ConsensusEngine` — majority vote with 1/2/3 judges, 2-judge split → tie, 3-judge 3-way split → tie, agreement rate calculation, per-dimension verdict tally, single judge failure handling
  **Spec scenarios**: llm-router-evaluation.9 (multi-judge consensus), llm-router-evaluation.15e (2-judge tie), llm-router-evaluation.15f (3-judge no majority), llm-router-evaluation.15b (judge failure)
  **Design decisions**: D4 (configurable judge count)
  **Files**: `tests/evaluation/test_consensus.py` (new)
  **Dependencies**: 4.5

- [ ] 4.7 Create `src/evaluation/consensus.py` — `ConsensusEngine` class with `evaluate_with_consensus()`: run N judges, handle individual judge failures (continue with remaining), compute majority vote with defined tie-breaking, compute agreement rate and per-dimension verdict tallies
  **Files**: `src/evaluation/consensus.py` (new)
  **Dependencies**: 4.6

## Phase 5: Evaluation Service & Dataset Management

- [ ] 5.1 Write tests for `EvaluationService` — dataset creation from pipeline history, dual-model output generation, evaluation execution with judge orchestration, result storage, sample error handling
  **Spec scenarios**: llm-router-evaluation.14 (dataset creation), llm-router-evaluation.15 (evaluation execution), llm-router-evaluation.15b (judge failure)
  **Files**: `tests/services/test_evaluation_service.py` (new)
  **Dependencies**: 4.7, 1.3

- [ ] 5.2 Create `src/services/evaluation_service.py` — `EvaluationService` with `create_dataset()`, `run_evaluation()`, `get_results()`. Handle per-sample judge failures: mark as error, continue to next sample
  **Files**: `src/services/evaluation_service.py` (new)
  **Dependencies**: 5.1

- [ ] 5.3 Write tests for human review integration — pass/fail verdict collection per dimension, 2.0x weight in consensus, storage as `judge_type='human'`, `judge_model='human'`
  **Spec scenarios**: llm-router-evaluation.11 (human review integration)
  **Files**: `tests/services/test_human_review_evaluation.py` (new)
  **Dependencies**: 5.2

- [ ] 5.4 Extend `ReviewService` to optionally collect pass/fail verdicts per quality dimension during review workflow, matching LLM judge output format. Store in `evaluation_results` with `judge_type='human'`
  **Files**: `src/services/review_service.py` (modify)
  **Dependencies**: 5.3, 1.3

## Phase 6: Threshold Calibration

- [ ] 6.1 Write tests for `ThresholdCalibrator` — threshold computation using consensus win-or-tie rate, minimum 30-sample enforcement, cost savings estimation
  **Spec scenarios**: llm-router-evaluation.12 (automated calibration — win-or-tie rate metric), llm-router-evaluation.13 (minimum samples)
  **Files**: `tests/evaluation/test_calibrator.py` (new)
  **Dependencies**: 5.2, 3.2

- [ ] 6.2 Create `src/evaluation/calibrator.py` — `ThresholdCalibrator` with `calibrate()` (find threshold where weak model win-or-tie rate >= target%), `estimate_savings()`
  **Files**: `src/evaluation/calibrator.py` (new)
  **Dependencies**: 6.1

- [ ] 6.3 Write tests for classifier training — train logistic regression from evaluation embeddings + consensus preferences, persist trained model, load model, version tracking
  **Files**: `tests/services/test_complexity_router_training.py` (new)
  **Dependencies**: 6.2, 3.2

- [ ] 6.4 Implement classifier training in `ComplexityRouter.train()` — logistic regression on evaluation embeddings + judge consensus preferences. Add `scikit-learn>=1.3.0` to dependencies
  **Files**: `src/services/complexity_router.py` (modify), `pyproject.toml` (modify)
  **Dependencies**: 6.3, 3.2

## Phase 7: CLI & API

- [ ] 7.1 Write tests for CLI commands — create-dataset, run, calibrate, compare, report, list-datasets
  **Spec scenarios**: llm-router-evaluation.18 (CLI commands)
  **Files**: `tests/cli/test_evaluate_commands.py` (new)
  **Dependencies**: 6.2, 5.2

- [ ] 7.2 Create `src/cli/evaluate_commands.py` — CLI command group `aca evaluate` with all subcommands. Register in main CLI entrypoint
  **Files**: `src/cli/evaluate_commands.py` (new), `src/cli/main.py` (modify)
  **Dependencies**: 7.1

- [ ] 7.3 Write tests for API endpoints — CRUD routing configs, dataset management, evaluation execution, reporting
  **Spec scenarios**: llm-router-evaluation.19 (API endpoints)
  **Files**: `tests/api/test_evaluation_api.py` (new)
  **Dependencies**: 5.2, 6.2

- [ ] 7.4 Create `src/api/evaluation.py` — FastAPI router with all evaluation endpoints (auth: `X-Admin-Key`). Register in main FastAPI app
  **Files**: `src/api/evaluation.py` (new), `src/api/main.py` (modify)
  **Dependencies**: 7.3

## Phase 8: Cost Reporting & Documentation

- [ ] 8.1 Write tests for cost savings report — per-step metrics, aggregate savings, consensus preference distribution, per-dimension pass rates, recommendations
  **Spec scenarios**: llm-router-evaluation.17 (cost savings reporting)
  **Files**: `tests/services/test_evaluation_report.py` (new)
  **Dependencies**: 7.2

- [ ] 8.2 Implement cost reporting in `EvaluationService.generate_report()` — query routing_decisions, compute savings vs. all-strong baseline, compute preference distribution and per-dimension pass rates
  **Files**: `src/services/evaluation_service.py` (modify)
  **Dependencies**: 8.1

- [ ] 8.3 Update `docs/MODEL_CONFIGURATION.md` with dynamic routing documentation
  **Files**: `docs/MODEL_CONFIGURATION.md` (modify)
  **Dependencies**: 7.4

- [ ] 8.4 Add evaluation section to `CLAUDE.md` quick reference
  **Files**: `CLAUDE.md` (modify)
  **Dependencies**: 8.3

- [ ] 8.5 End-to-end integration test — create dataset → run evaluation → calibrate → enable dynamic routing → verify routing decisions logged
  **Files**: `tests/integration/test_evaluation_e2e.py` (new)
  **Dependencies**: All previous phases

## Task Summary

| Phase | Tasks | Focus | Parallel Stream |
|-------|-------|-------|-----------------|
| 1. Database | 4 | Schema, models, migration | Stream A |
| 2. Config | 2 | Routing configuration, YAML, overrides | Stream A (after 1) |
| 3. Router | 4 | ComplexityRouter, LLMRouter integration | Stream A (after 2) |
| 4. Judge | 7 | Quality criteria, judge, consensus | Stream B (independent) |
| 5. Service | 4 | EvaluationService, datasets, human review | Merge (A+B) |
| 6. Calibration | 4 | Threshold discovery, classifier training | After 5 |
| 7. CLI & API | 4 | CLI commands, API endpoints | After 6 |
| 8. Reporting | 5 | Cost reporting, docs, E2E test | After 7 |
| **Total** | **34** | | |

## Dependency Graph (Critical Path)

```
Phase 1 ─► Phase 2 ─► Phase 3 ─┐
                                 ├─► Phase 5 ─► Phase 6 ─► Phase 7 ─► Phase 8
Phase 4 (parallel) ─────────────┘
```
