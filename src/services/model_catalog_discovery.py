"""Live provider model-catalog discovery.

Enumerates provider model catalogs via their list-models APIs and reports models
that are not yet in the registry. The SDK calls are isolated in small per-provider
methods so they can be mocked in tests; the diff logic (`find_candidates`) is pure.

See openspec/changes/auto-update-model-registry/.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.config.models import PROVIDER_MODEL_CONFIGS, Provider
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Provider -> environment variables that hold an API key (first match wins).
PROVIDER_API_KEYS: dict[str, list[str]] = {
    Provider.GOOGLE_AI.value: ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    Provider.ANTHROPIC.value: ["ANTHROPIC_API_KEY"],
    Provider.OPENAI.value: ["OPENAI_API_KEY"],
}


@dataclass(frozen=True)
class ModelCandidate:
    """A catalog model not present in the registry."""

    provider: str
    model_id: str  # the provider's catalog id (e.g. "gemini-3.1-flash-lite")
    source: str = "api"  # "api" | "scrape"


@dataclass
class DiscoveryReport:
    candidates: list[ModelCandidate] = field(default_factory=list)
    providers_checked: list[str] = field(default_factory=list)
    providers_failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def known_provider_model_ids(provider: str) -> set[str]:
    """The set of provider_model_id values already in the registry for a provider."""
    known: set[str] = set()
    for (_model_id, prov), pmc in PROVIDER_MODEL_CONFIGS.items():
        if prov.value == provider:
            known.add(pmc.provider_model_id)
    return known


def find_candidates(catalog_ids: set[str], known_ids: set[str]) -> list[str]:
    """Pure diff: catalog ids not already known to the registry, sorted."""
    return sorted(catalog_ids - known_ids)


def _api_key_for(provider: str) -> str | None:
    for env in PROVIDER_API_KEYS.get(provider, []):
        value = os.environ.get(env)
        if value:
            return value
    return None


class ModelCatalogDiscovery:
    """Discover newly-released models from live provider catalogs."""

    def discover(self, providers: list[str] | None = None) -> DiscoveryReport:
        """Enumerate catalogs and report models absent from the registry.

        Providers without a configured API key are skipped (recorded under
        ``providers_failed``) rather than failing the whole run.
        """
        targets = providers or list(PROVIDER_API_KEYS)
        report = DiscoveryReport()

        enumerators = {
            Provider.GOOGLE_AI.value: self._list_google,
            Provider.ANTHROPIC.value: self._list_anthropic,
            Provider.OPENAI.value: self._list_openai,
        }

        for provider in targets:
            key = _api_key_for(provider)
            if not key:
                logger.info(f"No API key for {provider}; skipping catalog discovery")
                report.providers_failed.append(provider)
                continue

            enumerator = enumerators.get(provider)
            if enumerator is None:
                report.providers_failed.append(provider)
                report.errors.append(f"No catalog enumerator for provider {provider}")
                continue

            try:
                catalog = set(enumerator(key))
            except Exception as e:  # network / auth / SDK errors degrade gracefully
                logger.warning(f"Catalog discovery failed for {provider}: {e}")
                report.providers_failed.append(provider)
                report.errors.append(f"{provider}: {e}")
                continue

            report.providers_checked.append(provider)
            for model_id in find_candidates(catalog, known_provider_model_ids(provider)):
                report.candidates.append(ModelCandidate(provider=provider, model_id=model_id))

        return report

    # --- Per-provider SDK seams (mocked in tests) ---

    def _list_google(self, api_key: str) -> list[str]:
        from google import genai

        client = genai.Client(api_key=api_key)
        ids: list[str] = []
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            # genai returns names like "models/gemini-2.5-flash"
            ids.append(name.split("/")[-1] if "/" in name else name)
        return [i for i in ids if i]

    def _list_anthropic(self, api_key: str) -> list[str]:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        return [m.id for m in client.models.list() if getattr(m, "id", None)]

    def _list_openai(self, api_key: str) -> list[str]:
        import openai

        client = openai.OpenAI(api_key=api_key)
        return [m.id for m in client.models.list() if getattr(m, "id", None)]
