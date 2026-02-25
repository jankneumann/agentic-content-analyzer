"""Tests for Perplexity search ingestion: CLI command + orchestrator integration.

Covers:
- Orchestrator `ingest_perplexity_search()` — service wiring, on_result callback,
  close() lifecycle, return value extraction.
- CLI `aca ingest perplexity-search` — all options, success/failure paths,
  JSON mode, help text.
"""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.ingestion.perplexity_search import PerplexitySearchResult

runner = CliRunner()


# ---------------------------------------------------------------------------
# Orchestrator unit tests
# ---------------------------------------------------------------------------


class TestOrchestratorIngestPerplexitySearch:
    """Test `src.ingestion.orchestrator.ingest_perplexity_search()`."""

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_returns_items_ingested(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = PerplexitySearchResult(
            items_ingested=7,
            queries_made=1,
            citations_found=12,
        )
        from src.ingestion.orchestrator import ingest_perplexity_search

        count = ingest_perplexity_search()
        assert count == 7

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_passes_all_kwargs_to_service(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = PerplexitySearchResult(items_ingested=3)
        from src.ingestion.orchestrator import ingest_perplexity_search

        ingest_perplexity_search(
            prompt="Latest AI research",
            max_results=20,
            force_reprocess=True,
            recency_filter="week",
            context_size="high",
        )
        mock_service.ingest_content.assert_called_once_with(
            prompt="Latest AI research",
            max_results=20,
            force_reprocess=True,
            recency_filter="week",
            context_size="high",
        )

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_on_result_callback_invoked(self, mock_service_cls):
        result_obj = PerplexitySearchResult(items_ingested=5, queries_made=2, citations_found=8)
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = result_obj
        callback = MagicMock()
        from src.ingestion.orchestrator import ingest_perplexity_search

        ingest_perplexity_search(on_result=callback)
        callback.assert_called_once_with(result_obj)

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_close_called_on_success(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = PerplexitySearchResult(items_ingested=2)
        from src.ingestion.orchestrator import ingest_perplexity_search

        ingest_perplexity_search()
        mock_service.close.assert_called_once()

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_close_called_on_failure(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.side_effect = RuntimeError("API failure")
        from src.ingestion.orchestrator import ingest_perplexity_search

        try:
            ingest_perplexity_search()
        except RuntimeError:
            pass
        mock_service.close.assert_called_once()

    @patch("src.ingestion.perplexity_search.PerplexityContentIngestionService")
    def test_default_kwargs(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.ingest_content.return_value = PerplexitySearchResult(items_ingested=0)
        from src.ingestion.orchestrator import ingest_perplexity_search

        ingest_perplexity_search()
        mock_service.ingest_content.assert_called_once_with(
            prompt=None,
            max_results=None,
            force_reprocess=False,
            recency_filter=None,
            context_size=None,
        )


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLIPerplexitySearch:
    """Test `aca ingest perplexity-search` CLI command."""

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_default_success(self, mock_ingest):
        mock_ingest.return_value = 5
        result = runner.invoke(app, ["ingest", "perplexity-search"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Perplexity search ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_custom_prompt(self, mock_ingest):
        mock_ingest.return_value = 3
        result = runner.invoke(
            app, ["ingest", "perplexity-search", "--prompt", "Find latest LLM benchmarks"]
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt="Find latest LLM benchmarks",
            max_results=None,
            force_reprocess=False,
            recency_filter=None,
            context_size=None,
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_custom_max_results(self, mock_ingest):
        mock_ingest.return_value = 10
        result = runner.invoke(app, ["ingest", "perplexity-search", "--max-results", "10"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt=None,
            max_results=10,
            force_reprocess=False,
            recency_filter=None,
            context_size=None,
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_force_flag(self, mock_ingest):
        mock_ingest.return_value = 1
        result = runner.invoke(app, ["ingest", "perplexity-search", "--force"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt=None,
            max_results=None,
            force_reprocess=True,
            recency_filter=None,
            context_size=None,
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_recency_filter(self, mock_ingest):
        mock_ingest.return_value = 4
        result = runner.invoke(app, ["ingest", "perplexity-search", "--recency", "week"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt=None,
            max_results=None,
            force_reprocess=False,
            recency_filter="week",
            context_size=None,
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_context_size(self, mock_ingest):
        mock_ingest.return_value = 6
        result = runner.invoke(app, ["ingest", "perplexity-search", "--context-size", "high"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt=None,
            max_results=None,
            force_reprocess=False,
            recency_filter=None,
            context_size="high",
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_all_options_combined(self, mock_ingest):
        mock_ingest.return_value = 8
        result = runner.invoke(
            app,
            [
                "ingest",
                "perplexity-search",
                "--prompt",
                "AI safety research",
                "--max-results",
                "15",
                "--force",
                "--recency",
                "month",
                "--context-size",
                "medium",
            ],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt="AI safety research",
            max_results=15,
            force_reprocess=True,
            recency_filter="month",
            context_size="medium",
            on_result=ANY,
        )

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_failure_path(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API key invalid")
        result = runner.invoke(app, ["ingest", "perplexity-search"])
        assert result.exit_code == 1
        assert "Perplexity search ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_json_mode_success(self, mock_ingest):
        mock_ingest.return_value = 4
        result = runner.invoke(app, ["--json", "ingest", "perplexity-search"])
        assert result.exit_code == 0
        assert '"source": "perplexity"' in result.output
        assert '"ingested": 4' in result.output

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_json_mode_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Rate limited")
        result = runner.invoke(app, ["--json", "ingest", "perplexity-search"])
        assert result.exit_code == 1
        assert '"error"' in result.output
        assert '"source": "perplexity"' in result.output

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_short_option_aliases(self, mock_ingest):
        mock_ingest.return_value = 2
        result = runner.invoke(
            app, ["ingest", "perplexity-search", "-p", "AI agents", "-m", "5", "-f"]
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt="AI agents",
            max_results=5,
            force_reprocess=True,
            recency_filter=None,
            context_size=None,
            on_result=ANY,
        )

    def test_help_text(self):
        result = runner.invoke(app, ["ingest", "perplexity-search", "--help"])
        assert result.exit_code == 0
        assert "Perplexity Sonar API" in result.output

    @patch("src.ingestion.orchestrator.ingest_perplexity_search")
    def test_zero_items_ingested(self, mock_ingest):
        mock_ingest.return_value = 0
        result = runner.invoke(app, ["ingest", "perplexity-search"])
        assert result.exit_code == 0
        assert "0" in result.output
        assert "Perplexity search ingestion complete" in result.output
