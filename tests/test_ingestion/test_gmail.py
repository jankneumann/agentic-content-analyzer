"""Tests for Gmail ingestion."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.gmail import GmailClient
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
