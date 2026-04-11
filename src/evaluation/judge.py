"""LLM-as-Judge evaluation for model output quality assessment.

Implements blinded pairwise evaluation with position bias mitigation.
Judges compare two model outputs using step-specific quality criteria
and produce binary preferences with per-dimension pass/fail critiques.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from typing import Any

from src.evaluation.criteria import EvaluationConfig, StepCriteria, get_criteria_for_step

logger = logging.getLogger(__name__)


@dataclass
class DimensionCritique:
    """Pass/fail verdict for a single quality dimension."""

    dimension: str
    verdict: str  # "pass" or "fail"
    explanation: str


@dataclass
class JudgeResult:
    """Result from a single judge evaluation."""

    judge_model: str
    preference: str  # "strong_wins", "weak_wins", "tie"
    critiques: list[DimensionCritique]
    reasoning: str
    position_order: str  # "strong_first" or "weak_first"
    raw_response: str | None = None

    def critiques_as_dict(self) -> dict:
        """Convert critiques to JSON-serializable dict."""
        return {
            c.dimension: {"verdict": c.verdict, "explanation": c.explanation}
            for c in self.critiques
        }


def build_judge_prompt(
    step_name: str,
    criteria: StepCriteria,
    output_a: str,
    output_b: str,
    prompt_text: str = "",
) -> str:
    """Construct the judge evaluation prompt with criteria and blinded outputs.

    Args:
        step_name: Pipeline step name for context
        criteria: Quality dimensions with descriptions and fail_when
        output_a: First output (blinded)
        output_b: Second output (blinded)
        prompt_text: Original prompt/input that produced the outputs

    Returns:
        Complete judge prompt string
    """
    dimensions_text = ""
    for i, dim in enumerate(criteria.dimensions, 1):
        dimensions_text += (
            f"{i}. **{dim.name}**: {dim.description}\n   - FAIL when: {dim.fail_when}\n\n"
        )

    dim_names = ", ".join(f'"{d.name}"' for d in criteria.dimensions)

    prompt_section = ""
    if prompt_text:
        prompt_section = f"""## Original Input
{prompt_text}

"""

    return f"""You are evaluating two outputs for a {step_name} task.

{prompt_section}## Quality Dimensions
For each dimension, assess BOTH outputs and give a binary verdict (pass/fail) with a brief explanation.

{dimensions_text}
## Outputs

**Output A:**
{output_a}

**Output B:**
{output_b}

## Instructions
Compare both outputs against the quality dimensions above. For each dimension, determine if EACH output passes or fails. Then decide your overall preference.

Return ONLY a JSON object with this exact structure (no markdown fences, no extra text):
{{
  "preference": "A_wins" or "B_wins" or "tie",
  "critiques": {{
    {dim_names}: {{"verdict": "pass" or "fail", "explanation": "brief reason"}},
    ...for each dimension...
  }},
  "reasoning": "Overall comparison explanation (1-2 sentences)"
}}"""


def _parse_judge_response(
    response_text: str,
    criteria: StepCriteria,
) -> tuple[str, list[DimensionCritique], str]:
    """Parse the judge's JSON response into structured data.

    Args:
        response_text: Raw text from the judge model
        criteria: Expected dimensions for validation

    Returns:
        Tuple of (preference, critiques, reasoning)

    Raises:
        ValueError: If response cannot be parsed or is missing required fields
    """
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge response is not valid JSON: {e}") from e

    # Validate preference
    preference = data.get("preference")
    if preference not in ("A_wins", "B_wins", "tie"):
        raise ValueError(f"Invalid preference: {preference}")

    # Parse critiques
    critiques_data = data.get("critiques", {})
    critiques = []
    for dim in criteria.dimensions:
        if dim.name in critiques_data:
            c = critiques_data[dim.name]
            verdict = c.get("verdict", "pass")
            if verdict not in ("pass", "fail"):
                verdict = "pass"  # Default to pass if malformed
            critiques.append(
                DimensionCritique(
                    dimension=dim.name,
                    verdict=verdict,
                    explanation=c.get("explanation", ""),
                )
            )
        else:
            # Missing dimension — treat as pass with note
            critiques.append(
                DimensionCritique(
                    dimension=dim.name,
                    verdict="pass",
                    explanation="(dimension not evaluated by judge)",
                )
            )

    reasoning = data.get("reasoning", "")
    return preference, critiques, reasoning


def _map_preference(ab_preference: str, strong_is_a: bool) -> str:
    """Map A/B preference back to strong/weak preference.

    Args:
        ab_preference: "A_wins", "B_wins", or "tie"
        strong_is_a: Whether the strong model's output was presented as Output A

    Returns:
        "strong_wins", "weak_wins", or "tie"
    """
    if ab_preference == "tie":
        return "tie"
    if ab_preference == "A_wins":
        return "strong_wins" if strong_is_a else "weak_wins"
    # B_wins
    return "weak_wins" if strong_is_a else "strong_wins"


class LLMJudge:
    """Single-judge evaluator using an LLM to compare model outputs.

    Implements blinded pairwise evaluation with:
    - Randomized A/B presentation (position bias mitigation)
    - Step-specific quality criteria
    - Binary preference + per-dimension pass/fail critiques
    - Parse failure retry (one attempt)
    """

    def __init__(
        self,
        judge_model: str,
        router: Any,  # LLMRouter instance — not typed to avoid circular import
        eval_config: EvaluationConfig,
        weight: float = 1.0,
    ):
        """Initialize the judge.

        Args:
            judge_model: Model ID for the judge (e.g., "claude-sonnet-4-5")
            router: LLMRouter instance for generating judge responses
            eval_config: Evaluation configuration with criteria
            weight: Weight of this judge in consensus (default 1.0)
        """
        self.judge_model = judge_model
        self.router = router
        self.eval_config = eval_config
        self.weight = weight

    async def evaluate_pair(
        self,
        step: str,
        prompt_text: str,
        strong_output: str,
        weak_output: str,
    ) -> JudgeResult:
        """Evaluate a pair of model outputs with blinded presentation.

        The strong and weak outputs are randomly assigned to Output A/B
        positions to mitigate position bias.

        Args:
            step: Pipeline step name (e.g., "summarization")
            prompt_text: Original prompt (for context)
            strong_output: Output from the strong (more capable) model
            weak_output: Output from the weak (cheaper) model

        Returns:
            JudgeResult with preference, critiques, and position tracking

        Raises:
            ValueError: If judge response cannot be parsed after retry
        """
        criteria = get_criteria_for_step(self.eval_config, step)

        # Randomize position (D5a: position bias mitigation)
        strong_is_a = random.random() < 0.5  # noqa: S311
        if strong_is_a:
            output_a, output_b = strong_output, weak_output
            position_order = "strong_first"
        else:
            output_a, output_b = weak_output, strong_output
            position_order = "weak_first"

        judge_prompt = build_judge_prompt(step, criteria, output_a, output_b, prompt_text)
        system_prompt = (
            "You are an expert evaluator assessing the quality of AI-generated content. "
            "Be rigorous and specific in your assessment. Always respond with valid JSON only."
        )

        # First attempt
        response = await self.router.generate(
            model=self.judge_model,
            system_prompt=system_prompt,
            user_prompt=judge_prompt,
            temperature=0.1,  # Low temperature for consistent evaluation
            max_tokens=2048,
        )

        try:
            ab_preference, critiques, reasoning = _parse_judge_response(response.text, criteria)
        except ValueError as e:
            logger.warning(
                "Judge %s parse failed (attempt 1): %s. Retrying with explicit format reminder.",
                self.judge_model,
                e,
            )
            # Retry with more explicit instructions (spec 15c)
            retry_prompt = (
                judge_prompt + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                "Return ONLY a JSON object, no markdown fences, no extra text."
            )
            response = await self.router.generate(
                model=self.judge_model,
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
                temperature=0.0,
                max_tokens=2048,
            )
            # Second attempt — let ValueError propagate
            ab_preference, critiques, reasoning = _parse_judge_response(response.text, criteria)

        # Map A/B preference back to strong/weak
        preference = _map_preference(ab_preference, strong_is_a)

        return JudgeResult(
            judge_model=self.judge_model,
            preference=preference,
            critiques=critiques,
            reasoning=reasoning,
            position_order=position_order,
            raw_response=response.text,
        )
