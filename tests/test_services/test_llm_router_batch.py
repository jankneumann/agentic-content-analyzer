"""Tests for LLMRouter batch execution (submit_batch / poll_batch).

Mocks the google-genai client per repo convention (``patch("google.genai.Client")``
+ ``patch.dict("os.environ", {"GOOGLE_API_KEY": ...})``). No network, no real
batch jobs.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


def _async_client() -> tuple[MagicMock, MagicMock]:
    client = MagicMock()
    batches = MagicMock()
    batches.create = AsyncMock()
    batches.get = AsyncMock()
    client.aio.batches = batches
    return client, batches


class TestSubmitBatch:
    @pytest.mark.asyncio
    async def test_rejects_non_google_model(self, router):
        with patch("google.genai.Client") as client_factory:
            with pytest.raises(ValueError, match="google_ai"):
                await router.submit_batch(
                    "claude-sonnet-4-5",
                    [BatchRequest(key="k1", contents="hi")],
                )
        client_factory.assert_not_called()

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
        mock_client, batches = _async_client()
        batches.create.return_value = SimpleNamespace(name="batches/abc")
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
        batches.create.assert_awaited_once()
        kwargs = batches.create.call_args.kwargs
        assert kwargs["model"] == "gemini-2.5-flash-lite"
        src = kwargs["src"]
        assert len(src) == 2
        # Each inlined request must carry its request_key for reconciliation.
        assert {r.metadata["request_key"] for r in src} == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_rejects_oversized_inline_payload(self, router):
        big = "x" * (19 * 1024 * 1024)
        mock_client, batches = _async_client()
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            with pytest.raises(ValueError, match="inline cap"):
                await router.submit_batch(
                    "gemini-2.5-flash-lite",
                    [BatchRequest(key="k1", contents=big)],
                )
        batches.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_payload_at_configured_limit_using_utf8_bytes(self, router):
        router.model_config._batch_config["inline_max_bytes"] = 100
        mock_client, batches = _async_client()
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            with pytest.raises(ValueError, match="inline cap"):
                await router.submit_batch(
                    "gemini-2.5-flash-lite",
                    [BatchRequest(key="k1", contents="é" * 100)],
                )
        batches.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_duplicate_request_keys_before_client_creation(self, router):
        with patch("google.genai.Client") as client_factory:
            with pytest.raises(ValueError, match="duplicate request key"):
                await router.submit_batch(
                    "gemini-2.5-flash-lite",
                    [
                        BatchRequest(key="same", contents="one"),
                        BatchRequest(key="same", contents="two"),
                    ],
                )
        client_factory.assert_not_called()


class TestPollBatch:
    @pytest.mark.asyncio
    async def test_success_returns_results_by_key_order_independent(self, router):
        # Responses come back in REVERSE order — reconciliation must use metadata.
        mock_client, batches = _async_client()
        batches.get.return_value = _job(
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
        batches.get.assert_awaited_once_with(name="batches/test-123")

    @pytest.mark.asyncio
    async def test_partial_success_splits_results_and_errors(self, router):
        mock_client, batches = _async_client()
        batches.get.return_value = _job(
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
        mock_client, batches = _async_client()
        batches.get.return_value = _job("JOB_STATE_FAILED", error="quota exceeded")
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
        mock_client, batches = _async_client()
        batches.get.return_value = _job("JOB_STATE_EXPIRED")
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
        mock_client, batches = _async_client()
        batches.get.return_value = _job("JOB_STATE_RUNNING")
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

    @pytest.mark.asyncio
    async def test_duplicate_response_key_is_an_error_not_last_write_wins(self, router):
        mock_client, batches = _async_client()
        batches.get.return_value = _job(
            "JOB_STATE_SUCCEEDED",
            responses=[_resp("first", "k1"), _resp("second", "k1")],
        )
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123", expected_request_keys={"k1"})

        assert result.results_by_key == {}
        assert result.errors_by_key == {"k1": "duplicate batch response request_key"}

    @pytest.mark.asyncio
    async def test_missing_metadata_and_missing_expected_key_are_reported(self, router):
        response = _resp("orphaned", "ignored")
        response.metadata = {}
        mock_client, batches = _async_client()
        batches.get.return_value = _job("JOB_STATE_SUCCEEDED", responses=[response])
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123", expected_request_keys={"k1"})

        assert result.errors_by_key == {"k1": "missing from batch response"}
        assert result.unmatched_errors == ("batch response missing request_key metadata",)

    @pytest.mark.asyncio
    async def test_empty_generated_text_is_a_per_request_error(self, router):
        mock_client, batches = _async_client()
        batches.get.return_value = _job("JOB_STATE_SUCCEEDED", responses=[_resp("", "k1")])
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            result = await router.poll_batch("batches/test-123")

        assert result.results_by_key == {}
        assert result.errors_by_key == {"k1": "batch response contained no text"}


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
