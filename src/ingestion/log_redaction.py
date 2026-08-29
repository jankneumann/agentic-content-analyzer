"""Opaque identifiers and bounded classification for adapter logs.

Durable ingestion results already go through :mod:`src.ingestion.result_sanitizer`.
Adapter log lines are a separate surface and must never carry configured-source
locators (URLs, mailbox paths, playlist/channel IDs), credentials, or raw
exception text.
"""

from __future__ import annotations

import re
from typing import Any

from src.ingestion.result_sanitizer import sanitize_ingestion_diagnostic_code

UNKEYED_SOURCE = "src_unkeyed"
_SOURCE_KEY_RE = re.compile(r"^src_[a-f0-9]{20}$")


def log_source_key(value: object) -> str:
    """Return a public source key, or a sentinel when one is not available."""

    if isinstance(value, str) and _SOURCE_KEY_RE.fullmatch(value):
        return value
    return UNKEYED_SOURCE


def log_error_type(exc: object) -> str:
    """Operational classification only — never the exception payload."""

    if isinstance(exc, BaseException):
        name = type(exc).__name__
    elif isinstance(exc, type):
        name = exc.__name__
    else:
        name = type(exc).__name__
    return name if name.isidentifier() else "Error"


def log_diagnostic_code(value: object) -> str:
    """Map a diagnostic into the closed public ingestion vocabulary."""

    return sanitize_ingestion_diagnostic_code(value)


def adapter_log_extra(
    *,
    source_key: object = None,
    code: object | None = None,
    error: object | None = None,
) -> dict[str, Any]:
    """Build a locator-free ``extra`` dict for adapter log records."""

    extra: dict[str, Any] = {"source_key": log_source_key(source_key)}
    if code is not None:
        extra["code"] = log_diagnostic_code(code)
    if error is not None:
        extra["error_type"] = log_error_type(error)
    return extra
