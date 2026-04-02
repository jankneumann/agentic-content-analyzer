"""Quality criteria management for LLM-as-Judge evaluation.

Loads per-step evaluation rubrics from settings/evaluation.yaml.
Each step has quality dimensions with description and fail_when fields.
Steps without custom criteria fall back to _default dimensions.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path(__file__).parent.parent.parent / "settings"
_EVALUATION_YAML = _SETTINGS_DIR / "evaluation.yaml"


@dataclass
class QualityDimension:
    """A single quality dimension for evaluation."""
    name: str
    description: str
    fail_when: str


@dataclass
class StepCriteria:
    """Quality criteria for a specific pipeline step."""
    step: str
    dimensions: list[QualityDimension] = field(default_factory=list)

    def dimension_names(self) -> list[str]:
        return [d.name for d in self.dimensions]


@dataclass
class JudgeConfig:
    """Configuration for a single judge model."""
    model: str
    weight: float = 1.0


@dataclass
class EvaluationConfig:
    """Top-level evaluation configuration."""
    judges: list[JudgeConfig] = field(default_factory=list)
    human_review_weight: float = 2.0
    criteria: dict[str, StepCriteria] = field(default_factory=dict)


def _parse_dimensions(dimensions_dict: dict) -> list[QualityDimension]:
    """Parse dimension dict from YAML into QualityDimension objects."""
    return [
        QualityDimension(
            name=name,
            description=dim_data["description"],
            fail_when=dim_data["fail_when"],
        )
        for name, dim_data in dimensions_dict.items()
    ]


def load_evaluation_config(config_path: Path | None = None) -> EvaluationConfig:
    """Load evaluation configuration from YAML.

    Args:
        config_path: Path to evaluation.yaml. Defaults to settings/evaluation.yaml.

    Returns:
        EvaluationConfig with judges, criteria, and human review weight.
    """
    path = config_path or _EVALUATION_YAML
    if not path.exists():
        logger.warning("Evaluation config not found at %s, using defaults", path)
        return EvaluationConfig(
            criteria={"_default": StepCriteria(
                step="_default",
                dimensions=[
                    QualityDimension("accuracy", "Key facts are faithfully represented", "Misrepresents facts or hallucinates"),
                    QualityDimension("completeness", "All important points are captured", "Omits major themes or findings"),
                    QualityDimension("conciseness", "No unnecessary repetition", "Contains redundant content"),
                    QualityDimension("clarity", "Clear, accessible language", "Uses ambiguous or convoluted phrasing"),
                ],
            )}
        )

    with open(path) as f:
        raw = yaml.safe_load(f)

    eval_section = raw.get("evaluation", {})

    # Parse judges
    judges = [
        JudgeConfig(model=j["model"], weight=j.get("weight", 1.0))
        for j in eval_section.get("judges", [])
    ]

    # Parse criteria
    criteria = {}
    for step_name, dims in eval_section.get("criteria", {}).items():
        criteria[step_name] = StepCriteria(
            step=step_name,
            dimensions=_parse_dimensions(dims),
        )

    return EvaluationConfig(
        judges=judges,
        human_review_weight=eval_section.get("human_review_weight", 2.0),
        criteria=criteria,
    )


def get_criteria_for_step(config: EvaluationConfig, step: str) -> StepCriteria:
    """Get quality criteria for a pipeline step, falling back to _default.

    Args:
        config: Loaded evaluation configuration
        step: Pipeline step name (e.g., "summarization")

    Returns:
        StepCriteria for the step, or _default if not defined
    """
    if step in config.criteria:
        return config.criteria[step]
    if "_default" in config.criteria:
        logger.debug("No custom criteria for step '%s', using _default", step)
        return config.criteria["_default"]
    raise ValueError(f"No criteria found for step '{step}' and no _default defined")
