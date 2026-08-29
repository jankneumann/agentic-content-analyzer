"""API process must call setup_logging() on startup.

The CLI is the only historical call site. Every API boot path (uvicorn in
Docker, ``make api``, TestClient) goes straight to the FastAPI app and used
to skip logging configuration entirely: log_level, JSON formatting, noisy
library suppression, and trace_id emission were all inert.
"""

from __future__ import annotations

import logging

from src.config import settings
from src.utils.logging import JsonFormatter, TraceContextFormatter


def test_api_startup_configures_root_logging(client):
    """Lifespan (or import) must leave the root logger actually configured."""
    root = logging.getLogger()
    expected_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    assert root.getEffectiveLevel() <= expected_level

    app_logger = logging.getLogger("src.api.middleware.error_handler")
    assert app_logger.propagate is True
    assert app_logger.getEffectiveLevel() <= expected_level
    assert app_logger.isEnabledFor(logging.INFO)

    formatters = [handler.formatter for handler in root.handlers]
    if settings.log_format == "json":
        assert any(isinstance(fmt, JsonFormatter) for fmt in formatters), (
            f"API startup must install JsonFormatter on the root logger; handlers={root.handlers!r}"
        )
    else:
        assert any(isinstance(fmt, TraceContextFormatter) for fmt in formatters), (
            "API startup must install TraceContextFormatter on the root logger; "
            f"handlers={root.handlers!r}"
        )
