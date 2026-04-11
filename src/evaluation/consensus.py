"""Multi-judge consensus engine for evaluation.

Runs multiple LLM judges on the same evaluation pair and computes
consensus preference via majority vote with defined tie-breaking rules.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field

from src.evaluation.judge import JudgeResult, LLMJudge

logger = logging.getLogger(__name__)


@dataclass
class ConsensusResult:
    """Aggregated result from multiple judges."""

    consensus_preference: str  # "strong_wins", "weak_wins", "tie"
    agreement_rate: float  # 0.0 to 1.0
    dimension_verdicts: dict  # {"dim": {"pass": N, "fail": M}}
    judge_results: list[JudgeResult] = field(default_factory=list)
    failed_judges: list[str] = field(default_factory=list)  # Models that errored

    @property
    def total_judges(self) -> int:
        return len(self.judge_results) + len(self.failed_judges)

    @property
    def successful_judges(self) -> int:
        return len(self.judge_results)


def _compute_majority_preference(results: list[JudgeResult]) -> tuple[str, float]:
    """Compute majority-vote preference with tie-breaking rules (D5c).

    Rules:
    - 1 judge: judge's preference is the consensus
    - 2 judges, same: that preference (agreement_rate=1.0)
    - 2 judges, split: tie (agreement_rate=0.0)
    - 3 judges, 2+ agree: majority wins
    - 3 judges, 3-way split: tie (agreement_rate=0.33)

    Returns:
        Tuple of (consensus_preference, agreement_rate)
    """
    if not results:
        return "tie", 0.0

    preferences = [r.preference for r in results]
    counts = Counter(preferences)
    n = len(preferences)

    if n == 1:
        return preferences[0], 1.0

    # Find the most common preference
    most_common = counts.most_common()
    top_count = most_common[0][1]

    # Check if there's a clear majority (more than any other)
    if top_count > n / 2:
        winner = most_common[0][0]
        agreement_rate = top_count / n
        return winner, round(agreement_rate, 2)

    # No majority — tie
    # Agreement rate is the max count / total
    agreement_rate = top_count / n
    return "tie", round(agreement_rate, 2)


def _compute_dimension_verdicts(results: list[JudgeResult]) -> dict:
    """Aggregate per-dimension pass/fail tallies across judges.

    Returns:
        Dict mapping dimension name to {"pass": count, "fail": count}
    """
    tallies: dict[str, dict[str, int]] = {}
    for result in results:
        for critique in result.critiques:
            if critique.dimension not in tallies:
                tallies[critique.dimension] = {"pass": 0, "fail": 0}
            if critique.verdict in ("pass", "fail"):
                tallies[critique.dimension][critique.verdict] += 1
    return tallies


class ConsensusEngine:
    """Run multiple judges and compute consensus.

    Handles individual judge failures gracefully — continues with
    remaining judges as long as at least one succeeds.
    """

    def __init__(self, judges: list[LLMJudge]):
        """Initialize with a list of judges.

        Args:
            judges: List of LLMJudge instances (1-3 judges)
        """
        if not judges:
            raise ValueError("At least one judge is required")
        if len(judges) > 3:
            raise ValueError("Maximum 3 judges supported")
        self.judges = judges

    async def evaluate_with_consensus(
        self,
        step: str,
        prompt_text: str,
        strong_output: str,
        weak_output: str,
    ) -> ConsensusResult:
        """Run all judges and compute consensus preference.

        Individual judge failures are handled gracefully — the failed judge
        is logged and excluded from consensus. At least one judge must succeed.

        Args:
            step: Pipeline step name
            prompt_text: Original prompt
            strong_output: Output from strong model
            weak_output: Output from weak model

        Returns:
            ConsensusResult with preference, agreement rate, and per-dimension tallies

        Raises:
            RuntimeError: If ALL judges fail
        """
        results: list[JudgeResult] = []
        failed: list[str] = []

        for judge in self.judges:
            try:
                result = await judge.evaluate_pair(
                    step=step,
                    prompt_text=prompt_text,
                    strong_output=strong_output,
                    weak_output=weak_output,
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Judge %s failed for step '%s': %s",
                    judge.judge_model,
                    step,
                    e,
                )
                failed.append(judge.judge_model)

        if not results:
            raise RuntimeError(
                f"All {len(self.judges)} judges failed for step '{step}'. Failed judges: {failed}"
            )

        if failed:
            logger.warning(
                "%d/%d judges failed, computing consensus from %d results",
                len(failed),
                len(self.judges),
                len(results),
            )

        preference, agreement_rate = _compute_majority_preference(results)
        dimension_verdicts = _compute_dimension_verdicts(results)

        return ConsensusResult(
            consensus_preference=preference,
            agreement_rate=agreement_rate,
            dimension_verdicts=dimension_verdicts,
            judge_results=results,
            failed_judges=failed,
        )
