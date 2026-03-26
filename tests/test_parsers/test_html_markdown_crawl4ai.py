"""Tests for Crawl4AI integration in HtmlMarkdownConverter.

Tests cover:
- Settings injection via __init__
- CacheMode string-to-enum mapping
- Remote server mode (mocked HTTP)
- Remote mode error handling (connection refused, timeout, 500)
- Local vs remote dispatch logic
- Excluded tags and page_timeout propagation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.parsers.html_markdown import (
    HtmlMarkdownConverter,
    _build_cache_mode_map,
)


@pytest.fixture
def mock_settings():
    """Create a mock Settings object with Crawl4AI defaults."""
    settings = MagicMock()
    settings.crawl4ai_enabled = False
    settings.crawl4ai_cache_mode = "bypass"
    settings.crawl4ai_server_url = None
    settings.crawl4ai_page_timeout = 30000
    settings.crawl4ai_excluded_tags = ["nav", "footer", "header"]
    return settings


@pytest.fixture
def mock_get_settings(mock_settings):
    """Patch get_settings to return our mock."""
    with patch("src.config.settings.get_settings", return_value=mock_settings) as m:
        yield m


class TestSettingsIntegration:
    """Test that converter reads configuration from Settings."""

    def test_defaults_from_settings(self, mock_get_settings, mock_settings):
        """Converter uses settings values when no constructor kwargs passed."""
        mock_settings.crawl4ai_enabled = True
        mock_settings.crawl4ai_server_url = "http://localhost:11235"
        mock_settings.crawl4ai_cache_mode = "enabled"
        mock_settings.crawl4ai_page_timeout = 60000
        mock_settings.crawl4ai_excluded_tags = ["aside"]

        converter = HtmlMarkdownConverter()

        assert converter.use_fallback is True
        assert converter.server_url == "http://localhost:11235"
        assert converter._cache_mode_str == "enabled"
        assert converter.page_timeout == 60000
        assert converter.excluded_tags == ["aside"]

    def test_constructor_overrides_settings(self, mock_get_settings, mock_settings):
        """Constructor kwargs take precedence over settings."""
        mock_settings.crawl4ai_enabled = True
        mock_settings.crawl4ai_server_url = "http://remote:11235"

        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=False,
            server_url="http://local:11235",
            cache_mode="disabled",
            page_timeout=5000,
            excluded_tags=["div"],
        )

        assert converter.use_fallback is False
        assert converter.server_url == "http://local:11235"
        assert converter._cache_mode_str == "disabled"
        assert converter.page_timeout == 5000
        assert converter.excluded_tags == ["div"]

    def test_none_sentinels_use_settings(self, mock_get_settings, mock_settings):
        """Passing None (default) uses settings values."""
        mock_settings.crawl4ai_enabled = True

        converter = HtmlMarkdownConverter(use_crawl4ai_fallback=None)

        assert converter.use_fallback is True

    def test_disabled_by_default(self, mock_get_settings):
        """Default settings have Crawl4AI disabled."""
        converter = HtmlMarkdownConverter()

        assert converter.use_fallback is False
        assert converter.server_url is None


class TestCacheModeMapping:
    """Test CacheMode string to enum mapping."""

    def test_build_cache_mode_map_without_crawl4ai(self):
        """Returns empty dict when crawl4ai is not installed."""
        with patch.dict("sys.modules", {"crawl4ai": None}):
            result = _build_cache_mode_map()
            assert result == {}

    def test_build_cache_mode_map_with_crawl4ai(self):
        """Returns full mapping when crawl4ai is available."""
        mock_cache_mode = MagicMock()
        mock_cache_mode.BYPASS = "BYPASS"
        mock_cache_mode.ENABLED = "ENABLED"
        mock_cache_mode.DISABLED = "DISABLED"
        mock_cache_mode.READ_ONLY = "READ_ONLY"
        mock_cache_mode.WRITE_ONLY = "WRITE_ONLY"

        mock_module = MagicMock()
        mock_module.CacheMode = mock_cache_mode

        with patch.dict("sys.modules", {"crawl4ai": mock_module}):
            result = _build_cache_mode_map()
            assert set(result.keys()) == {
                "bypass",
                "enabled",
                "disabled",
                "read_only",
                "write_only",
            }

    def test_invalid_cache_mode_raises(self, mock_get_settings):
        """Invalid cache mode string raises ValueError."""
        converter = HtmlMarkdownConverter(cache_mode="invalid_mode")

        # Mock CACHE_MODE_MAP to have entries so validation triggers
        with patch(
            "src.parsers.html_markdown.CACHE_MODE_MAP",
            {"bypass": "BYPASS", "enabled": "ENABLED"},
        ):
            with pytest.raises(ValueError, match="Invalid crawl4ai_cache_mode 'invalid_mode'"):
                converter._resolve_cache_mode()

    def test_valid_cache_mode_resolves(self, mock_get_settings):
        """Valid cache mode string resolves to enum value."""
        converter = HtmlMarkdownConverter(cache_mode="bypass")

        with patch(
            "src.parsers.html_markdown.CACHE_MODE_MAP",
            {"bypass": "BYPASS_ENUM"},
        ):
            result = converter._resolve_cache_mode()
            assert result == "BYPASS_ENUM"


class TestRemoteMode:
    """Test remote Crawl4AI server extraction via HTTP."""

    @pytest.mark.asyncio
    async def test_remote_extraction_success(self, mock_get_settings):
        """Successful remote extraction via POST /md."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"markdown": "# Extracted Content\n\nSome markdown text."}
        }

        with patch("src.parsers.html_markdown.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await converter._convert_with_crawl4ai_remote("https://example.com")

        assert result == "# Extracted Content\n\nSome markdown text."
        mock_client.post.assert_called_once_with(
            "http://localhost:11235/md",
            json={"url": "https://example.com", "c": "bypass"},
            headers={"Content-Type": "application/json"},
        )

    @pytest.mark.asyncio
    async def test_remote_extraction_server_error(self, mock_get_settings):
        """HTTP 500 from remote server returns None (fail-safe)."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("src.parsers.html_markdown.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await converter._convert_with_crawl4ai_remote("https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_remote_extraction_connection_refused(self, mock_get_settings):
        """Connection refused returns None (fail-safe)."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        with patch("src.parsers.html_markdown.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await converter._convert_with_crawl4ai_remote("https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_remote_extraction_timeout(self, mock_get_settings):
        """Timeout returns None (fail-safe)."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        with patch("src.parsers.html_markdown.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await converter._convert_with_crawl4ai_remote("https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_remote_extraction_empty_result(self, mock_get_settings):
        """Empty markdown in response returns None."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"markdown": None}}

        with patch("src.parsers.html_markdown.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await converter._convert_with_crawl4ai_remote("https://example.com")

        assert result is None


class TestDispatchLogic:
    """Test local vs remote dispatch in _convert_with_crawl4ai."""

    @pytest.mark.asyncio
    async def test_dispatches_to_remote_when_server_url_set(self, mock_get_settings):
        """With server_url configured, dispatches to remote mode."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url="http://localhost:11235",
        )

        with patch.object(
            converter, "_convert_with_crawl4ai_remote", new_callable=AsyncMock
        ) as mock_remote:
            mock_remote.return_value = "# Remote Content"
            result = await converter._convert_with_crawl4ai("https://example.com")

        assert result == "# Remote Content"
        mock_remote.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_dispatches_to_local_when_no_server_url(self, mock_get_settings):
        """Without server_url, dispatches to local mode."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            server_url=None,
        )

        with patch.object(
            converter, "_convert_with_crawl4ai_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.return_value = "# Local Content"
            result = await converter._convert_with_crawl4ai("https://example.com")

        assert result == "# Local Content"
        mock_local.assert_called_once_with("https://example.com")


class TestFallbackChain:
    """Test the full conversion flow with Crawl4AI fallback."""

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self, mock_get_settings):
        """With crawl4ai_enabled=False, only Trafilatura is used."""
        converter = HtmlMarkdownConverter(use_crawl4ai_fallback=False)

        # Short content that fails quality check
        with patch.object(
            converter, "_convert_with_trafilatura", new_callable=AsyncMock
        ) as mock_traf:
            mock_traf.return_value = "Short"
            result = await converter.convert(url="https://example.com")

        assert result.method == "trafilatura"
        assert result.markdown == "Short"

    @pytest.mark.asyncio
    async def test_fallback_triggered_on_low_quality(self, mock_get_settings):
        """With fallback enabled, Crawl4AI is tried when Trafilatura quality is low."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            min_length_threshold=200,
        )

        long_content = "# Good Content\n\n" + "x" * 300

        with (
            patch.object(
                converter, "_convert_with_trafilatura", new_callable=AsyncMock
            ) as mock_traf,
            patch.object(
                converter, "_convert_with_crawl4ai", new_callable=AsyncMock
            ) as mock_crawl4ai,
        ):
            mock_traf.return_value = "Short"  # Below threshold
            mock_crawl4ai.return_value = long_content

            result = await converter.convert(url="https://example.com")

        assert result.method == "crawl4ai"
        assert result.markdown == long_content

    @pytest.mark.asyncio
    async def test_trafilatura_success_skips_fallback(self, mock_get_settings):
        """Good Trafilatura result doesn't trigger Crawl4AI."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            min_length_threshold=50,
        )

        good_content = "# Great Article\n\n" + "This is good content. " * 20

        with (
            patch.object(
                converter, "_convert_with_trafilatura", new_callable=AsyncMock
            ) as mock_traf,
            patch.object(
                converter, "_convert_with_crawl4ai", new_callable=AsyncMock
            ) as mock_crawl4ai,
        ):
            mock_traf.return_value = good_content

            result = await converter.convert(url="https://example.com")

        assert result.method == "trafilatura"
        mock_crawl4ai.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_failure_returns_trafilatura_result(self, mock_get_settings):
        """When both fail, short Trafilatura result is returned."""
        converter = HtmlMarkdownConverter(
            use_crawl4ai_fallback=True,
            min_length_threshold=200,
        )

        with (
            patch.object(
                converter, "_convert_with_trafilatura", new_callable=AsyncMock
            ) as mock_traf,
            patch.object(
                converter, "_convert_with_crawl4ai", new_callable=AsyncMock
            ) as mock_crawl4ai,
        ):
            mock_traf.return_value = "Short but something"
            mock_crawl4ai.return_value = None  # Crawl4AI also fails

            result = await converter.convert(url="https://example.com")

        assert result.method == "trafilatura"
        assert result.markdown == "Short but something"
