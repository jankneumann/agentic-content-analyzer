import pytest
from fastapi.testclient import TestClient

from src.api.app import app

# Create a test client with raise_server_exceptions=False so we get the HTTP response
# instead of an exception bubbling up during tests.
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    return {"X-Admin-Key": "test-admin-key"}


def test_predict_monthly_costs_invalid_parameters_security(auth_headers, monkeypatch):
    """
    Test that invalid parameters to /predict do not leak internal exception details.
    """
    # Verify the global dependency or admin keys are appropriately mocked
    monkeypatch.setenv("ADMIN_KEYS", "test-admin-key")

    response = client.get(
        "/api/v1/pricing/predict?neon_plan=invalid_plan",
        headers=auth_headers
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid pricing parameters provided"
    assert "Unknown Neon plan" not in response.text


def test_estimate_neon_cost_invalid_parameters_security(auth_headers, monkeypatch):
    """
    Test that invalid parameters to /neon do not leak internal exception details.
    """
    monkeypatch.setenv("ADMIN_KEYS", "test-admin-key")

    response = client.get(
        "/api/v1/pricing/neon?plan=invalid_plan",
        headers=auth_headers
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid pricing parameters provided"
    assert "Unknown Neon plan" not in response.text


def test_estimate_resend_cost_invalid_parameters_security(auth_headers, monkeypatch):
    """
    Test that invalid parameters to /resend do not leak internal exception details.
    """
    monkeypatch.setenv("ADMIN_KEYS", "test-admin-key")

    response = client.get(
        "/api/v1/pricing/resend?plan=invalid_plan",
        headers=auth_headers
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid pricing parameters provided"
    assert "Unknown Resend plan" not in response.text
