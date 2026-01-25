"""HTML to Markdown converter with two-tier extraction.

Provides high-quality HTML-to-markdown conversion using:
- Trafilatura (primary): Fast, academic-quality extraction (~50ms)
- Crawl4AI (fallback): JS rendering for dynamic content (~2-5s)

Usage:
    converter = HtmlMarkdownConverter()

    # From URL (RSS feeds)
    markdown = await converter.convert(url="https://example.com/article")

    # From raw HTML (Gmail)
    markdown = await converter.convert(html="<html>...</html>")

    # Batch conversion
    results = await converter.batch_convert([
        {"url": "https://example.com/1"},
        {"html": "<html>...</html>"},
    ])
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QualityValidation:
    """Result of markdown quality validation."""

    valid: bool
    issues: list[str]
    stats: dict[str, Any]


@dataclass
class ConversionResult:
    """Result of HTML to markdown conversion."""

    markdown: str | None
    method: str  # "trafilatura", "crawl4ai", or "failed"
    quality: QualityValidation | None = None
    error: str | None = None


def validate_markdown_quality(
    markdown: str | None,
    min_length: int = 200,
) -> QualityValidation:
    """Validate extracted markdown quality.

    Args:
        markdown: Markdown content to validate
        min_length: Minimum acceptable content length

    Returns:
        QualityValidation with validity status, issues, and stats
    """
    issues: list[str] = []

    if not markdown:
        return QualityValidation(
            valid=False,
            issues=["No content extracted"],
            stats={"length": 0, "has_headings": False, "has_links": False, "code_blocks": 0},
        )

    # Length check
    if len(markdown) < min_length:
        issues.append(f"Content too short: {len(markdown)} chars (min: {min_length})")

    # Structure checks
    has_headings = "#" in markdown
    has_paragraphs = "\n\n" in markdown
    has_links = "](" in markdown

    if not has_headings and not has_paragraphs:
        issues.append("No document structure detected (no headings or paragraphs)")

    # Code block integrity check
    code_block_count = markdown.count("```")
    if code_block_count % 2 != 0:
        issues.append("Unmatched code blocks")

    return QualityValidation(
        valid=len(issues) == 0,
        issues=issues,
        stats={
            "length": len(markdown),
            "has_headings": has_headings,
            "has_paragraphs": has_paragraphs,
            "has_links": has_links,
            "code_blocks": code_block_count // 2,
        },
    )


class HtmlMarkdownConverter:
    """Two-tier HTML to Markdown converter with async support.

    Primary extraction uses Trafilatura for speed and quality.
    Falls back to Crawl4AI for JavaScript-heavy content (URL-only).
    """

    def __init__(
        self,
        use_crawl4ai_fallback: bool = False,  # Disabled by default until crawl4ai is added
        min_length_threshold: int = 200,
    ) -> None:
        """Initialize converter.

        Args:
            use_crawl4ai_fallback: Enable Crawl4AI fallback for low-quality extractions
            min_length_threshold: Minimum content length before triggering fallback
        """
        self.use_fallback = use_crawl4ai_fallback
        self.min_length_threshold = min_length_threshold
        self._trafilatura_available: bool | None = None
        self._crawl4ai_available: bool | None = None

    def _check_trafilatura(self) -> bool:
        """Check if trafilatura is available."""
        if self._trafilatura_available is None:
            try:
                import trafilatura  # noqa: F401

                self._trafilatura_available = True
            except ImportError:
                self._trafilatura_available = False
                logger.warning("trafilatura not installed, falling back to basic conversion")
        return self._trafilatura_available

    def _check_crawl4ai(self) -> bool:
        """Check if crawl4ai is available."""
        if self._crawl4ai_available is None:
            try:
                import crawl4ai  # noqa: F401

                self._crawl4ai_available = True
            except ImportError:
                self._crawl4ai_available = False
                logger.debug("crawl4ai not installed, fallback disabled")
        return self._crawl4ai_available

    def _convert_with_trafilatura_sync(
        self,
        url: str | None = None,
        html: str | None = None,
    ) -> str | None:
        """Synchronous Trafilatura extraction (called via to_thread).

        Args:
            url: URL to fetch and extract
            html: Raw HTML to extract from

        Returns:
            Extracted markdown or None
        """
        if not self._check_trafilatura():
            return None

        from trafilatura import extract, fetch_url

        try:
            # Get HTML content
            if url and not html:
                downloaded = fetch_url(url)
                if not downloaded:
                    logger.warning(f"Failed to fetch URL: {url}")
                    return None
                html = downloaded

            if not html:
                return None

            # Extract with markdown output
            result = extract(
                html,
                output_format="markdown",
                include_formatting=True,
                include_links=True,
                include_tables=True,
                favor_precision=True,
                with_metadata=False,  # We handle metadata separately
            )

            # trafilatura.extract() returns str | None but is typed as Any
            return str(result) if result else None

        except Exception as e:
            logger.error(f"Trafilatura extraction failed: {e}")
            return None

    async def _convert_with_trafilatura(
        self,
        url: str | None = None,
        html: str | None = None,
    ) -> str | None:
        """Async wrapper for Trafilatura extraction.

        Args:
            url: URL to fetch and extract
            html: Raw HTML to extract from

        Returns:
            Extracted markdown or None
        """
        return await asyncio.to_thread(self._convert_with_trafilatura_sync, url, html)

    async def _convert_with_crawl4ai(self, url: str) -> str | None:
        """Crawl4AI extraction for JavaScript-heavy content.

        Note: Crawl4AI requires a URL - cannot process raw HTML.

        Args:
            url: URL to fetch and extract

        Returns:
            Extracted markdown or None
        """
        if not self._check_crawl4ai():
            return None

        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
            from crawl4ai.content_filter_strategy import PruningContentFilter
            from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

            # Configure content filtering
            content_filter = PruningContentFilter(
                threshold=0.45,
                threshold_type="dynamic",
                min_word_threshold=5,
            )

            md_generator = DefaultMarkdownGenerator(content_filter=content_filter)

            config = CrawlerRunConfig(markdown_generator=md_generator)

            browser_config = BrowserConfig(headless=True, verbose=False)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=config)

                if result.success:
                    # fit_markdown is the cleaned/filtered version (typed as Any)
                    markdown_content = result.markdown.fit_markdown
                    return str(markdown_content) if markdown_content else None

                logger.warning(f"Crawl4AI extraction failed for {url}")
                return None

        except Exception as e:
            logger.error(f"Crawl4AI extraction failed: {e}")
            return None

    def _passes_quality_check(self, markdown: str | None) -> bool:
        """Quick quality gate check.

        Args:
            markdown: Markdown content to check

        Returns:
            True if content passes quality threshold
        """
        if not markdown:
            return False
        return len(markdown) >= self.min_length_threshold

    async def convert(
        self,
        url: str | None = None,
        html: str | None = None,
        force_crawl4ai: bool = False,
    ) -> ConversionResult:
        """Convert URL or raw HTML to markdown with automatic fallback.

        Args:
            url: URL to fetch and extract (for RSS feeds)
            html: Raw HTML to extract from (for Gmail)
            force_crawl4ai: Skip Trafilatura and use Crawl4AI directly

        Returns:
            ConversionResult with markdown, method used, and quality info
        """
        if not url and not html:
            return ConversionResult(
                markdown=None,
                method="failed",
                error="Either url or html must be provided",
            )

        # Force Crawl4AI if requested (requires URL)
        if force_crawl4ai:
            if not url:
                return ConversionResult(
                    markdown=None,
                    method="failed",
                    error="Crawl4AI requires a URL, cannot use with raw HTML",
                )
            result = await self._convert_with_crawl4ai(url)
            quality = validate_markdown_quality(result, self.min_length_threshold)
            return ConversionResult(
                markdown=result,
                method="crawl4ai" if result else "failed",
                quality=quality,
            )

        # Primary: Trafilatura
        result = await self._convert_with_trafilatura(url=url, html=html)
        quality = validate_markdown_quality(result, self.min_length_threshold)

        if quality.valid:
            return ConversionResult(markdown=result, method="trafilatura", quality=quality)

        # Check if fallback is possible
        if not self.use_fallback:
            logger.debug(f"Quality check failed, fallback disabled: {quality.issues}")
            return ConversionResult(
                markdown=result,
                method="trafilatura",
                quality=quality,
            )

        # Fallback only works with URLs
        if not url:
            logger.debug("Quality check failed, but no URL for Crawl4AI fallback")
            return ConversionResult(
                markdown=result,
                method="trafilatura",
                quality=quality,
            )

        # Fallback: Crawl4AI
        logger.info(f"Trafilatura quality low ({quality.issues}), trying Crawl4AI")
        fallback_result = await self._convert_with_crawl4ai(url)
        fallback_quality = validate_markdown_quality(fallback_result, self.min_length_threshold)

        # Use fallback if it's better
        if fallback_result and (not result or len(fallback_result) > len(result)):
            return ConversionResult(
                markdown=fallback_result,
                method="crawl4ai",
                quality=fallback_quality,
            )

        # Stick with Trafilatura result
        return ConversionResult(markdown=result, method="trafilatura", quality=quality)

    async def batch_convert(
        self,
        items: list[dict[str, str]],
        max_concurrent: int = 10,
    ) -> list[dict[str, Any]]:
        """Process multiple items concurrently.

        Args:
            items: List of dicts with "url" and/or "html" keys
            max_concurrent: Maximum concurrent conversions

        Returns:
            List of results with input, markdown, success status, and error
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_one(item: dict[str, str]) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.convert(
                        url=item.get("url"),
                        html=item.get("html"),
                    )
                    return {
                        "input": item,
                        "markdown": result.markdown,
                        "method": result.method,
                        "success": result.markdown is not None,
                        "error": result.error,
                    }
                except Exception as e:
                    return {
                        "input": item,
                        "markdown": None,
                        "method": "failed",
                        "success": False,
                        "error": str(e),
                    }

        return await asyncio.gather(*[process_one(item) for item in items])


# Convenience function for simple sync usage
def convert_html_to_markdown(
    html: str | None = None,
    url: str | None = None,
) -> str:
    """Synchronous convenience function for HTML to markdown conversion.

    This is a drop-in replacement for the existing html_to_markdown function.

    Args:
        html: Raw HTML content
        url: URL to fetch (alternative to html)

    Returns:
        Markdown string (empty string on failure)
    """
    converter = HtmlMarkdownConverter()

    try:
        result = asyncio.get_event_loop().run_until_complete(converter.convert(url=url, html=html))
        return result.markdown or ""
    except RuntimeError:
        # No event loop running, create a new one
        result = asyncio.run(converter.convert(url=url, html=html))
        return result.markdown or ""
