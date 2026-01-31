"""Braintrust observability provider.

Uses the native Braintrust SDK for rich LLM tracing with:
- Automatic client wrapping (wrap_anthropic, wrap_openai)
- Built-in evaluation scoring
- Prompt versioning and management
- Richer span metadata than pure OTel

Also configures OTel OTLP export for infrastructure traces.

Docs: https://www.braintrust.dev/docs
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default Braintrust API URL
DEFAULT_BRAINTRUST_API_URL = "https://api.braintrust.dev"


class BraintrustProvider:
    """Braintrust observability provider using native SDK.

    Provides richer LLM tracing than pure OTel through Braintrust's
    native logging capabilities. Falls back to no-op if the braintrust
    package is not installed.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        project_name: str = "newsletter-aggregator",
        api_url: str = DEFAULT_BRAINTRUST_API_URL,
        log_prompts: bool = False,
    ) -> None:
        self._api_key = api_key
        self._project_name = project_name
        self._api_url = api_url
        self._log_prompts = log_prompts
        self._logger = None
        self._setup_complete = False

    @property
    def name(self) -> str:
        return "braintrust"

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize Braintrust logger."""
        if self._setup_complete:
            return

        if not self._api_key:
            logger.warning(
                "Braintrust API key not configured (BRAINTRUST_API_KEY). "
                "LLM traces will not be exported."
            )
            self._setup_complete = True
            return

        try:
            import os

            import braintrust

            # Set API key in environment (Braintrust SDK reads from env)
            os.environ.setdefault("BRAINTRUST_API_KEY", self._api_key)
            if self._api_url != DEFAULT_BRAINTRUST_API_URL:
                os.environ.setdefault("BRAINTRUST_API_URL", self._api_url)

            self._logger = braintrust.init_logger(project=self._project_name)
            self._setup_complete = True

            logger.info(
                f"Braintrust provider initialized "
                f"(project: {self._project_name}, api: {self._api_url})"
            )
        except ImportError:
            logger.error(
                "Braintrust package not installed. "
                "Install with: pip install 'agentic-newsletter-aggregator[braintrust]'"
            )
            self._setup_complete = True
        except Exception as e:
            logger.error(f"Failed to initialize Braintrust: {e}")
            self._setup_complete = True

    def trace_llm_call(
        self,
        *,
        model: str,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM call using Braintrust's native logging."""
        if self._logger is None:
            return

        try:
            import braintrust

            span = braintrust.current_span()

            log_data: dict[str, Any] = {
                "input": user_prompt if self._log_prompts else f"[{len(user_prompt)} chars]",
                "output": response_text if self._log_prompts else f"[{len(response_text)} chars]",
                "metadata": {
                    "model": model,
                    "provider": provider,
                    "max_tokens": max_tokens,
                    **(metadata or {}),
                },
                "metrics": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "duration_ms": duration_ms,
                },
            }

            span.log(**log_data)
        except Exception as e:
            logger.debug(f"Error logging to Braintrust: {e}")

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """Start a Braintrust span."""
        if self._logger is None:
            yield None
            return

        try:
            import braintrust

            with braintrust.start_span(name=name) as span:
                if attributes:
                    span.log(metadata=attributes)
                yield span
        except Exception:
            yield None

    def flush(self) -> None:
        """Flush Braintrust logger."""
        if self._logger is not None:
            try:
                self._logger.flush()
            except Exception as e:
                logger.debug(f"Error flushing Braintrust: {e}")

    def shutdown(self) -> None:
        """Shut down Braintrust logger."""
        self.flush()
        self._logger = None
        self._setup_complete = False
