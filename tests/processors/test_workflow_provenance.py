"""Processor-level invariants for immutable workflow provenance."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.content import ContentSource, ContentStatus
from src.models.digest import DigestRequest, DigestType
from src.models.podcast import PodcastLength, PodcastRequest
from src.models.query import (
    DateBasis,
    ResolvedContentItem,
    ResolvedContentSet,
    SelectionPolicy,
    compute_selection_fingerprint,
)
from src.models.theme import ThemeCategory, ThemeData, ThemeTrend
from src.processors.digest_creator import DigestCreator
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.processors.provenance import (
    DigestProvenanceError,
    ExactContentSetLoader,
    LoadedContentItem,
    LoadedDigestContext,
    ProvenanceViolationError,
)
from src.processors.script_reviser import PodcastScriptReviser
from src.processors.theme_analyzer import ThemeAnalyzer


def _resolved_set() -> ResolvedContentSet:
    policy = SelectionPolicy(
        statuses=(ContentStatus.COMPLETED,),
        start_date=datetime(2026, 7, 1, tzinfo=UTC),
        end_date=datetime(2026, 7, 8, tzinfo=UTC),
        date_basis=DateBasis.PUBLISHED_DATE,
        sort_order="desc",
    )
    items = (
        ResolvedContentItem(
            content_id=20,
            summary_id=120,
            source_type=ContentSource.RSS,
            title="Second",
            publication="Feed",
            selection_date=datetime(2026, 7, 7, tzinfo=UTC),
        ),
        ResolvedContentItem(
            content_id=10,
            summary_id=110,
            source_type=ContentSource.GMAIL,
            title="First",
            publication="Inbox",
            selection_date=datetime(2026, 7, 6, tzinfo=UTC),
        ),
    )
    return ResolvedContentSet(
        policy=policy,
        items=items,
        fingerprint=compute_selection_fingerprint(
            policy,
            [item.content_id for item in items],
            [item.summary_id for item in items],
        ),
    )


def _loaded_items() -> tuple[LoadedContentItem, ...]:
    def content(content_id: int, title: str, source: ContentSource) -> SimpleNamespace:
        return SimpleNamespace(
            id=content_id,
            title=title,
            publication="Publication",
            published_date=datetime(2026, 7, 7, tzinfo=UTC),
            source_type=source,
            source_url=f"https://example.test/{content_id}",
            markdown_content=f"Full content {content_id}",
            raw_text=None,
        )

    def summary(summary_id: int, content_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            id=summary_id,
            content_id=content_id,
            executive_summary=f"Summary {content_id}",
            key_themes=["agents"],
            theme_tags=[],
            strategic_insights=["insight"],
            technical_details=["detail"],
            actionable_items=[],
            notable_quotes=[],
            relevant_links=[],
        )

    return (
        LoadedContentItem(content(20, "Second", ContentSource.RSS), summary(120, 20)),
        LoadedContentItem(content(10, "First", ContentSource.GMAIL), summary(110, 10)),
    )


def _digest(resolved: ResolvedContentSet) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        digest_type=DigestType.WEEKLY,
        period_start=datetime(2026, 7, 1, tzinfo=UTC),
        period_end=datetime(2026, 7, 8, tzinfo=UTC),
        title="Weekly Digest",
        executive_overview="Overview",
        strategic_insights=[],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        newsletter_count=resolved.eligible_content_count,
        source_content_ids=list(resolved.content_ids),
        source_summary_ids=list(resolved.summary_ids),
        selection_policy=resolved.policy.model_dump(mode="json"),
        selection_fingerprint=resolved.fingerprint,
    )


def test_exact_loader_restores_resolved_order_and_pairs() -> None:
    resolved = _resolved_set()
    contents = [item.content for item in reversed(_loaded_items())]
    summaries = [item.summary for item in _loaded_items()]
    session = MagicMock()
    session.query.side_effect = [
        MagicMock(filter=MagicMock(return_value=MagicMock(all=MagicMock(return_value=contents)))),
        MagicMock(filter=MagicMock(return_value=MagicMock(all=MagicMock(return_value=summaries)))),
    ]

    loaded = ExactContentSetLoader().load(resolved, session=session)

    assert [item.content.id for item in loaded] == [20, 10]
    assert [item.summary.id for item in loaded] == [120, 110]


def test_exact_loader_rejects_summary_content_mismatch() -> None:
    resolved = _resolved_set()
    loaded_items = list(_loaded_items())
    loaded_items[0].summary.content_id = 999
    session = MagicMock()
    session.query.side_effect = [
        MagicMock(
            filter=MagicMock(
                return_value=MagicMock(
                    all=MagicMock(return_value=[item.content for item in loaded_items])
                )
            )
        ),
        MagicMock(
            filter=MagicMock(
                return_value=MagicMock(
                    all=MagicMock(return_value=[item.summary for item in loaded_items])
                )
            )
        ),
    ]

    with pytest.raises(ProvenanceViolationError, match="summary 120"):
        ExactContentSetLoader().load(resolved, session=session)


def test_exact_loader_rejects_inconsistent_resolved_fingerprint() -> None:
    resolved = _resolved_set().model_copy(update={"fingerprint": "0" * 64})

    with pytest.raises(ProvenanceViolationError, match="fingerprint"):
        ExactContentSetLoader().load(resolved, session=MagicMock())


@pytest.mark.asyncio
async def test_theme_analyzer_consumes_exact_resolved_set() -> None:
    resolved = _resolved_set()
    loader = MagicMock()
    loader.load.return_value = _loaded_items()
    router = MagicMock()
    analyzer = ThemeAnalyzer(content_loader=loader, llm_router=router)
    analyzer._get_client = AsyncMock(return_value=None)
    analyzer._extract_themes_with_llm = AsyncMock(return_value=[])

    result = await analyzer.analyze_themes(
        request=SimpleNamespace(
            start_date=resolved.policy.start_date,
            end_date=resolved.policy.end_date,
            min_newsletters=1,
            max_themes=5,
            relevance_threshold=0.3,
        ),
        resolved_set=resolved,
        include_historical_context=False,
    )

    loader.load.assert_called_once_with(resolved)
    call = analyzer._extract_themes_with_llm.await_args.kwargs
    assert [item["id"] for item in call["contents"]] == [20, 10]
    assert [item["id"] for item in call["summaries"]] == [120, 110]
    assert result.content_ids == [20, 10]
    assert result.summary_ids == [120, 110]
    assert result.selection_fingerprint == resolved.fingerprint
    assert result.selection_policy == resolved.policy.model_dump(mode="json")


@pytest.mark.asyncio
async def test_theme_analyzer_preserves_snapshot_when_below_minimum() -> None:
    resolved = _resolved_set()
    loader = MagicMock()
    loader.load.return_value = _loaded_items()
    analyzer = ThemeAnalyzer(content_loader=loader, llm_router=MagicMock())
    analyzer._get_client = AsyncMock(return_value=None)
    analyzer._extract_themes_with_llm = AsyncMock()

    result = await analyzer.analyze_themes(
        request=SimpleNamespace(
            start_date=resolved.policy.start_date,
            end_date=resolved.policy.end_date,
            min_newsletters=3,
            max_themes=5,
            relevance_threshold=0.3,
        ),
        resolved_set=resolved,
        include_historical_context=False,
    )

    analyzer._extract_themes_with_llm.assert_not_awaited()
    assert result.content_count == 2
    assert result.content_ids == [20, 10]
    assert result.summary_ids == [120, 110]
    assert result.selection_fingerprint == resolved.fingerprint


def test_theme_parser_never_fabricates_or_leaks_content_ids() -> None:
    analyzer = ThemeAnalyzer(content_loader=MagicMock(), llm_router=MagicMock())
    contents = [
        {
            "id": 20,
            "published_date": datetime(2026, 7, 7, tzinfo=UTC),
        },
        {
            "id": 10,
            "published_date": datetime(2026, 7, 6, tzinfo=UTC),
        },
    ]
    response = """[{"name":"Agents","description":"Agent systems","category":"ml_ai",
        "mention_count":99,"content_ids":[20,999],"trend":"growing","relevance_score":0.9,
        "strategic_relevance":0.8,"tactical_relevance":0.7,"novelty_score":0.6,
        "cross_functional_impact":0.5}]"""

    themes = analyzer._parse_theme_response(response, contents)

    assert themes[0].content_ids == [20]
    assert themes[0].mention_count == 1


@pytest.mark.asyncio
async def test_digest_returns_exact_selection_snapshot() -> None:
    resolved = _resolved_set()
    loader = MagicMock()
    loader.load.return_value = _loaded_items()
    creator = DigestCreator(content_loader=loader, llm_router=MagicMock())
    creator._check_token_budget = AsyncMock(return_value=(False, {"content_budget": 10_000}))
    creator._generate_digest_content = AsyncMock(
        return_value={
            "title": "Exact Digest",
            "executive_overview": "Overview",
            "strategic_insights": [],
            "technical_developments": [],
            "emerging_trends": [],
            "actionable_recommendations": {},
        }
    )
    request = DigestRequest(
        digest_type=DigestType.WEEKLY,
        period_start=resolved.policy.start_date,
        period_end=resolved.policy.end_date,
    )

    digest = await creator.create_digest(request, resolved, themes=[])

    assert digest.source_content_ids == [20, 10]
    assert digest.source_summary_ids == [120, 110]
    assert digest.selection_policy == resolved.policy.model_dump(mode="json")
    assert digest.selection_fingerprint == resolved.fingerprint
    assert digest.newsletter_count == 2


@pytest.mark.asyncio
async def test_podcast_context_uses_digest_snapshot_without_period_query() -> None:
    resolved = _resolved_set()
    loader = MagicMock()
    loader.load_digest.return_value = LoadedDigestContext(
        digest=_digest(resolved),
        resolved_set=resolved,
        items=_loaded_items(),
    )
    generator = PodcastScriptGenerator(content_loader=loader, llm_router=MagicMock())
    request = PodcastRequest(digest_id=7, length=PodcastLength.BRIEF)

    context = await generator._assemble_lightweight_context(request)

    loader.load_digest.assert_called_once_with(7)
    assert [item["id"] for item in context["content_metadata"]] == [20, 10]
    assert [item.id for item in context["summaries"]] == [120, 110]
    assert context["selection_fingerprint"] == resolved.fingerprint
    assert generator.available_content_ids == (20, 10)


@pytest.mark.asyncio
async def test_podcast_tool_rejects_out_of_set_before_database_access() -> None:
    generator = PodcastScriptGenerator(content_loader=MagicMock(), llm_router=MagicMock())
    generator.available_content_ids = (20, 10)

    result = await generator._handle_get_content(999)

    assert '"type":"provenance_violation"' in result
    assert generator.content_ids_fetched == []


def test_podcast_rejects_out_of_set_citation() -> None:
    generator = PodcastScriptGenerator(content_loader=MagicMock(), llm_router=MagicMock())
    generator.available_content_ids = (20, 10)
    response = SimpleNamespace(
        text=(
            '{"title":"Episode","sections":[{"section_type":"intro",'
            '"title":"Intro","dialogue":[],"sources_cited":[999]}],'
            '"sources_summary":[]}'
        )
    )

    with pytest.raises(ProvenanceViolationError, match="citation"):
        generator._parse_script_response(response, PodcastLength.BRIEF)


def test_podcast_rejects_non_integer_source_summary_id() -> None:
    generator = PodcastScriptGenerator(content_loader=MagicMock(), llm_router=MagicMock())
    generator.available_content_ids = (20, 10)
    response = SimpleNamespace(
        text=(
            '{"title":"Episode","sections":[],"sources_summary":[{"id":"20","title":"Wrong type"}]}'
        )
    )

    with pytest.raises(ProvenanceViolationError, match="non-integer"):
        generator._parse_script_response(response, PodcastLength.BRIEF)


def test_legacy_digest_provenance_is_rejected_without_fallback() -> None:
    digest = _digest(_resolved_set())
    digest.selection_policy = {"schema_version": 0, "provenance": "legacy-v0"}
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = digest

    with pytest.raises(DigestProvenanceError, match="legacy-v0"):
        ExactContentSetLoader().load_digest(7, session=session)


@pytest.mark.parametrize(
    ("content_ids", "summary_ids", "message"),
    [
        ((20, 20), (120, 110), "duplicate IDs"),
        ((20, 10), (120, 120), "duplicate IDs"),
    ],
)
def test_digest_rejects_duplicate_provenance_ids(
    content_ids: tuple[int, ...],
    summary_ids: tuple[int, ...],
    message: str,
) -> None:
    resolved = _resolved_set()
    digest = _digest(resolved)
    digest.source_content_ids = list(content_ids)
    digest.source_summary_ids = list(summary_ids)
    digest.newsletter_count = len(content_ids)
    digest.selection_fingerprint = compute_selection_fingerprint(
        resolved.policy,
        content_ids,
        summary_ids,
    )
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = digest

    with pytest.raises(DigestProvenanceError, match=message):
        ExactContentSetLoader().load_digest(7, session=session)


def test_digest_rejects_count_mismatch() -> None:
    resolved = _resolved_set()
    digest = _digest(resolved)
    digest.newsletter_count = 99
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = digest

    with pytest.raises(DigestProvenanceError, match="count"):
        ExactContentSetLoader().load_digest(7, session=session)


def test_theme_ids_must_be_subset_of_digest_ids() -> None:
    resolved = _resolved_set()
    invalid_theme = ThemeData(
        name="Outside",
        description="Invalid provenance",
        category=ThemeCategory.ML_AI,
        mention_count=1,
        content_ids=[999],
        first_seen=datetime(2026, 7, 1, tzinfo=UTC),
        last_seen=datetime(2026, 7, 1, tzinfo=UTC),
        trend=ThemeTrend.EMERGING,
        relevance_score=0.9,
        strategic_relevance=0.9,
        tactical_relevance=0.9,
        novelty_score=0.9,
        cross_functional_impact=0.9,
    )
    creator = DigestCreator(content_loader=MagicMock(), llm_router=MagicMock())

    with pytest.raises(ProvenanceViolationError, match="theme"):
        creator._validate_theme_provenance([invalid_theme], resolved)


def test_revision_recomputes_cited_snapshot_in_available_order() -> None:
    script = SimpleNamespace(
        sections=[
            SimpleNamespace(sources_cited=[10]),
            SimpleNamespace(sources_cited=[20, 10]),
        ]
    )

    cited = PodcastScriptReviser._ordered_cited_ids(script, [20, 10, 30])

    assert cited == [20, 10]
