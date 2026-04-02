"""Automated model pricing extraction from provider pricing pages.

Reuses the existing URL fetcher + Trafilatura pipeline to scrape provider
pricing pages, then sends the extracted markdown to an LLM to produce
structured pricing data that can be diffed against models.yaml.

Usage:
    from src.services.model_pricing_extractor import ModelPricingExtractor

    extractor = ModelPricingExtractor()
    report = await extractor.run(dry_run=True)  # preview changes
    report = await extractor.run(dry_run=False)  # apply to models.yaml
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from src.config.models import (
    ModelConfig,
    Provider,
    get_model_config,
    load_model_registry,
)
from src.services.llm_router import LLMRouter
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Timeout for fetching pricing pages (some are slow / JS-heavy)
FETCH_TIMEOUT = 45.0

# Max content size (5 MB — pricing pages are text-heavy)
MAX_CONTENT_SIZE = 5 * 1024 * 1024

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Known pricing page URLs per provider
# ---------------------------------------------------------------------------
PRICING_SOURCES: dict[str, list[str]] = {
    "anthropic": [
        "https://docs.anthropic.com/en/docs/about-claude/models",
    ],
    "openai": [
        "https://platform.openai.com/docs/pricing",
    ],
    "google_ai": [
        "https://ai.google.dev/gemini-api/docs/pricing",
    ],
    "aws_bedrock": [
        "https://aws.amazon.com/bedrock/pricing/",
    ],
}

# Provider key → Provider enum mapping
_PROVIDER_KEY_MAP: dict[str, list[Provider]] = {
    "anthropic": [Provider.ANTHROPIC],
    "openai": [Provider.OPENAI],
    "google_ai": [Provider.GOOGLE_AI],
    "aws_bedrock": [Provider.AWS_BEDROCK],
}

# Model used for extraction (cheap + fast — structured extraction task)
EXTRACTION_MODEL = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class ExtractedModel:
    """A single model's pricing data extracted from a provider page."""

    model_id: str  # e.g. "claude-sonnet-4-5"
    provider_model_id: str  # e.g. "claude-sonnet-4-5-20250929"
    cost_per_mtok_input: float
    cost_per_mtok_output: float
    context_window: int
    max_output_tokens: int
    tier: str = "standard"
    notes: str = ""  # e.g. "new model not in registry"


@dataclass
class PricingDiff:
    """A single field-level diff between current and extracted values."""

    provider_key: str  # e.g. "anthropic.claude-sonnet-4-5"
    field: str
    current_value: Any
    extracted_value: Any


@dataclass
class PricingReport:
    """Full extraction report across all providers."""

    diffs: list[PricingDiff] = field(default_factory=list)
    new_models: list[ExtractedModel] = field(default_factory=list)
    providers_fetched: list[str] = field(default_factory=list)
    providers_failed: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    applied: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(self.diffs) or bool(self.new_models)


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """\
You are a structured data extractor. Your job is to extract model pricing \
information from a provider's pricing page content.

You will receive:
1. Markdown content scraped from a pricing page
2. The provider name
3. The current registry entries for that provider (so you know what to compare)

Extract ALL models you can find on the page. For each model return a JSON object with:
- model_id: The family-based model ID (e.g. "claude-sonnet-4-5", NOT the versioned API ID)
- provider_model_id: The exact API identifier including version (e.g. "claude-sonnet-4-5-20250929")
- cost_per_mtok_input: Cost in USD per million input tokens
- cost_per_mtok_output: Cost in USD per million output tokens
- context_window: Maximum context window in tokens
- max_output_tokens: Maximum output tokens
- tier: Pricing tier (usually "standard")
- notes: Any relevant notes (e.g. "pricing differs above 200k context")

IMPORTANT RULES:
- Prices should be in USD per MILLION tokens. Convert if the page shows per-1K or per-1M.
- If a page shows per-1K pricing, multiply by 1000 to get per-million.
- If a page shows per-token pricing, multiply by 1,000,000.
- Only extract models relevant to text/vision LLM use (skip embedding-only, fine-tuning-only models).
- Include speech-to-text models (Whisper, Deepgram) if present — note their per-minute pricing.
- If you cannot determine a value, use -1 as a sentinel.
- Return ONLY a JSON array of objects. No markdown formatting, no explanation.
"""


def _build_user_prompt(
    provider_name: str, markdown: str, current_entries: dict[str, Any]
) -> str:
    """Build the user prompt for pricing extraction."""
    current_json = json.dumps(current_entries, indent=2) if current_entries else "{}"
    # Truncate markdown to avoid blowing context (keep first ~80k chars)
    truncated = markdown[:80_000]
    if len(markdown) > 80_000:
        truncated += "\n\n[... truncated ...]"

    return f"""\
Provider: {provider_name}

## Current registry entries for this provider:
```json
{current_json}
```

## Pricing page content:
{truncated}

Extract all model pricing information as a JSON array."""


# ---------------------------------------------------------------------------
# Page fetcher (reuses url_extractor patterns)
# ---------------------------------------------------------------------------
async def fetch_pricing_page(url: str) -> str:
    """Fetch a pricing page URL and return markdown content.

    Reuses the same httpx + Trafilatura pattern from URLExtractor
    but without the database dependency.
    """
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if not any(
            ct in content_type
            for ct in ("text/html", "application/xhtml+xml", "text/plain")
        ):
            raise ValueError(f"Unexpected content type: {content_type}")

        html_content = response.text

    # Convert HTML → markdown via Trafilatura (same as url_extractor._parse_html)
    try:
        import trafilatura

        markdown = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=True,
            include_links=True,
            output_format="markdown",
        )
        if markdown:
            return markdown
    except ImportError:
        logger.warning("trafilatura not installed, falling back to basic extraction")

    # Fallback: strip HTML tags
    import html
    import re

    text = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------
class ModelPricingExtractor:
    """Orchestrates pricing page scraping + LLM extraction + YAML diffing."""

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        extraction_model: str = EXTRACTION_MODEL,
        pricing_sources: dict[str, list[str]] | None = None,
    ):
        self.model_config = model_config or get_model_config()
        self.router = LLMRouter(self.model_config)
        self.extraction_model = extraction_model
        self.pricing_sources = pricing_sources or PRICING_SOURCES

    async def run(
        self,
        providers: list[str] | None = None,
        dry_run: bool = True,
    ) -> PricingReport:
        """Run the full extraction pipeline.

        Args:
            providers: Limit to specific provider keys (e.g. ["anthropic", "openai"]).
                       If None, all configured providers are checked.
            dry_run: If True, only report diffs without modifying models.yaml.

        Returns:
            PricingReport with diffs, new models, and status.
        """
        report = PricingReport()

        target_providers = providers or list(self.pricing_sources.keys())

        # Load current registry for comparison
        registry_models, registry_configs, _ = load_model_registry()

        for provider_key in target_providers:
            urls = self.pricing_sources.get(provider_key)
            if not urls:
                report.extraction_errors.append(
                    f"No pricing URLs configured for provider: {provider_key}"
                )
                continue

            # Fetch all pages for this provider
            combined_markdown = ""
            fetch_ok = False
            for url in urls:
                try:
                    logger.info(f"Fetching pricing page: {url}")
                    md = await fetch_pricing_page(url)
                    combined_markdown += f"\n\n# Source: {url}\n\n{md}"
                    fetch_ok = True
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    report.extraction_errors.append(f"Fetch failed for {url}: {e}")

            if not fetch_ok:
                report.providers_failed.append(provider_key)
                continue

            report.providers_fetched.append(provider_key)

            # Gather current entries for this provider
            current_entries = self._current_provider_entries(provider_key, registry_configs)

            # LLM extraction
            try:
                extracted = await self._extract_with_llm(
                    provider_key, combined_markdown, current_entries
                )
            except Exception as e:
                logger.error(f"LLM extraction failed for {provider_key}: {e}")
                report.extraction_errors.append(f"LLM extraction failed for {provider_key}: {e}")
                continue

            # Diff against current registry
            self._diff_provider(provider_key, extracted, registry_configs, report)

        # Apply if not dry_run
        if not dry_run and report.has_changes:
            self._apply_to_yaml(report)
            report.applied = True

        return report

    def _current_provider_entries(
        self, provider_key: str, registry_configs: dict
    ) -> dict[str, Any]:
        """Get current registry entries for a provider as a plain dict."""
        entries = {}
        prefix = f"{provider_key}."
        for key, config in registry_configs.items():
            # registry_configs keys are (model_id, Provider) tuples
            model_id, provider = key
            if provider.value == provider_key or (
                provider_key == "aws_bedrock" and provider == Provider.AWS_BEDROCK
            ):
                config_key = f"{provider.value}.{model_id}"
                entries[config_key] = {
                    "provider_model_id": config.provider_model_id,
                    "cost_per_mtok_input": config.cost_per_mtok_input,
                    "cost_per_mtok_output": config.cost_per_mtok_output,
                    "context_window": config.context_window,
                    "max_output_tokens": config.max_output_tokens,
                    "tier": config.tier,
                }
        return entries

    async def _extract_with_llm(
        self,
        provider_name: str,
        markdown: str,
        current_entries: dict[str, Any],
    ) -> list[ExtractedModel]:
        """Use LLM to extract structured pricing data from page markdown."""
        user_prompt = _build_user_prompt(provider_name, markdown, current_entries)

        response = await self.router.generate(
            model=self.extraction_model,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8192,
            temperature=0.0,
        )

        # Parse JSON from response
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}\nResponse: {text[:500]}") from e

        if not isinstance(raw, list):
            raise ValueError(f"Expected JSON array, got {type(raw).__name__}")

        models = []
        for item in raw:
            try:
                models.append(
                    ExtractedModel(
                        model_id=item["model_id"],
                        provider_model_id=item.get("provider_model_id", ""),
                        cost_per_mtok_input=float(item.get("cost_per_mtok_input", -1)),
                        cost_per_mtok_output=float(item.get("cost_per_mtok_output", -1)),
                        context_window=int(item.get("context_window", -1)),
                        max_output_tokens=int(item.get("max_output_tokens", -1)),
                        tier=item.get("tier", "standard"),
                        notes=item.get("notes", ""),
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed model entry: {e} — {item}")

        logger.info(f"Extracted {len(models)} models for {provider_name}")
        return models

    def _diff_provider(
        self,
        provider_key: str,
        extracted: list[ExtractedModel],
        registry_configs: dict,
        report: PricingReport,
    ) -> None:
        """Compare extracted models against registry and populate report."""
        # Build lookup of known provider configs
        known: dict[str, Any] = {}
        for (model_id, provider), config in registry_configs.items():
            if provider.value == provider_key:
                known[model_id] = config

        for ext in extracted:
            # Skip sentinel values (couldn't extract)
            if ext.cost_per_mtok_input < 0 and ext.cost_per_mtok_output < 0:
                continue

            if ext.model_id in known:
                current = known[ext.model_id]
                config_key = f"{provider_key}.{ext.model_id}"
                # Compare each pricing field
                comparisons = [
                    ("cost_per_mtok_input", current.cost_per_mtok_input, ext.cost_per_mtok_input),
                    ("cost_per_mtok_output", current.cost_per_mtok_output, ext.cost_per_mtok_output),
                    ("context_window", current.context_window, ext.context_window),
                    ("max_output_tokens", current.max_output_tokens, ext.max_output_tokens),
                ]
                if ext.provider_model_id:
                    comparisons.append(
                        ("provider_model_id", current.provider_model_id, ext.provider_model_id)
                    )

                for field_name, cur_val, ext_val in comparisons:
                    # Skip sentinel extracted values
                    if isinstance(ext_val, (int, float)) and ext_val < 0:
                        continue
                    if cur_val != ext_val:
                        report.diffs.append(
                            PricingDiff(
                                provider_key=config_key,
                                field=field_name,
                                current_value=cur_val,
                                extracted_value=ext_val,
                            )
                        )
            else:
                # New model not in registry
                ext.notes = ext.notes or "New model not in registry"
                report.new_models.append(ext)

    def _apply_to_yaml(self, report: PricingReport) -> None:
        """Apply diffs to models.yaml using safe line-level YAML editing.

        Instead of round-tripping through a YAML library (which would lose
        comments and formatting), we do targeted string replacements on
        the raw YAML text.
        """
        yaml_path = self._find_models_yaml()
        content = yaml_path.read_text()

        for diff in report.diffs:
            # e.g. provider_key="anthropic.claude-sonnet-4-5", field="cost_per_mtok_input"
            # We look for lines like "  cost_per_mtok_input: 3.00" under the
            # section headed by "  anthropic.claude-sonnet-4-5:"
            section_key = diff.provider_key
            field_name = diff.field

            # Find the section in YAML
            section_marker = f"  {section_key}:"
            section_idx = content.find(section_marker)
            if section_idx == -1:
                logger.warning(f"Could not find section {section_key} in models.yaml")
                continue

            # Find the field within that section (search from section start to next section)
            section_end = content.find("\n  ", section_idx + len(section_marker) + 1)
            # Look further — sections are separated by blank lines or new top-level keys
            # Search for the field line within ~20 lines after section header
            search_start = section_idx
            search_end = min(len(content), section_idx + 800)
            section_block = content[search_start:search_end]

            # Find the specific field line
            import re

            # Match "    field_name: value" possibly with comment
            pattern = rf"^(    {re.escape(field_name)}:\s*)(.+?)(\s*#.*)?$"
            match = re.search(pattern, section_block, re.MULTILINE)
            if not match:
                logger.warning(
                    f"Could not find field {field_name} in section {section_key}"
                )
                continue

            # Format the new value
            new_val = diff.extracted_value
            if isinstance(new_val, float):
                # Format to match YAML style: remove trailing zeros but keep at least 2 decimals
                new_val_str = f"{new_val:.2f}"
            elif isinstance(new_val, int):
                new_val_str = str(new_val)
            else:
                new_val_str = f'"{new_val}"'

            # Reconstruct the line preserving inline comments
            old_line = match.group(0)
            comment = match.group(3) or ""
            new_line = f"{match.group(1)}{new_val_str}{comment}"

            # Replace in full content (use the absolute position)
            abs_start = search_start + match.start()
            abs_end = search_start + match.end()
            content = content[:abs_start] + new_line + content[abs_end:]

        # Update the "Pricing updated" timestamp
        import re as re_mod
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%B %Y")
        content = re_mod.sub(
            r"# Pricing updated:.*",
            f"# Pricing updated: {today}",
            content,
        )
        content = re_mod.sub(
            r"# Updated:.*",
            f"# Updated: {today} (auto-extracted)",
            content,
        )

        yaml_path.write_text(content)
        logger.info(f"Updated {yaml_path} with {len(report.diffs)} changes")

    @staticmethod
    def _find_models_yaml() -> Path:
        """Locate settings/models.yaml from project root."""
        # Walk up from this file to find project root
        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "settings" / "models.yaml"
            if candidate.exists():
                return candidate
            if (parent / "pyproject.toml").exists():
                return parent / "settings" / "models.yaml"
        raise FileNotFoundError("Cannot locate settings/models.yaml")
