"""Tests for LLMRouter batch execution (submit_batch / poll_batch).

Mocks the google-genai client per repo convention (``patch("google.genai.Client")``
+ ``patch.dict("os.environ", {"GOOGLE_API_KEY": ...})``). No network, no real
batch jobs.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config.models import ModelConfig
from src.services.batch.types import BatchPollResult, BatchRequest, BatchState
from src.services.llm_router import LLMRouter


@pytest.fixture
def router() -> LLMRouter:
    return LLMRouter(ModelConfig())


def _resp(text: str, request_key: str) -> SimpleNamespace:
    """A fake InlinedResponse carrying text + echoed request_key metadata."""
    part = SimpleNamespace(text=text)
    content = SimpleNamespace(parts=[part])
    candidate = SimpleNamespace(content=content)
    response = SimpleNamespace(candidates=[candidate])
    return SimpleNamespace(response=response, metadata={"request_key": request_key}, error=None)


def _err_resp(request_key: str, message: str) -> SimpleNamespace:
    return SimpleNamespace(response=None, metadata={"request_key": request_key}, error=message)


def _job(state_name: str, responses: list | None = None, error: str | None = None):
    state = SimpleNamespace(name=state_name)
    dest = SimpleNamespace(inlined_responses=responses) if responses is not None else None
    return SimpleNamespace(name="batches/test-123", state=state, dest=dest, error=error)


class TestSubmitBatch:
    @pytest.mark.asyncio
    async def test_rejects_non_google_model(self, router):
        with pytest.raises(ValueError, match="google_ai"):
            await router.submit_batch(
                "claude-sonnet-4-5",
                [BatchRequest(key="k1", contents="hi")],
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_requests(self, router):
        with pytest.raises(ValueError, match="at least one"):
            await router.submit_batch("gemini-2.5-flash-lite", [])

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, router):
        with patch.dict("os.environ", {}, clear=True):
            os.environ.pop("GOOGLE_API_KEY", None)
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
                await router.submit_batch(
                    "gemini-2.5-flash-lite",
                    [BatchRequest(key="k1", contents="hi")],
                )

    @pytest.mark.asyncio
    async def test_submits_inline_with_request_key_metadata(self, router):
        mock_client = MagicMock()
        mock_client.batches.create.return_value = SimpleNamespace(name="batches/abc")
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            job_name = await router.submit_batch(
                "gemini-2.5-flash-lite",
                [
                    BatchRequest(key="k1", contents="prompt one", config={"temperature": 0.0}),
                    BatchRequest(key="k2", contents="prompt two"),
                ],
            )

        assert job_name == "batches/abc"
        mock_client.batches.create.assert_called_once()
        kwargs = mock_client.batches.create.call_args.kwargs
        src = kwargs["src"]
        assert len(src) == 2
        # Each inlined request must carry its request_key for reconciliation.
        assert {r.metadata["request_key"] for r in src} == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_rejects_oversized_inline_payload(self, router):
        big = "x" * (19 * 1024 * 1024)
        mock_client = MagicMock()
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            with pytest.raises(ValueError, match="inline cap"):
                await router.submit_batch(
                    "gemini-2.5-flash-lite",
                    [BatchRequest(key="k1", contents=big)],
                )
        mock_client.batches.create.assert_not_called()


class TestPollBatch:
    @pytest.mark.asyncio
    async def test_success_returns_results_by_key_order_independent(self, router):
        # Responses come back in REVERSE order — reconciliation must use metadata.
        mock_client = MagicMock()
        mock_client.batches.get.return_value = _job(
            "JOB_STATE_SUCCEEDED",
            responses=[_resp("answer two", "k2"), _resp("answer one", "k1")],
        )
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert isinstance(result, BatchPollResult)
        assert result.state == BatchState.SUCCEEDED
        assert result.results_by_key == {"k1": "answer one", "k2": "answer two"}
        assert result.errors_by_key is None
        assert result.is_terminal is True

    @pytest.mark.asyncio
    async def test_partial_success_splits_results_and_errors(self, router):
        mock_client = MagicMock()
        mock_client.batches.get.return_value = _job(
            "JOB_STATE_PARTIALLY_SUCCEEDED",
            responses=[_resp("ok", "k1"), _err_resp("k2", "safety block")],
        )
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert result.state == BatchState.SUCCEEDED  # partial maps to succeeded
        assert result.results_by_key == {"k1": "ok"}
        assert result.errors_by_key == {"k2": "safety block"}

    @pytest.mark.asyncio
    async def test_failed_state_returns_no_results(self, router):
        mock_client = MagicMock()
        mock_client.batches.get.return_value = _job("JOB_STATE_FAILED", error="quota exceeded")
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert result.state == BatchState.FAILED
        assert result.results_by_key is None
        assert result.error == "quota exceeded"
        assert result.is_terminal is True

    @pytest.mark.asyncio
    async def test_expired_state_is_terminal(self, router):
        mock_client = MagicMock()
        mock_client.batches.get.return_value = _job("JOB_STATE_EXPIRED")
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert result.state == BatchState.EXPIRED
        assert result.is_terminal is True
        assert result.results_by_key is None

    @pytest.mark.asyncio
    async def test_running_state_is_non_terminal(self, router):
        mock_client = MagicMock()
        mock_client.batches.get.return_value = _job("JOB_STATE_RUNNING")
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert result.state == BatchState.RUNNING
        assert result.is_terminal is False

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, router):
        with patch.dict("os.environ", {}, clear=True):
            os.environ.pop("GOOGLE_API_KEY", None)
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
                await router.poll_batch("batches/test-123")


class TestStateMapping:
    @pytest.mark.parametrize(
        ("raw_name", "expected"),
        [
            ("JOB_STATE_PENDING", BatchState.PENDING),
            ("JOB_STATE_QUEUED", BatchState.PENDING),
            ("JOB_STATE_RUNNING", BatchState.RUNNING),
            ("JOB_STATE_CANCELLING", BatchState.RUNNING),
            ("JOB_STATE_SUCCEEDED", BatchState.SUCCEEDED),
            ("JOB_STATE_PARTIALLY_SUCCEEDED", BatchState.SUCCEEDED),
            ("JOB_STATE_FAILED", BatchState.FAILED),
            ("JOB_STATE_EXPIRED", BatchState.EXPIRED),
            ("JOB_STATE_CANCELLED", BatchState.CANCELLED),
            ("SOMETHING_UNKNOWN", BatchState.RUNNING),  # safe default: keep polling
        ],
    )
    def test_map_batch_state(self, raw_name, expected):
        assert LLMRouter._map_batch_state(SimpleNamespace(name=raw_name)) == expected

    def test_map_accepts_bare_string(self):
        assert LLMRouter._map_batch_state("JOB_STATE_SUCCEEDED") == BatchState.SUCCEEDED
