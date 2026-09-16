"""Gmail newsletter ingest must stay headless and fail loudly."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config.sources import GmailSource
from src.ingestion.gmail import ContentData, gmail_credentials_ready
from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.result import IngestionResponse
from src.models.content import ContentSource


def test_gmail_credentials_ready_requires_token_not_client_secrets(monkeypatch, tmp_path):
    from src.config import settings as app_settings

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", None)
    monkeypatch.setattr(app_settings, "gmail_credentials_json", '{"installed":{}}')
    monkeypatch.setattr(app_settings, "gmail_token_file", str(tmp_path / "token.json"))
    monkeypatch.setattr(app_settings, "gmail_credentials_file", str(tmp_path / "credentials.json"))
    (tmp_path / "credentials.json").write_text('{"installed":{}}')

    assert gmail_credentials_ready() is False

    (tmp_path / "token.json").write_text('{"token":"x"}')
    assert gmail_credentials_ready() is True


def test_gmail_credentials_ready_accepts_env_token_json(monkeypatch, tmp_path):
    from src.config import settings as app_settings

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", '{"token":"x"}')
    monkeypatch.setattr(app_settings, "gmail_token_file", str(tmp_path / "missing-token.json"))
    monkeypatch.setattr(
        app_settings, "gmail_credentials_file", str(tmp_path / "missing-creds.json")
    )

    assert gmail_credentials_ready() is True


def test_gmail_authenticate_does_not_start_browser_oauth(monkeypatch, tmp_path):
    from src.config import settings as app_settings
    from src.ingestion.gmail import GmailClient

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", None)
    monkeypatch.setattr(app_settings, "gmail_credentials_json", None)
    monkeypatch.setattr(app_settings, "gmail_token_file", str(tmp_path / "token.json"))
    monkeypatch.setattr(app_settings, "gmail_credentials_file", str(tmp_path / "credentials.json"))
    (tmp_path / "credentials.json").write_text('{"installed":{"client_id":"x"}}')

    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow:
        with pytest.raises(FileNotFoundError, match="aca auth gmail"):
            GmailClient()
        mock_flow.from_client_secrets_file.assert_not_called()
        mock_flow.return_value.run_local_server.assert_not_called()


@patch("src.ingestion.gmail.get_db")
@patch("src.ingestion.gmail.GmailClient")
def test_gmail_persist_error_is_counted_as_items_failed(mock_client_cls, mock_db):
    from src.ingestion.gmail import GmailContentIngestionService

    mock_client_cls.return_value.fetch_content.return_value = [
        ContentData(
            source_type=ContentSource.GMAIL,
            source_id="msg-1",
            title="Weekly AI",
            markdown_content="# Hello",
            content_hash="hash-1",
        ),
        ContentData(
            source_type=ContentSource.GMAIL,
            source_id="msg-2",
            title="Keep me",
            markdown_content="# Keep",
            content_hash="hash-2",
        ),
    ]
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.add.side_effect = [RuntimeError("flush failed"), None]
    mock_db.return_value.__enter__.return_value = session
    mock_db.return_value.__exit__.return_value = False

    result = GmailContentIngestionService().ingest_content(query="label:newsletters-ai")

    assert isinstance(result, IngestionResponse)
    assert result.command == "ingest.gmail"
    assert result.items_failed >= 1
    assert result.status in {"partial", "error"}
    assert any(err.code == "persistence_error" for err in result.errors)


def test_gmail_descriptor_is_not_ready_without_token(monkeypatch, tmp_path):
    from src.config import settings as app_settings

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", None)
    monkeypatch.setattr(app_settings, "gmail_credentials_json", None)
    monkeypatch.setattr(app_settings, "gmail_token_file", str(tmp_path / "token.json"))
    monkeypatch.setattr(app_settings, "gmail_credentials_file", str(tmp_path / "credentials.json"))

    readiness = SOURCE_REGISTRY.get("gmail").resolve_readiness(GmailSource())
    assert readiness.ready is False
    assert readiness.code == "oauth_unavailable"
