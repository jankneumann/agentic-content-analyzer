"""API tests for connection status endpoints."""

from unittest.mock import AsyncMock, patch

from src.services.connection_checker import ConnectionCheckResult, ServiceStatus


class TestGetConnectionStatus:
    """Test GET /api/v1/settings/connections."""

    def test_returns_services(self, client):
        """Mock all checks to ensure endpoint returns structured response."""
        mock_result = ConnectionCheckResult(
            services=[
                ServiceStatus(
                    name="PostgreSQL", status="ok", details="local provider", latency_ms=5.2
                ),
                ServiceStatus(name="Neo4j", status="not_configured", details="No URI configured"),
                ServiceStatus(name="Anthropic", status="ok", details="API key configured"),
                ServiceStatus(
                    name="OpenAI", status="not_configured", details="OPENAI_API_KEY not set"
                ),
                ServiceStatus(
                    name="Google AI", status="not_configured", details="GOOGLE_API_KEY not set"
                ),
                ServiceStatus(
                    name="ElevenLabs", status="not_configured", details="ELEVENLABS_API_KEY not set"
                ),
                ServiceStatus(name="Embeddings", status="ok", details="local provider"),
            ]
        )

        with patch(
            "src.api.connection_status_routes.check_all_connections",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get("/api/v1/settings/connections")
            assert resp.status_code == 200
            data = resp.json()
            assert "services" in data
            assert "all_ok" in data
            assert len(data["services"]) == 7

    def test_all_ok_when_all_healthy(self, client):
        mock_result = ConnectionCheckResult(
            services=[
                ServiceStatus(name="PostgreSQL", status="ok"),
                ServiceStatus(name="Neo4j", status="ok"),
            ]
        )

        with patch(
            "src.api.connection_status_routes.check_all_connections",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get("/api/v1/settings/connections")
            assert resp.json()["all_ok"] is True

    def test_not_ok_when_service_unavailable(self, client):
        mock_result = ConnectionCheckResult(
            services=[
                ServiceStatus(
                    name="PostgreSQL", status="unavailable", details="Connection refused"
                ),
                ServiceStatus(name="Neo4j", status="ok"),
            ]
        )

        with patch(
            "src.api.connection_status_routes.check_all_connections",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get("/api/v1/settings/connections")
            assert resp.json()["all_ok"] is False

    def test_not_configured_is_ok(self, client):
        """not_configured services don't fail the overall check."""
        mock_result = ConnectionCheckResult(
            services=[
                ServiceStatus(name="PostgreSQL", status="ok"),
                ServiceStatus(name="Neo4j", status="not_configured"),
            ]
        )

        with patch(
            "src.api.connection_status_routes.check_all_connections",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get("/api/v1/settings/connections")
            assert resp.json()["all_ok"] is True

    def test_service_has_latency(self, client):
        mock_result = ConnectionCheckResult(
            services=[
                ServiceStatus(name="PostgreSQL", status="ok", latency_ms=12.3),
            ]
        )

        with patch(
            "src.api.connection_status_routes.check_all_connections",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get("/api/v1/settings/connections")
            service = resp.json()["services"][0]
            assert service["latency_ms"] == 12.3
