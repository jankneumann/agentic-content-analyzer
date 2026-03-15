from asyncpg.exceptions import DataError as AsyncpgDataError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DataError

from src.api.middleware.error_handler import register_error_handlers


def test_data_error_leakage():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/data-error")
    def trigger_data_error():
        # Create a mock DataError with sensitive info
        class MockException:
            def __str__(self):
                return "SENSITIVE_DB_INFO_DATA_ERROR"

        raise DataError("statement", "params", MockException())

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/data-error")

    assert response.status_code == 422
    data = response.json()
    assert "SENSITIVE_DB_INFO_DATA_ERROR" not in data["detail"]
    assert data["detail"] == "Invalid parameter value"


def test_asyncpg_data_error_leakage():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/asyncpg-data-error")
    async def trigger_asyncpg_data_error():
        # Raise AsyncpgDataError
        raise AsyncpgDataError("SENSITIVE_ASYNCPG_INFO")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/asyncpg-data-error")

    assert response.status_code == 422
    data = response.json()
    assert "SENSITIVE_ASYNCPG_INFO" not in data["detail"]
    assert data["detail"] == "Invalid parameter value"
