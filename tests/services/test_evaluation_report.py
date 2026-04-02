"""Tests for cost savings report generation.

Tests cover:
- Empty report when no data
- Per-step metrics aggregation
- Cost savings calculation
"""

from unittest.mock import MagicMock, patch

from src.services.evaluation_service import EvaluationReport, EvaluationService


class TestGenerateReport:
    def test_no_db_returns_empty(self):
        svc = EvaluationService(db_session=None)
        reports = svc.generate_report()
        assert reports == []

    def test_no_decisions_returns_empty(self):
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.filter_by.return_value = mock_db.query.return_value

        svc = EvaluationService(db_session=mock_db)
        reports = svc.generate_report()
        assert reports == []

    def test_report_contains_expected_fields(self):
        """Verify report dataclass has all required fields."""
        report = EvaluationReport(
            step="summarization",
            total_decisions=50,
            pct_routed_to_weak=0.4,
            cost_savings_vs_all_strong=0.5,
            preference_distribution={"strong_wins": 20, "weak_wins": 25, "tie": 5},
            dimension_pass_rates={"accuracy": 0.95},
        )
        assert report.step == "summarization"
        assert report.total_decisions == 50
        assert report.pct_routed_to_weak == 0.4
        assert report.cost_savings_vs_all_strong == 0.5
        assert "strong_wins" in report.preference_distribution

    def test_filter_by_step(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.all.return_value = []

        svc = EvaluationService(db_session=mock_db)
        svc.generate_report(step="summarization")

        # Should have called filter_by with the step
        mock_db.query.return_value.filter_by.assert_called_once_with(step="summarization")
