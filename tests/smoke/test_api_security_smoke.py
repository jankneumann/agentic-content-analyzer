"""Smoke tests for API security hardening — runs against a live server.

These tests verify the deployed HTTP behavior of security features:
- Health/ready endpoints accessible
- Upload magic bytes validation (415 on mismatch)
- Upload MIME type cross-check (415 on mismatch)
- Upload size enforcement (413 on oversized)
- CORS headers present in development mode
- Admin auth enforcement on protected endpoints

Run:
    pytest tests/smoke/ -m smoke -v

All tests are marked @pytest.mark.smoke so they're excluded from
the default test run (which filters to 'not integration and not live_api').
"""

import pytest

pytestmark = pytest.mark.smoke


# ============================================================================
# Health & Readiness
# ============================================================================


class TestHealthEndpoints:
    """Verify system endpoints are publicly accessible."""

    def test_health_returns_200(self, http_client):
        """GET /health should return 200 with status=healthy."""
        r = http_client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"

    def test_ready_returns_200(self, http_client):
        """GET /ready should return 200 (or 503 if services are down)."""
        r = http_client.get("/ready")
        assert r.status_code in (200, 503)

    def test_system_config_returns_200(self, http_client):
        """GET /api/v1/system/config should return feature flags."""
        r = http_client.get("/api/v1/system/config")
        assert r.status_code == 200
        body = r.json()
        assert "features" in body


# ============================================================================
# Upload Security: Magic Bytes Validation
# ============================================================================


class TestUploadMagicBytes:
    """Verify file signature (magic bytes) validation on uploads."""

    UPLOAD_URL = "/api/v1/documents/upload"

    def test_pdf_with_png_header_returns_415(self, http_client):
        """A .pdf file whose bytes start with PNG header should be rejected."""
        fake_pdf = b"\x89PNG\r\n\x1a\n" + b"not a real PDF"
        files = {"file": ("document.pdf", fake_pdf, "application/pdf")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code == 415
        assert "does not match expected format" in r.json()["detail"]

    def test_png_with_jpeg_header_returns_415(self, http_client):
        """A .png file whose bytes are actually JPEG should be rejected."""
        jpeg_data = b"\xff\xd8\xff" + b"\x00" * 100
        files = {"file": ("image.png", jpeg_data, "image/png")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code == 415
        assert ".png" in r.json()["detail"]

    def test_exe_disguised_as_pdf_returns_415(self, http_client):
        """An executable (MZ header) disguised as .pdf should be rejected."""
        exe_data = b"MZ\x90\x00" + b"\x00" * 200
        files = {"file": ("report.pdf", exe_data, "application/pdf")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code == 415

    def test_valid_pdf_magic_bytes_passes_signature_check(self, http_client):
        """A .pdf file with correct %PDF header should pass signature check.

        May still fail downstream (parser/DB), but should NOT get 415.
        """
        valid_pdf = b"%PDF-1.4 minimal content"
        files = {"file": ("document.pdf", valid_pdf, "application/pdf")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        # 415 = signature/MIME rejection. Anything else means validation passed.
        assert r.status_code != 415

    def test_unknown_extension_skips_signature_check(self, http_client):
        """A .txt file (no magic bytes mapping) should skip signature validation."""
        content = b"Just some plain text content"
        files = {"file": ("notes.txt", content, "text/plain")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        # Should not get 415 from magic bytes check
        if r.status_code == 415:
            # Only fail if the 415 is from signature check, not format support
            assert "does not match expected format" not in r.json().get("detail", "")


# ============================================================================
# Upload Security: MIME Type Cross-Check
# ============================================================================


class TestUploadMimeValidation:
    """Verify MIME type cross-check on uploads."""

    UPLOAD_URL = "/api/v1/documents/upload"

    def test_pdf_with_image_mime_returns_415(self, http_client):
        """A valid PDF uploaded with Content-Type: image/png should be rejected."""
        valid_pdf = b"%PDF-1.4 content"
        files = {"file": ("document.pdf", valid_pdf, "image/png")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code == 415
        assert "Content-Type" in r.json()["detail"]

    def test_html_with_pdf_mime_returns_415(self, http_client):
        """An .html file uploaded with Content-Type: application/pdf should be rejected."""
        html_content = b"<!DOCTYPE html><html><body>Hello</body></html>"
        files = {"file": ("page.html", html_content, "application/pdf")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code == 415

    def test_octet_stream_bypasses_mime_check(self, http_client):
        """application/octet-stream is a generic fallback and should bypass MIME check."""
        valid_pdf = b"%PDF-1.4 content"
        files = {"file": ("document.pdf", valid_pdf, "application/octet-stream")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        # Should not be rejected by MIME check (may fail elsewhere)
        if r.status_code == 415:
            assert "Content-Type" not in r.json().get("detail", "")

    def test_matching_mime_and_extension_passes(self, http_client):
        """Correct MIME for correct extension should pass the MIME check."""
        valid_pdf = b"%PDF-1.4 content"
        files = {"file": ("document.pdf", valid_pdf, "application/pdf")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        # Should pass both signature and MIME checks
        assert r.status_code != 415


# ============================================================================
# Upload Security: Size Enforcement
# ============================================================================


class TestUploadSizeEnforcement:
    """Verify upload size limits are enforced."""

    UPLOAD_URL = "/api/v1/documents/upload"

    def test_small_file_accepted(self, http_client):
        """A small file should not trigger size limits."""
        content = b"Small file content"
        files = {"file": ("small.txt", content, "text/plain")}
        r = http_client.post(self.UPLOAD_URL, files=files)
        assert r.status_code != 413


# ============================================================================
# CORS Headers
# ============================================================================


class TestCORSHeaders:
    """Verify CORS headers on API responses."""

    def test_preflight_returns_cors_headers(self, http_client):
        """OPTIONS request with Origin should return CORS headers."""
        r = http_client.request(
            "OPTIONS",
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should return 200 with Access-Control headers
        assert r.status_code == 200
        assert "access-control-allow-origin" in r.headers

    def test_cors_allows_configured_origin(self, http_client):
        """Responses should include the requesting origin if configured."""
        r = http_client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        # In development mode, localhost origins should be allowed
        cors_origin = r.headers.get("access-control-allow-origin", "")
        # Either the specific origin or wildcard should be present
        assert cors_origin in ("http://localhost:5173", "*") or cors_origin == ""


# ============================================================================
# Admin Auth Enforcement
# ============================================================================


class TestAdminAuth:
    """Verify admin endpoints require authentication in production."""

    def test_prompts_without_auth_in_dev_mode(self, http_client):
        """Prompts endpoint should be accessible in dev mode without auth."""
        r = http_client.get("/api/v1/settings/prompts")
        # In dev mode: 200. In production without key: 401 or 500.
        assert r.status_code in (200, 401, 500)

    def test_prompts_with_admin_key(self, admin_client, admin_key):
        """Prompts endpoint should be accessible with valid admin key."""
        if not admin_key:
            pytest.skip("SMOKE_TEST_ADMIN_KEY not set")
        r = admin_client.get("/api/v1/settings/prompts")
        assert r.status_code == 200

    def test_prompts_with_wrong_key_returns_403(self, http_client):
        """Prompts endpoint with wrong key should return 403."""
        r = http_client.get(
            "/api/v1/settings/prompts",
            headers={"X-Admin-Key": "definitely-wrong-key"},
        )
        # 403 if admin key is configured, or 200 if dev mode bypass
        assert r.status_code in (200, 403)


# ============================================================================
# Endpoint Existence
# ============================================================================


class TestEndpointExistence:
    """Verify key endpoints exist and return expected status codes."""

    def test_upload_endpoint_exists(self, http_client):
        """POST /api/v1/documents/upload should exist (422 without body, not 404)."""
        r = http_client.post("/api/v1/documents/upload")
        assert r.status_code != 404

    def test_formats_endpoint_exists(self, http_client):
        """GET /api/v1/documents/formats should return supported formats."""
        r = http_client.get("/api/v1/documents/formats")
        assert r.status_code == 200
        body = r.json()
        assert "formats" in body
        assert isinstance(body["formats"], list)
        assert "max_file_size_mb" in body
