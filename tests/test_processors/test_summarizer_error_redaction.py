"""Guarded summarizer failures persist a closed code, not provider payloads."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from src.agents.base import AgentResponse
from src.processors.summarizer import SUMMARIZATION_ERROR_CODE, ContentSummarizer
from src.queue.execution_claim import ExecutionClaim, bind_execution_claim

HOSTILE = "ANTHROPIC_API_KEY=sk-ant-secret timeout talking to https://api.anthropic.com"


def _content(*, content_id: int = 7) -> MagicMock:
    content = MagicMock()
    content.id = content_id
    content.title = "ignored"
    content.status_owner_version = 1
    return content


def _db_with(content: MagicMock) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = content
    ctx = MagicMock()
    ctx.__enter__.return_value = db
    ctx.__exit__.return_value = False
    return ctx


class TestSummarizerFailureRedaction:
    def test_guarded_exception_does_not_persist_or_log_provider_text(self, caplog):
        content = _content()
        agent = MagicMock()
        agent.summarize_content.side_effect = RuntimeError(HOSTILE)
        summarizer = ContentSummarizer(agent=agent)

        with (
            caplog.at_level(logging.ERROR, logger="src.processors.summarizer"),
            patch("src.processors.summarizer.get_db", return_value=_db_with(content)),
            patch(
                "src.processors.summarizer.acquire_content_execution",
                return_value=content,
            ),
            patch(
                "src.processors.summarizer.guard_content_execution",
                return_value=content,
            ),
            bind_execution_claim(ExecutionClaim(job_id=1, claim_generation=1)),
        ):
            assert summarizer.summarize_content(content.id) is False

        assert content.error_message == SUMMARIZATION_ERROR_CODE
        blob = caplog.text
        assert HOSTILE not in blob
        assert "sk-ant-secret" not in blob
        assert "api.anthropic.com" not in blob
        assert any(
            getattr(record, "error_type", None) == "RuntimeError" for record in caplog.records
        )

    def test_agent_response_error_is_replaced_with_closed_code(self, caplog):
        content = _content()
        agent = MagicMock()
        agent.summarize_content.return_value = AgentResponse(success=False, error=HOSTILE)
        summarizer = ContentSummarizer(agent=agent)

        with (
            caplog.at_level(logging.ERROR, logger="src.processors.summarizer"),
            patch("src.processors.summarizer.get_db", return_value=_db_with(content)),
            patch(
                "src.processors.summarizer.acquire_content_execution",
                return_value=content,
            ),
            patch(
                "src.processors.summarizer.guard_content_execution",
                return_value=content,
            ),
            bind_execution_claim(ExecutionClaim(job_id=1, claim_generation=1)),
        ):
            assert summarizer.summarize_content(content.id) is False

        assert content.error_message == SUMMARIZATION_ERROR_CODE
        assert HOSTILE not in caplog.text
