"""Tests for system endpoints (health check, config)."""


class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_check_returns_healthy(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "newsletter-aggregator"


class TestSystemConfig:
    """Tests for the /api/v1/system/config endpoint."""

    def test_system_config_returns_version(self, client):
        """Test that system config returns version info."""
        response = client.get("/api/v1/system/config")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_system_config_returns_features(self, client):
        """Test that system config returns feature flags."""
        response = client.get("/api/v1/system/config")

        assert response.status_code == 200
        data = response.json()
        assert "features" in data
        features = data["features"]
        assert "sse_enabled" in features
        assert features["sse_enabled"] is True
        assert "chat_enabled" in features
        assert "themes_enabled" in features
