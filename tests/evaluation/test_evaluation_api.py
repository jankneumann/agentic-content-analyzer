"""Tests for evaluation API endpoints.

Tests cover:
- GET /api/v1/evaluation/datasets
- POST /api/v1/evaluation/datasets
- GET /api/v1/evaluation/report
- GET /api/v1/evaluation/routing-config
- PUT /api/v1/evaluation/routing-config/{step}

Note: Uses a standalone FastAPI app to avoid the heavyweight conftest
      that imports the full application (requires asyncpg, etc.).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.evaluation_routes import router

# Patch at source since routes use lazy imports
_SVC_PATH = "src.services.evaluation_service.EvaluationService"
_GET_DB_PATH = "src.api.evaluation_routes.get_db"


@contextmanager
def _mock_db():
    """Yield a mock DB session for route tests."""
    yield MagicMock()


@pytest.fixture
def client():
    """Create a lightweight test client with just the evaluation router."""
    test_app = FastAPI()
    # Mount router without auth dependency for tests
    clean_router = router
    clean_router.dependencies = []
    test_app.include_router(clean_router)
    with patch(_GET_DB_PATH, _mock_db):
        yield TestClient(test_app)


class TestListDatasets:
    def test_empty_list(self, client):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.get_datasets.return_value = []
            response = client.get("/api/v1/evaluation/datasets")
            assert response.status_code == 200
            assert response.json() == {"datasets": []}

    def test_with_step_filter(self, client):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.get_datasets.return_value = []
            response = client.get("/api/v1/evaluation/datasets?step=summarization")
            assert response.status_code == 200
            mock_svc_cls.return_value.get_datasets.assert_called_once_with(step="summarization")


class TestCreateDataset:
    def test_creates_dataset(self, client):
        from src.services.evaluation_service import DatasetInfo

        ds = DatasetInfo(
            id=1,
            step="summarization",
            name="test",
            status="pending_evaluation",
            sample_count=0,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.create_dataset.return_value = ds
            response = client.post(
                "/api/v1/evaluation/datasets",
                json={"step": "summarization", "name": "test"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["step"] == "summarization"
            assert data["id"] == 1


class TestGetReport:
    def test_empty_report(self, client):
        with patch(_SVC_PATH) as mock_svc_cls:
            mock_svc_cls.return_value.generate_report.return_value = []
            response = client.get("/api/v1/evaluation/report")
            assert response.status_code == 200
            assert response.json() == {"reports": []}


class TestRoutingConfig:
    def test_list_routing_configs(self, client):
        response = client.get("/api/v1/evaluation/routing-config")
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert len(data["configs"]) > 0
        for cfg in data["configs"]:
            assert "step" in cfg
            assert "mode" in cfg
            assert "enabled" in cfg

    def test_update_routing_config_invalid_step(self, client):
        response = client.put(
            "/api/v1/evaluation/routing-config/nonexistent_step",
            json={"mode": "dynamic"},
        )
        assert response.status_code == 404

    def test_update_routing_config_invalid_mode(self, client):
        response = client.put(
            "/api/v1/evaluation/routing-config/summarization",
            json={"mode": "invalid_mode"},
        )
        assert response.status_code == 400

    def test_update_routing_config_invalid_threshold(self, client):
        response = client.put(
            "/api/v1/evaluation/routing-config/summarization",
            json={"threshold": 1.5},
        )
        assert response.status_code == 400

    def test_update_routing_config_persists(self, client):
        """Verify PUT creates/updates a DB record."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with patch(_GET_DB_PATH) as mock_get_db:
            mock_get_db.return_value.__enter__ = lambda s: mock_db
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
            response = client.put(
                "/api/v1/evaluation/routing-config/summarization",
                json={"enabled": True, "threshold": 0.7},
            )
        assert response.status_code == 200
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
