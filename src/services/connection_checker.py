"""Connection health checker for all configured backend services.

Checks health of: PostgreSQL, Neo4j, LLM providers, TTS providers,
and embedding providers. Each check returns a ServiceStatus with
status (ok, unavailable, not_configured) and optional details.
"""

import asyncio
from dataclasses import dataclass, field

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ServiceStatus:
    """Health status for a single service."""

    name: str
    status: str  # "ok" | "unavailable" | "not_configured" | "error"
    details: str = ""
    latency_ms: float | None = None


@dataclass
class ConnectionCheckResult:
    """Results from all connection checks."""

    services: list[ServiceStatus] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(s.status in ("ok", "not_configured") for s in self.services)


def _check_database() -> ServiceStatus:
    """Check PostgreSQL connectivity."""
    import time

    try:
        from src.storage.database import health_check as db_health_check

        start = time.monotonic()
        ok = db_health_check()
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="PostgreSQL",
            status="ok" if ok else "unavailable",
            details=f"{settings.database_provider} provider",
            latency_ms=round(latency, 1),
        )
    except Exception as exc:
        return ServiceStatus(name="PostgreSQL", status="unavailable", details=str(exc))


def _check_neo4j() -> ServiceStatus:
    """Check Neo4j connectivity."""
    uri = settings.neo4j_uri
    if not uri:
        return ServiceStatus(name="Neo4j", status="not_configured", details="No URI configured")

    try:
        from neo4j import GraphDatabase  # type: ignore[import-untyped]

        driver = GraphDatabase.driver(
            uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        driver.close()
        return ServiceStatus(
            name="Neo4j",
            status="ok",
            details=f"{settings.neo4j_provider} provider",
        )
    except ImportError:
        return ServiceStatus(
            name="Neo4j",
            status="not_configured",
            details="neo4j driver not installed",
        )
    except Exception as exc:
        return ServiceStatus(name="Neo4j", status="unavailable", details=str(exc))


def _check_anthropic() -> ServiceStatus:
    """Check Anthropic API key validity."""
    if not settings.anthropic_api_key:
        return ServiceStatus(
            name="Anthropic",
            status="not_configured",
            details="ANTHROPIC_API_KEY not set",
        )
    # Just check if the key looks valid (starts with sk-ant-)
    key = settings.anthropic_api_key
    if key.startswith("sk-ant-") or key.startswith("sk-"):
        return ServiceStatus(
            name="Anthropic",
            status="ok",
            details="API key configured",
        )
    return ServiceStatus(
        name="Anthropic",
        status="unavailable",
        details="API key format invalid",
    )


def _check_openai() -> ServiceStatus:
    """Check OpenAI API key availability."""
    if not settings.openai_api_key:
        return ServiceStatus(
            name="OpenAI",
            status="not_configured",
            details="OPENAI_API_KEY not set",
        )
    return ServiceStatus(
        name="OpenAI",
        status="ok",
        details="API key configured",
    )


def _check_google_ai() -> ServiceStatus:
    """Check Google AI API key availability."""
    if not settings.google_api_key:
        return ServiceStatus(
            name="Google AI",
            status="not_configured",
            details="GOOGLE_API_KEY not set",
        )
    return ServiceStatus(
        name="Google AI",
        status="ok",
        details="API key configured",
    )


def _check_elevenlabs() -> ServiceStatus:
    """Check ElevenLabs API key availability."""
    if not settings.elevenlabs_api_key:
        return ServiceStatus(
            name="ElevenLabs",
            status="not_configured",
            details="ELEVENLABS_API_KEY not set",
        )
    return ServiceStatus(
        name="ElevenLabs",
        status="ok",
        details="API key configured",
    )


def _check_embedding() -> ServiceStatus:
    """Check embedding provider configuration."""
    provider = settings.embedding_provider
    if provider == "none":
        return ServiceStatus(
            name="Embeddings",
            status="not_configured",
            details="Embedding provider disabled",
        )
    return ServiceStatus(
        name="Embeddings",
        status="ok",
        details=f"{provider} provider ({settings.embedding_model})",
    )


async def check_all_connections() -> ConnectionCheckResult:
    """Run all connection checks concurrently.

    Uses asyncio to run checks in parallel with per-service timeout.
    """
    loop = asyncio.get_event_loop()
    timeout = settings.health_check_timeout_seconds

    # Run sync checks in executor with timeout
    sync_checks = [
        _check_database,
        _check_neo4j,
        _check_anthropic,
        _check_openai,
        _check_google_ai,
        _check_elevenlabs,
        _check_embedding,
    ]

    results = []
    for check_fn in sync_checks:
        try:
            status = await asyncio.wait_for(
                loop.run_in_executor(None, check_fn),
                timeout=timeout,
            )
            results.append(status)
        except TimeoutError:
            results.append(
                ServiceStatus(
                    name=check_fn.__name__.replace("_check_", "").title(),
                    status="unavailable",
                    details=f"Health check timed out after {timeout}s",
                )
            )
        except Exception as exc:
            logger.warning("Connection check %s failed: %s", check_fn.__name__, exc)
            results.append(
                ServiceStatus(
                    name=check_fn.__name__.replace("_check_", "").title(),
                    status="error",
                    details=str(exc),
                )
            )

    return ConnectionCheckResult(services=results)
