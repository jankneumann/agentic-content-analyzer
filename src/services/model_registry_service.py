"""Shared service for querying the model registry and triggering pricing refreshes.

Provides a unified interface used by CLI, API, and MCP layers.
All methods return Pydantic models for easy serialization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.config.models import (
    MODEL_REGISTRY,
    PROVIDER_MODEL_CONFIGS,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response models (shared across CLI, API, MCP)
# ---------------------------------------------------------------------------


class ProviderPricingInfo(BaseModel):
    """Pricing details for a model on a specific provider."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_model_id: str
    cost_per_mtok_input: float
    cost_per_mtok_output: float
    context_window: int
    max_output_tokens: int
    tier: str


class ModelSummary(BaseModel):
    """Brief model info for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    family: str
    supports_vision: bool = False
    supports_video: bool = False
    supports_audio: bool = False
    default_version: str | None = None
    providers: list[str] = []
    cost_per_mtok_input: float | None = None
    cost_per_mtok_output: float | None = None


class ModelDetail(BaseModel):
    """Full model info with per-provider pricing."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    family: str
    supports_vision: bool = False
    supports_video: bool = False
    supports_audio: bool = False
    default_version: str | None = None
    provider_pricing: list[ProviderPricingInfo] = []


class PricingDiffItem(BaseModel):
    """A single field-level change detected during refresh."""

    provider_key: str
    field: str
    current_value: Any
    extracted_value: Any


class NewModelItem(BaseModel):
    """A model found on a pricing page but not in the registry."""

    model_id: str
    provider_model_id: str
    cost_per_mtok_input: float
    cost_per_mtok_output: float
    notes: str = ""


class PricingRefreshReport(BaseModel):
    """Result of a pricing refresh operation."""

    providers_fetched: list[str] = []
    providers_failed: list[str] = []
    diffs: list[PricingDiffItem] = []
    new_models: list[NewModelItem] = []
    errors: list[str] = []
    applied: bool = False
    timestamp: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.diffs) or bool(self.new_models)


# ---------------------------------------------------------------------------
# Module-level state for last refresh (Design Decision D4)
# ---------------------------------------------------------------------------
_last_refresh_report: PricingRefreshReport | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ModelRegistryService:
    """Query the model registry and trigger pricing refreshes.

    All methods are synchronous for registry queries (in-memory data)
    and async for pricing refresh (HTTP + LLM calls).
    """

    def list_models(self, family: str | None = None) -> list[ModelSummary]:
        """List all models, optionally filtered by family.

        Args:
            family: Filter to this model family (e.g., "claude", "gemini").

        Returns:
            List of ModelSummary objects.
        """
        results = []
        for model_id, info in MODEL_REGISTRY.items():
            if family and info.family.value != family:
                continue

            providers = []
            cost_input = None
            cost_output = None
            for (mid, prov), pmc in PROVIDER_MODEL_CONFIGS.items():
                if mid == model_id:
                    providers.append(prov.value)
                    if cost_input is None:
                        cost_input = pmc.cost_per_mtok_input
                        cost_output = pmc.cost_per_mtok_output

            results.append(
                ModelSummary(
                    id=model_id,
                    name=info.name,
                    family=info.family.value,
                    supports_vision=info.supports_vision,
                    supports_video=info.supports_video,
                    supports_audio=info.supports_audio,
                    default_version=info.default_version,
                    providers=sorted(providers),
                    cost_per_mtok_input=cost_input,
                    cost_per_mtok_output=cost_output,
                )
            )
        return results

    def get_model(self, model_id: str) -> ModelDetail | None:
        """Get detailed model info with per-provider pricing.

        Args:
            model_id: Family-based model ID (e.g., "claude-sonnet-4-5").

        Returns:
            ModelDetail or None if not found.
        """
        info = MODEL_REGISTRY.get(model_id)
        if not info:
            return None

        pricing = []
        for (mid, prov), pmc in PROVIDER_MODEL_CONFIGS.items():
            if mid == model_id:
                pricing.append(
                    ProviderPricingInfo(
                        provider=prov.value,
                        provider_model_id=pmc.provider_model_id,
                        cost_per_mtok_input=pmc.cost_per_mtok_input,
                        cost_per_mtok_output=pmc.cost_per_mtok_output,
                        context_window=pmc.context_window,
                        max_output_tokens=pmc.max_output_tokens,
                        tier=pmc.tier,
                    )
                )

        return ModelDetail(
            id=model_id,
            name=info.name,
            family=info.family.value,
            supports_vision=info.supports_vision,
            supports_video=info.supports_video,
            supports_audio=info.supports_audio,
            default_version=info.default_version,
            provider_pricing=sorted(pricing, key=lambda p: p.provider),
        )

    async def refresh_pricing(
        self,
        providers: list[str] | None = None,
        dry_run: bool = True,
    ) -> PricingRefreshReport:
        """Trigger pricing extraction from provider pages.

        Args:
            providers: Limit to specific providers. None = all.
            dry_run: If True, only report diffs without modifying models.yaml.

        Returns:
            PricingRefreshReport with diffs and status.
        """
        global _last_refresh_report

        from src.services.model_pricing_extractor import ModelPricingExtractor

        extractor = ModelPricingExtractor()
        report = await extractor.run(providers=providers, dry_run=dry_run)

        result = PricingRefreshReport(
            providers_fetched=report.providers_fetched,
            providers_failed=report.providers_failed,
            diffs=[
                PricingDiffItem(
                    provider_key=d.provider_key,
                    field=d.field,
                    current_value=d.current_value,
                    extracted_value=d.extracted_value,
                )
                for d in report.diffs
            ],
            new_models=[
                NewModelItem(
                    model_id=m.model_id,
                    provider_model_id=m.provider_model_id,
                    cost_per_mtok_input=m.cost_per_mtok_input,
                    cost_per_mtok_output=m.cost_per_mtok_output,
                    notes=m.notes,
                )
                for m in report.new_models
            ],
            errors=report.extraction_errors,
            applied=report.applied,
            timestamp=datetime.now(UTC).isoformat(),
        )

        _last_refresh_report = result
        return result

    def get_last_refresh(self) -> PricingRefreshReport | None:
        """Get the last pricing refresh report, if any."""
        return _last_refresh_report
