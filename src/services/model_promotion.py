"""Pure decision logic for model-registry change risk and promotion gating.

Kept dependency-light so the risk-tiering and validate-before-promote rules can be
unit-tested without the eval harness or network. The orchestration that actually
runs evaluations and applies changes lives in ``ModelRegistryService``.

See openspec/changes/auto-update-model-registry/.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChangeKind(StrEnum):
    """The kind of registry change being proposed."""

    PRICING_DIFF = "pricing_diff"  # update cost/specs of an existing model
    NEW_MODEL = "new_model"  # add a model not currently in the registry
    DEFAULT_SWAP = "default_swap"  # change the model used for a pipeline step


class RiskTier(StrEnum):
    LOW = "low"  # auto-applicable
    MEDIUM = "medium"  # requires approval
    HIGH = "high"  # requires approval + passing eval gate


# Risk tier per change kind (policy: auto pricing, gated defaults).
_RISK_BY_KIND: dict[str, RiskTier] = {
    ChangeKind.PRICING_DIFF: RiskTier.LOW,
    ChangeKind.NEW_MODEL: RiskTier.MEDIUM,
    ChangeKind.DEFAULT_SWAP: RiskTier.HIGH,
}


def classify_change_risk(kind: str) -> RiskTier:
    """Map a change kind to its risk tier. Unknown kinds are treated as HIGH."""
    return _RISK_BY_KIND.get(kind, RiskTier.HIGH)


def can_auto_apply(kind: str) -> bool:
    """Only LOW-risk changes (pricing diffs) auto-apply without approval."""
    return classify_change_risk(kind) == RiskTier.LOW


@dataclass(frozen=True)
class PromotionInputs:
    """Metrics feeding the validate-before-promote gate."""

    parity_score: float  # 0..1: candidate quality vs incumbent (e.g. consensus win/tie rate)
    agreement_rate: float  # 0..1: judge agreement (confidence in the verdict)
    cost_incumbent: float  # $/Mtok (or any consistent unit) for the incumbent
    cost_candidate: float  # same unit for the candidate


@dataclass(frozen=True)
class PromotionDecision:
    recommend: bool
    reasons: list[str]


def summarize_consensus(
    verdicts: list[tuple[str, float]],
    *,
    candidate_label: str = "weak",
) -> tuple[float, float]:
    """Reduce per-sample (preference, agreement_rate) verdicts to gate metrics.

    The candidate is conventionally evaluated as the dataset's ``weak`` model and
    the incumbent as ``strong``. Parity counts candidate wins plus ties (the
    candidate is "good enough" if it wins or draws). Returns
    ``(parity_score, mean_agreement_rate)``; empty input yields ``(0.0, 0.0)``.
    """
    if not verdicts:
        return 0.0, 0.0
    wins_or_ties = sum(1 for pref, _ in verdicts if pref in (candidate_label, "tie"))
    parity_score = wins_or_ties / len(verdicts)
    mean_agreement = sum(rate for _, rate in verdicts) / len(verdicts)
    return parity_score, mean_agreement


def evaluate_promotion(
    inputs: PromotionInputs,
    *,
    target_parity: float = 0.9,
    min_agreement: float = 0.6,
    cost_budget_ratio: float = 1.0,
) -> PromotionDecision:
    """Decide whether to recommend promoting a candidate to a step default.

    A candidate is recommended only when it meets the quality parity target,
    the judges agree enough to trust the verdict, AND its cost is within
    ``cost_budget_ratio`` of the incumbent (default: must not be more expensive).
    """
    reasons: list[str] = []

    parity_ok = inputs.parity_score >= target_parity
    if not parity_ok:
        reasons.append(
            f"parity {inputs.parity_score:.2f} < target {target_parity:.2f}"
        )

    agreement_ok = inputs.agreement_rate >= min_agreement
    if not agreement_ok:
        reasons.append(
            f"agreement {inputs.agreement_rate:.2f} < min {min_agreement:.2f}"
        )

    # Guard against a zero/negative incumbent cost (treat as no budget ceiling).
    if inputs.cost_incumbent <= 0:
        cost_ok = True
    else:
        cost_ratio = inputs.cost_candidate / inputs.cost_incumbent
        cost_ok = cost_ratio <= cost_budget_ratio
        if not cost_ok:
            reasons.append(
                f"cost ratio {cost_ratio:.2f} > budget {cost_budget_ratio:.2f}"
            )

    recommend = parity_ok and agreement_ok and cost_ok
    if recommend:
        reasons.append("meets parity, agreement, and cost criteria")
    return PromotionDecision(recommend=recommend, reasons=reasons)
