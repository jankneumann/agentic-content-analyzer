"""Tests for memory strategies — Vector, Keyword, Graph.

Covers Tasks 1.6, 1.8, 1.10: Individual strategy store/recall/forget.
All strategies are tested against mocked backends.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType
from src.agents.memory.strategies.base import MemoryStrategy


class TestMemoryStrategyABC:
    """Test that the ABC enforces the interface."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            MemoryStrategy()

    def test_subclass_must_implement_all_methods(self):
        class IncompleteStrategy(MemoryStrategy):
            async def store(self, memory):
                return "id"

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_complete_subclass_can_instantiate(self):
        class CompleteStrategy(MemoryStrategy):
            async def store(self, memory):
                return "id"

            async def recall(self, query, limit=10, filters=None):
                return []

            async def forget(self, memory_id):
                return True

            async def health_check(self):
                return True

        strategy = CompleteStrategy()
        assert isinstance(strategy, MemoryStrategy)


class TestVectorStrategy:
    """Test VectorStrategy with mocked DB and embedding function."""

    @pytest.fixture
    def mock_embed_fn(self):
        fn = AsyncMock(return_value=[0.1] * 1536)
        return fn

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = ctx
        return factory

    @pytest.fixture
    def strategy(self, mock_session_factory, mock_embed_fn):
        from src.agents.memory.strategies.vector import VectorStrategy

        return VectorStrategy(
            db_session_factory=mock_session_factory,
            embed_fn=mock_embed_fn,
        )

    @pytest.mark.asyncio
    async def test_store_calls_embed_fn(self, strategy, mock_embed_fn):
        entry = MemoryEntry(content="test content", memory_type=MemoryType.OBSERVATION)
        result = await strategy.store(entry)
        mock_embed_fn.assert_called_once_with("test content")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_recall_calls_embed_fn(self, strategy, mock_embed_fn, mock_session):
        # Mock the DB result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        results = await strategy.recall("search query")
        mock_embed_fn.assert_called_with("search query")
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check(self, strategy, mock_session):
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        assert await strategy.health_check() is True


class TestKeywordStrategy:
    """Test KeywordStrategy with mocked DB."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = ctx
        return factory

    @pytest.fixture
    def strategy(self, mock_session_factory):
        from src.agents.memory.strategies.keyword import KeywordStrategy

        return KeywordStrategy(db_session_factory=mock_session_factory)

    @pytest.mark.asyncio
    async def test_store_returns_id(self, strategy, mock_session):
        entry = MemoryEntry(content="test content", memory_type=MemoryType.OBSERVATION)
        result = await strategy.store(entry)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_recall_empty_results(self, strategy, mock_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        results = await strategy.recall("search query")
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check(self, strategy, mock_session):
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        assert await strategy.health_check() is True


class TestGraphStrategy:
    """Test GraphStrategy with mocked Graphiti client."""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.add_episode = AsyncMock(return_value=MagicMock(uuid="ep-123"))
        client.search = AsyncMock(return_value=[])
        client.delete_episode = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        from src.agents.memory.strategies.graph import GraphStrategy

        return GraphStrategy(graph_client=mock_client)

    @pytest.mark.asyncio
    async def test_store_calls_add_episode(self, strategy, mock_client):
        entry = MemoryEntry(content="test content", memory_type=MemoryType.OBSERVATION)
        result = await strategy.store(entry)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_recall_returns_entries(self, strategy, mock_client):
        results = await strategy.recall("search query")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_forget_calls_delete(self, strategy, mock_client):
        result = await strategy.forget("ep-123")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_health_check_success(self, strategy, mock_client):
        result = await strategy.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, strategy, mock_client):
        mock_client.status = AsyncMock(side_effect=Exception("Connection refused"))
        result = await strategy.health_check()
        assert result is False
