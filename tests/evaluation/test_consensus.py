"""Tests for ConsensusEngine multi-judge evaluation.

Tests cover:
- Majority vote with 1/2/3 judges
- 2-judge split → tie (D5c)
- 3-judge 3-way split → tie (D5c)
- Agreement rate calculation
- Per-dimension verdict tally
- Single judge failure handling
- All judges failure raises RuntimeError
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.evaluation.consensus import (
    ConsensusEngine,
    ConsensusResult,
    _compute_dimension_verdicts,
    _compute_majority_preference,
)
from src.evaluation.judge import DimensionCritique, JudgeResult, LLMJudge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(preference: str, critiques: list[DimensionCritique] | None = None) -> JudgeResult:
    if critiques is None:
        critiques = [
            DimensionCritique("accuracy", "pass", "ok"),
            DimensionCritique("completeness", "pass", "ok"),
        ]
    return JudgeResult(
        judge_model="test-model",
        preference=preference,
        critiques=critiques,
        reasoning="test",
        position_order="strong_first",
    )


def _make_judge(preference: str = "tie", should_fail: bool = False) -> LLMJudge:
    """Create a mock LLMJudge that returns a fixed preference or raises."""
    judge = MagicMock(spec=LLMJudge)
    judge.judge_model = "test-model"
    if should_fail:
        judge.evaluate_pair = AsyncMock(side_effect=RuntimeError("Judge failed"))
    else:
        judge.evaluate_pair = AsyncMock(return_value=_make_result(preference))
    return judge


# ---------------------------------------------------------------------------
# _compute_majority_preference
# ---------------------------------------------------------------------------

class TestComputeMajorityPreference:
    def test_single_judge(self):
        results = [_make_result("strong_wins")]
        pref, rate = _compute_majority_preference(results)
        assert pref == "strong_wins"
        assert rate == 1.0

    def test_two_judges_agree(self):
        results = [_make_result("weak_wins"), _make_result("weak_wins")]
        pref, rate = _compute_majority_preference(results)
        assert pref == "weak_wins"
        assert rate == 1.0

    def test_two_judges_split_is_tie(self):
        results = [_make_result("strong_wins"), _make_result("weak_wins")]
        pref, rate = _compute_majority_preference(results)
        assert pref == "tie"
        assert rate == 0.5

    def test_three_judges_majority(self):
        results = [
            _make_result("strong_wins"),
            _make_result("strong_wins"),
            _make_result("weak_wins"),
        ]
        pref, rate = _compute_majority_preference(results)
        assert pref == "strong_wins"
        assert rate == 0.67

    def test_three_judges_three_way_split_is_tie(self):
        results = [
            _make_result("strong_wins"),
            _make_result("weak_wins"),
            _make_result("tie"),
        ]
        pref, rate = _compute_majority_preference(results)
        assert pref == "tie"
        assert rate == 0.33

    def test_three_judges_all_agree(self):
        results = [_make_result("tie"), _make_result("tie"), _make_result("tie")]
        pref, rate = _compute_majority_preference(results)
        assert pref == "tie"
        assert rate == 1.0

    def test_empty_results(self):
        pref, rate = _compute_majority_preference([])
        assert pref == "tie"
        assert rate == 0.0


# ---------------------------------------------------------------------------
# _compute_dimension_verdicts
# ---------------------------------------------------------------------------

class TestComputeDimensionVerdicts:
    def test_tallies_pass_fail(self):
        results = [
            _make_result("tie", [
                DimensionCritique("accuracy", "pass", "ok"),
                DimensionCritique("completeness", "fail", "missing"),
            ]),
            _make_result("tie", [
                DimensionCritique("accuracy", "pass", "ok"),
                DimensionCritique("completeness", "pass", "ok"),
            ]),
        ]
        verdicts = _compute_dimension_verdicts(results)
        assert verdicts["accuracy"] == {"pass": 2, "fail": 0}
        assert verdicts["completeness"] == {"pass": 1, "fail": 1}

    def test_empty_results(self):
        verdicts = _compute_dimension_verdicts([])
        assert verdicts == {}


# ---------------------------------------------------------------------------
# ConsensusEngine
# ---------------------------------------------------------------------------

class TestConsensusEngine:
    def test_requires_at_least_one_judge(self):
        with pytest.raises(ValueError, match="At least one judge"):
            ConsensusEngine([])

    def test_max_three_judges(self):
        judges = [_make_judge() for _ in range(4)]
        with pytest.raises(ValueError, match="Maximum 3 judges"):
            ConsensusEngine(judges)

    @pytest.mark.asyncio
    async def test_single_judge_consensus(self):
        engine = ConsensusEngine([_make_judge("strong_wins")])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.consensus_preference == "strong_wins"
        assert result.agreement_rate == 1.0
        assert result.successful_judges == 1
        assert len(result.failed_judges) == 0

    @pytest.mark.asyncio
    async def test_two_judges_agree(self):
        engine = ConsensusEngine([
            _make_judge("weak_wins"),
            _make_judge("weak_wins"),
        ])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.consensus_preference == "weak_wins"
        assert result.agreement_rate == 1.0

    @pytest.mark.asyncio
    async def test_two_judges_split(self):
        engine = ConsensusEngine([
            _make_judge("strong_wins"),
            _make_judge("weak_wins"),
        ])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.consensus_preference == "tie"

    @pytest.mark.asyncio
    async def test_three_judges_majority(self):
        engine = ConsensusEngine([
            _make_judge("strong_wins"),
            _make_judge("strong_wins"),
            _make_judge("weak_wins"),
        ])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.consensus_preference == "strong_wins"
        assert result.agreement_rate == 0.67

    @pytest.mark.asyncio
    async def test_one_judge_failure_continues(self):
        engine = ConsensusEngine([
            _make_judge("strong_wins"),
            _make_judge(should_fail=True),
        ])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.consensus_preference == "strong_wins"
        assert result.successful_judges == 1
        assert len(result.failed_judges) == 1

    @pytest.mark.asyncio
    async def test_all_judges_fail_raises(self):
        engine = ConsensusEngine([
            _make_judge(should_fail=True),
            _make_judge(should_fail=True),
        ])
        with pytest.raises(RuntimeError, match="All .* judges failed"):
            await engine.evaluate_with_consensus(
                "summarization", "prompt", "strong", "weak"
            )

    @pytest.mark.asyncio
    async def test_dimension_verdicts_aggregated(self):
        judge1 = _make_judge("tie")
        judge1.evaluate_pair.return_value = _make_result("tie", [
            DimensionCritique("accuracy", "pass", "ok"),
            DimensionCritique("completeness", "fail", "missing"),
        ])
        judge2 = _make_judge("tie")
        judge2.evaluate_pair.return_value = _make_result("tie", [
            DimensionCritique("accuracy", "fail", "wrong"),
            DimensionCritique("completeness", "pass", "ok"),
        ])

        engine = ConsensusEngine([judge1, judge2])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.dimension_verdicts["accuracy"] == {"pass": 1, "fail": 1}
        assert result.dimension_verdicts["completeness"] == {"pass": 1, "fail": 1}

    @pytest.mark.asyncio
    async def test_total_and_successful_judges(self):
        engine = ConsensusEngine([
            _make_judge("tie"),
            _make_judge(should_fail=True),
            _make_judge("tie"),
        ])
        result = await engine.evaluate_with_consensus(
            "summarization", "prompt", "strong", "weak"
        )
        assert result.total_judges == 3
        assert result.successful_judges == 2
