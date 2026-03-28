"""Tests for arXiv ingest CLI commands.

After the orchestrator refactor, CLI commands delegate to orchestrator functions.
Tests mock at `src.ingestion.orchestrator.<func>`.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestIngestArxiv:
    @patch("src.ingestion.orchestrator.ingest_arxiv")
    def test_arxiv_success(self, mock_ingest):
        mock_ingest.return_value = 10

        result = runner.invoke(app, ["--direct", "ingest", "arxiv"])
        assert result.exit_code == 0
        assert "10" in result.output
        assert "arXiv ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_arxiv")
    def test_arxiv_with_options(self, mock_ingest):
        mock_ingest.return_value = 5

        result = runner.invoke(
            app,
            ["--direct", "ingest", "arxiv", "--max", "50", "--days", "7", "--no-pdf"],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_results"] == 50
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["no_pdf"] is True

    @patch("src.ingestion.orchestrator.ingest_arxiv")
    def test_arxiv_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Connection failed")

        result = runner.invoke(app, ["--direct", "ingest", "arxiv"])
        assert result.exit_code == 1
        assert "arXiv ingestion failed" in result.output


class TestIngestArxivPaper:
    @patch("src.ingestion.orchestrator.ingest_arxiv_paper")
    def test_arxiv_paper_success(self, mock_ingest):
        mock_ingest.return_value = 1

        result = runner.invoke(app, ["--direct", "ingest", "arxiv-paper", "2301.12345"])
        assert result.exit_code == 0
        assert "Ingested arXiv paper" in result.output
        mock_ingest.assert_called_once_with(
            identifier="2301.12345", pdf_extraction=True, force_reprocess=False
        )

    @patch("src.ingestion.orchestrator.ingest_arxiv_paper")
    def test_arxiv_paper_not_found(self, mock_ingest):
        mock_ingest.return_value = 0

        result = runner.invoke(app, ["--direct", "ingest", "arxiv-paper", "9999.99999"])
        assert result.exit_code == 0
        assert "already exists or not found" in result.output

    @patch("src.ingestion.orchestrator.ingest_arxiv_paper")
    def test_arxiv_paper_no_pdf(self, mock_ingest):
        mock_ingest.return_value = 1

        result = runner.invoke(app, ["--direct", "ingest", "arxiv-paper", "2301.12345", "--no-pdf"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            identifier="2301.12345", pdf_extraction=False, force_reprocess=False
        )

    @patch("src.ingestion.orchestrator.ingest_arxiv_paper")
    def test_arxiv_paper_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["--direct", "ingest", "arxiv-paper", "2301.12345"])
        assert result.exit_code == 1
        assert "arXiv paper ingestion failed" in result.output
