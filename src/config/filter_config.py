"""Filter configuration loader.

Resolves IngestionFilterService configuration from the three-layer override
stack: settings/filtering.yaml defaults -> per-persona filter_profile -> per-
source `defaults.filter`. The DB-override layer is a hook reserved for a
future change; today it's a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from src.config.config_registry import ConfigDomain, get_config_registry


FILTERING_DOMAIN = "filtering"


def _ensure_domain_registered() -> None:
    registry = get_config_registry()
    if FILTERING_DOMAIN not in registry.registered_domains:
        registry.register(ConfigDomain(name=FILTERING_DOMAIN, yaml_file="filtering.yaml"))


@dataclass(frozen=True)
class BorderlineBand:
    low: float = 0.45
    high: float = 0.65

    def classify(self, score: float) -> str:
        """Return 'below' | 'borderline' | 'above'."""
        if score < self.low:
            return "below"
        if score > self.high:
            return "above"
        return "borderline"


@dataclass(frozen=True)
class FilterConfig:
    enabled: bool = True
    strict: bool = False
    min_word_count: int = 40
    allowed_languages: tuple[str, ...] = ("en",)
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_enabled: bool = True
    borderline_band: BorderlineBand = field(default_factory=BorderlineBand)
    priority_high_threshold: float = 0.65
    priority_low_threshold: float = 0.45
    excerpt_chars: int = 1200

    # Per-persona overrides (populated from persona YAML by the loader).
    interest_description: str | None = None
    must_include: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()

    def priority_bucket(self, score: float) -> str:
        if score >= self.priority_high_threshold:
            return "high"
        if score < self.priority_low_threshold:
            return "low"
        return "normal"


def load_defaults() -> dict[str, Any]:
    _ensure_domain_registered()
    return get_config_registry().get_raw(FILTERING_DOMAIN) or {}


def _coerce_band(raw: Any, fallback: BorderlineBand) -> BorderlineBand:
    if not isinstance(raw, dict):
        return fallback
    return BorderlineBand(
        low=float(raw.get("low", fallback.low)),
        high=float(raw.get("high", fallback.high)),
    )


def resolve_filter_config(
    *,
    persona: dict[str, Any] | None = None,
    source_overrides: dict[str, Any] | None = None,
) -> FilterConfig:
    """Compose a FilterConfig from the three override layers.

    Args:
        persona: Parsed persona YAML (the full document), or None.
        source_overrides: The `defaults.filter` block from a sources.d entry, or None.
    """
    raw = load_defaults()
    tiers = raw.get("tiers") or {}
    heuristic = tiers.get("heuristic") or {}
    embedding = tiers.get("embedding") or {}
    llm = tiers.get("llm") or {}

    band = _coerce_band(raw.get("borderline_band"), BorderlineBand())

    cfg = FilterConfig(
        enabled=bool(raw.get("enabled", True)),
        strict=bool(raw.get("strict", False)),
        min_word_count=int(heuristic.get("min_word_count", 40)),
        allowed_languages=tuple(heuristic.get("allowed_languages") or ["en"]),
        embedding_provider=embedding.get("provider"),
        embedding_model=embedding.get("model"),
        llm_enabled=bool(llm.get("enabled", True)),
        borderline_band=band,
        priority_high_threshold=float(
            (raw.get("priority_buckets") or {}).get("high_threshold", band.high)
        ),
        priority_low_threshold=float(
            (raw.get("priority_buckets") or {}).get("low_threshold", band.low)
        ),
        excerpt_chars=int(raw.get("excerpt_chars", 1200)),
    )

    if persona:
        profile = persona.get("filter_profile") or {}
        cfg = _apply_persona_overrides(cfg, persona, profile)

    if source_overrides:
        cfg = _apply_source_overrides(cfg, source_overrides)

    return cfg


def _apply_persona_overrides(
    base: FilterConfig, persona: dict[str, Any], profile: dict[str, Any]
) -> FilterConfig:
    interest = profile.get("interest_description") or persona.get("description")
    band_raw = profile.get("borderline_band")
    band = _coerce_band(band_raw, base.borderline_band) if band_raw else base.borderline_band
    return replace(
        base,
        min_word_count=int(profile.get("min_word_count", base.min_word_count)),
        allowed_languages=tuple(profile.get("languages") or base.allowed_languages),
        borderline_band=band,
        priority_high_threshold=band.high,
        priority_low_threshold=band.low,
        interest_description=interest,
        must_include=tuple(profile.get("must_include") or ()),
        must_exclude=tuple(profile.get("must_exclude") or ()),
    )


def _apply_source_overrides(base: FilterConfig, overrides: dict[str, Any]) -> FilterConfig:
    if overrides.get("enabled") is False:
        return replace(base, enabled=False)
    if "override_tier_3" in overrides:
        return replace(base, llm_enabled=bool(overrides["override_tier_3"]))
    return base
