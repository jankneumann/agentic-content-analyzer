"""Tests for model pricing extractor service.

Verifies page fetching, LLM extraction parsing, diffing logic,
and YAML update application — all with mocked HTTP and LLM calls.
"""

from __future__ import annotations

import json
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.model_pricing_extractor import (
    ExtractedModel,
    ModelPricingExtractor,
    PricingDiff,
    PricingReport,
    fetch_pricing_page,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_LLM_RESPONSE = json.dumps([
    {
        "model_id": "claude-haiku-4-5",
        "provider_model_id": "claude-haiku-4-5-20251001",
        "cost_per_mtok_input": 1.00,
        "cost_per_mtok_output": 5.00,  # Changed from 3.00 to 5.00
        "context_window": 200000,
        "max_output_tokens": 64000,
        "tier": "standard",
        "notes": "",
    },
    {
        "model_id": "claude-sonnet-4-5",
        "provider_model_id": "claude-sonnet-4-5-20250929",
        "cost_per_mtok_input": 3.00,
        "cost_per_mtok_output": 15.00,
        "context_window": 200000,
        "max_output_tokens": 64000,
        "tier": "standard",
        "notes": "",
    },
    {
        "model_id": "claude-4-6-sonnet",
        "provider_model_id": "claude-4-6-sonnet-20260301",
        "cost_per_mtok_input": 3.50,
        "cost_per_mtok_output": 17.50,
        "context_window": 200000,
        "max_output_tokens": 64000,
        "tier": "standard",
        "notes": "new model",
    },
])


SAMPLE_HTML = """\
<html><head><title>Model Pricing</title></head>
<body>
<h1>API Pricing</h1>
<table>
<tr><th>Model</th><th>Input</th><th>Output</th></tr>
<tr><td>Claude Haiku 4.5</td><td>$1.00/MTok</td><td>$5.00/MTok</td></tr>
</table>
</body></html>
"""


# ---------------------------------------------------------------------------
# fetch_pricing_page
# ---------------------------------------------------------------------------


class TestFetchPricingPage:
    @pytest.mark.asyncio
    async def test_fetches_html_and_extracts_markdown(self):
        """Should fetch HTML and convert to markdown via trafilatura."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("trafilatura.extract", return_value="# API Pricing\n\nSome content"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_pricing_page("https://example.com/pricing")
            assert "API Pricing" in result

    @pytest.mark.asyncio
    async def test_falls_back_when_trafilatura_unavailable(self):
        """Should fall back to basic HTML stripping if trafilatura fails."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><p>Hello pricing</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("trafilatura.extract", return_value=None),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_pricing_page("https://example.com/pricing")
            assert "Hello pricing" in result


# ---------------------------------------------------------------------------
# LLM extraction parsing
# ---------------------------------------------------------------------------


class TestExtractWithLLM:
    @pytest.mark.asyncio
    async def test_parses_json_response(self):
        """Should correctly parse a well-formed JSON response from LLM."""
        mock_llm_response = MagicMock()
        mock_llm_response.text = SAMPLE_LLM_RESPONSE

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor.router = MagicMock()
            extractor.router.generate = AsyncMock(return_value=mock_llm_response)
            extractor.extraction_model = "claude-haiku-4-5"

            result = await extractor._extract_with_llm("anthropic", "some markdown", {})
            assert len(result) == 3
            assert result[0].model_id == "claude-haiku-4-5"
            assert result[0].cost_per_mtok_output == 5.00

    @pytest.mark.asyncio
    async def test_handles_markdown_code_fences(self):
        """Should strip markdown code fences from LLM response."""
        wrapped = f"```json\n{SAMPLE_LLM_RESPONSE}\n```"
        mock_llm_response = MagicMock()
        mock_llm_response.text = wrapped

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor.router = MagicMock()
            extractor.router.generate = AsyncMock(return_value=mock_llm_response)
            extractor.extraction_model = "claude-haiku-4-5"

            result = await extractor._extract_with_llm("anthropic", "some markdown", {})
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self):
        """Should raise ValueError on non-JSON LLM output."""
        mock_llm_response = MagicMock()
        mock_llm_response.text = "I can't extract pricing from this page."

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor.router = MagicMock()
            extractor.router.generate = AsyncMock(return_value=mock_llm_response)
            extractor.extraction_model = "claude-haiku-4-5"

            with pytest.raises(ValueError, match="invalid JSON"):
                await extractor._extract_with_llm("anthropic", "some markdown", {})


# ---------------------------------------------------------------------------
# Diffing logic
# ---------------------------------------------------------------------------


class TestDiffProvider:
    def _make_config(self, **overrides):
        """Create a mock ProviderModelConfig."""
        defaults = {
            "model_id": "claude-haiku-4-5",
            "provider_model_id": "claude-haiku-4-5-20251001",
            "cost_per_mtok_input": 1.00,
            "cost_per_mtok_output": 3.00,
            "context_window": 200000,
            "max_output_tokens": 64000,
            "tier": "standard",
        }
        defaults.update(overrides)
        config = MagicMock()
        for k, v in defaults.items():
            setattr(config, k, v)
        return config

    def test_detects_price_change(self):
        """Should detect when extracted price differs from registry."""
        from src.config.models import Provider

        registry_configs = {
            ("claude-haiku-4-5", Provider.ANTHROPIC): self._make_config()
        }
        extracted = [
            ExtractedModel(
                model_id="claude-haiku-4-5",
                provider_model_id="claude-haiku-4-5-20251001",
                cost_per_mtok_input=1.00,
                cost_per_mtok_output=5.00,  # changed
                context_window=200000,
                max_output_tokens=64000,
            )
        ]
        report = PricingReport()

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor._diff_provider("anthropic", extracted, registry_configs, report)

        assert len(report.diffs) == 1
        assert report.diffs[0].field == "cost_per_mtok_output"
        assert report.diffs[0].current_value == 3.00
        assert report.diffs[0].extracted_value == 5.00

    def test_detects_new_model(self):
        """Should flag models not in the registry."""
        from src.config.models import Provider

        registry_configs = {
            ("claude-haiku-4-5", Provider.ANTHROPIC): self._make_config()
        }
        extracted = [
            ExtractedModel(
                model_id="claude-4-6-sonnet",
                provider_model_id="claude-4-6-sonnet-20260301",
                cost_per_mtok_input=3.50,
                cost_per_mtok_output=17.50,
                context_window=200000,
                max_output_tokens=64000,
            )
        ]
        report = PricingReport()

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor._diff_provider("anthropic", extracted, registry_configs, report)

        assert len(report.new_models) == 1
        assert report.new_models[0].model_id == "claude-4-6-sonnet"

    def test_no_diff_when_matching(self):
        """Should produce no diffs when extracted matches current."""
        from src.config.models import Provider

        registry_configs = {
            ("claude-haiku-4-5", Provider.ANTHROPIC): self._make_config()
        }
        extracted = [
            ExtractedModel(
                model_id="claude-haiku-4-5",
                provider_model_id="claude-haiku-4-5-20251001",
                cost_per_mtok_input=1.00,
                cost_per_mtok_output=3.00,
                context_window=200000,
                max_output_tokens=64000,
            )
        ]
        report = PricingReport()

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor._diff_provider("anthropic", extracted, registry_configs, report)

        assert len(report.diffs) == 0
        assert len(report.new_models) == 0

    def test_skips_sentinel_values(self):
        """Should skip fields with -1 sentinel (could not extract)."""
        from src.config.models import Provider

        registry_configs = {
            ("claude-haiku-4-5", Provider.ANTHROPIC): self._make_config()
        }
        extracted = [
            ExtractedModel(
                model_id="claude-haiku-4-5",
                provider_model_id="claude-haiku-4-5-20251001",
                cost_per_mtok_input=1.00,
                cost_per_mtok_output=-1,  # sentinel — couldn't extract
                context_window=-1,
                max_output_tokens=-1,
            )
        ]
        report = PricingReport()

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ):
            extractor = ModelPricingExtractor()
            extractor._diff_provider("anthropic", extracted, registry_configs, report)

        assert len(report.diffs) == 0


# ---------------------------------------------------------------------------
# YAML update application
# ---------------------------------------------------------------------------


class TestApplyToYaml:
    def test_replaces_pricing_value_in_yaml(self, tmp_path):
        """Should update a specific pricing field in the YAML file."""
        yaml_content = textwrap.dedent("""\
            # Model Registry Configuration
            # Updated: December 2024
            provider_model_configs:
              anthropic.claude-haiku-4-5:
                provider_model_id: "claude-haiku-4-5-20251001"
                cost_per_mtok_input: 1.00
                cost_per_mtok_output: 3.00
                context_window: 200000
                max_output_tokens: 64000
                tier: standard
            # Pricing updated: December 2024
        """)
        yaml_file = tmp_path / "settings" / "models.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(yaml_content)

        report = PricingReport(
            diffs=[
                PricingDiff(
                    provider_key="anthropic.claude-haiku-4-5",
                    field="cost_per_mtok_output",
                    current_value=3.00,
                    extracted_value=5.00,
                )
            ]
        )

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ), patch.object(
            ModelPricingExtractor, "_find_models_yaml", return_value=yaml_file
        ):
            extractor = ModelPricingExtractor()
            extractor._apply_to_yaml(report)

        updated = yaml_file.read_text()
        assert "cost_per_mtok_output: 5.00" in updated
        assert "cost_per_mtok_output: 3.00" not in updated

    def test_preserves_inline_comments(self, tmp_path):
        """Should keep inline comments when updating values."""
        yaml_content = textwrap.dedent("""\
            # Updated: December 2024
            provider_model_configs:
              google_ai.gemini-2.5-flash:
                provider_model_id: "gemini-2.5-flash"
                cost_per_mtok_input: 0.30 # 1.00 for audio input
                cost_per_mtok_output: 2.50
                context_window: 1048576
                max_output_tokens: 65536
                tier: standard
            # Pricing updated: December 2024
        """)
        yaml_file = tmp_path / "settings" / "models.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(yaml_content)

        report = PricingReport(
            diffs=[
                PricingDiff(
                    provider_key="google_ai.gemini-2.5-flash",
                    field="cost_per_mtok_input",
                    current_value=0.30,
                    extracted_value=0.15,
                )
            ]
        )

        with patch.object(
            ModelPricingExtractor, "__init__", lambda self, **kw: None
        ), patch.object(
            ModelPricingExtractor, "_find_models_yaml", return_value=yaml_file
        ):
            extractor = ModelPricingExtractor()
            extractor._apply_to_yaml(report)

        updated = yaml_file.read_text()
        assert "cost_per_mtok_input: 0.15 # 1.00 for audio input" in updated


# ---------------------------------------------------------------------------
# PricingReport
# ---------------------------------------------------------------------------


class TestPricingReport:
    def test_has_changes_with_diffs(self):
        report = PricingReport(diffs=[PricingDiff("a.b", "cost", 1.0, 2.0)])
        assert report.has_changes is True

    def test_has_changes_with_new_models(self):
        report = PricingReport(new_models=[
            ExtractedModel("new-model", "new-model-v1", 1.0, 2.0, 100000, 8192)
        ])
        assert report.has_changes is True

    def test_no_changes_when_empty(self):
        report = PricingReport()
        assert report.has_changes is False
