"""No-op observability provider.

Default provider that performs zero work. Used when observability is disabled
or not configured. Ensures zero runtime overhead.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI


class NoopProvider:
    """No-op observability provider with zero overhead.

    All methods are implemented as no-ops. This is the default provider
    when OBSERVABILITY_PROVIDER is not set or set to "noop".
    """

    @property
    def name(self) -> str:
        """Return provider name."""
        return "noop"

    def setup(self, app: FastAPI | None = None) -> None:
        """No-op setup."""

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
        """No-op LLM call trace."""

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[None, None, None]:
        """No-op span context manager."""
        yield

    def flush(self) -> None:
        """No-op flush."""

    def shutdown(self) -> None:
        """No-op shutdown."""
