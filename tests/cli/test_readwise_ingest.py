"""Tests for Readwise ingestion: CLI command + orchestrator integration.

Covers:
- Orchestrator `ingest_readwise()` — service wiring, on_result callback,
  close() lifecycle, return value, sources.d defaults cascade.
- CLI `aca ingest readwise` — all options, direct/API modes, JSON mode,
  help text, failure exit code.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from src.cli.app import app
from src.ingestion.readwise import ReadwiseIngestResult

runner = CliRunner()


# ---------------------------------------------------------------------------
# Orchestrator unit tests
# ---------------------------------------------------------------------------


class TestOrchestratorIngestReadwise:
    """Test `src.ingestion.orchestrator.ingest_readwise()`."""

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    def test_returns_items_ingested_combined(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = ReadwiseIngestResult(
            books_ingested=4,
            books_updated=3,
            highlights_created=20,
        )
        from src.ingestion.orchestrator import ingest_readwise

        count = ingest_readwise()
        assert count == 7  # books_ingested + books_updated

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    def test_passes_kwargs_to_service(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = ReadwiseIngestResult(books_ingested=1)
        from datetime import UTC, datetime

        from src.ingestion.orchestrator import ingest_readwise

        ts = datetime(2026, 4, 20, tzinfo=UTC)
        ingest_readwise(
            updated_after=ts,
            source_types=["kindle"],
            include_deleted=True,
            max_books=50,
            force_reprocess=True,
        )
        mock_service.ingest_content.assert_called_once_with(
            updated_after=ts,
            source_types=["kindle"],
            include_deleted=True,
            max_books=50,
            force_reprocess=True,
        )

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    def test_on_result_callback_invoked(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        result = ReadwiseIngestResult(books_ingested=2, highlights_created=9)
        mock_service.ingest_content.return_value = result

        captured: list[ReadwiseIngestResult] = []
        from src.ingestion.orchestrator import ingest_readwise

        ingest_readwise(on_result=captured.append)
        assert captured == [result]

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    def test_close_called_even_on_error(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.side_effect = RuntimeError("boom")
        from src.ingestion.orchestrator import ingest_readwise

        import pytest

        with pytest.raises(RuntimeError, match="boom"):
            ingest_readwise()
        mock_service.close.assert_called_once()

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    @patch("src.ingestion.orchestrator.load_sources_config", create=True)
    def test_applies_sources_d_defaults_when_missing(
        self, mock_load, mock_service_cls
    ):
        """When source_types/include_deleted aren't passed, defaults come from sources.d."""
        cfg = MagicMock()
        rw = MagicMock()
        rw.source_types = ["instapaper", "pocket"]
        rw.include_deleted = True
        cfg.get_readwise_sources.return_value = [rw]
        mock_load.return_value = cfg

        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = ReadwiseIngestResult()

        from src.ingestion.orchestrator import ingest_readwise

        ingest_readwise()

        kwargs = mock_service.ingest_content.call_args.kwargs
        assert kwargs["source_types"] == ["instapaper", "pocket"]
        assert kwargs["include_deleted"] is True

    @patch("src.ingestion.readwise.ReadwiseContentIngestionService")
    @patch("src.ingestion.orchestrator.load_sources_config", create=True)
    def test_explicit_args_win_over_defaults(self, mock_load, mock_service_cls):
        cfg = MagicMock()
        rw = MagicMock()
        rw.source_types = ["kindle"]
        rw.include_deleted = False
        cfg.get_readwise_sources.return_value = [rw]
        mock_load.return_value = cfg

        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = ReadwiseIngestResult()

        from src.ingestion.orchestrator import ingest_readwise

        ingest_readwise(source_types=["reader"], include_deleted=True)

        kwargs = mock_service.ingest_content.call_args.kwargs
        assert kwargs["source_types"] == ["reader"]
        assert kwargs["include_deleted"] is True


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestReadwiseCliHelp:
    def test_help_lists_command(self):
        result = runner.invoke(app, ["ingest", "readwise", "--help"])
        assert result.exit_code == 0
        assert "readwise" in result.stdout.lower()
        assert "--source-types" in result.stdout
        assert "--include-deleted" in result.stdout
        assert "--max" in result.stdout


class TestReadwiseCliDirectMode:
    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_readwise")
    def test_basic_invocation(self, mock_orch, _direct):
        def fake_orch(**kwargs):
            cb = kwargs.get("on_result")
            if cb:
                cb(
                    ReadwiseIngestResult(
                        books_ingested=3,
                        books_updated=1,
                        highlights_created=15,
                    )
                )
            return 4

        mock_orch.side_effect = fake_orch

        result = runner.invoke(app, ["ingest", "readwise"])
        assert result.exit_code == 0
        assert "Readwise ingestion complete" in result.stdout
        assert "3 new" in result.stdout
        assert "1 updated" in result.stdout
        assert "15 new" in result.stdout

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_readwise")
    def test_passes_options_to_orchestrator(self, mock_orch, _direct):
        mock_orch.return_value = 0

        result = runner.invoke(
            app,
            [
                "ingest",
                "readwise",
                "--days",
                "14",
                "--source-types",
                "kindle,instapaper",
                "--include-deleted",
                "--max",
                "25",
                "--force",
            ],
        )
        assert result.exit_code == 0
        kwargs = mock_orch.call_args.kwargs
        assert kwargs["source_types"] == ["kindle", "instapaper"]
        assert kwargs["include_deleted"] is True
        assert kwargs["max_books"] == 25
        assert kwargs["force_reprocess"] is True
        assert kwargs["updated_after"] is not None  # 14 days ago

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_readwise")
    def test_failure_exits_nonzero(self, mock_orch, _direct):
        mock_orch.side_effect = RuntimeError("readwise api down")
        result = runner.invoke(app, ["ingest", "readwise"])
        assert result.exit_code == 1
        assert "Readwise ingestion failed" in result.stdout

    @patch("src.cli.ingest_commands.is_json_mode", return_value=True)
    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_readwise")
    def test_json_output_shape(self, mock_orch, _direct, _json):
        def fake_orch(**kwargs):
            cb = kwargs.get("on_result")
            if cb:
                cb(
                    ReadwiseIngestResult(
                        books_ingested=2,
                        books_updated=0,
                        highlights_created=7,
                        highlights_soft_deleted=1,
                    )
                )
            return 2

        mock_orch.side_effect = fake_orch

        result = runner.invoke(app, ["ingest", "readwise"])
        assert result.exit_code == 0
        assert '"source": "readwise"' in result.stdout
        assert '"books_ingested": 2' in result.stdout
        assert '"highlights_created": 7' in result.stdout
        assert '"highlights_soft_deleted": 1' in result.stdout


class TestReadwiseCliApiMode:
    @patch("src.cli.ingest_commands._ingest_via_api")
    @patch("src.cli.ingest_commands.is_direct_mode", return_value=False)
    def test_api_mode_params_shape(self, _direct, mock_api):
        result = runner.invoke(
            app,
            [
                "ingest",
                "readwise",
                "--days",
                "7",
                "--source-types",
                "kindle",
                "--max",
                "10",
            ],
        )
        assert result.exit_code == 0
        source_arg, params, label = mock_api.call_args.args
        assert source_arg == "readwise"
        assert params["days_back"] == 7
        assert params["source_types"] == ["kindle"]
        assert params["max_books"] == 10

    @patch("src.cli.ingest_commands._readwise_direct")
    @patch("src.cli.ingest_commands._ingest_via_api")
    @patch("src.cli.ingest_commands.is_direct_mode", return_value=False)
    def test_falls_back_to_direct_on_connect_error(
        self, _direct, mock_api, mock_direct
    ):
        mock_api.side_effect = httpx.ConnectError("conn refused")
        result = runner.invoke(app, ["ingest", "readwise"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()
