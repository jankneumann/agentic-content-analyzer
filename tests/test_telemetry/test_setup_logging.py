"""Tests for application logging setup.

``setup_logging()`` is the only place this app attaches a handler to the root
logger. It must be idempotent and must not rely on ``logging.basicConfig``,
which is a no-op once any root handler already exists (pytest, uvicorn
``LOGGING_CONFIG``, a prior call).
"""

from __future__ import annotations

import logging
import logging.config
import sys

import pytest

from src.config import settings
from src.utils.logging import JsonFormatter, TraceContextFormatter, setup_logging


@pytest.fixture
def isolated_root_logger():
    """Snapshot and restore the root logger so these tests cannot leak handlers."""
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    try:
        yield root
    finally:
        root.handlers[:] = previous_handlers
        root.setLevel(previous_level)


def _app_formatters(root: logging.Logger) -> list[logging.Formatter]:
    return [handler.formatter for handler in root.handlers if handler.formatter is not None]


class TestSetupLogging:
    def test_installs_stderr_handler_with_configured_formatter(self, isolated_root_logger):
        setup_logging()

        root = isolated_root_logger
        expected_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        assert root.level == expected_level

        stderr_handlers = [
            handler
            for handler in root.handlers
            if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr
        ]
        assert stderr_handlers, "setup_logging() must attach a stderr StreamHandler to root"

        formatter = stderr_handlers[0].formatter
        if settings.log_format == "json":
            assert isinstance(formatter, JsonFormatter)
        else:
            assert isinstance(formatter, TraceContextFormatter)

        app_logger = logging.getLogger("src.api.middleware.error_handler")
        assert app_logger.propagate is True
        assert app_logger.isEnabledFor(logging.INFO)

    def test_is_idempotent_does_not_stack_handlers(self, isolated_root_logger):
        setup_logging()
        setup_logging()

        app_handlers = [
            handler
            for handler in isolated_root_logger.handlers
            if isinstance(handler.formatter, (JsonFormatter, TraceContextFormatter))
        ]
        assert len(app_handlers) == 1

    def test_attaches_app_handler_even_when_root_already_has_handlers(self, isolated_root_logger):
        """``basicConfig`` would be a no-op here; the app handler must still land."""
        preexisting = logging.StreamHandler(sys.stderr)
        isolated_root_logger.addHandler(preexisting)

        setup_logging()

        assert any(
            isinstance(fmt, (JsonFormatter, TraceContextFormatter))
            for fmt in _app_formatters(isolated_root_logger)
        )

    def test_survives_uvicorn_logging_config(self, isolated_root_logger):
        """Uvicorn's default dictConfig does not configure root; we still must."""
        import uvicorn.config

        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
        setup_logging()

        app_logger = logging.getLogger("src.api.middleware.error_handler")
        assert app_logger.propagate is True
        assert app_logger.isEnabledFor(logging.INFO)
        assert any(
            isinstance(fmt, (JsonFormatter, TraceContextFormatter))
            for fmt in _app_formatters(logging.getLogger())
        )
