"""API tests for the source-override write endpoints.

Self-contained on SQLite (patches get_db) so they run without Postgres. Covers
spec scenarios under "Source Override Management API".
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.models.base import Base
from src.models.source_override import SourceOverride


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False so the in-memory DB is shared with
    # the TestClient's request thread.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[SourceOverride.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


ADMIN_KEY = "test-admin-key"


@pytest.fixture
def client(db_session, monkeypatch):
    """Authenticated client; write routes use the SQLite session via patched get_db."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    from src.config.settings import get_settings

    get_settings.cache_clear()

    @contextmanager
    def mock_get_db():
        yield db_session

    with patch("src.api.source_write_routes.get_db", mock_get_db):
        with TestClient(app, headers={"X-Admin-Key": ADMIN_KEY}) as c:
            yield c

    get_settings.cache_clear()


BLOG = {"type": "blog", "url": "https://www.normaltech.ai/", "name": "Normal Tech"}


class TestUpsert:
    def test_add_source_returns_key_and_version(self, client):
        resp = client.post("/api/v1/sources", json={"config": BLOG})
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_key"] == "blog:https://www.normaltech.ai/"
        assert body["version"] == 1
        assert body["origin"] == "db"
        assert body["enabled"] is True

    def test_update_bumps_version(self, client):
        client.post("/api/v1/sources", json={"config": BLOG})
        resp = client.post("/api/v1/sources", json={"config": {**BLOG, "max_entries": 5}})
        assert resp.json()["version"] == 2

    def test_invalid_config_returns_400(self, client):
        resp = client.post("/api/v1/sources", json={"config": {"type": "blog"}})
        assert resp.status_code == 400


class TestDelete:
    def test_delete_existing(self, client):
        client.post("/api/v1/sources", json={"config": BLOG})
        resp = client.delete("/api/v1/sources/blog:https://www.normaltech.ai/")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_missing_returns_404(self, client):
        resp = client.delete("/api/v1/sources/blog:missing")
        assert resp.status_code == 404


class TestEnableDisable:
    def test_disable_existing_source(self, client):
        client.post("/api/v1/sources", json={"config": BLOG})
        resp = client.patch(
            "/api/v1/sources/blog:https://www.normaltech.ai/", json={"enabled": False}
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_unknown_key_without_yaml_twin_returns_404(self, client):
        # No override row and no YAML source resolves to this key.
        with patch("src.api.source_write_routes._resolve_source_config", return_value=None):
            resp = client.patch("/api/v1/sources/blog:ghost", json={"enabled": False})
        assert resp.status_code == 404


class TestAuth:
    @pytest.fixture
    def production_client(self, db_session, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
        from src.config.settings import get_settings

        get_settings.cache_clear()

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.api.source_write_routes.get_db", mock_get_db):
            with TestClient(app) as c:
                yield c

        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()

    def test_post_requires_auth(self, production_client):
        resp = production_client.post("/api/v1/sources", json={"config": BLOG})
        assert resp.status_code == 401

    def test_delete_requires_auth(self, production_client):
        resp = production_client.delete("/api/v1/sources/blog:x")
        assert resp.status_code == 401

    def test_patch_requires_auth(self, production_client):
        resp = production_client.patch("/api/v1/sources/blog:x", json={"enabled": False})
        assert resp.status_code == 401


class TestOverviewOrigin:
    def test_list_reports_origin(self, monkeypatch):
        """GET /api/v1/sources tags each source with origin and source_key."""
        from src.config.sources import BlogSource, SourcesConfig

        cfg = SourcesConfig(
            sources=[
                BlogSource(url="https://yaml.example/blog", origin="yaml"),
                BlogSource(url="https://www.normaltech.ai/", origin="db"),
            ]
        )

        @contextmanager
        def mock_get_db():
            db = MagicMock()
            db.query.return_value.group_by.return_value.all.return_value = []
            yield db

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
        from src.config.settings import get_settings

        get_settings.cache_clear()
        mock_settings = MagicMock()
        mock_settings.get_sources_config.return_value = cfg
        with (
            patch("src.api.source_routes.get_db", mock_get_db),
            patch("src.api.source_routes.settings", mock_settings),
        ):
            with TestClient(app, headers={"X-Admin-Key": ADMIN_KEY}) as c:
                resp = c.get("/api/v1/sources")
        get_settings.cache_clear()

        assert resp.status_code == 200
        by_origin = {s["url"]: s["origin"] for s in resp.json()["sources"]}
        assert by_origin["https://yaml.example/blog"] == "yaml"
        assert by_origin["https://www.normaltech.ai/"] == "db"
        keys = {s["source_key"] for s in resp.json()["sources"]}
        assert "blog:https://www.normaltech.ai/" in keys
