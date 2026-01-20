"""Tests for Gmail ingestion."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.gmail import GmailClient
from src.models.content import ContentSource
from src.models.newsletter import NewsletterSource, ProcessingStatus


@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service."""
    with patch("src.ingestion.gmail.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_credentials():
    """Mock OAuth credentials."""
    with patch("src.ingestion.gmail.Credentials") as mock_creds:
        mock_instance = MagicMock()
        mock_instance.valid = True
        mock_creds.from_authorized_user_file.return_value = mock_instance
        yield mock_instance


def test_gmail_client_initialization(mock_credentials, mock_gmail_service):
    """Test Gmail client initialization."""
    with patch("os.path.exists", return_value=True):
        client = GmailClient()
        assert client.service is not None


def test_extract_publication_name():
    """Test publication name extraction from sender."""
    client = GmailClient.__new__(GmailClient)

    # Test "Name <email>" format
    assert (
        client._extract_publication_name("Newsletter Name <news@example.com>") == "Newsletter Name"
    )

    # Test email only
    assert client._extract_publication_name("news@example.com") == "Example"

    # Test quoted name
    assert client._extract_publication_name('"My Newsletter" <news@example.com>') == "My Newsletter"


def test_parse_date():
    """Test email date parsing."""
    client = GmailClient.__new__(GmailClient)

    # Test valid RFC 2822 date
    date_str = "Wed, 26 Dec 2024 10:00:00 -0500"
    parsed = client._parse_date(date_str)
    assert isinstance(parsed, datetime)
    assert parsed.day == 26
    assert parsed.month == 12
    assert parsed.year == 2024

    # Test invalid date (should return current time without error)
    invalid_date = "not a valid date"
    parsed = client._parse_date(invalid_date)
    assert isinstance(parsed, datetime)


@pytest.fixture
def sample_message():
    """Sample Gmail message data."""
    return {
        "id": "test_message_id",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Newsletter"},
                {"name": "From", "value": "Test Publication <test@example.com>"},
                {"name": "Date", "value": "Wed, 26 Dec 2024 10:00:00 -0500"},
                {"name": "Message-ID", "value": "<test@example.com>"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": "VGVzdCBjb250ZW50"  # Base64 for "Test content"
                    },
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": "PHA+VGVzdCBjb250ZW50PC9wPg=="  # Base64 for "<p>Test content</p>"
                    },
                },
            ],
        },
    }


def test_fetch_and_parse_message(mock_credentials, mock_gmail_service, sample_message):
    """Test message fetching and parsing."""
    with patch("os.path.exists", return_value=True):
        # Setup mock
        mock_gmail_service.users().messages().get().execute.return_value = sample_message

        # Create client and parse
        client = GmailClient()
        newsletter_data = client._fetch_and_parse_message("test_message_id")

        # Verify
        assert newsletter_data is not None
        assert newsletter_data.source == NewsletterSource.GMAIL
        assert newsletter_data.title == "Test Newsletter"
        assert newsletter_data.publication == "Test Publication"
        assert newsletter_data.sender == "Test Publication <test@example.com>"
        assert newsletter_data.status == ProcessingStatus.PENDING
        assert newsletter_data.raw_text is not None
        assert newsletter_data.raw_html is not None


def test_extract_body():
    """Test email body extraction."""
    client = GmailClient.__new__(GmailClient)

    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": "VGVzdCB0ZXh0"},  # "Test text"
            },
            {
                "mimeType": "text/html",
                "body": {"data": "PHA+VGVzdCBIVE1MPC9wPg=="},  # "<p>Test HTML</p>"
            },
        ],
    }

    html, text = client._extract_body(payload)
    assert html is not None
    assert text is not None
    assert "Test text" in text
    assert "<p>Test HTML</p>" in html


# --- Content Model Tests (Trafilatura Integration) ---


@pytest.fixture
def sample_content_message():
    """Sample Gmail message for Content model testing."""
    return {
        "id": "content_test_id",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "AI Newsletter: Weekly Digest"},
                {"name": "From", "value": "AI Weekly <digest@aiweekly.com>"},
                {"name": "Date", "value": "Mon, 13 Jan 2025 09:00:00 -0500"},
                {"name": "Message-ID", "value": "<newsletter-123@aiweekly.com>"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "UGxhaW4gdGV4dCB2ZXJzaW9u"},  # "Plain text version"
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        # Base64 for rich HTML newsletter content
                        "data": "PGh0bWw+CjxoZWFkPjx0aXRsZT5BSSBXZWVrbHk8L3RpdGxlPjwvaGVhZD4KPGJvZHk+CjxoMT5UaGlzIFdlZWsgaW4gQUk8L2gxPgo8cD5XZWxjb21lIHRvIG91ciB3ZWVrbHkgQUkgbmV3c2xldHRlci4gSGVyZSBhcmUgdGhlIHRvcCBzdG9yaWVzOjwvcD4KPHVsPgo8bGk+TGFyZ2UgTGFuZ3VhZ2UgTW9kZWxzIGNvbnRpbnVlIHRvIGltcHJvdmU8L2xpPgo8bGk+TmV3IHJlc2VhcmNoIGluIEFJIHNhZmV0eTwvbGk+CjxsaT5JbmR1c3RyeSBhZG9wdGlvbiBhY2NlbGVyYXRlczwvbGk+CjwvdWw+CjxwPkZvciBtb3JlIGRldGFpbHMsIHZpc2l0IDxhIGhyZWY9Imh0dHBzOi8vYWl3ZWVrbHkuY29tIj5vdXIgd2Vic2l0ZTwvYT4uPC9wPgo8L2JvZHk+CjwvaHRtbD4="
                    },
                },
            ],
        },
    }


class TestGmailContentIngestion:
    """Tests for Gmail Content model ingestion with Trafilatura."""

    def test_fetch_and_parse_content_uses_trafilatura(
        self, mock_credentials, mock_gmail_service, sample_content_message
    ):
        """Test that content parsing uses Trafilatura and sets correct parser_used."""
        with patch("os.path.exists", return_value=True):
            mock_gmail_service.users().messages().get().execute.return_value = (
                sample_content_message
            )

            client = GmailClient()
            content_data = client._fetch_and_parse_content("content_test_id")

        assert content_data is not None
        assert content_data.source_type == ContentSource.GMAIL
        assert content_data.title == "AI Newsletter: Weekly Digest"
        assert content_data.publication == "AI Weekly"
        # Should use trafilatura (not markitdown)
        assert content_data.parser_used == "trafilatura"
        assert content_data.markdown_content is not None
        assert len(content_data.markdown_content) > 0

    def test_fetch_and_parse_content_metadata(
        self, mock_credentials, mock_gmail_service, sample_content_message
    ):
        """Test that content metadata is properly populated."""
        with patch("os.path.exists", return_value=True):
            mock_gmail_service.users().messages().get().execute.return_value = (
                sample_content_message
            )

            client = GmailClient()
            content_data = client._fetch_and_parse_content("content_test_id")

        assert content_data.metadata_json is not None
        assert content_data.metadata_json["gmail_message_id"] == "content_test_id"
        assert content_data.metadata_json["has_html"] is True
        assert content_data.raw_format == "html"

    def test_fetch_and_parse_content_plaintext_fallback(self, mock_credentials, mock_gmail_service):
        """Test fallback to plaintext when no HTML is available."""
        plaintext_message = {
            "id": "plaintext_test_id",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Plain Text Newsletter"},
                    {"name": "From", "value": "Simple News <simple@news.com>"},
                    {"name": "Date", "value": "Mon, 13 Jan 2025 09:00:00 -0500"},
                    {"name": "Message-ID", "value": "<plain-123@news.com>"},
                ],
                "mimeType": "text/plain",
                "body": {
                    # Base64 for "This is a plain text newsletter with enough content to be valid."
                    "data": "VGhpcyBpcyBhIHBsYWluIHRleHQgbmV3c2xldHRlciB3aXRoIGVub3VnaCBjb250ZW50IHRvIGJlIHZhbGlkLg=="
                },
            },
        }

        with patch("os.path.exists", return_value=True):
            mock_gmail_service.users().messages().get().execute.return_value = plaintext_message

            client = GmailClient()
            content_data = client._fetch_and_parse_content("plaintext_test_id")

        assert content_data is not None
        assert content_data.parser_used == "plaintext"
        assert "plain text newsletter" in content_data.markdown_content.lower()


class TestGmailHtmlToMarkdown:
    """Tests for Gmail HTML-to-markdown conversion."""

    def test_html_to_markdown_uses_trafilatura(self):
        """Test that html_to_markdown function uses Trafilatura."""
        from src.ingestion.gmail import html_to_markdown

        html = """
        <html>
        <body>
        <h1>Newsletter Title</h1>
        <p>This is the newsletter content with important information about AI trends.</p>
        <ul>
        <li>Point one about machine learning</li>
        <li>Point two about neural networks</li>
        </ul>
        </body>
        </html>
        """

        result = html_to_markdown(html)

        assert result is not None
        assert len(result) > 50
        # Should contain some of the content
        assert (
            "newsletter" in result.lower() or "ai" in result.lower() or "machine" in result.lower()
        )

    def test_html_to_markdown_empty_input(self):
        """Test html_to_markdown with empty input."""
        from src.ingestion.gmail import html_to_markdown

        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""
