"""Admin endpoint the Chrome extension calls to push a fresh browser session.

``PUT /api/v1/browser-sessions/substack`` and ``PUT /api/v1/browser-sessions/x``
accept only the site's cookies, validate them server-side with the same single
authenticated request as ``aca auth session``, and write them to OpenBao in one
KV v2 merge-PATCH (see :mod:`src.services.browser_session_sync`).

Authentication: the ``X-Admin-Key`` header only. :func:`verify_admin_key` also
admits a web-UI session cookie and, in unconfigured development, no credential
at all; neither is accepted for writing a credential. Every request is audited
by ``AuditMiddleware`` (operation ``browser_sessions.sync``, ``admin_key_fp``
from the raw header, accepted or not); handler notes add the site, the outcome
and key names, never a value.

Errors are ``application/problem+json`` (the path is registered in
``_PROBLEM_PATH_PREFIXES``), so request-validation failures report the field
path and error code but never echo the submitted input.

Rate limit: an in-process sliding window per client IP
(:class:`~src.api.rate_limiter_base.EndpointRateLimiter`). Each accepted call
costs one request to Substack or X and one OpenBao write, so a looping client
must not turn the API into a hammer against the operator's own accounts.

These routes are not part of the canonical workflow contract
(``openspec/contracts/content-workflows/openapi/v1.yaml``), which declares only
the durable-operation surface; like ``/api/v1/sources`` writes and
``/api/v1/auth``, they are admin routes documented by FastAPI's OpenAPI only.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.api.dependencies import api_key_header, verify_admin_key
from src.api.middleware.audit import audited
from src.api.middleware.error_handler import _problem_body
from src.api.rate_limiter_base import EndpointRateLimiter
from src.config.credentials import SUBSTACK_SESSION_COOKIE, X_AUTH_TOKEN, X_CT0
from src.ingestion.browser_session_validation import SessionValidationError
from src.services import browser_session_sync as sync_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/browser-sessions", tags=["browser-sessions"])

#: Browsers cap one cookie at 4096 bytes (name + value).
MAX_COOKIE_VALUE_LENGTH = 4096
#: Two cookies plus JSON framing fit well inside this.
MAX_BODY_BYTES = 16 * 1024
#: RFC 6265 ``cookie-octet``: printable US-ASCII except space, ``"``, ``,``, ``;``, ``\\``.
#: Besides rejecting non-cookies, this keeps CR/LF and non-ASCII out of the
#: validation request's headers, whose encoding errors would quote the value.
_COOKIE_OCTETS = re.compile(r"[\x21\x23-\x2B\x2D-\x3A\x3C-\x5B\x5D-\x7E]+")

browser_session_rate_limiter = EndpointRateLimiter(max_requests=10, window_seconds=300)

_PROBLEM_MEDIA_TYPE = "application/problem+json"
_AUDIT_OPERATION = "browser_sessions.sync"


# ============================================================================
# Request / response models
# ============================================================================


def _cookie_field(cookie: str) -> Any:
    return Field(
        min_length=1,
        max_length=MAX_COOKIE_VALUE_LENGTH,
        repr=False,
        description=f"Value of the `{cookie}` cookie as the browser holds it.",
    )


class _SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def _cookie_octets(cls, value: SecretStr) -> SecretStr:
        # Value-free message: the problem body echoes it, the input never.
        if not _COOKIE_OCTETS.fullmatch(value.get_secret_value()):
            raise ValueError('must be a cookie value (printable ASCII, no space ; , " or \\)')
        return value

    def credential_values(self) -> dict[str, str]:  # pragma: no cover - abstract
        raise NotImplementedError


class SubstackSessionSyncRequest(_SessionBody):
    """The Substack session cookie ``substack.sid``."""

    substack_sid: SecretStr = _cookie_field("substack.sid")

    def credential_values(self) -> dict[str, str]:
        return {SUBSTACK_SESSION_COOKIE: self.substack_sid.get_secret_value()}


class XSessionSyncRequest(_SessionBody):
    """The X session cookie pair, written together."""

    auth_token: SecretStr = _cookie_field("auth_token")
    ct0: SecretStr = _cookie_field("ct0")

    def credential_values(self) -> dict[str, str]:
        return {
            X_AUTH_TOKEN: self.auth_token.get_secret_value(),
            X_CT0: self.ct0.get_secret_value(),
        }


class BrowserSessionSyncResponse(BaseModel):
    """What was written to OpenBao. Never carries a value."""

    model_config = ConfigDict(extra="forbid")

    site: Literal["substack", "x"]
    keys_written: list[str] = Field(
        description="OpenBao keys patched: the credential keys and their `_SAVED_AT` siblings."
    )
    saved_at: datetime = Field(description="The `<KEY>_SAVED_AT` timestamp written (UTC).")


_PROBLEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "title", "status", "detail"],
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "code": {"type": "string"},
    },
}


def _problem_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {_PROBLEM_MEDIA_TYPE: {"schema": _PROBLEM_SCHEMA}},
    }


_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _problem_response("No `X-Admin-Key` header (session and dev-bypass auth are refused)"),
    403: _problem_response("Invalid `X-Admin-Key`"),
    413: _problem_response("Request body larger than the limit"),
    422: _problem_response(
        "Body invalid (unknown field, bad cookie value) or the site refused the session "
        "(`code: session_invalid`); nothing was written"
    ),
    429: _problem_response("Too many sync attempts from this client"),
    502: _problem_response(
        "The site could not validate the session (`session_validation_unavailable`) or "
        "OpenBao refused the write (`openbao_write_failed`)"
    ),
    503: _problem_response("OpenBao is not configured on this server (`openbao_not_configured`)"),
}


# ============================================================================
# Dependencies
# ============================================================================


async def require_admin_key_header(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> None:
    """``verify_admin_key``, then refuse anything but a valid ``X-Admin-Key``."""
    verified = await verify_admin_key(request, api_key)
    if not api_key or verified != api_key:
        raise HTTPException(
            status_code=401,
            detail="Browser-session sync requires a valid X-Admin-Key header.",
        )


def enforce_body_limit(request: Request) -> None:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=f"Request body exceeds {MAX_BODY_BYTES} bytes.")


def enforce_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if browser_session_rate_limiter.is_limited(client_ip):
        retry_after = browser_session_rate_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many browser-session sync attempts; try again later.",
            headers={"Retry-After": str(retry_after)},
        )


_DEPENDENCIES = [
    Depends(require_admin_key_header),
    Depends(enforce_body_limit),
    Depends(enforce_rate_limit),
]


# ============================================================================
# Handler
# ============================================================================


def _problem(status: int, title: str, code: str, detail: str, **extra: Any) -> JSONResponse:
    body = _problem_body(title=title, status=status, detail=detail, code=code)
    body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type=_PROBLEM_MEDIA_TYPE)


def _note(request: Request, site: str, outcome: str, **extra: Any) -> None:
    request.state.audit_notes = {"site": site, "outcome": outcome, **extra}


def _sync(request: Request, site: Literal["substack", "x"], body: _SessionBody) -> Any:
    try:
        result = sync_service.sync_browser_session(site, body.credential_values())
    except sync_service.BrowserSessionStoreUnavailableError as exc:
        _note(request, site, "openbao_not_configured")
        return _problem(
            503,
            "Service Unavailable",
            "openbao_not_configured",
            str(exc),
            missing=exc.missing,
        )
    except SessionValidationError as exc:
        _note(request, site, "session_invalid", reason=exc.reason)
        return _problem(
            422,
            "Unprocessable Entity",
            "session_invalid",
            f"{exc} Nothing was written.",
            reason=exc.reason,
        )
    except sync_service.BrowserSessionUnreachableError as exc:
        _note(request, site, "session_validation_unavailable")
        return _problem(
            502,
            "Bad Gateway",
            "session_validation_unavailable",
            f"{exc} Nothing was written.",
        )
    except sync_service.BrowserSessionWriteError as exc:
        _note(request, site, "openbao_write_failed")
        return _problem(502, "Bad Gateway", "openbao_write_failed", str(exc))

    _note(request, site, "written", keys=result.keys_written)
    return BrowserSessionSyncResponse(
        site=site, keys_written=result.keys_written, saved_at=result.saved_at
    )


@router.put(
    "/substack",
    response_model=BrowserSessionSyncResponse,
    responses=_RESPONSES,
    dependencies=_DEPENDENCIES,
    operation_id="syncSubstackBrowserSession",
    summary="Store a validated Substack session in OpenBao",
)
@audited(operation=_AUDIT_OPERATION)
def sync_substack_session(request: Request, body: SubstackSessionSyncRequest) -> Any:
    """Validate ``substack.sid`` and PATCH ``SUBSTACK_SESSION_COOKIE`` (+ ``_SAVED_AT``)."""
    return _sync(request, "substack", body)


@router.put(
    "/x",
    response_model=BrowserSessionSyncResponse,
    responses=_RESPONSES,
    dependencies=_DEPENDENCIES,
    operation_id="syncXBrowserSession",
    summary="Store a validated X session in OpenBao",
)
@audited(operation=_AUDIT_OPERATION)
def sync_x_session(request: Request, body: XSessionSyncRequest) -> Any:
    """Validate ``auth_token`` + ``ct0`` and PATCH ``X_AUTH_TOKEN`` + ``X_CT0`` in one write."""
    return _sync(request, "x", body)
