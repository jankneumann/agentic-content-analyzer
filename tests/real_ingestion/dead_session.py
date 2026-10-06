"""A real Substack adapter whose browser session the remote site refuses.

Network-free: Substack answers from an ``httpx.MockTransport`` that treats every
cookie as logged out, and the credential provider reads an in-memory OpenBao
double. What runs is the genuine ``SubstackContentIngestionService`` fail-closed
branch (probe, one refresh, one retry, ``SessionExpiredError``), so the
``IngestionResponse`` the durable workflow receives is the adapter's own.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import httpx

from src.config.credentials import SUBSTACK_SESSION_COOKIE, CredentialProvider
from src.config.sources import SubstackSource
from src.ingestion.commands import IngestCommandBase
from src.ingestion.result import IngestionResponse
from src.ingestion.substack import SubstackClient, SubstackContentIngestionService

#: A recognisable value no alert, log, or artifact may ever contain.
DEAD_SUBSTACK_COOKIE = "sid-dead-sentinel-7c1f0e"


def _refuse_every_session(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"error": "Not authorized"})


def dead_substack_session_orchestrator(
    cookie: str = DEAD_SUBSTACK_COOKIE,
) -> Callable[[IngestCommandBase], IngestionResponse]:
    """Return a registry orchestrator that runs the real adapter against a dead session."""

    cache = {SUBSTACK_SESSION_COOKIE: cookie}
    provider = CredentialProvider(
        settings_factory=lambda: SimpleNamespace(
            substack_session_cookie=None, x_auth_token=None, x_ct0=None
        ),
        bao_reader=lambda: dict(cache),
        bao_refresher=lambda **_kwargs: False,
    )

    def orchestrator(_command: IngestCommandBase) -> IngestionResponse:
        service = SubstackContentIngestionService(credentials=provider)
        service.client.close()
        service.client = SubstackClient(
            credentials=provider,
            http_client=httpx.Client(transport=httpx.MockTransport(_refuse_every_session)),
            request_delay_s=0.0,
        )
        try:
            return service.ingest_content(
                sources=[
                    SubstackSource(name="TheSequence", url="https://thesequence.substack.com")
                ],
                max_entries_per_source=2,
            )
        finally:
            service.close()

    return orchestrator
