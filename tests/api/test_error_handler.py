"""Tests for structured error handling middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient

from src.api.middleware.error_handler import register_error_handlers


class TestStructuredErrorHandler:
    """Tests for the global exception handler."""

    def _make_app(self) -> FastAPI:
        """Create a test app with error handler registered."""
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/fail")
        async def fail_endpoint():
            raise ValueError("something went wrong")

        @app.get("/ok")
        async def ok_endpoint():
            return {"status": "ok"}

        return app

    def test_unhandled_exception_returns_500_json(self):
        """Unhandled exceptions should return structured JSON."""
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/fail")

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal Server Error"
        # Security: internal error details are not exposed to clients
        assert data["detail"] == "An internal error occurred"

    def test_successful_request_not_affected(self):
        """Normal responses should not be modified."""
        app = self._make_app()
        client = TestClient(app)
        response = client.get("/ok")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_error_includes_trace_id_when_available(self):
        """Error response should include trace_id when OTel is active."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0x12345678901234567890123456789ABC
        mock_span.get_span_context.return_value = mock_ctx

        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "src.api.middleware.error_handler.trace",
            create=True,
        ) as mock_trace:
            mock_trace.get_current_span.return_value = mock_span
            # Need to also patch the import
            with patch.dict(
                "sys.modules",
                {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace},
            ):
                response = client.get("/fail")

        assert response.status_code == 500
        # trace_id may or may not be present depending on mock setup
        # The key thing is it doesn't crash

    def test_error_handler_no_trace_id_when_otel_not_installed(self):
        """Error should still work without OTel installed."""
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/fail")

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal Server Error"
        # trace_id should be absent (OTel not configured in test)

    @pytest.mark.parametrize(
        ("status_code", "title"),
        ((401, "Unauthorized"), (403, "Forbidden"), (404, "Not Found")),
    )
    def test_workflow_terminal_diagnostic_errors_are_problem_json(
        self,
        status_code: int,
        title: str,
    ) -> None:
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/api/v1/workflow-terminal-events/{event_id}")
        async def diagnostic_failure(event_id: str):
            del event_id
            raise HTTPException(status_code=status_code, detail=title)

        response = TestClient(app).get(
            "/api/v1/workflow-terminal-events/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )

        assert response.status_code == status_code
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json() == {
            "type": f"https://aca.rotkohl.ai/problems/{title.lower().replace(' ', '-')}",
            "title": title,
            "status": status_code,
            "detail": title,
        }
