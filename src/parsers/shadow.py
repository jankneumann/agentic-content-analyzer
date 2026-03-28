"""Shadow evaluation for parser comparison.

Runs a secondary parser in parallel with the canonical parser to collect
comparison telemetry. Shadow results are never persisted — they serve only
to inform parser promotion decisions.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import BinaryIO

from src.models.document import DocumentContent
from src.parsers.base import DocumentParser

logger = logging.getLogger(__name__)


async def run_shadow_parse(
    shadow_parser: DocumentParser,
    canonical_result: DocumentContent,
    source: str | Path | BinaryIO | bytes,
    format_hint: str | None = None,
) -> None:
    """Run a shadow parse and emit comparison telemetry.

    This function is designed to be called via asyncio.create_task()
    as a fire-and-forget operation. It never raises — all errors are
    caught and logged.

    Args:
        shadow_parser: The parser to evaluate (typically Kreuzberg).
        canonical_result: The result from the canonical parser for comparison.
        source: Document source (same as passed to canonical parser).
        format_hint: Optional format override.
    """
    source_str = (
        str(source) if not (isinstance(source, bytes) or hasattr(source, "read")) else "stream"
    )
    start_time = time.time()

    try:
        shadow_result = await shadow_parser.parse(source, format_hint=format_hint)
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Compute comparison metrics
        canonical_len = len(canonical_result.markdown_content)
        shadow_len = len(shadow_result.markdown_content)
        length_delta = shadow_len - canonical_len
        length_ratio = shadow_len / canonical_len if canonical_len > 0 else 0.0

        canonical_warnings = len(canonical_result.warnings)
        shadow_warnings = len(shadow_result.warnings)

        canonical_tables = len(canonical_result.tables)
        shadow_tables = len(shadow_result.tables)

        canonical_links = len(canonical_result.links)
        shadow_links = len(shadow_result.links)

        logger.info(
            "Shadow parse comparison",
            extra={
                "shadow_parser": shadow_parser.name,
                "canonical_parser": canonical_result.parser_used,
                "source": source_str,
                "format": format_hint or canonical_result.source_format,
                "shadow_elapsed_ms": elapsed_ms,
                "canonical_elapsed_ms": canonical_result.processing_time_ms,
                "latency_delta_ms": elapsed_ms - canonical_result.processing_time_ms,
                "shadow_content_length": shadow_len,
                "canonical_content_length": canonical_len,
                "content_length_delta": length_delta,
                "content_length_ratio": round(length_ratio, 3),
                "shadow_warning_count": shadow_warnings,
                "canonical_warning_count": canonical_warnings,
                "shadow_table_count": shadow_tables,
                "canonical_table_count": canonical_tables,
                "shadow_link_count": shadow_links,
                "canonical_link_count": canonical_links,
                "shadow_success": True,
            },
        )

    except Exception:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            "Shadow parse failed",
            extra={
                "shadow_parser": shadow_parser.name,
                "canonical_parser": canonical_result.parser_used,
                "source": source_str,
                "format": format_hint,
                "shadow_elapsed_ms": elapsed_ms,
                "shadow_success": False,
            },
            exc_info=True,
        )


def maybe_shadow_parse(
    shadow_parser: DocumentParser | None,
    shadow_formats: set[str],
    detected_format: str,
    canonical_result: DocumentContent,
    source: str | Path | BinaryIO | bytes,
    format_hint: str | None = None,
) -> asyncio.Task[None] | None:
    """Conditionally launch a shadow parse as a background task.

    Returns the task if launched, None otherwise. The caller does NOT
    need to await the task — it runs to completion independently.

    Args:
        shadow_parser: The parser to use for shadow evaluation (None = disabled).
        shadow_formats: Set of formats that should trigger shadow evaluation.
        detected_format: The detected format of the current document.
        canonical_result: Result from the canonical parser.
        source: Document source.
        format_hint: Optional format override.

    Returns:
        The background task if shadow was launched, None otherwise.
    """
    if shadow_parser is None or not shadow_formats:
        return None

    if detected_format not in shadow_formats:
        return None

    # Don't shadow if canonical already used the shadow parser
    if canonical_result.parser_used == shadow_parser.name:
        return None

    logger.debug(f"Launching shadow parse with {shadow_parser.name} for format {detected_format}")

    return asyncio.create_task(
        run_shadow_parse(
            shadow_parser=shadow_parser,
            canonical_result=canonical_result,
            source=source,
            format_hint=format_hint,
        ),
        name=f"shadow-{shadow_parser.name}-{detected_format}",
    )
