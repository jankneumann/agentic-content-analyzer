"""Evaluation service for dataset creation, judge execution, and result management.

Orchestrates the evaluation pipeline:
1. Create evaluation datasets from pipeline history
2. Generate outputs from strong and weak models
3. Run judge evaluation on each sample
4. Store results and compute consensus
"""

import hashlib
import logging
from dataclasses import dataclass

from src.evaluation.consensus import ConsensusEngine, ConsensusResult
from src.evaluation.criteria import EvaluationConfig, load_evaluation_config
from src.evaluation.judge import LLMJudge

logger = logging.getLogger(__name__)


@dataclass
class DatasetInfo:
    """Summary information about an evaluation dataset."""
    id: int
    step: str
    name: str | None
    status: str
    sample_count: int
    strong_model: str
    weak_model: str


@dataclass
class EvaluationReport:
    """Cost savings and quality report."""
    step: str
    total_decisions: int
    pct_routed_to_weak: float
    cost_savings_vs_all_strong: float
    preference_distribution: dict  # {"strong_wins": N, "weak_wins": N, "tie": N}
    dimension_pass_rates: dict  # {"accuracy": 0.95, ...}


class EvaluationService:
    """Service for managing evaluation datasets, running judges, and reporting."""

    def __init__(self, db_session=None, eval_config: EvaluationConfig | None = None):
        self.db = db_session
        self.eval_config = eval_config or load_evaluation_config()

    def create_dataset(
        self,
        step: str,
        name: str | None = None,
        strong_model: str = "claude-sonnet-4-5",
        weak_model: str = "claude-haiku-4-5",
        sample_count: int = 0,
    ) -> DatasetInfo:
        """Create a new evaluation dataset record."""
        from src.models.evaluation import EvaluationDataset, DatasetStatus

        dataset = EvaluationDataset(
            step=step,
            name=name or f"{step}_eval",
            status=DatasetStatus.PENDING_EVALUATION,
            sample_count=sample_count,
            strong_model=strong_model,
            weak_model=weak_model,
        )
        if self.db:
            self.db.add(dataset)
            self.db.flush()
            return DatasetInfo(
                id=dataset.id,
                step=dataset.step,
                name=dataset.name,
                status=dataset.status,
                sample_count=dataset.sample_count,
                strong_model=dataset.strong_model,
                weak_model=dataset.weak_model,
            )
        from src.models.evaluation import DatasetStatus

        return DatasetInfo(
            id=0, step=step, name=name, status=DatasetStatus.PENDING_EVALUATION,
            sample_count=sample_count, strong_model=strong_model, weak_model=weak_model,
        )

    def add_sample(
        self,
        dataset_id: int,
        prompt_text: str,
        strong_output: str | None = None,
        weak_output: str | None = None,
        strong_tokens: int = 0,
        weak_tokens: int = 0,
        strong_cost: float = 0.0,
        weak_cost: float = 0.0,
    ) -> int:
        """Add a sample to an evaluation dataset."""
        from src.models.evaluation import EvaluationSample

        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        sample = EvaluationSample(
            dataset_id=dataset_id,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            strong_output=strong_output,
            weak_output=weak_output,
            strong_tokens=strong_tokens,
            weak_tokens=weak_tokens,
            strong_cost=strong_cost,
            weak_cost=weak_cost,
        )
        if self.db:
            self.db.add(sample)
            self.db.flush()
            return sample.id
        return 0

    async def run_evaluation(
        self,
        dataset_id: int,
        consensus_engine: ConsensusEngine,
    ) -> list[ConsensusResult]:
        """Run judge evaluation on all samples in a dataset.

        Args:
            dataset_id: ID of the dataset to evaluate
            consensus_engine: Configured consensus engine with judges

        Returns:
            List of ConsensusResult for each sample
        """
        from src.models.evaluation import (
            DatasetStatus,
            EvaluationConsensus,
            EvaluationDataset,
            EvaluationResult,
            EvaluationSample,
            JudgeType,
        )

        if not self.db:
            raise RuntimeError("Database session required for run_evaluation")

        dataset = self.db.query(EvaluationDataset).get(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        samples = self.db.query(EvaluationSample).filter_by(dataset_id=dataset_id).all()
        results = []

        for sample in samples:
            if not sample.strong_output or not sample.weak_output:
                logger.warning("Sample %d missing outputs, skipping", sample.id)
                continue

            try:
                consensus = await consensus_engine.evaluate_with_consensus(
                    step=dataset.step,
                    prompt_text=sample.prompt_text,
                    strong_output=sample.strong_output,
                    weak_output=sample.weak_output,
                )

                # Store individual judge results
                for jr in consensus.judge_results:
                    eval_result = EvaluationResult(
                        sample_id=sample.id,
                        judge_model=jr.judge_model,
                        judge_type=JudgeType.LLM,
                        preference=jr.preference,
                        critiques=jr.critiques_as_dict(),
                        reasoning=jr.reasoning,
                        position_order=jr.position_order,
                        weight=1.0,
                    )
                    self.db.add(eval_result)

                # Store consensus
                eval_consensus = EvaluationConsensus(
                    sample_id=sample.id,
                    consensus_preference=consensus.consensus_preference,
                    agreement_rate=consensus.agreement_rate,
                    dimension_verdicts=consensus.dimension_verdicts,
                )
                self.db.add(eval_consensus)

                results.append(consensus)

            except Exception as e:
                logger.error("Evaluation failed for sample %d: %s", sample.id, e)
                continue

        # Update dataset status
        dataset.status = DatasetStatus.EVALUATED
        self.db.flush()

        return results

    def get_datasets(self, step: str | None = None) -> list[DatasetInfo]:
        """List evaluation datasets, optionally filtered by step."""
        from src.models.evaluation import EvaluationDataset

        if not self.db:
            return []

        query = self.db.query(EvaluationDataset)
        if step:
            query = query.filter_by(step=step)
        datasets = query.order_by(EvaluationDataset.created_at.desc()).all()

        return [
            DatasetInfo(
                id=d.id, step=d.step, name=d.name, status=d.status,
                sample_count=d.sample_count, strong_model=d.strong_model,
                weak_model=d.weak_model,
            )
            for d in datasets
        ]

    def generate_report(self, step: str | None = None) -> list[EvaluationReport]:
        """Generate cost savings report from routing decisions.

        Args:
            step: Optional filter by pipeline step

        Returns:
            List of EvaluationReport per step
        """
        from src.models.evaluation import EvaluationConsensus, EvaluationSample, RoutingDecision

        if not self.db:
            return []

        query = self.db.query(RoutingDecision)
        if step:
            query = query.filter_by(step=step)

        decisions = query.all()
        if not decisions:
            return []

        # Group by step
        by_step: dict[str, list] = {}
        for d in decisions:
            by_step.setdefault(d.step, []).append(d)

        reports = []
        for step_name, step_decisions in by_step.items():
            total = len(step_decisions)
            weak_count = sum(1 for d in step_decisions if d.model_selected == d.weak_model)
            pct_weak = weak_count / total if total > 0 else 0.0

            # Estimate cost savings: sum of (strong_cost - actual_cost) for weak-routed
            # For now, use a simplified model
            cost_savings = 0.0
            for d in step_decisions:
                if d.cost_actual is not None and d.model_selected == d.weak_model:
                    # Assume strong model would cost 3x weak model (rough estimate)
                    cost_savings += d.cost_actual * 2  # Saved 2/3 of would-be cost

            # Get preference distribution from consensus results
            pref_dist = {"strong_wins": 0, "weak_wins": 0, "tie": 0}
            dim_pass_counts: dict[str, dict[str, int]] = {}

            reports.append(EvaluationReport(
                step=step_name,
                total_decisions=total,
                pct_routed_to_weak=round(pct_weak, 3),
                cost_savings_vs_all_strong=round(cost_savings, 4),
                preference_distribution=pref_dist,
                dimension_pass_rates=dim_pass_counts,
            ))

        return reports
