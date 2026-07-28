from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.config.sources import RSSSource, configured_source_public_key, source_key
from src.ingestion.gmail import ContentData
from src.ingestion.result import SourceFetchResult, use_public_source_keys
from src.ingestion.rss import RSSClient, RSSContentIngestionService
from src.models.content import ContentSource


def _content(source_id: str, feed_url: str) -> ContentData:
    return ContentData(
        source_type=ContentSource.RSS,
        source_id=source_id,
        title=source_id,
        markdown_content="body",
        metadata_json={"feed_url": feed_url},
        content_hash="",
    )


def test_rss_source_outcome_counts_only_successful_persistence() -> None:
    secret = "configured-source-key-secret-for-tests"
    source = RSSSource(url="https://private.example/feed")
    public_key = configured_source_public_key(source, secret=secret)
    fetch_result = SourceFetchResult(url=source.url, items_fetched=2)
    database = MagicMock()
    first_savepoint = MagicMock(is_active=True)
    second_savepoint = MagicMock(is_active=True)
    database.begin_nested.side_effect = [first_savepoint, second_savepoint]
    database.query.return_value.filter.return_value.first.return_value = None
    database.flush.side_effect = [None, RuntimeError("private database failure")]
    database_context = MagicMock()
    database_context.__enter__.return_value = database

    with (
        use_public_source_keys({source_key(source): public_key}),
        patch.object(
            RSSClient,
            "fetch_content",
            return_value=(
                [_content("first", source.url), _content("second", source.url)],
                fetch_result,
            ),
        ),
        patch("src.ingestion.rss.get_db", return_value=database_context),
        patch("src.services.indexing.index_content"),
    ):
        response = RSSContentIngestionService().ingest_content(sources=[source])

    assert response.items_ingested == 1
    assert response.items_failed == 1
    assert len(response.source_outcomes) == 1
    outcome = response.source_outcomes[0]
    assert outcome.source_key == public_key
    assert outcome.status == "partial"
    assert outcome.items_ingested == 1
    assert outcome.items_failed == 1
    assert [error.code for error in outcome.errors] == ["persistence_error"]
    first_savepoint.commit.assert_called_once_with()
    second_savepoint.rollback.assert_called_once_with()
    database.rollback.assert_not_called()
