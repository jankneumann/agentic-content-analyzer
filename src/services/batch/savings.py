"""Cost-savings projection for Gemini batch execution.

Pure functions (no DB, no I/O) so they unit-test directly: given per-step item
volumes, compute standard vs batch (flat 50%-off) cost using the live pricing in
:class:`ModelConfig`. The CLI (`aca evaluate batch-savings`) supplies real
``contents`` volumes; tests supply fixed ones.

This is the dry-run the project didn't have before — it answers "what would
flipping batch on actually save?" against the real model assignments and the
real corpus size.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from src.config.models import ModelStep, Provider

if TYPE_CHECKING:
    from src.config.models import ModelConfig

#: Gemini Batch API discount — a flat 50% off both input and output tokens.
BATCH_DISCOUNT = 0.5

#: Per-item (input, output) token estimates for each batch-eligible step.
#: Deliberately conservative round numbers — the report is an order-of-magnitude
#: planning aid, not an invoice. Tuned to flash-lite-class text workloads.
STEP_TOKEN_ESTIMATES: dict[ModelStep, tuple[int, int]] = {
    ModelStep.CONTENT_FILTERING: (1200, 50),  # excerpt in → short label out
    ModelStep.CAPTION_PROOFREADING: (2500, 2500),  # transcript in/out
    ModelStep.YOUTUBE_RSS_PROCESSING: (8000, 1500),  # transcript → summary
    ModelStep.YOUTUBE_PROCESSING: (8000, 1500),  # video/transcript → summary
}


@dataclass
class StepSavings:
    """Standard vs batch cost for one step at a given item volume."""

    step: str
    model_id: str
    items: int
    input_tokens_each: int
    output_tokens_each: int
    std_cost: float
    batch_cost: float
    savings: float


def compute_batch_savings(
    model_config: ModelConfig,
    volumes: dict[ModelStep, int],
) -> dict:
    """Project standard vs batch cost across all batch-eligible steps.

    Args:
        model_config: Source of per-step model assignment and pricing.
        volumes: Item count per step (e.g. backfill size or monthly throughput).

    Returns:
        A JSON-serializable dict: per-step rows plus totals and the discount.
    """
    rows: list[StepSavings] = []
    for step, (tin, tout) in STEP_TOKEN_ESTIMATES.items():
        items = int(volumes.get(step, 0))
        model_id = model_config.get_model_for_step(step)
        per_item = model_config.calculate_cost(model_id, tin, tout, Provider.GOOGLE_AI)
        std = per_item * items
        batch = std * BATCH_DISCOUNT
        rows.append(
            StepSavings(
                step=step.value,
                model_id=model_id,
                items=items,
                input_tokens_each=tin,
                output_tokens_each=tout,
                std_cost=round(std, 6),
                batch_cost=round(batch, 6),
                savings=round(std - batch, 6),
            )
        )

    total_std = round(sum(r.std_cost for r in rows), 6)
    total_batch = round(sum(r.batch_cost for r in rows), 6)
    return {
        "discount": BATCH_DISCOUNT,
        "assumptions": {
            "batch_discount": BATCH_DISCOUNT,
            "pricing_basis": "configured model input/output price per 1M tokens",
            "volume_basis": (
                "content rows for filtering; YouTube content rows for caption and video steps"
            ),
            "limitations": (
                "planning estimate only; row counts do not identify borderline filters, "
                "caption availability, or provider cache effects"
            ),
            "token_estimates": {
                step.value: {
                    "input_tokens_each": tokens[0],
                    "output_tokens_each": tokens[1],
                }
                for step, tokens in STEP_TOKEN_ESTIMATES.items()
            },
        },
        "steps": [asdict(r) for r in rows],
        "total_std_cost": total_std,
        "total_batch_cost": total_batch,
        "total_savings": round(total_std - total_batch, 6),
    }
