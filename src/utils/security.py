"""Security utilities for the application."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from src.utils.logging import get_logger

logger = get_logger(__name__)


async def validate_url(url: str) -> None:
    """
    Validate that a URL does not point to a private, loopback, or link-local address.

    This helps prevent Server-Side Request Forgery (SSRF) attacks where an attacker
    causes the server to access internal resources.

    Args:
        url: The URL to validate.

    Raises:
        ValueError: If the URL is invalid or points to a restricted IP.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError(f"Invalid URL: {url}")

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            # If it's already an IP, check it directly
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"Access to private IP address blocked: {hostname}")
            if ip.is_multicast or ip.is_reserved:
                raise ValueError(f"Access to restricted IP address blocked: {hostname}")
            return
        except ValueError:
            # Not an IP address, proceed to DNS resolution
            pass

        # Resolve hostname to IP
        # NOTE: This is susceptible to DNS rebinding attacks where the DNS record
        # changes between this check and the actual fetch. A more robust solution
        # would require a custom transport adapter that connects to the resolved IP.
        try:
            loop = asyncio.get_running_loop()
            # Use getaddrinfo to resolve
            addr_info = await loop.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except RuntimeError:
            # Fallback if no running loop (e.g. in synch context or tests sometimes)
            # though this function is async, so it should have a loop.
            # But getaddrinfo is blocking if not run in executor,
            # asyncio.getaddrinfo runs in default executor.
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise ValueError(f"Could not resolve hostname: {hostname}") from e

        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)

            if ip.is_private or ip.is_loopback or ip.is_link_local:
                logger.warning(f"Blocked SSRF attempt to private IP: {ip_str} ({hostname})")
                raise ValueError(f"Access to private resource blocked: {hostname} ({ip_str})")

            if ip.is_multicast or ip.is_reserved:
                logger.warning(f"Blocked SSRF attempt to restricted IP: {ip_str} ({hostname})")
                raise ValueError(f"Access to restricted resource blocked: {hostname} ({ip_str})")

    except ValueError as e:
        raise e
    except Exception as e:
        logger.error(f"Error validating URL {url}: {e}")
        raise ValueError(f"Error validating URL: {e}")
