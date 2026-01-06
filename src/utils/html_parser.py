"""HTML parsing utilities."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.utils.logging import get_logger

logger = get_logger(__name__)


def html_to_text(html: str) -> str:
    """
    Convert HTML to plain text.

    Args:
        html: HTML string

    Returns:
        Plain text with basic formatting preserved
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "lxml")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text

    except Exception as e:
        logger.error(f"Error converting HTML to text: {e}")
        return ""


def extract_links(html: str, base_url: str | None = None) -> list[str]:
    """
    Extract all links from HTML.

    Args:
        html: HTML string
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute URLs
    """
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
        links = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]

            # Skip mailto, javascript, and anchor links
            if href.startswith(("mailto:", "javascript:", "#")):
                continue

            # Resolve relative URLs if base_url provided
            if base_url and not bool(urlparse(href).netloc):
                href = urljoin(base_url, href)

            # Only include http/https links
            if href.startswith(("http://", "https://")):
                links.append(href)

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        return unique_links

    except Exception as e:
        logger.error(f"Error extracting links: {e}")
        return []


def clean_html(html: str, preserve_links: bool = True) -> str:
    """
    Clean and sanitize HTML.

    Args:
        html: HTML string
        preserve_links: Whether to preserve links

    Returns:
        Cleaned HTML
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted tags
        for tag in soup(["script", "style", "iframe", "embed", "object"]):
            tag.decompose()

        # Remove tracking pixels (1x1 images)
        for img in soup.find_all("img"):
            width = img.get("width", "")
            height = img.get("height", "")
            if width == "1" and height == "1":
                img.decompose()

        # If not preserving links, remove them but keep text
        if not preserve_links:
            for anchor in soup.find_all("a"):
                anchor.unwrap()

        return str(soup)

    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return html


def extract_article_content(html: str) -> str | None:
    """
    Attempt to extract main article content from HTML.

    This is a simple heuristic-based approach. For better results,
    consider using libraries like readability-lxml or newspaper3k.

    Args:
        html: HTML string

    Returns:
        Extracted article HTML or None
    """
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "lxml")

        # Try common article container selectors
        selectors = [
            "article",
            '[role="article"]',
            ".article-content",
            ".post-content",
            ".entry-content",
            "#content",
            "main",
        ]

        for selector in selectors:
            article = soup.select_one(selector)
            if article:
                return str(article)

        # Fallback: find the div with most paragraph tags
        divs = soup.find_all("div")
        if divs:
            best_div = max(divs, key=lambda d: len(d.find_all("p")))
            if len(best_div.find_all("p")) > 2:
                return str(best_div)

        return None

    except Exception as e:
        logger.error(f"Error extracting article content: {e}")
        return None


def remove_tracking_params(url: str) -> str:
    """
    Remove common tracking parameters from URL.

    Args:
        url: URL string

    Returns:
        URL with tracking params removed
    """
    if not url:
        return url

    # Common tracking parameters
    tracking_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }

    try:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Remove tracking params
        cleaned_params = {k: v for k, v in query_params.items() if k not in tracking_params}

        # Rebuild query string
        new_query = urlencode(cleaned_params, doseq=True)

        # Rebuild URL
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )

    except Exception as e:
        logger.error(f"Error removing tracking params: {e}")
        return url
