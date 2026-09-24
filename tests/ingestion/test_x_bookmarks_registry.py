"""Registry, configuration, and readiness of the ``x_bookmarks`` source.

Network-free. The adapter is not shipped yet, so these tests pin the registry
layer: the source config, the scheduled planner, the credential-gated
readiness, the fail-closed orchestrator entry, and the live-tier policy.
No test uses or prints a real cookie.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import src.config.credentials as credentials_mod
from src.config.credentials import X_AUTH_TOKEN, X_CT0, CredentialProvider
from src.config.sources import (
    RSSSource,
    SourcesConfig,
    XBookmarksSource,
    configured_source_public_key,
    load_sources_directory,
    source_key,
)
from src.ingestion.commands import XBookmarksIngestCommand
from src.ingestion.credential_failures import CREDENTIALS_MISSING, SESSION_EXPIRED
from src.ingestion.real_ingest_policy import LiveDecision, evaluate_live_adapter
from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.result_sanitizer import sanitize_ingestion_metadata
from src.ingestion.service import IngestionService
from src.models.content import ContentSource
from src.models.jobs import OperationType
from src.queue.workflow_handlers import WorkflowExecutionError, build_workflow_handler_registry
from src.services.capability_service import CapabilityService

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRET = "x-bookmarks-registry-test-secret-0123456789"
AUTH_TOKEN_VALUE = "fake-auth-token-value-aaa"
CT0_VALUE = "fake-ct0-value-bbb"
ROTATED_VALUE = "fake-rotated-value-ccc"
SOURCE = XBookmarksSource(name="x-bookmarks", max_entries=40, expand_links=True)


# -- source configuration ---------------------------------------------------


def test_source_defaults_and_fixed_single_account_identity() -> None:
    source = XBookmarksSource()

    assert (source.type, source.expand_links, source.max_entries) == ("x_bookmarks", False, None)
    # The natural key never depends on the entry's name: one account, one source.
    assert source_key(source) == "x_bookmarks:account"
    assert source_key(XBookmarksSource(name="renamed")) == "x_bookmarks:account"
    assert source_key({"type": "x_bookmarks", "name": "from-db"}) == "x_bookmarks:account"
    assert configured_source_public_key(
        XBookmarksSource(name="a"), secret=SECRET
    ) == configured_source_public_key(XBookmarksSource(name="b"), secret=SECRET)


@pytest.mark.parametrize("max_entries", [0, 10_001])
def test_max_entries_matches_the_command_bounds(max_entries: int) -> None:
    with pytest.raises(ValidationError):
        XBookmarksSource(max_entries=max_entries)


def test_union_and_accessor_return_only_enabled_bookmark_sources() -> None:
    config = SourcesConfig.model_validate(
        {
            "sources": [
                {"type": "x_bookmarks", "name": "on", "expand_links": True},
                {"type": "x_bookmarks", "name": "off", "enabled": False},
                {"type": "rss", "url": "https://example.com/feed"},
            ]
        }
    )

    assert isinstance(config.sources[0], XBookmarksSource)
    assert [source.name for source in config.get_x_bookmarks_sources()] == ["on"]


def test_shipped_config_is_one_disabled_entry_so_fresh_installs_do_not_plan_it(
    tmp_path: Path,
) -> None:
    sources_dir = tmp_path / "sources.d"
    sources_dir.mkdir()
    for name in ("_defaults.yaml", "x_bookmarks.yaml"):
        (sources_dir / name).write_text((REPO_ROOT / "sources.d" / name).read_text())

    config = load_sources_directory(sources_dir)

    bookmarks = [source for source in config.sources if isinstance(source, XBookmarksSource)]
    assert len(bookmarks) == 1
    assert bookmarks[0].enabled is False
    assert bookmarks[0].expand_links is False
    assert bookmarks[0].max_entries == 100
    assert config.get_x_bookmarks_sources() == []
    SOURCE_REGISTRY.validate_config(config)
    assert (
        SOURCE_REGISTRY.plan_scheduled_commands(
            config,
            sources=None,
            period_start=datetime(2026, 9, 1, tzinfo=UTC),
            period_end=datetime(2026, 9, 2, tzinfo=UTC),
        )
        == ()
    )


# -- descriptor ---------------------------------------------------------------


def test_descriptor_is_scheduled_and_emits_x_bookmarks() -> None:
    descriptor = SOURCE_REGISTRY.get("x_bookmarks")

    assert descriptor.display_name == "X Bookmarks"
    assert descriptor.command_model is XBookmarksIngestCommand
    assert descriptor.scheduled is True
    assert descriptor.emitted_sources == frozenset({ContentSource.X_BOOKMARKS})
    assert descriptor.options.supports_force is True
    assert descriptor.options.supports_date_range is False
    assert SOURCE_REGISTRY.descriptor_for_config(SOURCE) is descriptor
    assert SOURCE_REGISTRY.keys()[-1] == "x_bookmarks"


def test_planner_maps_config_and_ignores_the_period() -> None:
    config = SourcesConfig(sources=[RSSSource(url="https://example.com/feed"), SOURCE])

    plans = [
        SOURCE_REGISTRY.plan_scheduled_commands(
            config,
            sources=["x_bookmarks"],
            period_start=start,
            period_end=datetime(2026, 9, 30, tzinfo=UTC),
        )
        for start in (datetime(2026, 9, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
    ]

    assert plans[0] == plans[1]
    (command,) = plans[0]
    assert command.model_dump(mode="json") == {
        "kind": "x_bookmarks",
        "configured_sources": [SOURCE.model_dump(mode="json")],
        "max_items": 40,
        "full": False,
        "expand_links": True,
        "force_reprocess": False,
    }


def test_planner_leaves_max_items_to_the_adapter_when_unconfigured() -> None:
    config = SourcesConfig(sources=[XBookmarksSource()])

    (command,) = SOURCE_REGISTRY.plan_scheduled_commands(
        config,
        sources=["x_bookmarks"],
        period_start=datetime(2026, 9, 1, tzinfo=UTC),
        period_end=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert (command.max_items, command.expand_links) == (None, False)


def test_dispatch_forwards_only_command_fields() -> None:
    descriptor = SOURCE_REGISTRY.get("x_bookmarks")
    command = XBookmarksIngestCommand(max_items=5, full=True, expand_links=False)

    with patch("src.ingestion.orchestrator.ingest_x_bookmarks") as orchestrator:
        descriptor.orchestrator(command)

    orchestrator.assert_called_once_with(
        max_items=5, full=True, expand_links=False, force_reprocess=False
    )


# -- readiness ---------------------------------------------------------------


class _FakeBao:
    def __init__(self, values: dict[str, str]) -> None:
        self.cache = dict(values)

    def read(self) -> dict[str, str]:
        return dict(self.cache)

    def refresh(self, *, min_interval_s: float = 0.0) -> bool:
        return False


def _provider(bao: _FakeBao, **settings_values: str | None) -> CredentialProvider:
    settings = SimpleNamespace(
        substack_session_cookie=None,
        x_auth_token=settings_values.get("x_auth_token"),
        x_ct0=settings_values.get("x_ct0"),
    )
    return CredentialProvider(
        settings_factory=lambda: settings,
        bao_reader=bao.read,
        bao_refresher=bao.refresh,
    )


@pytest.fixture
def install_provider(monkeypatch: pytest.MonkeyPatch):
    def install(provider: CredentialProvider) -> None:
        monkeypatch.setattr(credentials_mod, "_default_provider", provider)

    # Readiness must go through the provider, never through Settings.
    def _forbidden() -> None:
        raise AssertionError("readiness read Settings directly")

    settings_module = importlib.import_module("src.config.settings")
    monkeypatch.setattr(settings_module, "get_settings", _forbidden)
    return install


def _readiness() -> tuple[bool, str | None]:
    result = SOURCE_REGISTRY.get("x_bookmarks").resolve_readiness(SOURCE)
    return result.ready, result.code


@pytest.mark.parametrize(
    "values",
    [{}, {X_AUTH_TOKEN: AUTH_TOKEN_VALUE}, {X_CT0: CT0_VALUE}],
    ids=["neither", "auth_token_only", "ct0_only"],
)
def test_readiness_requires_both_cookies(install_provider, values: dict[str, str]) -> None:
    install_provider(_provider(_FakeBao(values)))

    assert _readiness() == (False, CREDENTIALS_MISSING)


def test_readiness_accepts_the_pair_from_openbao_or_settings(install_provider) -> None:
    install_provider(_provider(_FakeBao({X_AUTH_TOKEN: AUTH_TOKEN_VALUE, X_CT0: CT0_VALUE})))
    assert _readiness() == (True, None)

    install_provider(_provider(_FakeBao({}), x_auth_token=AUTH_TOKEN_VALUE, x_ct0=CT0_VALUE))
    assert _readiness() == (True, None)


@pytest.mark.parametrize("rejected", [X_AUTH_TOKEN, X_CT0])
def test_either_rejected_cookie_reports_session_expired_until_rotated(
    install_provider, rejected: str
) -> None:
    bao = _FakeBao({X_AUTH_TOKEN: AUTH_TOKEN_VALUE, X_CT0: CT0_VALUE})
    provider = _provider(bao)
    install_provider(provider)

    provider.mark_rejected(rejected)
    assert _readiness() == (False, SESSION_EXPIRED)

    # A freshly captured session flips readiness in the same process.
    bao.cache[rejected] = ROTATED_VALUE
    assert _readiness() == (True, None)


def test_readiness_fails_closed_when_the_provider_breaks(
    install_provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(_FakeBao({X_AUTH_TOKEN: AUTH_TOKEN_VALUE, X_CT0: CT0_VALUE}))
    install_provider(provider)

    def _boom(_name: str) -> None:
        raise RuntimeError(f"backend exploded holding {CT0_VALUE}")

    monkeypatch.setattr(provider, "metadata", _boom)

    assert _readiness() == (False, "source_unavailable")


def test_configured_source_listing_is_value_free(install_provider) -> None:
    install_provider(_provider(_FakeBao({X_AUTH_TOKEN: AUTH_TOKEN_VALUE})))

    page = CapabilityService(configured_source_key_secret=SECRET).list_configured_sources(
        SourcesConfig(sources=[SOURCE])
    )

    (listed,) = page.data
    assert listed.command_key == "x_bookmarks"
    assert (listed.ready, listed.readiness_code) == (False, CREDENTIALS_MISSING)
    assert listed.configuration["expand_links"] is True
    assert listed.configuration["max_entries"] == 40
    serialized = page.model_dump_json()
    assert AUTH_TOKEN_VALUE not in serialized
    assert "x-bookmarks" not in serialized


# -- orchestrator: fails closed until the adapter ships ------------------------


def test_orchestrator_fails_closed_with_a_stable_code() -> None:
    from src.ingestion.orchestrator import ingest_x_bookmarks

    with (
        patch("src.ingestion.filter_hook.apply_filter_to_recent"),
        patch("httpx.Client.send", side_effect=AssertionError("network")),
    ):
        response = ingest_x_bookmarks(max_items=3, full=True, expand_links=True)

    assert response.command == "ingest.x-bookmarks"
    assert response.source == "x_bookmarks"
    assert response.status == "error"
    assert (response.items_ingested, response.items_failed) == (0, 0)
    assert [error.code for error in response.errors] == ["source_unavailable"]
    projection = sanitize_ingestion_metadata(errors=[e.model_dump() for e in response.errors])
    assert projection["errors"][0]["code"] == "source_unavailable"


@pytest.mark.asyncio
async def test_durable_operation_records_the_failure_and_persists_nothing() -> None:
    attached: list[dict] = []

    class _Operations:
        async def attach_result(self, _operation_id: int, result: dict) -> None:
            attached.append(result)

        async def update_progress(self, *_args: object) -> None:
            return None

        async def checkpoint_cancellation(self, *_args: object, **_kwargs: object) -> None:
            return None

    registry = build_workflow_handler_registry(
        operation_service=_Operations(),
        ingestion_service=IngestionService(configured_source_key_secret=SECRET),
    )
    payload = {
        "kind": "x_bookmarks",
        "max_items": 2,
        "configured_sources": [SOURCE.model_dump(mode="json")],
    }

    with (
        patch("src.ingestion.filter_hook.apply_filter_to_recent"),
        pytest.raises(WorkflowExecutionError, match="Ingestion 'x_bookmarks' failed"),
    ):
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 41, payload)

    (result,) = attached
    assert result["command_key"] == "x_bookmarks"
    assert result["emitted_sources"] == ["x_bookmarks"]
    assert (result["status"], result["outcome"]) == ("error", "failed")
    assert (result["items_ingested"], result["content_ids"]) == (0, [])
    assert result["errors"] == [
        {"code": "source_unavailable", "message": "The configured source is unavailable"}
    ]


# -- live-tier policy ------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "decision"),
    [
        ({"X_AUTH_TOKEN": "t", "X_CT0": "c"}, LiveDecision.LIVE),
        ({"X_AUTH_TOKEN": "t"}, LiveDecision.SKIP_MISSING_CREDENTIAL),
        ({"X_CT0": "c"}, LiveDecision.SKIP_MISSING_CREDENTIAL),
        ({}, LiveDecision.SKIP_MISSING_CREDENTIAL),
    ],
)
def test_live_policy_needs_both_cookies(env: dict[str, str], decision: LiveDecision) -> None:
    evaluation = evaluate_live_adapter("x_bookmarks", live_enabled=True, env=env)

    assert evaluation.decision is decision
    if decision is LiveDecision.SKIP_MISSING_CREDENTIAL:
        assert evaluation.reason == "Skipped: missing credential (X_AUTH_TOKEN and X_CT0)"
