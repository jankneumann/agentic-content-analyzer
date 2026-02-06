"""Integration tests for worker CLI commands.

Tests cover:
- Concurrency limit enforcement (default, env var, CLI flag)
- Invalid concurrency values rejection
- Worker start command help text
- Graceful shutdown signal registration

Task 7.3 from add-parallel-job-queue proposal.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.worker_commands import (
    DEFAULT_CONCURRENCY,
    MAX_CONCURRENCY,
    _get_default_concurrency,
)

runner = CliRunner()


# =============================================================================
# Tests: _get_default_concurrency()
# =============================================================================


class TestGetDefaultConcurrency:
    """Tests for _get_default_concurrency() env var resolution."""

    def test_returns_default_when_no_env_set(self):
        """Returns DEFAULT_CONCURRENCY when WORKER_CONCURRENCY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove WORKER_CONCURRENCY if present
            os.environ.pop("WORKER_CONCURRENCY", None)
            result = _get_default_concurrency()
        assert result == DEFAULT_CONCURRENCY

    def test_returns_env_value_when_valid(self):
        """Returns parsed int when WORKER_CONCURRENCY is a valid number."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "10"}):
            result = _get_default_concurrency()
        assert result == 10

    def test_returns_default_when_env_below_minimum(self):
        """Returns default when WORKER_CONCURRENCY is below 1."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "0"}):
            result = _get_default_concurrency()
        assert result == DEFAULT_CONCURRENCY

    def test_returns_default_when_env_above_maximum(self):
        """Returns default when WORKER_CONCURRENCY exceeds MAX_CONCURRENCY."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": str(MAX_CONCURRENCY + 1)}):
            result = _get_default_concurrency()
        assert result == DEFAULT_CONCURRENCY

    def test_returns_default_when_env_not_a_number(self):
        """Returns default when WORKER_CONCURRENCY is not a valid integer."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "fast"}):
            result = _get_default_concurrency()
        assert result == DEFAULT_CONCURRENCY

    def test_accepts_minimum_value(self):
        """WORKER_CONCURRENCY=1 is accepted (minimum valid)."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "1"}):
            result = _get_default_concurrency()
        assert result == 1

    def test_accepts_maximum_value(self):
        """WORKER_CONCURRENCY=MAX_CONCURRENCY is accepted (maximum valid)."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": str(MAX_CONCURRENCY)}):
            result = _get_default_concurrency()
        assert result == MAX_CONCURRENCY

    def test_returns_default_for_negative_value(self):
        """Returns default when WORKER_CONCURRENCY is negative."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "-5"}):
            result = _get_default_concurrency()
        assert result == DEFAULT_CONCURRENCY


# =============================================================================
# Tests: Worker Start CLI Command
# =============================================================================


class TestWorkerStartCommand:
    """Tests for `aca worker start` CLI command."""

    def test_help_text(self):
        """Worker start --help shows usage info."""
        result = runner.invoke(app, ["worker", "start", "--help"])
        assert result.exit_code == 0
        assert "concurrency" in result.output.lower()

    def test_rejects_concurrency_zero(self):
        """--concurrency 0 is rejected by Typer's min=1 constraint."""
        result = runner.invoke(app, ["worker", "start", "--concurrency", "0"])
        # Typer validation should reject this
        assert result.exit_code != 0

    def test_rejects_concurrency_above_max(self):
        """--concurrency above MAX_CONCURRENCY is rejected."""
        result = runner.invoke(app, ["worker", "start", "--concurrency", str(MAX_CONCURRENCY + 1)])
        assert result.exit_code != 0

    @patch("src.cli.worker_commands._run_worker", new_callable=AsyncMock)
    def test_uses_cli_concurrency_flag(self, mock_run_worker):
        """CLI --concurrency flag overrides env var and default."""
        result = runner.invoke(app, ["worker", "start", "--concurrency", "8"])

        assert result.exit_code == 0
        # _run_worker should be called with the CLI-specified concurrency
        mock_run_worker.assert_called_once_with(8)

    @patch("src.cli.worker_commands._run_worker", new_callable=AsyncMock)
    def test_uses_env_var_when_no_cli_flag(self, mock_run_worker):
        """Uses WORKER_CONCURRENCY env var when --concurrency not specified."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "12"}):
            result = runner.invoke(app, ["worker", "start"])

        assert result.exit_code == 0
        mock_run_worker.assert_called_once_with(12)

    @patch("src.cli.worker_commands._run_worker", new_callable=AsyncMock)
    def test_uses_default_when_no_flag_or_env(self, mock_run_worker):
        """Uses DEFAULT_CONCURRENCY when neither --concurrency nor env var set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WORKER_CONCURRENCY", None)
            result = runner.invoke(app, ["worker", "start"])

        assert result.exit_code == 0
        mock_run_worker.assert_called_once_with(DEFAULT_CONCURRENCY)

    @patch("src.cli.worker_commands._run_worker", new_callable=AsyncMock)
    def test_cli_flag_takes_precedence_over_env(self, mock_run_worker):
        """CLI --concurrency overrides WORKER_CONCURRENCY env var."""
        with patch.dict(os.environ, {"WORKER_CONCURRENCY": "12"}):
            result = runner.invoke(app, ["worker", "start", "--concurrency", "3"])

        assert result.exit_code == 0
        mock_run_worker.assert_called_once_with(3)


# =============================================================================
# Tests: Worker Initialization
# =============================================================================


class TestWorkerInitialization:
    """Tests for worker startup behavior."""

    @pytest.mark.asyncio
    async def test_run_worker_initializes_queue(self):
        """_run_worker calls get_queue() to initialize the queue connection."""
        from src.cli.worker_commands import _run_worker

        mock_pgq = MagicMock()
        # Make pgq.run() raise KeyboardInterrupt to exit the worker loop immediately
        mock_pgq.run = AsyncMock(side_effect=KeyboardInterrupt)

        # Lazy imports inside _run_worker: must patch at source module
        with (
            patch(
                "src.queue.setup.get_queue",
                new_callable=AsyncMock,
                return_value=mock_pgq,
            ) as mock_get_queue,
            patch(
                "src.queue.setup.close_queue",
                new_callable=AsyncMock,
            ) as mock_close_queue,
            patch("src.tasks.content.register_content_tasks") as mock_register,
        ):
            with pytest.raises(KeyboardInterrupt):
                await _run_worker(5)

            mock_get_queue.assert_called_once()
            mock_register.assert_called_once_with(mock_pgq)
            # close_queue should be called in finally block
            mock_close_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_worker_registers_signal_handlers(self):
        """_run_worker registers SIGTERM and SIGINT signal handlers."""
        import signal

        from src.cli.worker_commands import _run_worker

        mock_pgq = MagicMock()
        mock_pgq.run = AsyncMock(side_effect=KeyboardInterrupt)

        registered_signals = []

        def capture_signal(signum, handler):
            registered_signals.append(signum)

        with (
            patch(
                "src.queue.setup.get_queue",
                new_callable=AsyncMock,
                return_value=mock_pgq,
            ),
            patch("src.queue.setup.close_queue", new_callable=AsyncMock),
            patch("src.tasks.content.register_content_tasks"),
            patch("signal.signal", side_effect=capture_signal),
        ):
            with pytest.raises(KeyboardInterrupt):
                await _run_worker(5)

        # Should have registered handlers for SIGTERM and SIGINT
        assert signal.SIGTERM in registered_signals
        assert signal.SIGINT in registered_signals

    @pytest.mark.asyncio
    async def test_run_worker_passes_concurrency_to_pgq_run(self):
        """_run_worker passes max_concurrent_tasks to pgq.run()."""
        from src.cli.worker_commands import _run_worker

        mock_pgq = MagicMock()
        mock_pgq.run = AsyncMock(return_value=None)  # Normal exit

        with (
            patch(
                "src.queue.setup.get_queue",
                new_callable=AsyncMock,
                return_value=mock_pgq,
            ),
            patch("src.queue.setup.close_queue", new_callable=AsyncMock),
            patch("src.tasks.content.register_content_tasks"),
        ):
            await _run_worker(10)

        # Verify pgq.run was called with the correct concurrency
        mock_pgq.run.assert_called_once()
        call_kwargs = mock_pgq.run.call_args.kwargs
        assert call_kwargs["max_concurrent_tasks"] == 10

    @pytest.mark.asyncio
    async def test_run_worker_cleans_up_on_cancelled_error(self):
        """_run_worker calls close_queue on CancelledError (graceful shutdown)."""
        import asyncio

        from src.cli.worker_commands import _run_worker

        mock_pgq = MagicMock()
        mock_pgq.run = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch(
                "src.queue.setup.get_queue",
                new_callable=AsyncMock,
                return_value=mock_pgq,
            ),
            patch(
                "src.queue.setup.close_queue",
                new_callable=AsyncMock,
            ) as mock_close,
            patch("src.tasks.content.register_content_tasks"),
        ):
            await _run_worker(5)

        mock_close.assert_called_once()
