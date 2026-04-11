"""Automated pricing extraction for Neon and Resend from their pricing pages.

Reuses ``fetch_pricing_page`` from the model pricing extractor (same httpx +
Trafilatura pipeline) and follows the same fetch → LLM extract → diff/apply
pattern, but targets infrastructure service pricing rather than LLM token costs.

Both Neon and Resend expose agent-friendly ``.md`` pricing pages.  The extractor
tries those first, then falls back to the HTML pages.

Usage:
    from src.services.infrastructure_pricing_extractor import InfrastructurePricingExtractor

    extractor = InfrastructurePricingExtractor()
    report = await extractor.run(dry_run=True)   # preview changes
    report = await extractor.run(dry_run=False)   # apply to pricing.yaml
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from src.services.model_pricing_extractor import fetch_pricing_page
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pricing page URLs (agent-friendly .md first, HTML fallback)
# ---------------------------------------------------------------------------
PRICING_SOURCES: dict[str, list[str]] = {
    "neon": [
        "https://neon.com/pricing.md",
        "https://neon.com/docs/introduction/plans.md",
        "https://neon.com/pricing",
        "https://neon.com/docs/introduction/plans",
    ],
    "resend": [
        "https://resend.com/pricing.md",
        "https://resend.com/pricing",
        "https://resend.com/docs/knowledge-base/account-quotas-and-limits",
    ],
}

# Model used for extraction (cheap + fast — structured extraction task)
EXTRACTION_MODEL = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class InfraPricingDiff:
    """A single field-level diff between current and extracted pricing."""

    service: str  # "neon" or "resend"
    plan: str  # plan name (e.g. "launch", "pro")
    field: str  # field name (e.g. "cost_per_compute_hour")
    current_value: Any
    extracted_value: Any


@dataclass
class InfraPricingReport:
    """Full extraction report across all services."""

    diffs: list[InfraPricingDiff] = field(default_factory=list)
    new_plans: list[dict[str, Any]] = field(default_factory=list)
    services_fetched: list[str] = field(default_factory=list)
    services_failed: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    applied: bool = False
    timestamp: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.diffs) or bool(self.new_plans)


# ---------------------------------------------------------------------------
# LLM extraction prompts
# ---------------------------------------------------------------------------
NEON_EXTRACTION_PROMPT = """\
You are a structured data extractor. Extract Neon Postgres pricing from the \
page content below.

Return a JSON object with this structure:
{
  "plans": {
    "free": {
      "monthly_price": 0.00,
      "included_compute_hours": <number>,
      "included_storage_gb": <number per project>,
      "max_projects": <number>,
      "max_storage_gb": <number across all projects>,
      "max_compute_cu": <number>,
      "pitr_hours": <number or null>,
      "branches": "unlimited" or <number>,
      "scale_to_zero": true/false,
      "idle_timeout_minutes": <number or null>
    },
    "launch": {
      "monthly_price": <minimum spend>,
      "cost_per_compute_hour": <per CU-hour>,
      "cost_per_storage_gb": <per GB-month, first tier>,
      "cost_per_storage_gb_over_50": <per GB-month above 50GB, or null>,
      "cost_per_pitr_gb": <per GB-month>,
      "cost_per_snapshot_gb": <per GB-month, or null>,
      "max_compute_cu": <number>,
      "pitr_days": <number>,
      "branches": "unlimited" or <number>,
      "scale_to_zero": true/false
    },
    "scale": { ... same fields as launch ... }
  },
  "notes": "<any important caveats about pricing>"
}

RULES:
- All monetary values in USD.
- If a value isn't mentioned on the page, use null (not -1).
- Only include plans you can find pricing for. Skip "Enterprise" / custom-quote plans.
- Return ONLY valid JSON. No markdown fences, no explanation.
"""

RESEND_EXTRACTION_PROMPT = """\
You are a structured data extractor. Extract Resend email pricing from the \
page content below.

Return a JSON object with this structure:
{
  "plans": {
    "free": {
      "monthly_price": 0.00,
      "emails_per_month": <number>,
      "daily_limit": <number or null>,
      "domains": <number or "unlimited">,
      "pay_as_you_go": false
    },
    "pro": {
      "monthly_price": <number>,
      "emails_per_month": <number>,
      "daily_limit": null,
      "domains": "unlimited",
      "pay_as_you_go": true,
      "overage_per_1000_emails": <cost per extra 1000-email bucket>
    },
    "scale": { ... same fields as pro ... }
  },
  "marketing": {
    "pro": {
      "monthly_price": <number>,
      "contacts": <number>,
      "sends": "unlimited" or <number>
    }
  },
  "overage_cap_multiplier": <number, e.g. 5>,
  "notes": "<any important caveats>"
}

RULES:
- All monetary values in USD.
- If overage per-email cost is given instead of per-1000, multiply by 1000.
- If a value isn't mentioned, use null.
- Skip "Enterprise" / custom-quote plans.
- Return ONLY valid JSON. No markdown fences, no explanation.
"""

_SERVICE_PROMPTS = {
    "neon": NEON_EXTRACTION_PROMPT,
    "resend": RESEND_EXTRACTION_PROMPT,
}


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------
class InfrastructurePricingExtractor:
    """Orchestrates pricing page scraping + LLM extraction + YAML diff for Neon & Resend."""

    def __init__(
        self,
        extraction_model: str = EXTRACTION_MODEL,
        pricing_sources: dict[str, list[str]] | None = None,
    ):
        self.extraction_model = extraction_model
        self.pricing_sources = pricing_sources or PRICING_SOURCES

    async def run(
        self,
        services: list[str] | None = None,
        dry_run: bool = True,
    ) -> InfraPricingReport:
        """Run the full extraction pipeline.

        Args:
            services: Limit to specific services (e.g. ["neon"]). None = all.
            dry_run: If True, only report diffs without modifying pricing.yaml.

        Returns:
            InfraPricingReport with diffs and status.
        """
        report = InfraPricingReport(timestamp=datetime.now(UTC).isoformat())
        target_services = services or list(self.pricing_sources.keys())

        current_config = self._load_current_pricing()

        for service_key in target_services:
            urls = self.pricing_sources.get(service_key)
            if not urls:
                report.extraction_errors.append(f"No pricing URLs for service: {service_key}")
                continue

            # Fetch pages — try each URL, keep first success
            markdown = await self._fetch_service_pages(service_key, urls, report)
            if not markdown:
                report.services_failed.append(service_key)
                continue

            report.services_fetched.append(service_key)

            # LLM extraction
            try:
                extracted = await self._extract_with_llm(service_key, markdown)
            except Exception as e:
                logger.error(f"LLM extraction failed for {service_key}: {e}")
                report.extraction_errors.append(f"LLM extraction failed for {service_key}: {e}")
                continue

            # Diff against current
            current_service = current_config.get(service_key, {})
            self._diff_service(service_key, extracted, current_service, report)

        # Apply if not dry_run
        if not dry_run and report.has_changes:
            self._apply_to_yaml(report, current_config)
            report.applied = True

        return report

    async def _fetch_service_pages(
        self,
        service_key: str,
        urls: list[str],
        report: InfraPricingReport,
    ) -> str:
        """Fetch pricing pages, trying each URL until one succeeds.

        Concatenates all successful fetches for maximum coverage.
        """
        combined = ""
        for url in urls:
            try:
                logger.info(f"Fetching {service_key} pricing: {url}")
                md = await fetch_pricing_page(url)
                combined += f"\n\n# Source: {url}\n\n{md}"
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                report.extraction_errors.append(f"Fetch failed for {url}: {e}")
        return combined

    async def _extract_with_llm(
        self,
        service_key: str,
        markdown: str,
    ) -> dict[str, Any]:
        """Use LLM to extract structured pricing from page markdown."""
        from src.config.models import get_model_config
        from src.services.llm_router import LLMRouter

        model_config = get_model_config()
        router = LLMRouter(model_config)

        system_prompt = _SERVICE_PROMPTS[service_key]

        # Truncate to stay within context (keep first ~60k chars)
        truncated = markdown[:60_000]
        if len(markdown) > 60_000:
            truncated += "\n\n[... truncated ...]"

        user_prompt = f"## {service_key.title()} Pricing Page Content:\n\n{truncated}"

        response = await router.generate(
            model=self.extraction_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
        )

        text = _strip_json_fences(response.text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON for {service_key}: {e}\n{text[:500]}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object for {service_key}, got {type(data).__name__}")

        logger.info(f"Extracted {service_key} pricing: {len(data.get('plans', {}))} plans")
        return data

    def _diff_service(
        self,
        service_key: str,
        extracted: dict[str, Any],
        current_service: dict[str, Any],
        report: InfraPricingReport,
    ) -> None:
        """Compare extracted pricing against current YAML and populate report."""
        current_plans = current_service.get("plans", {})
        extracted_plans = extracted.get("plans", {})

        for plan_name, ext_plan in extracted_plans.items():
            if plan_name not in current_plans:
                report.new_plans.append(
                    {
                        "service": service_key,
                        "plan": plan_name,
                        "data": ext_plan,
                    }
                )
                continue

            cur_plan = current_plans[plan_name]
            for field_name, ext_value in ext_plan.items():
                if ext_value is None:
                    continue  # Couldn't extract — skip
                cur_value = cur_plan.get(field_name)
                if cur_value is not None and cur_value != ext_value:
                    report.diffs.append(
                        InfraPricingDiff(
                            service=service_key,
                            plan=plan_name,
                            field=field_name,
                            current_value=cur_value,
                            extracted_value=ext_value,
                        )
                    )

    def _apply_to_yaml(
        self,
        report: InfraPricingReport,
        current_config: dict[str, Any],
    ) -> None:
        """Apply diffs to pricing.yaml using targeted line-level edits.

        Preserves comments and formatting by doing regex-based replacements
        on the raw YAML text, matching the approach in ModelPricingExtractor.
        """
        yaml_path = self._find_pricing_yaml()
        content = yaml_path.read_text()

        replacements: list[tuple[int, int, str]] = []

        for diff in report.diffs:
            # Locate the plan section: e.g. "    launch:" under "  plans:" under "neon:"
            # Strategy: find "service:" then "plan:" then "field: value"
            service_pattern = rf"^{re.escape(diff.service)}:"
            service_match = re.search(service_pattern, content, re.MULTILINE)
            if not service_match:
                logger.warning(f"Could not find service section '{diff.service}' in pricing.yaml")
                continue

            # Search from the service section for the plan
            search_start = service_match.start()
            plan_pattern = rf"^\s+{re.escape(diff.plan)}:"
            plan_match = re.search(plan_pattern, content[search_start:], re.MULTILINE)
            if not plan_match:
                logger.warning(f"Could not find plan '{diff.plan}' under '{diff.service}'")
                continue

            plan_abs_start = search_start + plan_match.start()

            # Search for the field within ~500 chars after the plan header
            field_search_start = plan_abs_start
            field_search_end = min(len(content), plan_abs_start + 500)
            field_block = content[field_search_start:field_search_end]

            field_pattern = rf"^(\s+{re.escape(diff.field)}:\s*)(.+?)(\s*#.*)?$"
            field_match = re.search(field_pattern, field_block, re.MULTILINE)
            if not field_match:
                logger.warning(
                    f"Could not find field '{diff.field}' in plan "
                    f"'{diff.plan}' under '{diff.service}'"
                )
                continue

            # Format replacement value
            new_val = diff.extracted_value
            if isinstance(new_val, bool):
                new_val_str = "true" if new_val else "false"
            elif isinstance(new_val, float):
                # Preserve precision: use enough decimals to be accurate
                new_val_str = f"{new_val:.2f}" if new_val >= 1 else f"{new_val}"
            elif isinstance(new_val, int):
                new_val_str = str(new_val)
            elif isinstance(new_val, str):
                new_val_str = new_val
            else:
                new_val_str = str(new_val)

            comment = field_match.group(3) or ""
            new_line = f"{field_match.group(1)}{new_val_str}{comment}"

            abs_start = field_search_start + field_match.start()
            abs_end = field_search_start + field_match.end()
            replacements.append((abs_start, abs_end, new_line))

        # Apply in reverse order to preserve offsets
        for abs_start, abs_end, new_line in sorted(replacements, reverse=True):
            content = content[:abs_start] + new_line + content[abs_end:]

        # Update timestamp
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        content = re.sub(
            r"# Last updated:.*",
            f"# Last updated: {today} (auto-extracted)",
            content,
        )

        yaml_path.write_text(content)
        logger.info(f"Updated {yaml_path} with {len(report.diffs)} pricing changes")

    @staticmethod
    def _load_current_pricing() -> dict[str, Any]:
        """Load current pricing.yaml as a dict."""
        yaml_path = InfrastructurePricingExtractor._find_pricing_yaml()
        with open(yaml_path) as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _find_pricing_yaml() -> Path:
        """Locate settings/pricing.yaml from project root."""
        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "settings" / "pricing.yaml"
            if candidate.exists():
                return candidate
            if (parent / "pyproject.toml").exists():
                return parent / "settings" / "pricing.yaml"
        raise FileNotFoundError("Cannot locate settings/pricing.yaml")
