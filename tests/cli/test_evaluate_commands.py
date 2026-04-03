"""Tests for evaluate CLI commands.

Tests cover:
- list-datasets command output
- create-dataset command
- report command with no data
- calibrate command output
"""

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.evaluate_commands import app

runner = CliRunner()

# Patch at source module since CLI uses lazy imports inside functions
_SVC_PATH = "src.services.evaluation_service.EvaluationService"


class TestListDatasets:
    def test_no_datasets(self):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.get_datasets.return_value = []
            result = runner.invoke(app, ["list-datasets"])
            assert result.exit_code == 0
            assert "No evaluation datasets found" in result.output

    def test_with_datasets(self):
        from src.services.evaluation_service import DatasetInfo

        ds = DatasetInfo(
            id=1, step="summarization", name="test_ds",
            status="pending_evaluation", sample_count=10,
            strong_model="strong", weak_model="weak",
        )
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.get_datasets.return_value = [ds]
            result = runner.invoke(app, ["list-datasets"])
            assert result.exit_code == 0
            assert "summarization" in result.output
            assert "test_ds" in result.output

    def test_filter_by_step(self):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.get_datasets.return_value = []
            result = runner.invoke(app, ["list-datasets", "--step", "summarization"])
            assert result.exit_code == 0
            mock_svc_cls.return_value.get_datasets.assert_called_once_with(step="summarization")


class TestCreateDataset:
    def test_creates_dataset(self):
        from src.services.evaluation_service import DatasetInfo

        ds = DatasetInfo(
            id=42, step="summarization", name="my_ds",
            status="pending_evaluation", sample_count=0,
            strong_model="claude-sonnet-4-5", weak_model="claude-haiku-4-5",
        )
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.create_dataset.return_value = ds
            result = runner.invoke(app, [
                "create-dataset", "--step", "summarization", "--name", "my_ds",
            ])
            assert result.exit_code == 0
            assert "42" in result.output
            assert "summarization" in result.output


class TestReport:
    def test_no_data(self):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.generate_report.return_value = []
            result = runner.invoke(app, ["report"])
            assert result.exit_code == 0
            assert "No routing decisions found" in result.output

    def test_with_data(self):
        from src.services.evaluation_service import EvaluationReport

        report = EvaluationReport(
            step="summarization",
            total_decisions=100,
            pct_routed_to_weak=0.6,
            cost_savings_vs_all_strong=1.23,
            preference_distribution={"strong_wins": 30, "weak_wins": 50, "tie": 20},
            dimension_pass_rates={},
        )
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.generate_report.return_value = [report]
            result = runner.invoke(app, ["report"])
            assert result.exit_code == 0
            assert "summarization" in result.output
            assert "100" in result.output


class TestRunEvaluation:
    def test_invalid_num_judges(self):
        result = runner.invoke(app, ["run", "1", "--num-judges", "5"])
        assert result.exit_code == 1
        assert "num-judges must be between 1 and 3" in result.output

    def test_run_without_db_fails_gracefully(self):
        """Run command fails gracefully when services can't be initialized."""
        with patch("src.storage.database.SessionLocal", side_effect=Exception("No DB")):
            result = runner.invoke(app, ["run", "1"])
            assert result.exit_code == 1
            assert "Error" in result.output


class TestCalibrate:
    def test_outputs_info(self):
        result = runner.invoke(app, ["calibrate", "--step", "summarization"])
        assert result.exit_code == 0
        assert "summarization" in result.output
