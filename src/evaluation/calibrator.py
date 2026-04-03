"""Threshold calibration engine for dynamic routing.

Analyzes evaluation results to find the optimal complexity threshold
where the weak model achieves acceptable quality (measured by win-or-tie
rate against the strong model).
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MIN_SAMPLES = 30


@dataclass
class CalibrationResult:
    """Result of threshold calibration."""

    step: str
    threshold: float
    win_or_tie_rate: float
    total_samples: int
    estimated_cost_savings_pct: float
    target_quality: float


class ThresholdCalibrator:
    """Calibrate routing thresholds from evaluation data.

    Finds the complexity threshold where the weak model's consensus
    win-or-tie rate meets the target quality percentage.
    """

    def calibrate(
        self,
        step: str,
        complexity_scores: list[float],
        consensus_preferences: list[str],
        target_quality: float = 0.95,
    ) -> CalibrationResult:
        """Find optimal threshold for a pipeline step.

        Args:
            step: Pipeline step name
            complexity_scores: Complexity scores from the router (one per sample)
            consensus_preferences: Consensus preferences ("strong_wins", "weak_wins", "tie")
            target_quality: Target win-or-tie rate for the weak model (0.0-1.0)

        Returns:
            CalibrationResult with optimal threshold and metrics

        Raises:
            ValueError: If insufficient evaluation data
        """
        from src.models.evaluation import Preference

        n = len(complexity_scores)
        if n < MIN_SAMPLES:
            raise ValueError(f"Insufficient evaluation data ({n}/{MIN_SAMPLES} minimum)")

        if len(complexity_scores) != len(consensus_preferences):
            raise ValueError("complexity_scores and consensus_preferences must have same length")

        # Sort by complexity score
        paired = sorted(
            zip(complexity_scores, consensus_preferences, strict=True), key=lambda x: x[0]
        )

        # Try different thresholds and find where win-or-tie rate >= target
        # Default 0.0 = route everything to strong (safe fallback since
        # ComplexityRouter routes scores < threshold to weak model)
        best_threshold = 0.0
        best_savings = 0.0
        best_wot_rate = 0.0

        # Test thresholds at each complexity score value
        candidate_thresholds = sorted(set(s for s, _ in paired))

        for threshold in candidate_thresholds:
            # Samples below threshold would go to weak model
            weak_samples = [(s, p) for s, p in paired if s < threshold]

            if not weak_samples:
                continue

            # Win-or-tie rate: % of weak-routed samples where weak_wins or tie
            wot_count = sum(
                1 for _, p in weak_samples if p in (Preference.WEAK_WINS, Preference.TIE)
            )
            wot_rate = wot_count / len(weak_samples)

            if wot_rate >= target_quality:
                savings_pct = len(weak_samples) / n
                if savings_pct > best_savings:
                    best_threshold = threshold
                    best_savings = savings_pct
                    best_wot_rate = wot_rate

        return CalibrationResult(
            step=step,
            threshold=round(best_threshold, 4),
            win_or_tie_rate=round(best_wot_rate, 4),
            total_samples=n,
            estimated_cost_savings_pct=round(best_savings, 4),
            target_quality=target_quality,
        )

    def estimate_savings(
        self,
        complexity_scores: list[float],
        threshold: float,
        strong_cost_per_call: float = 0.01,
        weak_cost_per_call: float = 0.001,
    ) -> dict:
        """Estimate cost savings at a given threshold.

        Args:
            complexity_scores: All complexity scores
            threshold: Routing threshold
            strong_cost_per_call: Average cost for strong model
            weak_cost_per_call: Average cost for weak model

        Returns:
            Dict with cost estimates
        """
        total = len(complexity_scores)
        if total == 0:
            return {"total_calls": 0, "savings": 0.0}

        weak_count = sum(1 for s in complexity_scores if s < threshold)
        strong_count = total - weak_count

        all_strong_cost = total * strong_cost_per_call
        routed_cost = (strong_count * strong_cost_per_call) + (weak_count * weak_cost_per_call)
        savings = all_strong_cost - routed_cost

        return {
            "total_calls": total,
            "weak_routed": weak_count,
            "strong_routed": strong_count,
            "pct_weak": round(weak_count / total, 3),
            "all_strong_cost": round(all_strong_cost, 4),
            "routed_cost": round(routed_cost, 4),
            "savings": round(savings, 4),
            "savings_pct": round(savings / all_strong_cost, 3) if all_strong_cost > 0 else 0.0,
        }
