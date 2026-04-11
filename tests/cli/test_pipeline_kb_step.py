"""Tests for the optional KB compile pipeline step.

Validates that ``_maybe_run_kb_compile_stage`` respects the
``kb_pipeline_enabled`` setting and degrades gracefully on errors.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestPipelineKBStep:
    def test_skipped_when_disabled(self, monkeypatch):
        """kb.14: Default disabled — pipeline skips KB step entirely."""
        from src.cli.pipeline_commands import _maybe_run_kb_compile_stage

        # Force kb_pipeline_enabled = False
        with patch("src.config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(kb_pipeline_enabled=False)
            result = _maybe_run_kb_compile_stage()

        assert result["status"] == "skipped"
        assert "kb_pipeline_enabled=false" in result["reason"]

    def test_runs_compile_when_enabled(self):
        """kb.14: When enabled, the stage invokes the KB service."""
        from src.cli.pipeline_commands import _maybe_run_kb_compile_stage
        from src.services.knowledge_base import CompileSummary

        summary = CompileSummary(
            started_at=datetime(2026, 4, 9, tzinfo=UTC),
            finished_at=datetime(2026, 4, 9, tzinfo=UTC),
            topics_found=3,
            topics_compiled=3,
        )
        mock_service = MagicMock()
        mock_service.compile = AsyncMock(return_value=summary)

        @contextmanager
        def fake_get_db():
            yield MagicMock()

        with (
            patch("src.config.settings.get_settings") as mock_settings,
            patch(
                "src.services.knowledge_base.KnowledgeBaseService",
                return_value=mock_service,
            ),
            patch("src.storage.database.get_db", side_effect=fake_get_db),
        ):
            mock_settings.return_value = MagicMock(kb_pipeline_enabled=True)
            result = _maybe_run_kb_compile_stage()

        assert result["status"] == "completed"
        assert result["topics_compiled"] == 3
        mock_service.compile.assert_called_once()

    def test_compile_failure_is_non_fatal(self):
        """kb.14: KB compile failures do not raise (pipeline continues)."""
        from src.cli.pipeline_commands import _maybe_run_kb_compile_stage

        mock_service = MagicMock()
        mock_service.compile = AsyncMock(side_effect=RuntimeError("LLM down"))

        @contextmanager
        def fake_get_db():
            yield MagicMock()

        with (
            patch("src.config.settings.get_settings") as mock_settings,
            patch(
                "src.services.knowledge_base.KnowledgeBaseService",
                return_value=mock_service,
            ),
            patch("src.storage.database.get_db", side_effect=fake_get_db),
        ):
            mock_settings.return_value = MagicMock(kb_pipeline_enabled=True)
            result = _maybe_run_kb_compile_stage()

        assert result["status"] == "failed"
        assert "LLM down" in result["error"]
