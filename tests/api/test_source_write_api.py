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
APP_SECRET_KEY = "test-app-secret-key-at-least-32-characters"


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
OBSIDIAN = {
    "type": "obsidian_vault",
    "vault_id": "personal",
    "vault_path": "/srv/obsidian/private-vault",
    "ingest_folder": "Clients/Private",
}


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

    def test_nested_type_is_authoritative_and_unknown_top_level_type_is_ignored(
        self, client, db_session
    ):
        response = client.post(
            "/api/v1/sources",
            json={"type": "obsidian_vault", "config": BLOG, "unknown": "ignored"},
        )

        assert response.status_code == 200
        assert response.json()["source_key"] == "blog:https://www.normaltech.ai/"
        row = db_session.query(SourceOverride).one()
        assert row.source_type == "blog"
        assert "unknown" not in row.config

    def test_missing_nested_type_is_400_and_does_not_create_override(self, client, db_session):
        response = client.post(
            "/api/v1/sources",
            json={"type": "blog", "config": {"url": "https://example.test/feed"}},
        )

        assert response.status_code == 400
        assert set(response.json()) == {"detail"}
        assert db_session.query(SourceOverride).count() == 0

    def test_malformed_body_is_422_and_does_not_create_override(self, client, db_session):
        response = client.post("/api/v1/sources", json={"config": "not-an-object"})

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
        assert db_session.query(SourceOverride).count() == 0

    def test_obsidian_mutation_response_uses_only_opaque_source_key(self, client):
        response = client.post("/api/v1/sources", json={"config": OBSIDIAN})

        assert response.status_code == 200
        assert response.json()["source_key"].startswith("src_")
        assert "/srv/obsidian" not in response.text
        assert "Clients/Private" not in response.text
        assert "personal" not in response.text
        assert "configured_source_version" not in response.text
        assert "configured_sources" not in response.text

    def test_invalid_obsidian_error_does_not_echo_private_fields(self, client):
        private_path = "/srv/obsidian/clients/acquisition/private-vault"
        response = client.post(
            "/api/v1/sources",
            json={
                "config": {
                    **OBSIDIAN,
                    "vault_id": "invalid vault id",
                    "vault_path": private_path,
                }
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid obsidian_vault source config"
        assert private_path not in response.text


class TestDelete:
    def test_delete_existing(self, client):
        client.post("/api/v1/sources", json={"config": BLOG})
        resp = client.delete("/api/v1/sources/blog:https://www.normaltech.ai/")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_missing_returns_404(self, client):
        resp = client.delete("/api/v1/sources/blog:missing")
        assert resp.status_code == 404

    def test_delete_rejects_nul_key(self, client):
        resp = client.delete("/api/v1/sources/bad%00key")
        assert resp.status_code == 422

    def test_delete_accepts_opaque_obsidian_key(self, client):
        created = client.post("/api/v1/sources", json={"config": OBSIDIAN}).json()

        response = client.delete(f"/api/v1/sources/{created['source_key']}")

        assert response.status_code == 200
        assert response.json() == {"source_key": created["source_key"], "deleted": True}
        assert "personal" not in response.text

    def test_delete_rejects_natural_obsidian_key_without_echoing_it(self, client):
        client.post("/api/v1/sources", json={"config": OBSIDIAN})

        response = client.delete("/api/v1/sources/obsidian_vault:personal")

        assert response.status_code == 400
        assert response.json()["detail"] == "Obsidian source mutations require an opaque source key"
        assert "personal" not in response.text


class TestEnableDisable:
    def test_disable_existing_source(self, client):
        client.post("/api/v1/sources", json={"config": BLOG})
        resp = client.patch(
            "/api/v1/sources/blog:https://www.normaltech.ai/", json={"enabled": False}
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_ignores_unknown_sibling_and_only_changes_enabled(self, client, db_session):
        created = client.post("/api/v1/sources", json={"config": BLOG}).json()

        response = client.patch(
            f"/api/v1/sources/{created['source_key']}",
            json={"enabled": False, "config": {"type": "rss"}, "version": 99},
        )

        assert response.status_code == 200
        assert response.json()["version"] == 2
        row = db_session.query(SourceOverride).one()
        assert row.enabled is False
        assert row.source_type == "blog"
        assert row.config["url"] == BLOG["url"]

    def test_patch_unknown_key_without_yaml_twin_returns_404(self, client):
        # No override row and no YAML source resolves to this key.
        with patch("src.api.source_write_routes._resolve_source_config", return_value=None):
            resp = client.patch("/api/v1/sources/blog:ghost", json={"enabled": False})
        assert resp.status_code == 404

    def test_disable_obsidian_by_opaque_key_keeps_response_opaque(self, client):
        created = client.post("/api/v1/sources", json={"config": OBSIDIAN}).json()

        response = client.patch(f"/api/v1/sources/{created['source_key']}", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["source_key"] == created["source_key"]
        assert response.json()["enabled"] is False

    def test_disable_rejects_natural_obsidian_key_without_echoing_it(self, client):
        client.post("/api/v1/sources", json={"config": OBSIDIAN})

        response = client.patch(
            "/api/v1/sources/obsidian_vault:personal",
            json={"enabled": False},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Obsidian source mutations require an opaque source key"
        assert "personal" not in response.text


class TestAuth:
    @pytest.fixture
    def production_client(self, db_session, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
        monkeypatch.setenv("APP_SECRET_KEY", APP_SECRET_KEY)
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

    def test_post_requires_auth_without_mutating(self, production_client, db_session):
        resp = production_client.post("/api/v1/sources", json={"config": BLOG})
        assert resp.status_code == 401
        assert set(resp.json()) >= {"error", "detail"}
        assert db_session.query(SourceOverride).count() == 0

    def test_post_rejects_invalid_admin_key_without_mutating(self, production_client, db_session):
        resp = production_client.post(
            "/api/v1/sources",
            json={"config": BLOG},
            headers={"X-Admin-Key": "wrong-key"},
        )

        assert resp.status_code == 403
        assert set(resp.json()) >= {"error", "detail"}
        assert db_session.query(SourceOverride).count() == 0

    def test_delete_requires_auth(self, production_client):
        resp = production_client.delete("/api/v1/sources/blog:x")
        assert resp.status_code == 401

    def test_patch_requires_auth(self, production_client):
        resp = production_client.patch("/api/v1/sources/blog:x", json={"enabled": False})
        assert resp.status_code == 401

    @pytest.mark.parametrize("credential", ["admin", "session"])
    def test_writes_accept_either_documented_credential(
        self, production_client, credential, db_session
    ):
        from src.api.auth_routes import _COOKIE_NAME, _create_jwt

        headers = (
            {"X-Admin-Key": ADMIN_KEY}
            if credential == "admin"
            else {"Cookie": f"{_COOKIE_NAME}={_create_jwt(APP_SECRET_KEY)}"}
        )
        created = production_client.post("/api/v1/sources", json={"config": BLOG}, headers=headers)
        assert created.status_code == 200
        source_key = created.json()["source_key"]

        patched = production_client.patch(
            f"/api/v1/sources/{source_key}",
            json={"enabled": False},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["version"] == 2

        deleted = production_client.delete(f"/api/v1/sources/{source_key}", headers=headers)
        assert deleted.status_code == 200
        assert db_session.query(SourceOverride).count() == 0

    @pytest.mark.parametrize("operation", ["patch", "delete"])
    @pytest.mark.parametrize(
        ("headers", "expected_status"),
        [({}, 401), ({"X-Admin-Key": "wrong-key"}, 403)],
    )
    def test_rejected_member_write_preserves_state_and_version(
        self, production_client, db_session, operation, headers, expected_status
    ):
        created = production_client.post(
            "/api/v1/sources",
            json={"config": BLOG},
            headers={"X-Admin-Key": ADMIN_KEY},
        ).json()
        path = f"/api/v1/sources/{created['source_key']}"

        if operation == "patch":
            response = production_client.patch(path, json={"enabled": False}, headers=headers)
        else:
            response = production_client.delete(path, headers=headers)

        assert response.status_code == expected_status
        db_session.expire_all()
        row = db_session.query(SourceOverride).one()
        assert row.enabled is True
        assert row.version == 1

    def test_get_requires_auth(self, production_client):
        response = production_client.get("/api/v1/sources")

        assert response.status_code == 401
        assert set(response.json()) >= {"error", "detail"}

    def test_get_rejects_invalid_admin_key(self, production_client):
        response = production_client.get("/api/v1/sources", headers={"X-Admin-Key": "wrong-key"})

        assert response.status_code == 403
        assert set(response.json()) >= {"error", "detail"}

    @pytest.mark.parametrize("credential", ["admin", "session"])
    def test_get_accepts_either_documented_credential(self, production_client, credential):
        from src.api.auth_routes import _COOKIE_NAME, _create_jwt
        from src.config.sources import SourcesConfig

        @contextmanager
        def mock_read_db():
            db = MagicMock()
            db.query.return_value.group_by.return_value.all.return_value = []
            yield db

        mock_settings = MagicMock()
        mock_settings.get_sources_config.return_value = SourcesConfig(sources=[])
        headers = (
            {"X-Admin-Key": ADMIN_KEY}
            if credential == "admin"
            else {"Cookie": f"{_COOKIE_NAME}={_create_jwt(APP_SECRET_KEY)}"}
        )

        with (
            patch("src.api.source_routes.get_db", mock_read_db),
            patch("src.api.source_routes.settings", mock_settings),
        ):
            response = production_client.get("/api/v1/sources", headers=headers)

        assert response.status_code == 200
        assert response.json() == {
            "sources": [],
            "counts": {},
            "total_sources": 0,
            "enabled_sources": 0,
        }


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
