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


_EXPIRED_TOKEN = (
    '{"token":"ya29.old","refresh_token":"1//r","client_id":"c","client_secret":"s",'
    '"expiry":"2020-01-01T00:00:00Z"}'
)


def _unwritable(tmp_path):
    # A path under a regular file can never be opened for writing, as root or not:
    # the same OSError a read-only container root raises.
    (tmp_path / "file").write_text("")
    return str(tmp_path / "file" / "token.json")


def test_a_rejected_refresh_token_is_a_typed_session_expired(monkeypatch, tmp_path):
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials

    from src.config import settings as app_settings
    from src.ingestion.credential_failures import SessionExpiredError
    from src.ingestion.gmail import GmailClient

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", _EXPIRED_TOKEN)
    monkeypatch.setattr(app_settings, "gmail_credentials_json", None)
    monkeypatch.setattr(app_settings, "gmail_token_file", str(tmp_path / "token.json"))

    with patch.object(Credentials, "refresh", side_effect=RefreshError("invalid_grant")):
        with pytest.raises(SessionExpiredError) as caught:
            GmailClient()

    assert caught.value.code == "session_expired"
    assert "aca auth gmail" in str(caught.value)
    assert "1//r" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_a_read_only_token_path_still_authenticates(monkeypatch, tmp_path):
    from google.oauth2.credentials import Credentials

    from src.config import settings as app_settings
    from src.ingestion.gmail import GmailClient

    monkeypatch.setattr(app_settings, "gmail_oauth_token_json", _EXPIRED_TOKEN)
    monkeypatch.setattr(app_settings, "gmail_credentials_json", None)
    monkeypatch.setattr(app_settings, "gmail_token_file", _unwritable(tmp_path))

    def refreshed(self, request):
        self.token = "ya29.new"
        self.expiry = None

    with (
        patch.object(Credentials, "refresh", refreshed),
        patch("src.ingestion.gmail.build") as build,
    ):
        client = GmailClient()

    assert client.service is build.return_value
    assert build.call_args.kwargs["credentials"].token == "ya29.new"


def test_orchestrator_reports_session_expired_not_a_crash(monkeypatch):
    from src.ingestion.credential_failures import SessionExpiredError
    from src.ingestion.orchestrator import ingest_gmail

    expired = SessionExpiredError(
        source="gmail", credential_label="OAuth refresh token", refresh_command="aca auth gmail"
    )
    with patch("src.ingestion.gmail.GmailContentIngestionService", side_effect=expired):
        response = ingest_gmail(query="label:x", max_results=1)

    assert response.status == "error"
    assert [error.code for error in response.errors] == ["session_expired"]
