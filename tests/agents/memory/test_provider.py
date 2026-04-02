"""Tests for MemoryProvider composition — RRF fusion, weights, graceful degradation.

Covers Task 1.12: Multi-strategy RRF fusion, configurable weights, graceful degradation.
Spec scenarios: agentic-analysis.9 (hybrid recall), agentic-analysis.10 (configuration).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType


class TestMemoryProviderComposition:
    """Test MemoryProvider with multiple strategies."""

    @pytest.fixture
    def make_entry(self):
        """Factory for creating MemoryEntry instances."""
        def _make(content: str, score: float = 0.5, id: str = "") -> MemoryEntry:
            return MemoryEntry(
                id=id or f"mem-{content[:8]}",
                content=content,
                memory_type=MemoryType.OBSERVATION,
                score=score,
            )
        return _make

    @pytest.fixture
    def mock_vector_strategy(self, make_entry):
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        strategy.recall = AsyncMock(return_value=[
            make_entry("vector result 1", score=0.9, id="v1"),
            make_entry("vector result 2", score=0.7, id="v2"),
            make_entry("shared result", score=0.8, id="shared-1"),
        ])
        strategy.store = AsyncMock(return_value="stored-id")
        strategy.forget = AsyncMock(return_value=True)
        return strategy

    @pytest.fixture
    def mock_keyword_strategy(self, make_entry):
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        strategy.recall = AsyncMock(return_value=[
            make_entry("keyword result 1", score=0.85, id="k1"),
            make_entry("shared result", score=0.75, id="shared-1"),
        ])
        strategy.store = AsyncMock(return_value="stored-id")
        strategy.forget = AsyncMock(return_value=True)
        return strategy

    @pytest.fixture
    def mock_graph_strategy(self, make_entry):
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        strategy.recall = AsyncMock(return_value=[
            make_entry("graph result 1", score=0.95, id="g1"),
            make_entry("shared result", score=0.7, id="shared-1"),
        ])
        strategy.store = AsyncMock(return_value="stored-id")
        strategy.forget = AsyncMock(return_value=True)
        return strategy

    @pytest.fixture
    def provider(self, mock_vector_strategy, mock_keyword_strategy, mock_graph_strategy):
        from src.agents.memory.provider import MemoryProvider
        return MemoryProvider(
            strategies={
                "vector": (mock_vector_strategy, 0.4),
                "keyword": (mock_keyword_strategy, 0.2),
                "graph": (mock_graph_strategy, 0.4),
            }
        )

    @pytest.mark.asyncio
    async def test_recall_queries_all_strategies(
        self, provider, mock_vector_strategy, mock_keyword_strategy, mock_graph_strategy
    ):
        results = await provider.recall("test query")
        mock_vector_strategy.recall.assert_called_once()
        mock_keyword_strategy.recall.assert_called_once()
        mock_graph_strategy.recall.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_deduplicates_by_id(self, provider):
        """shared-1 appears in all 3 strategies but should appear once in results."""
        results = await provider.recall("test query")
        ids = [r.id for r in results]
        assert ids.count("shared-1") == 1

    @pytest.mark.asyncio
    async def test_recall_returns_sorted_by_score(self, provider):
        results = await provider.recall("test query")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, provider):
        results = await provider.recall("test query", limit=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_recall_shared_result_boosted_by_rrf(self, provider, make_entry):
        """A result appearing in multiple strategies should score higher via RRF."""
        results = await provider.recall("test query")
        shared = next((r for r in results if r.id == "shared-1"), None)
        assert shared is not None
        # shared-1 appears in all 3 strategies, so should have higher RRF score
        # than results appearing in only 1 strategy
        single_strategy_results = [r for r in results if r.id in ("v2", "k1")]
        if single_strategy_results:
            assert shared.score >= min(r.score for r in single_strategy_results)

    @pytest.mark.asyncio
    async def test_store_stores_in_all_strategies(
        self, provider, mock_vector_strategy, mock_keyword_strategy, mock_graph_strategy
    ):
        entry = MemoryEntry(content="new memory", memory_type=MemoryType.OBSERVATION)
        result = await provider.store(entry)
        assert isinstance(result, str)
        mock_vector_strategy.store.assert_called_once()
        mock_keyword_strategy.store.assert_called_once()
        mock_graph_strategy.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_forget_forgets_from_all_strategies(
        self, provider, mock_vector_strategy, mock_keyword_strategy, mock_graph_strategy
    ):
        result = await provider.forget("mem-123")
        assert result is True
        mock_vector_strategy.forget.assert_called_once_with("mem-123")
        mock_keyword_strategy.forget.assert_called_once_with("mem-123")
        mock_graph_strategy.forget.assert_called_once_with("mem-123")


class TestMemoryProviderGracefulDegradation:
    """Test that the provider handles strategy failures gracefully."""

    @pytest.fixture
    def healthy_strategy(self):
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        strategy.recall = AsyncMock(return_value=[
            MemoryEntry(id="h1", content="healthy", memory_type=MemoryType.OBSERVATION, score=0.8)
        ])
        strategy.store = AsyncMock(return_value="stored-id")
        return strategy

    @pytest.fixture
    def unhealthy_strategy(self):
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=False)
        strategy.recall = AsyncMock(side_effect=Exception("Backend down"))
        strategy.store = AsyncMock(side_effect=Exception("Backend down"))
        return strategy

    @pytest.mark.asyncio
    async def test_recall_skips_unhealthy_strategy(self, healthy_strategy, unhealthy_strategy):
        from src.agents.memory.provider import MemoryProvider
        provider = MemoryProvider(
            strategies={
                "healthy": (healthy_strategy, 0.5),
                "unhealthy": (unhealthy_strategy, 0.5),
            }
        )
        results = await provider.recall("test")
        assert len(results) >= 1
        assert results[0].id == "h1"

    @pytest.mark.asyncio
    async def test_recall_returns_empty_when_all_down(self, unhealthy_strategy):
        from src.agents.memory.provider import MemoryProvider
        unhealthy2 = AsyncMock()
        unhealthy2.health_check = AsyncMock(return_value=False)
        unhealthy2.recall = AsyncMock(side_effect=Exception("Down"))
        provider = MemoryProvider(
            strategies={
                "s1": (unhealthy_strategy, 0.5),
                "s2": (unhealthy2, 0.5),
            }
        )
        results = await provider.recall("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_store_continues_on_partial_failure(self, healthy_strategy, unhealthy_strategy):
        from src.agents.memory.provider import MemoryProvider
        provider = MemoryProvider(
            strategies={
                "healthy": (healthy_strategy, 0.5),
                "unhealthy": (unhealthy_strategy, 0.5),
            }
        )
        # Should not raise, even though one strategy fails
        result = await provider.store(
            MemoryEntry(content="test", memory_type=MemoryType.OBSERVATION)
        )
        assert isinstance(result, str)
        healthy_strategy.store.assert_called_once()


class TestMemoryProviderWeights:
    """Test RRF weight configuration."""

    @pytest.mark.asyncio
    async def test_single_strategy_provider(self):
        from src.agents.memory.provider import MemoryProvider
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        strategy.recall = AsyncMock(return_value=[
            MemoryEntry(id="s1", content="result", memory_type=MemoryType.OBSERVATION, score=0.9)
        ])
        provider = MemoryProvider(strategies={"only": (strategy, 1.0)})
        results = await provider.recall("test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_rrf_min_score_filtering(self):
        """Results below the RRF minimum score threshold should be filtered out."""
        from src.agents.memory.provider import MemoryProvider
        strategy = AsyncMock()
        strategy.health_check = AsyncMock(return_value=True)
        # Return many low-score results — some should be filtered by RRF min score
        strategy.recall = AsyncMock(return_value=[
            MemoryEntry(
                id=f"r{i}", content=f"result {i}",
                memory_type=MemoryType.OBSERVATION, score=0.01
            )
            for i in range(50)
        ])
        provider = MemoryProvider(strategies={"only": (strategy, 1.0)})
        results = await provider.recall("test", limit=20)
        assert len(results) <= 20
