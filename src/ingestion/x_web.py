"""Constants and request headers for X's own web-app API (x.com/i/api/...).

X's web client authenticates every API call with two things at once:

* a **public bearer token** embedded in the x.com JavaScript bundle. It is the
  same for every user and every browser, identifies the web *application*, and
  grants nothing on its own. It is not a secret, which is why it is a constant;
* the **operator's session**: the ``auth_token`` and ``ct0`` cookies, with
  ``ct0`` echoed in the ``x-csrf-token`` header (double-submit CSRF).

This module is the single place those facts live, shared by the session
capture command (``aca auth session x``, which validates a freshly captured
pair) and the X bookmarks adapter. The header shape mirrors the upstream
exporter's ``buildHeaders`` (github.com/displace-agency/x-bookmarks-exporter,
``src/api.ts``).

The cookie values passed to :func:`x_web_headers` are secrets: never log the
returned mapping.
"""

from __future__ import annotations

#: Public bearer token of X's web app (not an account credential). If X rotates
#: it, every request fails with 401 regardless of the cookies; update it here.
X_WEB_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

#: Desktop Chrome user agent the web app's own requests carry.
X_WEB_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

#: Cheapest authenticated read: returns the logged-in account's settings JSON
#: (``screen_name`` among others) and 401/403 when the session is not valid.
X_ACCOUNT_SETTINGS_URL = "https://x.com/i/api/1.1/account/settings.json"

#: Cookie names of an X web session, in the order they are written.
X_AUTH_TOKEN_COOKIE = "auth_token"
X_CT0_COOKIE = "ct0"


def x_web_headers(auth_token: str, ct0: str, *, referer: str = "https://x.com/") -> dict[str, str]:
    """Headers for an authenticated call to ``https://x.com/i/api/...``.

    Contains the cookie values: the result must never be logged or echoed.
    """
    return {
        "authorization": f"Bearer {X_WEB_BEARER_TOKEN}",
        "cookie": f"{X_AUTH_TOKEN_COOKIE}={auth_token}; {X_CT0_COOKIE}={ct0}",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "referer": referer,
        "user-agent": X_WEB_USER_AGENT,
    }
