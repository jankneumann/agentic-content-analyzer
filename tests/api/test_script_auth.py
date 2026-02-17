import os
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app


def test_script_routes_auth(db_session):
    """
    Test that script routes are protected by authentication.
    """

    @contextmanager
    def mock_get_db():
        yield db_session

    # Patch get_db in both the router and the service it uses
    with (
        patch("src.api.script_routes.get_db", side_effect=mock_get_db),
        patch("src.services.script_review_service.get_db", side_effect=mock_get_db),
    ):
        client = TestClient(app)

        # 1. Test UNAUTHORIZED access (missing header)
        response = client.get("/api/v1/scripts/")
        assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}"
        assert response.json()["detail"] == "Missing authentication header X-Admin-Key"

        # 2. Test FORBIDDEN access (invalid key)
        response = client.get("/api/v1/scripts/", headers={"X-Admin-Key": "wrong-key"})
        assert response.status_code == 403, f"Expected 403 Forbidden, got {response.status_code}"
        assert response.json()["detail"] == "Invalid admin API key"

        # 3. Test AUTHORIZED access (valid key)
        # We need to ensure the env var matches what we send
        # In the test execution below, we export ADMIN_API_KEY="test-key"
        valid_key = os.environ.get("ADMIN_API_KEY", "test-key")

        response = client.get("/api/v1/scripts/", headers={"X-Admin-Key": valid_key})
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
