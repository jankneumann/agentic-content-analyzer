"""Tests for GET /api/v1/content/shortcut (iOS Shortcut installation page)."""


class TestShortcutPageEndpoint:
    """Tests for GET /api/v1/content/shortcut."""

    def test_shortcut_page_renders(self, client):
        """Renders the shortcut installation page."""
        response = client.get("/api/v1/content/shortcut")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_shortcut_page_contains_api_url(self, client):
        """Page contains the API endpoint URL for configuration."""
        response = client.get("/api/v1/content/shortcut")
        assert response.status_code == 200
        assert "/api/v1/content/save-url" in response.text

    def test_shortcut_page_contains_setup_instructions(self, client):
        """Page contains setup instructions."""
        response = client.get("/api/v1/content/shortcut")
        assert response.status_code == 200
        assert "Shortcuts" in response.text  # References the iOS app
        assert "Share" in response.text  # References Share Sheet

    def test_shortcut_page_includes_json_body_example(self, client):
        """Page shows the JSON body structure for the API call."""
        response = client.get("/api/v1/content/shortcut")
        assert response.status_code == 200
        assert "ios_shortcut" in response.text
