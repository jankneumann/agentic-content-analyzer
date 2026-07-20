"""Architecture and behavior tests for provider-neutral processor routing."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.podcast import PodcastLength, PodcastRequest
from src.processors.digest_creator import DigestCreator
from src.processors.historical_context import HistoricalContextAnalyzer
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.processors.script_reviser import PodcastScriptReviser
from src.services.llm_router import LLMResponse, LLMRouter

PROCESSORS = (
    "theme_analyzer.py",
    "digest_creator.py",
    "podcast_script_generator.py",
    "digest_reviser.py",
    "script_reviser.py",
    "historical_context.py",
)
FORBIDDEN_MODULES = {"anthropic", "google", "openai"}


@pytest.mark.parametrize("filename", PROCESSORS)
def test_pipeline_processors_do_not_import_provider_sdks(filename: str) -> None:
    path = Path("src/processors") / filename
    tree = ast.parse(path.read_text())
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported.update(
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imported.isdisjoint(FORBIDDEN_MODULES)


@pytest.mark.asyncio
async def test_digest_generation_routes_with_step_and_records_metadata() -> None:
    router = MagicMock()
    router.generate = AsyncMock(
        return_value=LLMResponse(
            text='{"title":"Digest"}',
            input_tokens=11,
            output_tokens=7,
            provider=Provider.OPENAI,
            selected_model="gpt-5-mini",
            model_version="gpt-version",
        )
    )
    config = MagicMock()
    config.get_model_for_step.return_value = "gpt-5"
    config.get_family.return_value = SimpleNamespace(value="gpt")
    config.calculate_cost.return_value = 0.02
    creator = DigestCreator(model_config=config, llm_router=router)

    result = await creator._route_json("prompt", max_tokens=100, temperature=0.2)

    assert result == {"title": "Digest"}
    assert router.generate.await_args.kwargs["step"] == ModelStep.DIGEST_CREATION
    assert creator.provider_used == Provider.OPENAI
    assert creator.input_tokens == 11
    assert creator.output_tokens == 7
    assert creator.model_version == "gpt-version"
    assert creator.model_used == "gpt-5-mini"
    assert config.calculate_cost.call_args.kwargs["model_id"] == "gpt-5-mini"


@pytest.mark.asyncio
async def test_podcast_uses_one_provider_neutral_tool_loop() -> None:
    router = MagicMock()
    router.generate_with_tools = AsyncMock(
        return_value=LLMResponse(
            text='{"title":"Episode","sections":[],"sources_summary":[]}',
            input_tokens=13,
            output_tokens=5,
            provider=Provider.GOOGLE_AI,
            selected_model="gemini-2.5-flash-lite",
            model_version="gemini-version",
        )
    )
    config = MagicMock()
    config.get_model_for_step.return_value = "gemini-2.5-flash"
    config.calculate_cost.return_value = 0.01
    generator = PodcastScriptGenerator(
        model_config=config,
        content_loader=MagicMock(),
        llm_router=router,
    )
    context = {
        "digest": {
            "digest_type": "weekly",
            "title": "Digest",
            "period_start": "2026-07-01",
            "period_end": "2026-07-08",
            "executive_overview": "Overview",
        },
        "content_metadata": [],
        "summaries": [],
        "selection_fingerprint": "a" * 64,
        "custom_focus_topics": [],
        "custom_instructions": None,
    }

    await generator._generate_script_with_tools(
        context,
        PodcastRequest(digest_id=1, length=PodcastLength.BRIEF),
    )

    router.generate_with_tools.assert_awaited_once()
    assert generator.provider_used == Provider.GOOGLE_AI
    assert generator.input_tokens == 13
    assert generator.output_tokens == 5
    assert generator.model_version == "gemini-version"
    assert generator.model_used == "gemini-2.5-flash-lite"
    assert config.calculate_cost.call_args.kwargs["model_id"] == "gemini-2.5-flash-lite"
    assert router.generate_with_tools.await_args.kwargs["step"] == ModelStep.PODCAST_SCRIPT


@pytest.mark.asyncio
async def test_podcast_revision_routes_through_router() -> None:
    router = MagicMock()
    router.generate = AsyncMock(
        return_value=LLMResponse(
            text=('{"section_type":"intro","title":"Revised","dialogue":[],"sources_cited":[]}'),
            provider=Provider.OPENAI,
        )
    )
    config = MagicMock()
    config.get_model_for_step.return_value = "gpt-5"
    reviser = PodcastScriptReviser(model_config=config, llm_router=router)

    section = await reviser._generate_revision("revise")

    assert section.title == "Revised"
    assert router.generate.await_args.kwargs["step"] == ModelStep.PODCAST_SCRIPT


@pytest.mark.asyncio
async def test_historical_context_routes_through_router() -> None:
    router = MagicMock()
    router.generate = AsyncMock(
        return_value=LLMResponse(
            text=('{"evolution_summary":"Growing","previous_discussions":[],"stance_change":null}'),
            input_tokens=2,
            output_tokens=3,
            provider=Provider.OPENAI,
        )
    )
    config = MagicMock()
    config.get_model_for_step.return_value = "gpt-5"
    analyzer = HistoricalContextAnalyzer(model_config=config, llm_router=router)

    result = await analyzer._analyze_evolution_with_llm(
        "Agents",
        [{"timestamp": "2026-07-01", "title": "Item", "content": "Context"}],
        [],
    )

    assert result[0] == "Growing"
    assert router.generate.await_args.kwargs["step"] == ModelStep.HISTORICAL_CONTEXT


def test_router_uses_configured_provider_priority() -> None:
    config = ModelConfig(
        providers=[
            ProviderConfig(provider=Provider.AWS_BEDROCK, api_key=""),
            ProviderConfig(provider=Provider.GOOGLE_VERTEX, api_key=""),
        ]
    )

    assert LLMRouter(config).get_provider_candidates("claude-sonnet-4-5") == (
        Provider.AWS_BEDROCK,
        Provider.GOOGLE_VERTEX,
    )


def test_router_supports_azure_only_configuration() -> None:
    config = ModelConfig(providers=[ProviderConfig(provider=Provider.MICROSOFT_AZURE, api_key="")])

    assert LLMRouter(config).resolve_provider("gpt-4o-mini") == Provider.MICROSOFT_AZURE


def test_router_rejects_model_unsupported_by_explicit_provider_configuration() -> None:
    config = ModelConfig(providers=[ProviderConfig(provider=Provider.AWS_BEDROCK, api_key="")])

    with pytest.raises(ValueError, match="not available on any configured providers"):
        LLMRouter(config).get_provider_candidates("gpt-5-mini")


@pytest.mark.asyncio
async def test_router_fails_over_across_configured_providers() -> None:
    config = ModelConfig(
        providers=[
            ProviderConfig(provider=Provider.AWS_BEDROCK, api_key=""),
            ProviderConfig(provider=Provider.GOOGLE_VERTEX, api_key=""),
        ]
    )
    router = LLMRouter(config)
    router._generate_anthropic = AsyncMock(
        side_effect=[
            RuntimeError("bedrock unavailable"),
            LLMResponse(text="vertex", provider=Provider.GOOGLE_VERTEX),
        ]
    )

    response = await router.generate(
        model="claude-sonnet-4-5",
        system_prompt="system",
        user_prompt="user",
    )

    assert response.provider == Provider.GOOGLE_VERTEX
    assert [call.args[1] for call in router._generate_anthropic.await_args_list] == [
        Provider.AWS_BEDROCK,
        Provider.GOOGLE_VERTEX,
    ]


def test_sync_router_fails_over_across_configured_providers() -> None:
    config = ModelConfig(
        providers=[
            ProviderConfig(provider=Provider.AWS_BEDROCK, api_key=""),
            ProviderConfig(provider=Provider.GOOGLE_VERTEX, api_key=""),
        ]
    )
    router = LLMRouter(config)
    router._generate_anthropic_sync = MagicMock(
        side_effect=[
            RuntimeError("bedrock unavailable"),
            LLMResponse(text="vertex", provider=Provider.GOOGLE_VERTEX),
        ]
    )

    response = router.generate_sync(
        model="claude-sonnet-4-5",
        system_prompt="system",
        user_prompt="user",
    )

    assert response.provider == Provider.GOOGLE_VERTEX
