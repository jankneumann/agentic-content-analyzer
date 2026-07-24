"""Browser request and complete-asset policy tests."""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import httpx
import pytest

from src.release_smoke.browser import (
    AssetManifestError,
    RetiredRoute,
    _browser_session_cookie,
    load_and_scan_assets,
    normalize_request,
    run_browser_discovery,
)
from src.release_smoke.models import ProtectedTargetPolicy

SHA = "a" * 40
SAFE_JS = b'fetch("/api/v1/capabilities?limit=100")'
RETIRED_JS = b'fetch("/api/v1/contents/ingest", {method:"POST"})'


def _manifest(source: bytes = SAFE_JS) -> dict[str, object]:
    return {
        "schema_version": 1,
        "revision": SHA,
        "revision_source": "verified_detached_sha",
        "javascript": [
            {
                "path": "/assets/app.js",
                "size_bytes": len(source),
                "sha256": hashlib.sha256(source).hexdigest(),
            }
        ],
    }


def test_normalized_request_matches_encoded_query_variant() -> None:
    assert normalize_request(
        "post",
        "https://frontend.example.test/api/v1/contents/%69ngest?cache=1",
    ) == ("POST", "/api/v1/contents/ingest")


def test_manifest_scans_every_digest_verified_asset() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/release-assets.json":
            return httpx.Response(200, json=_manifest())
        if request.url.path == "/assets/app.js":
            return httpx.Response(
                200,
                content=SAFE_JS,
                headers={"Content-Type": "text/javascript"},
            )
        return httpx.Response(404)

    assets, retired_count = load_and_scan_assets(
        frontend_origin="https://frontend.example.test",
        expected_revision=SHA,
        retired_routes=(RetiredRoute("POST", "/api/v1/contents/ingest"),),
        transport=httpx.MockTransport(handler),
    )

    assert len(assets) == 1
    assert retired_count == 0


def test_manifest_detects_retired_literal_in_dormant_asset() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/release-assets.json":
            return httpx.Response(200, json=_manifest(RETIRED_JS))
        return httpx.Response(
            200,
            content=RETIRED_JS,
            headers={"Content-Type": "application/javascript"},
        )

    _, retired_count = load_and_scan_assets(
        frontend_origin="https://frontend.example.test",
        expected_revision=SHA,
        retired_routes=(RetiredRoute("POST", "/api/v1/contents/ingest"),),
        transport=httpx.MockTransport(handler),
    )

    assert retired_count == 1


def test_manifest_stream_stops_at_decompressed_byte_bound() -> None:
    chunks_consumed = 0

    class OversizedStream(httpx.SyncByteStream):
        def __iter__(self):
            nonlocal chunks_consumed
            for _ in range(4):
                chunks_consumed += 1
                yield b"x" * 600_000

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/release-assets.json"
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=OversizedStream(),
        )

    with pytest.raises(AssetManifestError, match="byte limit"):
        load_and_scan_assets(
            frontend_origin="https://frontend.example.test",
            expected_revision=SHA,
            retired_routes=(),
            transport=httpx.MockTransport(handler),
        )

    assert chunks_consumed == 2


def test_browser_auth_preserves_and_requires_server_cookie_security() -> None:
    policy = ProtectedTargetPolicy(
        target_id="staging-primary",
        target="staging",
        frontend_origin="https://staging-frontend.example.test",
        api_origin="https://staging-api.example.test",
        expected_frontend_revision=SHA,
        expected_api_revision=SHA,
        production_target_ids=["production-primary"],
        production_origins=[
            "https://frontend.example.test",
            "https://api.example.test",
        ],
    )

    def lax_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Set-Cookie": "session=opaque; Path=/; Secure; HttpOnly; SameSite=Lax"},
        )

    with pytest.raises(AssetManifestError, match="SameSite=None"):
        _browser_session_cookie(
            policy,
            "app-password",
            transport=httpx.MockTransport(lax_handler),
        )

    def secure_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Set-Cookie": "session=opaque; Path=/; Secure; HttpOnly; SameSite=None"},
        )

    cookie = _browser_session_cookie(
        policy,
        "app-password",
        transport=httpx.MockTransport(secure_handler),
    )
    assert cookie is not None
    assert cookie["sameSite"] == "None"
    assert cookie["secure"] is True
    assert cookie["httpOnly"] is True


@pytest.mark.parametrize(
    "mutation",
    ["redirect", "digest", "size", "mime", "revision", "duplicate"],
)
def test_manifest_fails_closed_on_incomplete_or_untrusted_assets(mutation: str) -> None:
    manifest = _manifest()
    javascript = manifest["javascript"]
    assert isinstance(javascript, list)
    asset = javascript[0]
    assert isinstance(asset, dict)
    if mutation == "digest":
        asset["sha256"] = "0" * 64
    elif mutation == "size":
        asset["size_bytes"] = len(SAFE_JS) + 1
    elif mutation == "revision":
        manifest["revision"] = "b" * 40
    elif mutation == "duplicate":
        javascript.append(dict(asset))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/release-assets.json":
            return httpx.Response(200, json=manifest)
        if mutation == "redirect":
            return httpx.Response(302, headers={"Location": "https://attacker.invalid/app.js"})
        return httpx.Response(
            200,
            content=SAFE_JS,
            headers={
                "Content-Type": ("text/html" if mutation == "mime" else "application/javascript")
            },
        )

    with pytest.raises(AssetManifestError):
        load_and_scan_assets(
            frontend_origin="https://frontend.example.test",
            expected_revision=SHA,
            retired_routes=(RetiredRoute("POST", "/api/v1/contents/ingest"),),
            transport=httpx.MockTransport(handler),
        )


def test_retired_route_baseline_is_not_downward_configurable(tmp_path) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": [{"method": "POST", "path": "/extra"}],
            }
        ),
        encoding="utf-8",
    )

    from src.release_smoke.browser import load_retired_routes

    routes = load_retired_routes(policy)

    assert RetiredRoute("POST", "/api/v1/contents/ingest") in routes
    assert RetiredRoute("POST", "/api/v1/content/save-url") in routes
    assert RetiredRoute("POST", "/extra") in routes


class _BrowserFixtureHandler(BaseHTTPRequestHandler):
    javascript: ClassVar[bytes] = (
        b'fetch("/api/v1/capabilities?limit=100");fetch("/api/v1/configured-sources?limit=100");'
    )
    redirect_location: ClassVar[str | None] = None
    document_extra: ClassVar[str] = ""

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/ingest", "/"}:
            if self.redirect_location is not None:
                self.send_response(302)
                self.send_header("Location", self.redirect_location)
                self.end_headers()
                return
            body = f"""<!doctype html>
<html><head>
<meta name="release-revision" content="{SHA}">
<meta name="release-revision-source" content="github_sha">
</head><body>{self.document_extra}<script src="/assets/app.js"></script></body></html>""".encode()
            self._send(200, "text/html", body)
            return
        if path == "/assets/app.js":
            self._send(200, "application/javascript", self.javascript)
            return
        if path == "/release-assets.json":
            body = json.dumps(_manifest(self.javascript)).encode()
            self._send(200, "application/json", body)
            return
        if path == "/api/v1/capabilities":
            body = json.dumps(
                {
                    "contract_version": "2",
                    "source_commands": [],
                    "operation_types": [],
                    "resource_types": [],
                }
            ).encode()
            self._send(200, "application/json", body)
            return
        if path == "/api/v1/configured-sources":
            self._send(200, "application/json", b'{"data":[]}')
            return
        self._send(404, "text/plain", b"not found")

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_real_browser_observes_both_first_page_discovery_requests() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    policy = ProtectedTargetPolicy(
        target_id="local-browser",
        target="local",
        frontend_origin=origin,
        api_origin=origin,
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    try:
        observation = run_browser_discovery(
            policy,
            app_secret=None,
            retired_routes=(RetiredRoute("POST", "/api/v1/contents/ingest"),),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert observation.revision == SHA
    assert observation.retired_route_count == 0


def test_browser_blocks_every_off_policy_origin() -> None:
    original = _BrowserFixtureHandler.javascript
    _BrowserFixtureHandler.javascript = (
        original + b';fetch("http://127.0.0.1:9/collect",{method:"POST",body:"x"})'
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    policy = ProtectedTargetPolicy(
        target_id="local-browser",
        target="local",
        frontend_origin=origin,
        api_origin=origin,
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    try:
        with pytest.raises(AssetManifestError, match="off-policy network"):
            run_browser_discovery(policy, app_secret=None, retired_routes=())
    finally:
        _BrowserFixtureHandler.javascript = original
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_browser_blocks_non_read_only_same_origin_requests() -> None:
    original = _BrowserFixtureHandler.javascript
    _BrowserFixtureHandler.javascript = original + b';fetch("/collect",{method:"POST",body:"x"})'
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    policy = ProtectedTargetPolicy(
        target_id="local-browser",
        target="local",
        frontend_origin=origin,
        api_origin=origin,
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    try:
        with pytest.raises(AssetManifestError, match="non-read-only"):
            run_browser_discovery(policy, app_secret=None, retired_routes=())
    finally:
        _BrowserFixtureHandler.javascript = original
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_browser_rejects_cross_origin_navigation_redirect() -> None:
    _BrowserFixtureHandler.redirect_location = "http://127.0.0.1:9/collect"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    policy = ProtectedTargetPolicy(
        target_id="local-browser",
        target="local",
        frontend_origin=origin,
        api_origin=origin,
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    try:
        with pytest.raises(AssetManifestError, match="navigation"):
            run_browser_discovery(policy, app_secret=None, retired_routes=())
    finally:
        _BrowserFixtureHandler.redirect_location = None
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_browser_scans_loaded_html_for_retired_literals() -> None:
    _BrowserFixtureHandler.document_extra = (
        '<script type="application/json">"/api/v1/contents/ingest"</script>'
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    policy = ProtectedTargetPolicy(
        target_id="local-browser",
        target="local",
        frontend_origin=origin,
        api_origin=origin,
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    try:
        observation = run_browser_discovery(
            policy,
            app_secret=None,
            retired_routes=(RetiredRoute("POST", "/api/v1/contents/ingest"),),
        )
    finally:
        _BrowserFixtureHandler.document_extra = ""
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert observation.retired_route_count == 1
    assert len(observation.assets) == 1
