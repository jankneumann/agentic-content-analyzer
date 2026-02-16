"""Tests for the switch-embeddings script.

Tests:
- Dry run reports without making changes
- Clear embeddings nulls all embedding data
- Invalid provider returns error
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("src.storage.database.get_db_session")
@patch("src.config.settings.get_settings")
@patch("src.services.embedding.get_embedding_provider")
async def test_dry_run_does_not_modify_data(mock_get_provider, mock_get_settings, mock_get_db):
    from src.scripts.switch_embeddings import switch_embeddings

    mock_provider = MagicMock()
    mock_provider.dimensions = 1536
    mock_get_provider.return_value = mock_provider

    mock_settings = MagicMock()
    mock_settings.embedding_provider = "openai"
    mock_settings.embedding_model = "text-embedding-3-small"
    mock_get_settings.return_value = mock_settings

    mock_db = MagicMock()
    # COUNT(*) WHERE embedding IS NOT NULL
    mock_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=50)),  # existing count
        MagicMock(scalar=MagicMock(return_value=100)),  # total count
    ]
    mock_get_db.return_value = mock_db

    result = await switch_embeddings(dry_run=True)

    assert result["dry_run"] is True
    assert result["existing_embeddings"] == 50
    assert result["total_chunks"] == 100
    assert result["target_provider"] == "openai"
    assert result["target_dimensions"] == 1536

    # Verify no UPDATE or DROP was executed (only 2 SELECT calls)
    assert mock_db.execute.call_count == 2
    assert mock_db.commit.call_count == 0


@pytest.mark.asyncio
@patch("src.storage.database.get_db_session")
@patch("src.config.settings.get_settings")
@patch("src.services.embedding.get_embedding_provider")
async def test_clear_embeddings_nulls_data(mock_get_provider, mock_get_settings, mock_get_db):
    from src.scripts.switch_embeddings import switch_embeddings

    mock_provider = MagicMock()
    mock_provider.dimensions = 1024
    mock_get_provider.return_value = mock_provider

    mock_settings = MagicMock()
    mock_settings.embedding_provider = "voyage"
    mock_settings.embedding_model = "voyage-3"
    mock_get_settings.return_value = mock_settings

    mock_db = MagicMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=25)),  # existing count
        MagicMock(scalar=MagicMock(return_value=50)),  # total count
        None,  # UPDATE (NULL embeddings)
        None,  # DROP INDEX
        None,  # CREATE INDEX
    ]
    mock_get_db.return_value = mock_db

    result = await switch_embeddings(skip_backfill=True)

    assert result["embeddings_cleared"] == 25
    assert result["index_rebuilt"] is True
    assert result.get("backfill") is None

    # Verify commit was called (for clearing and index rebuild)
    assert mock_db.commit.call_count == 2


@pytest.mark.asyncio
@patch("src.config.settings.get_settings")
@patch("src.services.embedding.get_embedding_provider")
async def test_invalid_provider_returns_error(mock_get_provider, mock_get_settings):
    from src.scripts.switch_embeddings import switch_embeddings

    mock_get_provider.side_effect = ValueError("Unknown embedding provider: bogus")
    mock_settings = MagicMock()
    mock_settings.embedding_provider = "bogus"
    mock_settings.embedding_model = "test"
    mock_get_settings.return_value = mock_settings

    result = await switch_embeddings(provider="bogus")

    assert "error" in result
    assert "bogus" in result["error"]
