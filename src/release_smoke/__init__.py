"""Production-safe cross-surface release verification."""

from src.release_smoke.models import ProtectedTargetPolicy
from src.release_smoke.runner import run_api_discovery, run_cli_discovery

__all__ = ["ProtectedTargetPolicy", "run_api_discovery", "run_cli_discovery"]
