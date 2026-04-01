"""
Connection Status API Routes — Redirect to /api/v1/status/connections

This endpoint now redirects to the new status endpoint.
The redirect preserves query parameters and will be removed after one release cycle.
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api/v1/settings/connections", tags=["settings"])


@router.get(
    "",
    response_class=RedirectResponse,
    status_code=307,
)
async def get_connection_status_redirect(request: Request) -> RedirectResponse:
    """Redirect to new status endpoint at /api/v1/status/connections.

    Returns 307 Temporary Redirect to preserve request method and headers.
    Query parameters are forwarded. This redirect will be removed after one release cycle.
    """
    target = "/api/v1/status/connections"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=307)
