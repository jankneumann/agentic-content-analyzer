"""CLI tests for `aca evaluate batch-savings` and `aca batch status`.

Fakes the DB session (a context manager) so no Postgres is needed; the real
ModelConfig + savings math run unchanged.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.main import get_command
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import _set_json_mode

runner = CliRunner()


def _fake_get_db(mock_db):
    @contextmanager
    def _cm():
        yield mock_db

    return _cm


def teardown_function():
    # The --json flag sets a process-global; reset so tests don't leak mode.
    _set_json_mode(False)


class TestBatchSavingsCLI:
    def test_json_output_shape(self):
        mock_db = MagicMock()
        scoped = mock_db.query.return_value
        scoped.count.return_value = 200  # total contents
        scoped.filter.return_value.count.return_value = 80  # youtube subset

        with patch("src.storage.database.get_db", _fake_get_db(mock_db)):
            result = runner.invoke(app, ["--json", "evaluate", "batch-savings"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["projection"] == "backfill"
        assert payload["discount"] == 0.5
        assert {"steps", "total_std_cost", "total_batch_cost", "total_savings"} <= payload.keys()
        # content_filtering uses the total volume (200); youtube steps use 80.
        by_step = {r["step"]: r for r in payload["steps"]}
        assert by_step["content_filtering"]["items"] == 200
        assert by_step["youtube_processing"]["items"] == 80
        assert payload["total_savings"] > 0
        assert payload["assumptions"]["batch_discount"] == 0.5
        assert payload["assumptions"]["token_estimates"]

    def test_human_output_has_total_row(self):
        mock_db = MagicMock()
        scoped = mock_db.query.return_value
        scoped.count.return_value = 10
        scoped.filter.return_value.count.return_value = 4

        with patch("src.storage.database.get_db", _fake_get_db(mock_db)):
            result = runner.invoke(app, ["evaluate", "batch-savings"])

        assert result.exit_code == 0, result.output
        assert "Batch savings" in result.output
        assert "TOTAL" in result.output


class TestBatchStatusCLI:
    def test_status_json(self):
        mock_db = MagicMock()
        # db.query(...).group_by(...).all() → grouped (key, count) tuples.
        grouped = mock_db.query.return_value.group_by.return_value
        grouped.all.side_effect = [
            [("running", 2), ("succeeded", 1)],  # jobs
            [("pending", 5), ("submitted", 2)],  # requests
        ]

        with patch("src.storage.database.get_db", _fake_get_db(mock_db)):
            result = runner.invoke(app, ["--json", "batch", "status"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["jobs"] == {"running": 2, "succeeded": 1}
        assert payload["requests"] == {"pending": 5, "submitted": 2}
        assert payload["recent_jobs"] == []
        mock_db.commit.assert_not_called()

    def test_status_json_includes_bounded_recent_jobs(self):
        mock_db = MagicMock()
        grouped = mock_db.query.return_value.group_by.return_value
        grouped.all.side_effect = [[], []]
        ordered = mock_db.query.return_value.order_by.return_value
        recent = ordered.limit.return_value
        recent.all.return_value = [
            SimpleNamespace(
                id="job-1",
                provider_job_name="batches/provider-1",
                model_step="content_filtering",
                model_id="gemini-2.5-flash-lite",
                state="running",
                request_count=3,
                created_at=datetime(2026, 7, 22, tzinfo=UTC),
                submitted_at=None,
                completed_at=None,
                error=None,
            )
        ]

        with patch("src.storage.database.get_db", _fake_get_db(mock_db)):
            result = runner.invoke(app, ["--json", "batch", "status"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["recent_jobs"][0] == {
            "id": "job-1",
            "provider_job_name": "batches/provider-1",
            "model_step": "content_filtering",
            "model_id": "gemini-2.5-flash-lite",
            "state": "running",
            "request_count": 3,
            "created_at": "2026-07-22T00:00:00+00:00",
            "submitted_at": None,
            "completed_at": None,
            "error": None,
        }
        ordered.limit.assert_called_once_with(10)

    def test_status_human_empty(self):
        mock_db = MagicMock()
        grouped = mock_db.query.return_value.group_by.return_value
        grouped.all.side_effect = [[], []]

        with patch("src.storage.database.get_db", _fake_get_db(mock_db)):
            result = runner.invoke(app, ["batch", "status"])

        assert result.exit_code == 0, result.output
        assert "Batch jobs by state" in result.output
        assert "(none)" in result.output

    def test_batch_cli_exposes_only_read_only_status(self):
        root = get_command(app)
        batch = root.commands["batch"]

        assert set(batch.commands) == {"status"}
