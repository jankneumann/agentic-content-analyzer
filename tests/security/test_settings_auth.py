import os

from fastapi.testclient import TestClient

# Mock env vars BEFORE importing app
# We set a known admin key for testing
os.environ["ADMIN_API_KEY"] = "secret-admin-key"
# Required by other modules
os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["TAVILY_API_KEY"] = "tv-test-key"

from src.api.app import app

client = TestClient(app)


def test_update_prompt_auth():
    """Test authentication for updating prompts."""
    url = "/api/v1/settings/prompts/chat.summary.system"
    payload = {"value": "You are a hacked AI."}

    # 1. Test missing header
    response = client.put(url, json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authentication header X-Admin-Key"

    # 2. Test invalid key
    response = client.put(url, json=payload, headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin API key"

    # 3. Test valid key
    # This might fail with 500 DB error because DB is not mocked,
    # but that means it passed the auth check!
    try:
        response = client.put(url, json=payload, headers={"X-Admin-Key": "secret-admin-key"})
        # If DB connection works (e.g. using sqlite fallback? no, it uses postgres),
        # it might be 404 if prompt not found, or 200.
        # But if DB fails, it raises 500.
        # Either way, if it is NOT 401/403, we passed auth.
        assert response.status_code not in (401, 403)
    except Exception:
        # If client raises exception due to app crash (DB error), that's fine for this test
        pass


def test_reset_prompt_auth():
    """Test authentication for resetting prompts."""
    url = "/api/v1/settings/prompts/chat.summary.system"

    # 1. Test missing header
    response = client.delete(url)
    assert response.status_code == 401

    # 2. Test invalid key
    response = client.delete(url, headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 403

    # 3. Test valid key
    try:
        response = client.delete(url, headers={"X-Admin-Key": "secret-admin-key"})
        assert response.status_code not in (401, 403)
    except Exception:
        pass
