"""Tests for LLM-as-Judge evaluation.

Tests cover:
- Judge prompt construction (blinded A/B, criteria from YAML)
- Binary preference parsing from JSON response
- Pass/fail per-dimension critique validation
- Position bias mitigation (A/B randomization)
- Parse failure retry behavior
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.evaluation.criteria import (
    EvaluationConfig,
    QualityDimension,
    StepCriteria,
)
from src.evaluation.judge import (
    DimensionCritique,
    LLMJudge,
    _map_preference,
    _parse_judge_response,
    build_judge_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_criteria():
    return StepCriteria(
        step="summarization",
        dimensions=[
            QualityDimension("accuracy", "Facts are correct", "Misrepresents facts"),
            QualityDimension("completeness", "All points covered", "Omits major points"),
        ],
    )


@pytest.fixture
def eval_config(sample_criteria):
    return EvaluationConfig(
        criteria={
            "summarization": sample_criteria,
            "_default": StepCriteria(
                step="_default",
                dimensions=[
                    QualityDimension("accuracy", "Facts are correct", "Misrepresents facts"),
                ],
            ),
        }
    )


@pytest.fixture
def mock_router():
    router = MagicMock()
    router.generate = AsyncMock()
    return router


@pytest.fixture
def judge(mock_router, eval_config):
    return LLMJudge(
        judge_model="claude-sonnet-4-5",
        router=mock_router,
        eval_config=eval_config,
    )


# ---------------------------------------------------------------------------
# build_judge_prompt
# ---------------------------------------------------------------------------

class TestBuildJudgePrompt:
    def test_includes_step_name(self, sample_criteria):
        prompt = build_judge_prompt("summarization", sample_criteria, "out A", "out B")
        assert "summarization" in prompt

    def test_includes_all_dimensions(self, sample_criteria):
        prompt = build_judge_prompt("summarization", sample_criteria, "out A", "out B")
        assert "accuracy" in prompt
        assert "completeness" in prompt
        assert "Facts are correct" in prompt
        assert "Misrepresents facts" in prompt

    def test_includes_both_outputs(self, sample_criteria):
        prompt = build_judge_prompt("summarization", sample_criteria, "OUTPUT_A_TEXT", "OUTPUT_B_TEXT")
        assert "OUTPUT_A_TEXT" in prompt
        assert "OUTPUT_B_TEXT" in prompt

    def test_includes_json_format_instructions(self, sample_criteria):
        prompt = build_judge_prompt("summarization", sample_criteria, "A", "B")
        assert "preference" in prompt
        assert "A_wins" in prompt
        assert "B_wins" in prompt
        assert "tie" in prompt
        assert "critiques" in prompt

    def test_does_not_reveal_model_identity(self, sample_criteria):
        prompt = build_judge_prompt("summarization", sample_criteria, "out A", "out B")
        assert "strong" not in prompt.lower() or "strong_wins" not in prompt
        assert "weak" not in prompt.lower() or "weak_wins" not in prompt
        # Only "Output A" and "Output B" labels
        assert "Output A" in prompt
        assert "Output B" in prompt


# ---------------------------------------------------------------------------
# _parse_judge_response
# ---------------------------------------------------------------------------

class TestParseJudgeResponse:
    def test_valid_response(self, sample_criteria):
        response = json.dumps({
            "preference": "A_wins",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "Both accurate"},
                "completeness": {"verdict": "fail", "explanation": "Missing key point"},
            },
            "reasoning": "A is better overall",
        })
        pref, critiques, reasoning = _parse_judge_response(response, sample_criteria)
        assert pref == "A_wins"
        assert len(critiques) == 2
        assert critiques[0].dimension == "accuracy"
        assert critiques[0].verdict == "pass"
        assert critiques[1].verdict == "fail"
        assert reasoning == "A is better overall"

    def test_strips_markdown_fences(self, sample_criteria):
        response = "```json\n" + json.dumps({
            "preference": "tie",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "Equal",
        }) + "\n```"
        pref, _, _ = _parse_judge_response(response, sample_criteria)
        assert pref == "tie"

    def test_missing_dimension_defaults_to_pass(self, sample_criteria):
        response = json.dumps({
            "preference": "B_wins",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                # completeness is missing
            },
            "reasoning": "B wins",
        })
        _, critiques, _ = _parse_judge_response(response, sample_criteria)
        assert len(critiques) == 2
        comp = [c for c in critiques if c.dimension == "completeness"][0]
        assert comp.verdict == "pass"
        assert "not evaluated" in comp.explanation

    def test_invalid_json_raises(self, sample_criteria):
        with pytest.raises(ValueError, match="not valid JSON"):
            _parse_judge_response("not json at all", sample_criteria)

    def test_invalid_preference_raises(self, sample_criteria):
        response = json.dumps({
            "preference": "invalid_value",
            "critiques": {},
            "reasoning": "",
        })
        with pytest.raises(ValueError, match="Invalid preference"):
            _parse_judge_response(response, sample_criteria)

    def test_malformed_verdict_defaults_to_pass(self, sample_criteria):
        response = json.dumps({
            "preference": "A_wins",
            "critiques": {
                "accuracy": {"verdict": "maybe", "explanation": "unclear"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "A wins",
        })
        _, critiques, _ = _parse_judge_response(response, sample_criteria)
        assert critiques[0].verdict == "pass"  # Defaults to pass


# ---------------------------------------------------------------------------
# _map_preference
# ---------------------------------------------------------------------------

class TestMapPreference:
    def test_tie_always_tie(self):
        assert _map_preference("tie", strong_is_a=True) == "tie"
        assert _map_preference("tie", strong_is_a=False) == "tie"

    def test_a_wins_strong_first(self):
        assert _map_preference("A_wins", strong_is_a=True) == "strong_wins"

    def test_a_wins_weak_first(self):
        assert _map_preference("A_wins", strong_is_a=False) == "weak_wins"

    def test_b_wins_strong_first(self):
        assert _map_preference("B_wins", strong_is_a=True) == "weak_wins"

    def test_b_wins_weak_first(self):
        assert _map_preference("B_wins", strong_is_a=False) == "strong_wins"


# ---------------------------------------------------------------------------
# LLMJudge.evaluate_pair
# ---------------------------------------------------------------------------

class TestLLMJudgeEvaluatePair:
    @pytest.mark.asyncio
    async def test_successful_evaluation(self, judge, mock_router):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "preference": "A_wins",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "Both accurate"},
                "completeness": {"verdict": "pass", "explanation": "Both complete"},
            },
            "reasoning": "A is slightly better",
        })
        mock_router.generate.return_value = mock_response

        result = await judge.evaluate_pair(
            step="summarization",
            prompt_text="Summarize this article",
            strong_output="Strong summary",
            weak_output="Weak summary",
        )

        assert result.judge_model == "claude-sonnet-4-5"
        assert result.preference in ("strong_wins", "weak_wins", "tie")
        assert len(result.critiques) == 2
        assert result.position_order in ("strong_first", "weak_first")
        assert result.reasoning == "A is slightly better"

    @pytest.mark.asyncio
    async def test_retry_on_parse_failure(self, judge, mock_router):
        """First call returns invalid JSON, retry succeeds."""
        bad_response = MagicMock()
        bad_response.text = "Not JSON"
        good_response = MagicMock()
        good_response.text = json.dumps({
            "preference": "tie",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "Equal quality",
        })
        mock_router.generate.side_effect = [bad_response, good_response]

        result = await judge.evaluate_pair(
            step="summarization",
            prompt_text="prompt",
            strong_output="strong",
            weak_output="weak",
        )
        assert result.preference == "tie"
        assert mock_router.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_both_attempts_fail(self, judge, mock_router):
        bad_response = MagicMock()
        bad_response.text = "Not JSON"
        mock_router.generate.return_value = bad_response

        with pytest.raises(ValueError, match="not valid JSON"):
            await judge.evaluate_pair(
                step="summarization",
                prompt_text="prompt",
                strong_output="strong",
                weak_output="weak",
            )

    @pytest.mark.asyncio
    async def test_position_randomization(self, judge, mock_router):
        """Run multiple evaluations and verify both positions occur."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "preference": "tie",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "Equal",
        })
        mock_router.generate.return_value = mock_response

        positions = set()
        for _ in range(20):
            result = await judge.evaluate_pair(
                step="summarization",
                prompt_text="prompt",
                strong_output="strong",
                weak_output="weak",
            )
            positions.add(result.position_order)

        # With 20 trials, probability of NOT seeing both positions is ~(0.5^20)*2 ≈ 0.000002
        assert "strong_first" in positions
        assert "weak_first" in positions

    @pytest.mark.asyncio
    async def test_low_temperature_for_evaluation(self, judge, mock_router):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "preference": "tie",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "Equal",
        })
        mock_router.generate.return_value = mock_response

        await judge.evaluate_pair("summarization", "prompt", "strong", "weak")

        # Verify low temperature was used
        call_kwargs = mock_router.generate.call_args.kwargs
        assert call_kwargs.get("temperature", 1.0) <= 0.2

    @pytest.mark.asyncio
    async def test_uses_step_criteria(self, judge, mock_router):
        """Verify the judge prompt includes step-specific criteria."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "preference": "tie",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "ok"},
                "completeness": {"verdict": "pass", "explanation": "ok"},
            },
            "reasoning": "Equal",
        })
        mock_router.generate.return_value = mock_response

        await judge.evaluate_pair("summarization", "prompt", "strong", "weak")

        call_kwargs = mock_router.generate.call_args.kwargs
        user_prompt = call_kwargs.get("user_prompt", "")
        assert "accuracy" in user_prompt
        assert "completeness" in user_prompt
        assert "Misrepresents facts" in user_prompt

    @pytest.mark.asyncio
    async def test_critiques_as_dict(self, judge, mock_router):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "preference": "A_wins",
            "critiques": {
                "accuracy": {"verdict": "pass", "explanation": "good"},
                "completeness": {"verdict": "fail", "explanation": "missing"},
            },
            "reasoning": "A better",
        })
        mock_router.generate.return_value = mock_response

        result = await judge.evaluate_pair("summarization", "prompt", "strong", "weak")
        d = result.critiques_as_dict()
        assert "accuracy" in d
        assert d["accuracy"]["verdict"] == "pass"
        assert d["completeness"]["verdict"] == "fail"
