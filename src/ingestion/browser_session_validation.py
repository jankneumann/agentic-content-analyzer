"""Value-free validation of a browser session with ONE cheap authenticated request.

Shared by ``aca auth session substack|x`` (:mod:`src.cli.session_commands`) and
the admin browser-session sync endpoint (:mod:`src.api.browser_session_routes`),
so a session is judged by the same request and the same rules whichever way it
arrives.

Each validator takes ``{CREDENTIAL_KEY: value}`` (the keys of
:data:`src.config.credentials.BROWSER_SESSION_CREDENTIALS`) and an
``httpx.Client``, sends exactly one GET, and returns ``None`` when the site
answered 200 with the expected JSON shape. Otherwise it raises
:class:`SessionValidationError`, whose message carries the method, the URL
without its query string and the status code, never a header, a body or a
cookie value. ``httpx.HTTPError`` (the site could not be reached) propagates
unchanged for the caller to classify.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

from src.config.credentials import SUBSTACK_SESSION_COOKIE, X_AUTH_TOKEN, X_CT0
from src.ingestion.x_web import X_ACCOUNT_SETTINGS_URL, x_web_headers

__all__ = [
    "SUBSTACK_SID_COOKIE",
    "SUBSTACK_VALIDATION_URL",
    "VALIDATION_TIMEOUT_S",
    "SessionValidationError",
    "SessionValidator",
    "new_validation_client",
    "require_json_ok",
    "validate_substack_session",
    "validate_x_session",
]

#: Authenticated JSON endpoint the Substack adapter already calls
#: (``SubstackClient._fetch_subscriptions_from_http``). Anonymous or expired
#: sessions get a 401/403 or an HTML page instead of JSON.
SUBSTACK_VALIDATION_URL = "https://substack.com/api/v1/subscriptions"
SUBSTACK_SID_COOKIE = "substack.sid"

VALIDATION_TIMEOUT_S = 15.0

SessionValidator = Callable[[Mapping[str, str], httpx.Client], None]


class SessionValidationError(Exception):
    """The site did not accept the session. Messages never contain cookie values.

    ``reason`` is a stable code: ``http_status`` (non-200), ``not_json`` (usually
    the login page) or ``unexpected_json``. ``status_code`` is the upstream HTTP
    status when there was one.
    """

    def __init__(self, message: str, *, reason: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code

    @property
    def upstream_unavailable(self) -> bool:
        """True when the site failed or throttled, rather than rejecting the session."""
        return self.status_code is not None and (self.status_code >= 500 or self.status_code == 429)


def new_validation_client() -> httpx.Client:
    """The client for the one validation request (no redirects followed).

    A redirect is usually the site bouncing an anonymous session to its login
    page, so it counts as a rejection rather than being followed.
    """
    return httpx.Client(timeout=VALIDATION_TIMEOUT_S, follow_redirects=False)


def require_json_ok(response: httpx.Response, site: str, accept: Callable[[Any], bool]) -> None:
    """Raise unless ``response`` is a 200 carrying the expected JSON shape.

    Messages carry the status code and URL only, never headers or body.
    """
    where = f"{response.request.method} {response.request.url.copy_with(query=None)}"
    if response.status_code != 200:
        raise SessionValidationError(
            f"{site} rejected the session: {where} returned HTTP {response.status_code}",
            reason="http_status",
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except ValueError:
        raise SessionValidationError(
            f"{site} did not accept the session: {where} returned a non-JSON "
            "page (usually the login page)",
            reason="not_json",
            status_code=response.status_code,
        ) from None
    if not accept(data):
        raise SessionValidationError(
            f"{site} did not accept the session: {where} returned unexpected JSON",
            reason="unexpected_json",
            status_code=response.status_code,
        )


def validate_substack_session(values: Mapping[str, str], http: httpx.Client) -> None:
    """One GET of the Substack subscriptions API with ``substack.sid``."""
    cookie = values[SUBSTACK_SESSION_COOKIE]
    response = http.get(
        SUBSTACK_VALIDATION_URL,
        headers={"cookie": f"{SUBSTACK_SID_COOKIE}={cookie}", "accept": "application/json"},
    )
    require_json_ok(response, "Substack", lambda data: isinstance(data, list | dict))


def validate_x_session(values: Mapping[str, str], http: httpx.Client) -> None:
    """One GET of X's account settings with ``auth_token`` + ``ct0``."""
    response = http.get(
        X_ACCOUNT_SETTINGS_URL,
        headers=x_web_headers(values[X_AUTH_TOKEN], values[X_CT0]),
    )
    require_json_ok(
        response, "X", lambda data: isinstance(data, dict) and bool(data.get("screen_name"))
    )
