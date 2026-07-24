"""Browser-adjacent request normalization and complete frontend asset scanning."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

import httpx

from src.release_smoke.models import ProtectedTargetPolicy, RevisionSource

_MAX_MANIFEST_BYTES = 1_048_576
_MAX_DOCUMENT_BYTES = 1_048_576
_MAX_ASSET_COUNT = 512
_MAX_ASSET_BYTES = 10_485_760
_MAX_TOTAL_BYTES = 67_108_864
_SCAN_DEADLINE_SECONDS = 60.0
_JAVASCRIPT_TYPES = frozenset(
    {
        "application/javascript",
        "application/x-javascript",
        "text/javascript",
    }
)


class AssetManifestError(RuntimeError):
    """The served frontend asset inventory is incomplete or untrusted."""


@dataclass(frozen=True, order=True)
class RetiredRoute:
    method: str
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", self.method.upper())


@dataclass(frozen=True)
class AssetEvidence:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class BrowserObservation:
    revision: str
    revision_source: RevisionSource
    assets: tuple[AssetEvidence, ...]
    retired_route_count: int


_BASELINE_RETIRED_ROUTES = frozenset(
    {
        RetiredRoute("POST", "/api/v1/content/save-url"),
        RetiredRoute("POST", "/api/v1/contents/ingest"),
    }
)


def normalize_request(method: str, url: str) -> tuple[str, str]:
    """Normalize absolute, encoded, and query-bearing request URLs."""
    path = unquote(urlsplit(url).path)
    return method.upper(), path


def load_retired_routes(additive_policy: Path | None = None) -> tuple[RetiredRoute, ...]:
    """Return the immutable baseline plus optional reviewed additive routes."""
    routes = set(_BASELINE_RETIRED_ROUTES)
    if additive_policy is not None:
        try:
            document = json.loads(additive_policy.read_text(encoding="utf-8"))
            entries = document["routes"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AssetManifestError("Retired-route additive policy is invalid") from exc
        if not isinstance(entries, list):
            raise AssetManifestError("Retired-route additive policy routes must be a list")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"method", "path"}:
                raise AssetManifestError("Retired-route entry is invalid")
            method = entry["method"]
            path = entry["path"]
            if (
                not isinstance(method, str)
                or not isinstance(path, str)
                or not path.startswith("/")
                or "?" in path
                or "#" in path
            ):
                raise AssetManifestError("Retired-route method/path is invalid")
            routes.add(RetiredRoute(method, path))
    return tuple(sorted(routes))


def _require_response(response: httpx.Response, check: str) -> None:
    if response.is_redirect:
        raise AssetManifestError(f"{check} redirected")
    if response.status_code != 200:
        raise AssetManifestError(f"{check} returned HTTP {response.status_code}")


def _manifest_document(source: bytes) -> dict[str, Any]:
    try:
        document = json.loads(source)
    except ValueError as exc:
        raise AssetManifestError("Asset manifest is not valid JSON") from exc
    if not isinstance(document, dict):
        raise AssetManifestError("Asset manifest is not an object")
    return document


def _read_bounded(
    client: httpx.Client,
    url: str,
    *,
    check: str,
    max_bytes: int,
    started: float,
) -> tuple[bytes, str]:
    """Stream decompressed response bytes and stop at byte/deadline bounds."""
    body = bytearray()
    try:
        with client.stream("GET", url) as response:
            _require_response(response, check)
            media_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            for chunk in response.iter_bytes():
                if time.monotonic() - started > _SCAN_DEADLINE_SECONDS:
                    raise AssetManifestError("Asset scan exceeded deadline")
                if len(body) + len(chunk) > max_bytes:
                    raise AssetManifestError(f"{check} exceeds byte limit")
                body.extend(chunk)
    except httpx.HTTPError as exc:
        raise AssetManifestError(f"{check} request failed") from exc
    return bytes(body), media_type


def _asset_has_retired_literal(source: bytes, routes: tuple[RetiredRoute, ...]) -> int:
    decoded = unquote(source.decode("utf-8", errors="ignore"))
    return sum(route.path in decoded for route in routes)


def _browser_session_cookie(
    policy: ProtectedTargetPolicy,
    app_secret: str | None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any] | None:
    """Authenticate only to the exact API origin and return a scoped cookie."""
    if app_secret is None:
        return None
    try:
        with (
            httpx.Client(
                follow_redirects=False,
                timeout=20.0,
                transport=transport,
            ) as client,
            client.stream(
                "POST",
                f"{policy.api_origin}/api/v1/auth/login",
                json={"password": app_secret},
            ) as response,
        ):
            _require_response(response, "Browser authentication")
            cookies = SimpleCookie()
            for header in response.headers.get_list("set-cookie"):
                cookies.load(header)
    except httpx.HTTPError as exc:
        raise AssetManifestError("Browser authentication request failed") from exc
    morsel = cookies.get("session")
    if morsel is None or not morsel.value:
        raise AssetManifestError("Browser authentication did not issue a session cookie")
    secure = bool(morsel["secure"])
    http_only = bool(morsel["httponly"])
    same_site_value = morsel["samesite"].casefold()
    same_site = {"none": "None", "lax": "Lax", "strict": "Strict"}.get(same_site_value)
    if not http_only or same_site is None:
        raise AssetManifestError("Browser authentication cookie attributes are unsafe")
    if policy.target != "local" and not secure:
        raise AssetManifestError("Browser authentication cookie is not secure")
    if policy.frontend_origin != policy.api_origin and same_site != "None":
        raise AssetManifestError("Cross-origin browser authentication cookie is not SameSite=None")
    return {
        "name": "session",
        "value": morsel.value,
        "url": policy.api_origin,
        "httpOnly": http_only,
        "secure": secure,
        "sameSite": same_site,
    }


def load_and_scan_assets(
    *,
    frontend_origin: str,
    expected_revision: str,
    retired_routes: tuple[RetiredRoute, ...],
    transport: httpx.BaseTransport | None = None,
) -> tuple[list[AssetEvidence], int]:
    """Fetch the revision-bound manifest and every declared JavaScript chunk."""
    started = time.monotonic()
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        timeout=20.0,
    ) as client:
        manifest_source, _manifest_media_type = _read_bounded(
            client,
            f"{frontend_origin}/release-assets.json",
            check="Asset manifest",
            max_bytes=_MAX_MANIFEST_BYTES,
            started=started,
        )
        manifest = _manifest_document(manifest_source)
        if manifest.get("schema_version") != 1:
            raise AssetManifestError("Asset manifest schema version is unsupported")
        if manifest.get("revision") != expected_revision:
            raise AssetManifestError("Asset manifest revision mismatch")
        if manifest.get("revision_source") not in {
            "railway_commit_sha",
            "github_sha",
            "verified_detached_sha",
            "local_development",
        }:
            raise AssetManifestError("Asset manifest revision provenance is invalid")
        javascript = manifest.get("javascript")
        if not isinstance(javascript, list) or not javascript:
            raise AssetManifestError("Asset manifest has no JavaScript inventory")
        if len(javascript) > _MAX_ASSET_COUNT:
            raise AssetManifestError("Asset manifest exceeds asset-count limit")

        evidence: list[AssetEvidence] = []
        retired_count = 0
        seen_paths: set[str] = set()
        total_bytes = 0
        for entry in javascript:
            if time.monotonic() - started > _SCAN_DEADLINE_SECONDS:
                raise AssetManifestError("Asset scan exceeded deadline")
            if not isinstance(entry, dict) or set(entry) != {
                "path",
                "size_bytes",
                "sha256",
            }:
                raise AssetManifestError("Asset manifest entry is invalid")
            path = entry["path"]
            declared_size = entry["size_bytes"]
            declared_sha256 = entry["sha256"]
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or not path.endswith(".js")
                or urlsplit(path).query
                or urlsplit(path).fragment
                or path in seen_paths
            ):
                raise AssetManifestError("Asset manifest path is invalid or duplicated")
            if (
                not isinstance(declared_size, int)
                or declared_size < 0
                or declared_size > _MAX_ASSET_BYTES
            ):
                raise AssetManifestError("Asset manifest size is invalid")
            if (
                not isinstance(declared_sha256, str)
                or len(declared_sha256) != 64
                or any(character not in "0123456789abcdef" for character in declared_sha256)
            ):
                raise AssetManifestError("Asset manifest digest is invalid")
            seen_paths.add(path)

            asset_url = urljoin(f"{frontend_origin}/", path.removeprefix("/"))
            if f"{urlsplit(asset_url).scheme}://{urlsplit(asset_url).netloc}" != frontend_origin:
                raise AssetManifestError("Asset escaped the frontend origin")
            remaining_bytes = _MAX_TOTAL_BYTES - total_bytes
            source, media_type = _read_bounded(
                client,
                asset_url,
                check="Frontend asset",
                max_bytes=min(_MAX_ASSET_BYTES, remaining_bytes),
                started=started,
            )
            if media_type not in _JAVASCRIPT_TYPES:
                raise AssetManifestError("Frontend asset has invalid content type")
            total_bytes += len(source)
            if len(source) != declared_size or len(source) > _MAX_ASSET_BYTES:
                raise AssetManifestError("Frontend asset size mismatch")
            if total_bytes > _MAX_TOTAL_BYTES:
                raise AssetManifestError("Frontend asset inventory exceeds total byte limit")
            digest = hashlib.sha256(source).hexdigest()
            if digest != declared_sha256:
                raise AssetManifestError("Frontend asset digest mismatch")
            evidence.append(AssetEvidence(path=path, sha256=digest, size_bytes=len(source)))
            retired_count += _asset_has_retired_literal(source, retired_routes)
    return evidence, retired_count


def run_browser_discovery(
    policy: ProtectedTargetPolicy,
    *,
    app_secret: str | None,
    retired_routes: tuple[RetiredRoute, ...],
) -> BrowserObservation:
    """Exercise deployed frontend discovery in a fresh, cache-busted browser."""
    try:
        from playwright.sync_api import Request, Route, sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency gate has a focused test
        raise AssetManifestError("Python Playwright release-smoke extra is unavailable") from exc

    observed_api: list[tuple[str, str, int | None]] = []
    discovery_with_cursor: list[str] = []
    observed_javascript_paths: set[str] = set()
    off_policy_requests: list[str] = []
    unsafe_methods: list[str] = []
    api_origin = urlsplit(policy.api_origin)
    frontend_origin = urlsplit(policy.frontend_origin)
    allowed_origins = {policy.api_origin, policy.frontend_origin}

    def observe_request(request: Request) -> None:
        parsed = urlsplit(request.url)
        if request.resource_type == "script" and parsed.netloc == frontend_origin.netloc:
            observed_javascript_paths.add(unquote(parsed.path))
        if parsed.path.startswith("/api/v1/"):
            if parsed.scheme != api_origin.scheme or parsed.netloc != api_origin.netloc:
                off_policy_requests.append(parsed.path)
            observed_api.append((request.method.upper(), unquote(parsed.path), None))
            if unquote(parsed.path) in {
                "/api/v1/capabilities",
                "/api/v1/configured-sources",
            } and any(key == "cursor" for key, _value in parse_qsl(parsed.query)):
                discovery_with_cursor.append(unquote(parsed.path))

    def enforce_origin(route: Route, request: Request) -> None:
        parsed = urlsplit(request.url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme in {"http", "https"} and origin not in allowed_origins:
            off_policy_requests.append(parsed.path)
            route.abort()
            return
        if parsed.scheme in {"http", "https"} and request.method.upper() not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            unsafe_methods.append(request.method.upper())
            route.abort()
            return
        route.continue_()

    session_cookie = _browser_session_cookie(policy, app_secret)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            service_workers="block",
            extra_http_headers={
                "Cache-Control": "no-cache, no-store",
                "Pragma": "no-cache",
            },
        )
        if session_cookie is not None:
            context.add_cookies([cast(Any, session_cookie)])
        context.route("**/*", enforce_origin)
        page = context.new_page()
        page.on("request", observe_request)

        def observe_response(response: Any) -> None:
            parsed = urlsplit(response.url)
            if parsed.path.startswith("/api/v1/"):
                key = (response.request.method.upper(), unquote(parsed.path))
                for index, (method, path, status) in enumerate(observed_api):
                    if status is None and (method, path) == key:
                        observed_api[index] = (method, path, response.status)
                        break

        page.on("response", observe_response)
        try:
            navigation = page.goto(
                f"{policy.frontend_origin}/ingest?release-smoke=1",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
        except Exception as exc:
            context.close()
            browser.close()
            raise AssetManifestError("Frontend navigation failed") from exc
        if navigation is None or navigation.status != 200:
            context.close()
            browser.close()
            raise AssetManifestError("Frontend navigation returned an invalid response")
        final_url = urlsplit(page.url)
        if f"{final_url.scheme}://{final_url.netloc}" != policy.frontend_origin:
            context.close()
            browser.close()
            raise AssetManifestError("Frontend navigation escaped the protected origin")
        deadline = time.monotonic() + 20.0
        required_paths = {
            "/api/v1/capabilities",
            "/api/v1/configured-sources",
        }
        while time.monotonic() < deadline:
            observed_paths = {path for _method, path, status in observed_api if status is not None}
            if required_paths <= observed_paths:
                break
            page.wait_for_timeout(100)

        revision = page.locator('meta[name="release-revision"]').get_attribute("content")
        revision_source = page.locator('meta[name="release-revision-source"]').get_attribute(
            "content"
        )
        document_source = page.content().encode("utf-8")
        if len(document_source) > _MAX_DOCUMENT_BYTES:
            context.close()
            browser.close()
            raise AssetManifestError("Frontend document exceeds byte limit")
        context.close()
        browser.close()

    if off_policy_requests:
        raise AssetManifestError("Frontend attempted off-policy network traffic")
    if unsafe_methods:
        raise AssetManifestError("Frontend attempted a non-read-only request")
    for required_path in required_paths:
        matches = [
            (method, status) for method, path, status in observed_api if path == required_path
        ]
        if not matches or any(method != "GET" or status != 200 for method, status in matches):
            raise AssetManifestError(f"Frontend discovery failed for {required_path}")
    if discovery_with_cursor:
        raise AssetManifestError("Frontend first discovery page serialized cursor")
    if revision is None or revision_source is None:
        raise AssetManifestError("Frontend release identity metadata is missing")
    if policy.target != "local":
        if revision != policy.expected_frontend_revision:
            raise AssetManifestError("Frontend release revision mismatch")
        if revision_source not in {
            "railway_commit_sha",
            "github_sha",
            "verified_detached_sha",
        }:
            raise AssetManifestError("Frontend release provenance is untrusted")

    assets, asset_retired_count = load_and_scan_assets(
        frontend_origin=policy.frontend_origin,
        expected_revision=revision,
        retired_routes=retired_routes,
    )
    declared_paths = {asset.path for asset in assets}
    if not observed_javascript_paths.issubset(declared_paths):
        raise AssetManifestError("Observed JavaScript asset is absent from release manifest")
    request_retired_count = sum(
        RetiredRoute(method, path) in retired_routes for method, path, _status in observed_api
    )
    return BrowserObservation(
        revision=revision,
        revision_source=cast(RevisionSource, revision_source),
        assets=tuple(assets),
        retired_route_count=(
            asset_retired_count
            + request_retired_count
            + _asset_has_retired_literal(document_source, retired_routes)
        ),
    )
