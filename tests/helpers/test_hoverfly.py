"""Unit tests for HoverflyClient helper.

These tests mock httpx to verify the client's API interaction logic
without requiring a running Hoverfly instance.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.hoverfly import HoverflyClient


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.Client for unit testing HoverflyClient."""
    with patch("tests.helpers.hoverfly.httpx.Client") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_httpx_client):
    """Create HoverflyClient with mocked HTTP."""
    return HoverflyClient(
        admin_url="http://localhost:8888",
        proxy_url="http://localhost:8500",
    )


class TestHoverflyClientHealth:
    def test_is_healthy_returns_true(self, client, mock_httpx_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx_client.get.return_value = mock_resp

        assert client.is_healthy() is True
        mock_httpx_client.get.assert_called_once_with("http://localhost:8888/api/v2/hoverfly")

    def test_is_healthy_returns_false_on_connection_error(self, client, mock_httpx_client):
        import httpx

        mock_httpx_client.get.side_effect = httpx.ConnectError("refused")

        assert client.is_healthy() is False


class TestHoverflyClientMode:
    def test_get_mode(self, client, mock_httpx_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"mode": "simulate"}
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_resp

        assert client.get_mode() == "simulate"

    def test_set_mode(self, client, mock_httpx_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.put.return_value = mock_resp

        client.set_mode("capture")
        mock_httpx_client.put.assert_called_once_with(
            "http://localhost:8888/api/v2/hoverfly/mode",
            json={"mode": "capture"},
        )


class TestHoverflyClientSimulation:
    def test_import_simulation(self, client, mock_httpx_client, tmp_path):
        sim_data = {
            "data": {"pairs": [{"request": {}, "response": {}}]},
            "meta": {"schemaVersion": "v5"},
        }
        sim_file = tmp_path / "test.json"
        sim_file.write_text(json.dumps(sim_data))

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.put.return_value = mock_resp

        count = client.import_simulation(sim_file)

        assert count == 1
        mock_httpx_client.put.assert_called_once()

    def test_import_simulation_file_not_found(self, client):
        with pytest.raises(FileNotFoundError, match="Simulation file not found"):
            client.import_simulation("/nonexistent/file.json")

    def test_append_simulation(self, client, mock_httpx_client, tmp_path):
        sim_data = {
            "data": {"pairs": [{"request": {}, "response": {}}]},
            "meta": {"schemaVersion": "v5"},
        }
        sim_file = tmp_path / "test.json"
        sim_file.write_text(json.dumps(sim_data))

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_resp

        count = client.append_simulation(sim_file)

        assert count == 1
        # append uses POST, not PUT
        mock_httpx_client.post.assert_called_once()

    def test_export_simulation(self, client, mock_httpx_client):
        expected = {"data": {"pairs": []}, "meta": {"schemaVersion": "v5"}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_resp

        result = client.export_simulation()

        assert result == expected

    def test_reset_simulation(self, client, mock_httpx_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.delete.return_value = mock_resp

        client.reset_simulation()

        mock_httpx_client.delete.assert_called_once_with("http://localhost:8888/api/v2/simulation")

    def test_get_simulation_pair_count(self, client, mock_httpx_client):
        sim = {"data": {"pairs": [{}, {}, {}]}, "meta": {}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = sim
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_resp

        assert client.get_simulation_pair_count() == 3


class TestHoverflyClientInit:
    def test_strips_trailing_slash(self, mock_httpx_client):
        c = HoverflyClient(
            admin_url="http://localhost:8888/",
            proxy_url="http://localhost:8500/",
        )
        assert c.admin_url == "http://localhost:8888"
        assert c.proxy_url == "http://localhost:8500"

    def test_default_urls(self, mock_httpx_client):
        c = HoverflyClient()
        assert c.admin_url == "http://localhost:8888"
        assert c.proxy_url == "http://localhost:8500"
