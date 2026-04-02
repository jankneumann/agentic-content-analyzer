# Tasks: LLM Router Evaluation & Dynamic Routing

**Change ID**: `llm-router-evaluation`

## Phase 1: Database Schema & Models

- [ ] 1.1 Write tests for evaluation database models — CRUD, constraints, cascading deletes
  **Spec scenarios**: llm-router-evaluation.16 (decision logging), llm-router-evaluation.14 (dataset creation)
  **Design decisions**: D6 (PostgreSQL for all persistence)
  **Dependencies**: None

- [ ] 1.2 Create Alembic migration for new tables (`routing_configs`, `evaluation_datasets`, `evaluation_samples`, `evaluation_results`, `evaluation_consensus`, `routing_decisions`)
  **Dependencies**: 1.1

- [ ] 1.3 Create SQLAlchemy models in `src/models/evaluation.py`
  **Dependencies**: 1.1

- [ ] 1.4 Run migration and verify all models against database schema
  **Dependencies**: 1.2, 1.3

## Phase 2: Routing Configuration

- [ ] 2.1 Write tests for `RoutingConfig` loading — YAML parsing, env var overrides, DB overrides, default fallbacks
  **Spec scenarios**: llm-router-evaluation.1 (per-step config), llm-router-evaluation.2 (fixed mode), llm-router-evaluation.4 (disabled fallback)
  **Design decisions**: D7 (override hierarchy)
  **Dependencies**: 1.3

- [ ] 2.2 Add `RoutingMode` enum and `RoutingConfig` dataclass to `src/config/models.py`
  **Dependencies**: 2.1

- [ ] 2.3 Add `routing:` section to `settings/models.yaml` with per-step defaults (all `fixed`, `enabled: false`)
  **Dependencies**: 2.2

- [ ] 2.4 Extend `ModelConfig` to load routing configuration from YAML, with env var and DB override support
  **Dependencies**: 2.2, 2.3

## Phase 3: Complexity Router

- [ ] 3.1 Write tests for `ComplexityRouter` — classify (with/without trained model), cold start fallback, model persistence
  **Spec scenarios**: llm-router-evaluation.6 (embedding-based scoring), llm-router-evaluation.7 (cold start fallback)
  **Design decisions**: D1 (separate service), D2 (embedding reuse), D3 (logistic regression)
  **Dependencies**: 2.4

- [ ] 3.2 Create `src/services/complexity_router.py` — `ComplexityRouter` class with `classify()`, `train()`, `load_model()`, `save_model()`
  **Dependencies**: 3.1

- [ ] 3.3 Write tests for `LLMRouter` integration — step parameter, dynamic routing dispatch, backward compatibility
  **Spec scenarios**: llm-router-evaluation.3 (dynamic routing), llm-router-evaluation.5 (backward compat)
  **Dependencies**: 3.2

- [ ] 3.4 Modify `LLMRouter.generate()` and `generate_with_tools()` — add optional `step` parameter, integrate `ComplexityRouter` for dynamic mode
  **Dependencies**: 3.3

- [ ] 3.5 Write tests for routing decision logging — verify `routing_decisions` table populated correctly
  **Spec scenarios**: llm-router-evaluation.16 (decision logging)
  **Dependencies**: 3.4, 1.3

- [ ] 3.6 Implement routing decision logging in `LLMRouter` — async insert to `routing_decisions` after generation
  **Dependencies**: 3.5

## Phase 4: Evaluation Criteria & Judge Framework

- [ ] 4.1 Write tests for quality criteria loading — per-step rubrics from YAML, dimension validation
  **Spec scenarios**: llm-router-evaluation.10 (step-specific criteria)
  **Design decisions**: D5 (criteria from CONTENT_GUIDELINES.md)
  **Dependencies**: None

- [ ] 4.2 Create `settings/evaluation.yaml` with quality criteria per step (summarization, digest_creation, podcast_script, and default fallback)
  **Dependencies**: 4.1

- [ ] 4.3 Create `src/evaluation/criteria.py` — `QualityCriteria` class, per-step rubric loading
  **Dependencies**: 4.1

- [ ] 4.4 Write tests for `LLMJudge` — single evaluation, binary preference output, pass/fail per-dimension critiques, prompt construction, critique text validation
  **Spec scenarios**: llm-router-evaluation.8 (single judge — binary preference + structured critiques)
  **Dependencies**: 4.3

- [ ] 4.5 Create `src/evaluation/judge.py` — `LLMJudge` class with `evaluate_pair()` returning binary preference + per-dimension pass/fail verdicts with text critiques, using `LLMRouter.generate()`
  **Dependencies**: 4.4

- [ ] 4.6 Write tests for `ConsensusEngine` — majority vote with 1/2/3 judges, tie breaking, agreement rate calculation
  **Spec scenarios**: llm-router-evaluation.9 (multi-judge consensus)
  **Design decisions**: D4 (configurable judge count)
  **Dependencies**: 4.5

- [ ] 4.7 Create `src/evaluation/consensus.py` — `ConsensusEngine` class with `evaluate_with_consensus()`
  **Dependencies**: 4.6

## Phase 5: Evaluation Service & Dataset Management

- [ ] 5.1 Write tests for `EvaluationService` — dataset creation, sample generation, evaluation execution, result storage
  **Spec scenarios**: llm-router-evaluation.14 (dataset creation), llm-router-evaluation.15 (evaluation execution)
  **Dependencies**: 4.7, 1.3

- [ ] 5.2 Create `src/services/evaluation_service.py` — `EvaluationService` with `create_dataset()`, `run_evaluation()`, `get_results()`
  **Dependencies**: 5.1

- [ ] 5.3 Write tests for human review integration — structured score collection, weight application
  **Spec scenarios**: llm-router-evaluation.11 (human review integration)
  **Dependencies**: 5.2

- [ ] 5.4 Extend `ReviewService` to optionally collect structured quality scores during review workflow
  **Dependencies**: 5.3

## Phase 6: Threshold Calibration

- [ ] 6.1 Write tests for `ThresholdCalibrator` — threshold computation, minimum sample enforcement, cost savings estimation
  **Spec scenarios**: llm-router-evaluation.12 (automated calibration), llm-router-evaluation.13 (minimum samples)
  **Dependencies**: 5.2, 3.2

- [ ] 6.2 Create `src/evaluation/calibrator.py` — `ThresholdCalibrator` with `calibrate()`, `estimate_savings()`
  **Dependencies**: 6.1

- [ ] 6.3 Write tests for classifier training — train from evaluation data, persist model, load model
  **Dependencies**: 6.2

- [ ] 6.4 Implement classifier training in `ComplexityRouter.train()` — logistic regression on evaluation embeddings + judge preferences
  **Dependencies**: 6.3

## Phase 7: CLI & API

- [ ] 7.1 Write tests for CLI commands — create-dataset, run, calibrate, compare, report, list-datasets
  **Spec scenarios**: llm-router-evaluation.18 (CLI commands)
  **Dependencies**: 6.2, 5.2

- [ ] 7.2 Create `src/cli/evaluate_commands.py` — CLI command group `aca evaluate` with all subcommands
  **Dependencies**: 7.1

- [ ] 7.3 Register CLI commands in main CLI entrypoint
  **Dependencies**: 7.2

- [ ] 7.4 Write tests for API endpoints — CRUD routing configs, dataset management, evaluation execution, reporting
  **Spec scenarios**: llm-router-evaluation.19 (API endpoints)
  **Dependencies**: 5.2, 6.2

- [ ] 7.5 Create `src/api/evaluation.py` — FastAPI router with all evaluation endpoints
  **Dependencies**: 7.4

- [ ] 7.6 Register API router in main FastAPI app
  **Dependencies**: 7.5

## Phase 8: Cost Reporting & Documentation

- [ ] 8.1 Write tests for cost savings report — per-step metrics, aggregate savings, recommendations
  **Spec scenarios**: llm-router-evaluation.17 (cost savings reporting)
  **Dependencies**: 7.2

- [ ] 8.2 Implement cost reporting in `EvaluationService.generate_report()` — query routing_decisions, compute savings vs. all-strong baseline
  **Dependencies**: 8.1

- [ ] 8.3 Update `docs/MODEL_CONFIGURATION.md` with dynamic routing documentation
  **Dependencies**: 7.6

- [ ] 8.4 Add evaluation section to `CLAUDE.md` quick reference
  **Dependencies**: 8.3

- [ ] 8.5 End-to-end integration test — create dataset → run evaluation → calibrate → enable dynamic routing → verify routing decisions logged
  **Dependencies**: All previous phases

## Task Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1. Database | 4 | Schema, models, migration |
| 2. Config | 4 | Routing configuration, YAML, overrides |
| 3. Router | 6 | ComplexityRouter, LLMRouter integration, decision logging |
| 4. Judge | 7 | Quality criteria, single judge, multi-judge consensus |
| 5. Service | 4 | EvaluationService, datasets, human review |
| 6. Calibration | 4 | Threshold discovery, classifier training |
| 7. CLI & API | 6 | CLI commands, API endpoints |
| 8. Reporting | 5 | Cost reporting, docs, E2E test |
| **Total** | **40** | |
