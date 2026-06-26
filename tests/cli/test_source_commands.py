"""Tests for `aca sources` CLI commands.

Covers both modes without a live Postgres:
- HTTP mode: mock ``get_api_client`` and assert the right ApiClient method
  is called and output rendered.
- Direct mode (--direct): mock the SourceOverrideService / load_sources_config
  so no real database is required.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_db():
    """Mock the DB session context manager (patched at the source module)."""
    mock_session = MagicMock()

    @contextmanager
    def mock_get_db():
        yield mock_session

    with patch("src.storage.database.get_db", mock_get_db):
        yield mock_session


def _http_error(status_code: int, detail: str = "boom") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://test/api/v1/sources")
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


# ---------------------------------------------------------------------------
# HTTP mode
# ---------------------------------------------------------------------------


class TestListHttp:
    def test_list_renders_rows(self):
        client = MagicMock()
        client.list_sources.return_value = {
            "sources": [
                {
                    "type": "blog",
                    "name": "Normal Tech",
                    "url": "https://www.normaltech.ai/",
                    "enabled": True,
                    "tags": [],
                    "origin": "db",
                    "source_key": "blog:https://www.normaltech.ai/",
                }
            ],
            "counts": {},
            "total_sources": 1,
            "enabled_sources": 1,
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "list"])
        assert result.exit_code == 0
        assert "blog:https://www.normaltech.ai/" in result.output
        assert "blog" in result.output
        client.list_sources.assert_called_once_with()

    def test_list_filter_by_type(self):
        client = MagicMock()
        client.list_sources.return_value = {
            "sources": [
                {"type": "blog", "source_key": "blog:x", "enabled": True, "origin": "yaml"},
                {"type": "rss", "source_key": "rss:y", "enabled": True, "origin": "yaml"},
            ],
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "list", "--type", "blog"])
        assert result.exit_code == 0
        assert "blog:x" in result.output
        assert "rss:y" not in result.output
        client.list_sources.assert_called_once_with(source_type="blog")

    def test_list_json(self):
        client = MagicMock()
        payload = {"sources": [], "counts": {}, "total_sources": 0, "enabled_sources": 0}
        client.list_sources.return_value = payload
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["--json", "sources", "list"])
        assert result.exit_code == 0
        assert '"total_sources": 0' in result.output


class TestAddHttp:
    def test_add_builds_config_and_posts(self):
        client = MagicMock()
        client.add_source.return_value = {
            "source_key": "blog:https://www.normaltech.ai/",
            "version": 1,
            "origin": "db",
            "enabled": True,
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(
                app,
                [
                    "sources",
                    "add",
                    "blog",
                    "--url",
                    "https://www.normaltech.ai/",
                    "--name",
                    "Normal Tech",
                    "--tag",
                    "ai",
                    "--tag",
                    "infra",
                ],
            )
        assert result.exit_code == 0
        assert "blog:https://www.normaltech.ai/" in result.output
        client.add_source.assert_called_once()
        config = client.add_source.call_args.args[0]
        assert config["type"] == "blog"
        assert config["url"] == "https://www.normaltech.ai/"
        assert config["name"] == "Normal Tech"
        assert config["tags"] == ["ai", "infra"]

    def test_add_set_escape_hatch_and_json_blob(self):
        client = MagicMock()
        client.add_source.return_value = {
            "source_key": "blog:https://x/",
            "version": 1,
            "origin": "db",
            "enabled": True,
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(
                app,
                [
                    "sources",
                    "add",
                    "blog",
                    "--json",
                    '{"url": "https://x/", "request_delay": 2.0}',
                    "--set",
                    "max_entries=5",
                ],
            )
        assert result.exit_code == 0
        config = client.add_source.call_args.args[0]
        assert config["url"] == "https://x/"
        assert config["request_delay"] == 2.0
        assert config["max_entries"] == 5
        assert config["type"] == "blog"

    def test_add_validation_error_exits_nonzero(self):
        client = MagicMock()
        client.add_source.side_effect = _http_error(400, "invalid source config: url required")
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "add", "blog", "--name", "no-url"])
        assert result.exit_code == 1
        assert "invalid source config" in result.output

    def test_add_bad_json_blob(self):
        client = MagicMock()
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "add", "blog", "--json", "{not json"])
        assert result.exit_code != 0
        client.add_source.assert_not_called()


class TestRemoveHttp:
    def test_remove_calls_delete(self):
        client = MagicMock()
        client.remove_source.return_value = {"source_key": "blog:x", "deleted": True}
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "remove", "blog:x"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        client.remove_source.assert_called_once_with("blog:x")

    def test_remove_not_found(self):
        client = MagicMock()
        client.remove_source.side_effect = _http_error(404, "not found")
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "remove", "blog:missing"])
        assert result.exit_code == 1
        assert "No source override found" in result.output


class TestEnableDisableHttp:
    def test_enable(self):
        client = MagicMock()
        client.set_source_enabled.return_value = {
            "source_key": "blog:x",
            "version": 2,
            "origin": "db",
            "enabled": True,
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "enable", "blog:x"])
        assert result.exit_code == 0
        client.set_source_enabled.assert_called_once_with("blog:x", True)
        assert "enabled=True" in result.output

    def test_disable(self):
        client = MagicMock()
        client.set_source_enabled.return_value = {
            "source_key": "blog:x",
            "version": 2,
            "origin": "db",
            "enabled": False,
        }
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "disable", "blog:x"])
        assert result.exit_code == 0
        client.set_source_enabled.assert_called_once_with("blog:x", False)
        assert "enabled=False" in result.output

    def test_enable_not_found(self):
        client = MagicMock()
        client.set_source_enabled.side_effect = _http_error(404, "nope")
        with patch("src.cli.api_client.get_api_client", return_value=client):
            result = runner.invoke(app, ["sources", "enable", "blog:missing"])
        assert result.exit_code == 1
        assert "No source found" in result.output


# ---------------------------------------------------------------------------
# Direct mode (--direct, no live DB)
# ---------------------------------------------------------------------------


def _fake_source(stype="blog", name="Normal Tech", enabled=True, origin="yaml", key="blog:x"):
    src = MagicMock()
    src.type = stype
    src.name = name
    src.enabled = enabled
    src.origin = origin
    src.model_dump.return_value = {
        "type": stype,
        "name": name,
        "enabled": enabled,
        "origin": origin,
        "url": "https://x/",
    }
    return src, key


class TestDirectMode:
    def test_list_direct(self):
        src, key = _fake_source()
        config = MagicMock()
        config.sources = [src]
        with (
            patch("src.config.sources.load_sources_config", return_value=config),
            patch("src.config.sources.source_key", return_value=key),
        ):
            result = runner.invoke(app, ["--direct", "sources", "list"])
        assert result.exit_code == 0
        assert key in result.output

    def test_add_direct(self):
        row = MagicMock()
        row.source_key = "blog:https://x/"
        row.version = 1
        row.enabled = True
        with patch(
            "src.services.source_override_service.SourceOverrideService.upsert", return_value=row
        ) as mock_upsert:
            result = runner.invoke(
                app, ["--direct", "sources", "add", "blog", "--url", "https://x/"]
            )
        assert result.exit_code == 0
        assert "blog:https://x/" in result.output
        mock_upsert.assert_called_once()

    def test_add_direct_validation_error(self):
        from src.services.source_override_service import SourceOverrideError

        with patch(
            "src.services.source_override_service.SourceOverrideService.upsert",
            side_effect=SourceOverrideError("invalid source config: boom"),
        ):
            result = runner.invoke(app, ["--direct", "sources", "add", "blog", "--name", "x"])
        assert result.exit_code == 1
        assert "invalid source config" in result.output

    def test_remove_direct(self):
        with patch(
            "src.services.source_override_service.SourceOverrideService.delete", return_value=True
        ):
            result = runner.invoke(app, ["--direct", "sources", "remove", "blog:x"])
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_direct_not_found(self):
        with patch(
            "src.services.source_override_service.SourceOverrideService.delete", return_value=False
        ):
            result = runner.invoke(app, ["--direct", "sources", "remove", "blog:missing"])
        assert result.exit_code == 1
        assert "No source override found" in result.output

    def test_disable_direct_yaml_source_resolves_fallback(self):
        src, key = _fake_source()
        config = MagicMock()
        config.sources = [src]
        row = MagicMock()
        row.source_key = key
        row.version = 1
        row.enabled = False
        with (
            patch("src.config.sources.load_sources_config", return_value=config),
            patch("src.config.sources.source_key", return_value=key),
            patch(
                "src.services.source_override_service.SourceOverrideService.get",
                return_value=None,
            ),
            patch(
                "src.services.source_override_service.SourceOverrideService.set_enabled",
                return_value=row,
            ) as mock_set,
        ):
            result = runner.invoke(app, ["--direct", "sources", "disable", key])
        assert result.exit_code == 0
        # fallback_config must be supplied for a YAML source with no row
        assert mock_set.call_args.kwargs["fallback_config"] is not None
        assert mock_set.call_args.kwargs["fallback_config"]["type"] == "blog"
