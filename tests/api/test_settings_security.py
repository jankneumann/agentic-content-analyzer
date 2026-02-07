"""Tests for security controls on settings API endpoints."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


class TestSettingsSecurity:
    """Tests for authentication on settings endpoints."""

    @pytest.fixture
    def plain_client(self, db_session):
        """Create a TestClient with database patching but NO automatic auth."""
        @contextmanager
        def mock_get_db():
            yield db_session

        # Patch get_db where it is used in settings_routes
        with patch("src.api.settings_routes.get_db", mock_get_db):
            with TestClient(app) as c:
                yield c

    def test_get_prompts_no_auth(self, plain_client):
        """Test that accessing prompts without auth is denied."""
        response = plain_client.get("/api/v1/settings/prompts")

        # Expect 401 Unauthorized because the X-Admin-Key header is missing
        assert response.status_code in [401, 403]
