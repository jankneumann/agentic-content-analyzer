"""Tests for Kreuzberg extensions to ParserRouter and shadow evaluation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import DocumentContent, DocumentFormat
from src.parsers.router import ParserRouter
from src.parsers.shadow import maybe_shadow_parse, run_shadow_parse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_parser(
    name: str,
    supported: set[str] | None = None,
    fallback: set[str] | None = None,
) -> MagicMock:
    """Create a mock parser conforming to the DocumentParser interface."""
    parser = MagicMock()
    parser.name = name
    parser.supported_formats = supported or set()
    parser.fallback_formats = fallback or set()
    parser.can_parse = MagicMock(return_value=True)
    parser.parse = AsyncMock(
        return_value=DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used=name,
            processing_time_ms=50,
        )
    )
    return parser


def make_router(
    kreuzberg: MagicMock | None = None,
    docling: MagicMock | None = None,
    preferred: set[str] | None = None,
    shadow: set[str] | None = None,
) -> ParserRouter:
    """Build a ParserRouter with the given optional parsers."""
    return ParserRouter(
        markitdown_parser=make_mock_parser("markitdown"),
        docling_parser=docling,
        kreuzberg_parser=kreuzberg,
        kreuzberg_preferred_formats=preferred,
        kreuzberg_shadow_formats=shadow,
    )


# ===================================================================
# 1. Kreuzberg registration
# ===================================================================


class TestKreuzbergRegistration:
    def test_router_without_kreuzberg(self) -> None:
        router = make_router()
        assert router.has_kreuzberg is False
        assert "kreuzberg" not in router.available_parsers

    def test_router_with_kreuzberg(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg", supported={"pdf", "docx"})
        router = make_router(kreuzberg=kreuzberg)
        assert router.has_kreuzberg is True
        assert "kreuzberg" in router.available_parsers


# ===================================================================
# 2. Preference routing
# ===================================================================


class TestPreferenceRouting:
    def test_preferred_format_routes_to_kreuzberg(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        router = make_router(kreuzberg=kreuzberg, preferred={"docx"})
        parser = router.route("report.docx")
        assert parser.name == "kreuzberg"

    def test_non_preferred_format_uses_routing_table(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        router = make_router(kreuzberg=kreuzberg, preferred=set())
        parser = router.route("report.docx")
        # ROUTING_TABLE maps docx -> markitdown
        assert parser.name == "markitdown"

    def test_ocr_overrides_kreuzberg_preference(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        docling = make_mock_parser("docling")
        router = make_router(kreuzberg=kreuzberg, docling=docling, preferred={"pdf"})
        parser = router.route("document.pdf", ocr_needed=True)
        assert parser.name == "docling"

    def test_prefer_structured_overrides_kreuzberg(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        docling = make_mock_parser("docling")
        router = make_router(kreuzberg=kreuzberg, docling=docling, preferred={"pdf"})
        parser = router.route("document.pdf", prefer_structured=True)
        assert parser.name == "docling"


# ===================================================================
# 3. Fallback behavior
# ===================================================================


class TestFallbackBehavior:
    def test_kreuzberg_fallback_when_unavailable(self) -> None:
        """Kreuzberg in ROUTING_TABLE but parser not registered -> markitdown."""
        router = make_router()  # no kreuzberg parser
        # Temporarily patch ROUTING_TABLE to map docx -> kreuzberg
        with patch.dict(ParserRouter.ROUTING_TABLE, {"docx": "kreuzberg"}):
            parser = router.route("report.docx")
        assert parser.name == "markitdown"

    def test_kreuzberg_preferred_but_not_registered(self) -> None:
        """Preference set but no kreuzberg parser -> uses routing table."""
        router = ParserRouter(
            markitdown_parser=make_mock_parser("markitdown"),
            kreuzberg_preferred_formats={"docx"},
            # kreuzberg_parser NOT provided
        )
        parser = router.route("report.docx")
        # has_kreuzberg is False, so preference is skipped -> ROUTING_TABLE -> markitdown
        assert parser.name == "markitdown"


# ===================================================================
# 4. Full routing precedence chain
# ===================================================================


class TestRoutingPrecedence:
    def test_routing_precedence_order(self) -> None:
        """Verify: OCR > prefer_structured > kreuzberg_preferred > ROUTING_TABLE > default."""
        kreuzberg = make_mock_parser("kreuzberg")
        docling = make_mock_parser("docling")
        router = make_router(
            kreuzberg=kreuzberg,
            docling=docling,
            preferred={"pdf"},
        )

        # OCR wins over everything
        assert router.route("doc.pdf", ocr_needed=True).name == "docling"

        # prefer_structured wins over kreuzberg preference
        assert router.route("doc.pdf", prefer_structured=True).name == "docling"

        # kreuzberg preference wins over routing table
        assert router.route("doc.pdf").name == "kreuzberg"

        # Without kreuzberg preference, routing table wins
        router2 = make_router(kreuzberg=kreuzberg, docling=docling, preferred=set())
        assert router2.route("doc.pdf").name == "docling"

        # Unknown format falls back to default parser
        assert router2.route("doc.xyz").name == "markitdown"


# ===================================================================
# 5. maybe_shadow_parse
# ===================================================================


class TestMaybeShadowParse:
    def test_shadow_not_launched_when_no_parser(self) -> None:
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
        )
        result = maybe_shadow_parse(
            shadow_parser=None,
            shadow_formats={"pdf"},
            detected_format="pdf",
            canonical_result=canonical,
            source="test.pdf",
        )
        assert result is None

    def test_shadow_not_launched_when_no_formats(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
        )
        result = maybe_shadow_parse(
            shadow_parser=kreuzberg,
            shadow_formats=set(),
            detected_format="pdf",
            canonical_result=canonical,
            source="test.pdf",
        )
        assert result is None

    def test_shadow_not_launched_for_non_matching_format(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.html",
            source_format=DocumentFormat.HTML,
            parser_used="markitdown",
        )
        result = maybe_shadow_parse(
            shadow_parser=kreuzberg,
            shadow_formats={"pdf", "docx"},
            detected_format="html",
            canonical_result=canonical,
            source="test.html",
        )
        assert result is None

    def test_shadow_not_launched_when_canonical_is_shadow_parser(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="kreuzberg",  # canonical already used kreuzberg
        )
        result = maybe_shadow_parse(
            shadow_parser=kreuzberg,
            shadow_formats={"pdf"},
            detected_format="pdf",
            canonical_result=canonical,
            source="test.pdf",
        )
        assert result is None

    def test_shadow_launched_for_matching_format(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
        )

        async def _run() -> asyncio.Task[None] | None:
            return maybe_shadow_parse(
                shadow_parser=kreuzberg,
                shadow_formats={"pdf"},
                detected_format="pdf",
                canonical_result=canonical,
                source="test.pdf",
            )

        loop = asyncio.new_event_loop()
        try:
            task = loop.run_until_complete(_run())
            assert task is not None
            assert isinstance(task, asyncio.Task)
            # Let the task complete so it doesn't warn about pending tasks
            loop.run_until_complete(task)
        finally:
            loop.close()


# ===================================================================
# 6. run_shadow_parse
# ===================================================================


class TestRunShadowParse:
    @pytest.mark.asyncio
    async def test_shadow_parse_success_logs_comparison(self) -> None:
        shadow = make_mock_parser("kreuzberg")
        shadow.parse = AsyncMock(
            return_value=DocumentContent(
                markdown_content="# Shadow result with more content here",
                source_path="test.pdf",
                source_format=DocumentFormat.PDF,
                parser_used="kreuzberg",
            )
        )
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
            processing_time_ms=100,
        )

        with patch("src.parsers.shadow.logger") as mock_logger:
            await run_shadow_parse(
                shadow_parser=shadow,
                canonical_result=canonical,
                source="test.pdf",
                format_hint="pdf",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "Shadow parse comparison"

            extra = call_args[1]["extra"]
            assert extra["shadow_parser"] == "kreuzberg"
            assert extra["canonical_parser"] == "markitdown"
            assert extra["shadow_success"] is True
            assert extra["canonical_content_length"] == len("# Test")
            assert extra["shadow_content_length"] == len("# Shadow result with more content here")
            assert "content_length_delta" in extra
            assert "content_length_ratio" in extra
            assert "shadow_elapsed_ms" in extra
            assert "latency_delta_ms" in extra
            assert "shadow_warning_count" in extra
            assert "shadow_table_count" in extra
            assert "shadow_link_count" in extra

    @pytest.mark.asyncio
    async def test_shadow_parse_failure_logs_warning(self) -> None:
        shadow = make_mock_parser("kreuzberg")
        shadow.parse = AsyncMock(side_effect=RuntimeError("extraction failed"))
        canonical = DocumentContent(
            markdown_content="# Test",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
            processing_time_ms=50,
        )

        with patch("src.parsers.shadow.logger") as mock_logger:
            # Should not raise
            await run_shadow_parse(
                shadow_parser=shadow,
                canonical_result=canonical,
                source="test.pdf",
                format_hint="pdf",
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "Shadow parse failed"
            extra = call_args[1]["extra"]
            assert extra["shadow_success"] is False
            assert extra["shadow_parser"] == "kreuzberg"
            assert call_args[1]["exc_info"] is True


# ===================================================================
# 7. Router parse() integration with shadow
# ===================================================================


class TestParseIntegrationWithShadow:
    @pytest.mark.asyncio
    async def test_parse_triggers_shadow_when_configured(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        markitdown = make_mock_parser("markitdown")
        router = ParserRouter(
            markitdown_parser=markitdown,
            kreuzberg_parser=kreuzberg,
            kreuzberg_shadow_formats={"pdf"},
        )

        with patch("src.parsers.shadow.maybe_shadow_parse") as mock_shadow:
            mock_shadow.return_value = None  # Pretend task was created
            result = await router.parse("document.pdf")

            assert result.parser_used == "markitdown"
            mock_shadow.assert_called_once()
            call_kwargs = mock_shadow.call_args[1]
            assert call_kwargs["shadow_parser"] is kreuzberg
            assert call_kwargs["shadow_formats"] == {"pdf"}
            assert call_kwargs["detected_format"] == "pdf"

    @pytest.mark.asyncio
    async def test_parse_no_shadow_when_not_configured(self) -> None:
        kreuzberg = make_mock_parser("kreuzberg")
        markitdown = make_mock_parser("markitdown")
        router = ParserRouter(
            markitdown_parser=markitdown,
            kreuzberg_parser=kreuzberg,
            kreuzberg_shadow_formats=set(),  # empty -> no shadow
        )

        with patch("src.parsers.shadow.maybe_shadow_parse") as mock_shadow:
            await router.parse("document.pdf")
            mock_shadow.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_no_shadow_without_kreuzberg_parser(self) -> None:
        markitdown = make_mock_parser("markitdown")
        router = ParserRouter(
            markitdown_parser=markitdown,
            # No kreuzberg parser at all
            kreuzberg_shadow_formats={"pdf"},
        )

        with patch("src.parsers.shadow.maybe_shadow_parse") as mock_shadow:
            await router.parse("document.pdf")
            # _has_kreuzberg is False, so shadow branch is skipped entirely
            mock_shadow.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_shadow_receives_canonical_result(self) -> None:
        """Verify the canonical result passed to shadow matches what parse() returns."""
        kreuzberg = make_mock_parser("kreuzberg")
        markitdown = make_mock_parser("markitdown")
        expected_result = DocumentContent(
            markdown_content="# Parsed content",
            source_path="report.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
            processing_time_ms=75,
        )
        markitdown.parse = AsyncMock(return_value=expected_result)

        router = ParserRouter(
            markitdown_parser=markitdown,
            kreuzberg_parser=kreuzberg,
            kreuzberg_shadow_formats={"pdf"},
        )

        with patch("src.parsers.shadow.maybe_shadow_parse") as mock_shadow:
            mock_shadow.return_value = None
            result = await router.parse("report.pdf")

            assert result is expected_result
            call_kwargs = mock_shadow.call_args[1]
            assert call_kwargs["canonical_result"] is expected_result
