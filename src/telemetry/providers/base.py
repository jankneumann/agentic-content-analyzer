"""Base protocol for observability providers.

Uses structural subtyping (Protocol) consistent with the database provider pattern
in src/storage/providers/base.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI


@runtime_checkable
class ObservabilityProvider(Protocol):
    """Protocol for observability providers.

    Each provider implements tracing for LLM calls, pipeline spans,
    and lifecycle management. The protocol mirrors the DatabaseProvider
    pattern from src/storage/providers/base.py.
    """

    @property
    def name(self) -> str:
        """Return the provider name identifier (e.g., 'noop', 'opik', 'braintrust')."""
        ...

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize the provider (called once at application startup).

        Args:
            app: FastAPI application instance for middleware/instrumentation
        """
        ...

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
        """Record an LLM call with all relevant attributes.

        Args:
            model: Model identifier (e.g., "claude-sonnet-4-5")
            provider: LLM provider name (e.g., "anthropic", "openai")
            system_prompt: System prompt text
            user_prompt: User prompt text
            response_text: Model response text
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated
            duration_ms: Call duration in milliseconds
            max_tokens: Maximum tokens requested (optional)
            metadata: Additional key-value metadata (optional)
        """
        ...

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[None, None, None]:
        """Start a named span for pipeline tracing.

        Args:
            name: Span name (e.g., "summarize_content", "ingest_gmail")
            attributes: Initial span attributes

        Yields:
            None (span is managed by the context manager)
        """
        ...

    def flush(self) -> None:
        """Flush any buffered telemetry data."""
        ...

    def shutdown(self) -> None:
        """Gracefully shut down the provider and release resources."""
        ...
