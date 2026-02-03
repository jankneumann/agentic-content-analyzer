import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.url_extractor import URLExtractor
from src.utils.security import validate_url


@pytest.mark.asyncio
async def test_validate_url_public_ip():
    """Test that public IPs are allowed."""
    # Mock getaddrinfo to return a public IP
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))
        ])

        # Should not raise exception
        await validate_url("http://google.com")

@pytest.mark.asyncio
async def test_validate_url_private_ip():
    """Test that private IPs are blocked."""
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80))
        ])

        with pytest.raises(ValueError, match="Access to private resource blocked"):
            await validate_url("http://internal.server")

@pytest.mark.asyncio
async def test_validate_url_localhost():
    """Test that localhost is blocked."""
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ])

        with pytest.raises(ValueError, match="Access to private resource blocked"):
            await validate_url("http://localhost")

@pytest.mark.asyncio
async def test_validate_url_aws_metadata():
    """Test that AWS metadata IP is blocked."""
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))
        ])

        with pytest.raises(ValueError, match="Access to private resource blocked"):
            await validate_url("http://169.254.169.254/latest/meta-data/")

@pytest.mark.asyncio
async def test_validate_url_direct_ip_private():
    """Test that direct private IP usage is blocked (no DNS needed)."""
    # Accept either message, as long as it blocks
    with pytest.raises(ValueError, match="blocked"):
        await validate_url("http://192.168.1.50/admin")

@pytest.mark.asyncio
async def test_url_extractor_uses_validation():
    """Test that URLExtractor calls validate_url."""
    mock_db = MagicMock()
    extractor = URLExtractor(mock_db)

    # Mock validate_url to raise ValueError
    with patch("src.services.url_extractor.validate_url", side_effect=ValueError("Blocked!")) as mock_validate:
        with pytest.raises(ValueError, match="Blocked!"):
            await extractor._fetch_url("http://evil.com")

        mock_validate.assert_called_once_with("http://evil.com")
