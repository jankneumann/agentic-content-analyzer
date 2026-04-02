"""Memory provider with configurable strategy composition.

Composes multiple memory strategies (vector, keyword, graph) using
weighted Reciprocal Rank Fusion (RRF) for hybrid recall. Supports
graceful degradation when backends are unavailable.

RRF Formula: score(d) = Σ_s (weight_s / (k + rank_s(d)))
where k = 60 (standard RRF constant).

See spec: agentic-analysis.9 (hybrid recall), agentic-analysis.22 (RRF formula).
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict

from src.agents.memory.models import MemoryEntry, MemoryFilter
from src.agents.memory.strategies.base import MemoryStrategy

logger = logging.getLogger(__name__)

# RRF constants (spec: agentic-analysis.22)
RRF_K = 60
RRF_MIN_SCORE = 0.01
DEFAULT_MAX_RESULTS = 20

# Circuit breaker cooldown (spec: agentic-analysis.26)
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60


class MemoryProvider:
    """Composes multiple memory strategies with weighted RRF fusion.

    Args:
        strategies: Dict mapping strategy name to (strategy_instance, weight) tuples.
                    Weights should sum to ~1.0 but are normalized internally.
                    Example: {"graph": (GraphStrategy(), 0.4), "vector": (VectorStrategy(), 0.4)}
    """

    def __init__(self, strategies: dict[str, tuple[MemoryStrategy, float]]) -> None:
        self._strategies = strategies
        self._circuit_breaker: dict[str, float] = {}  # strategy_name -> failure_timestamp

    async def store(self, memory: MemoryEntry) -> str:
        """Store a memory entry across all healthy strategies.

        Returns the memory ID from the first successful store.
        Continues storing in remaining strategies even if some fail.
        """
        # Generate a consistent ID so all strategies store with the same key
        if not memory.id:
            memory = memory.model_copy(update={"id": str(uuid.uuid4())})
        stored_id = memory.id
        tasks = []

        for name, (strategy, _weight) in self._strategies.items():
            if self._is_circuit_open(name):
                logger.warning(f"Memory store: skipping {name} (circuit breaker open)")
                continue
            tasks.append(self._store_one(name, strategy, memory))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Memory store failed for a strategy: {result}")
            elif isinstance(result, str) and result and not stored_id:
                stored_id = result

        return stored_id

    async def recall(
        self,
        query: str,
        limit: int = DEFAULT_MAX_RESULTS,
        filters: MemoryFilter | None = None,
    ) -> list[MemoryEntry]:
        """Query all healthy strategies and merge results using weighted RRF.

        Returns deduplicated, score-ranked results up to the specified limit.
        If all strategies are unavailable, returns an empty list.
        """
        # Gather results from all healthy strategies
        strategy_results: dict[str, list[MemoryEntry]] = {}
        tasks = []
        task_names = []

        for name, (strategy, _weight) in self._strategies.items():
            if self._is_circuit_open(name):
                logger.warning(f"Memory recall: skipping {name} (circuit breaker open)")
                continue
            tasks.append(self._recall_one(name, strategy, query, limit, filters))
            task_names.append(name)

        if not tasks:
            logger.warning("Memory recall: all strategies unavailable, returning empty")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Memory recall failed for {name}: {result}")
                self._trip_circuit(name)
            elif isinstance(result, list):
                strategy_results[name] = result

        if not strategy_results:
            return []

        # Compute weighted RRF fusion
        merged = self._weighted_rrf(strategy_results)

        # Filter by minimum score and limit
        merged = [e for e in merged if e.score >= RRF_MIN_SCORE]
        merged.sort(key=lambda e: e.score, reverse=True)
        return merged[:limit]

    async def forget(self, memory_id: str) -> bool:
        """Remove a memory entry from all strategies.

        Respects circuit breaker state and trips on failure.
        """
        tasks = []
        task_names = []
        for name, (strategy, _weight) in self._strategies.items():
            if self._is_circuit_open(name):
                logger.warning("Memory forget: skipping %s (circuit breaker open)", name)
                continue
            tasks.append(strategy.forget(memory_id))
            task_names.append(name)

        if not tasks:
            return False

        results = await asyncio.gather(*tasks, return_exceptions=True)
        any_success = False
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.warning("Memory forget failed for %s: %s", name, result)
                self._trip_circuit(name)
            elif result is True:
                any_success = True
        return any_success

    def _weighted_rrf(
        self, strategy_results: dict[str, list[MemoryEntry]]
    ) -> list[MemoryEntry]:
        """Merge results from multiple strategies using weighted Reciprocal Rank Fusion.

        Formula: score(d) = Σ_s (weight_s / (k + rank_s(d)))
        where k = 60 and weight_s is the strategy's configured weight.

        Weights are redistributed proportionally among available strategies.
        """
        # Compute available weight total for normalization
        available_weights = {
            name: self._strategies[name][1]
            for name in strategy_results
            if name in self._strategies
        }
        total_weight = sum(available_weights.values())
        if total_weight == 0:
            return []

        # Normalize weights to sum to 1.0
        normalized_weights = {
            name: w / total_weight for name, w in available_weights.items()
        }

        # Compute RRF scores
        doc_scores: dict[str, float] = defaultdict(float)
        doc_entries: dict[str, MemoryEntry] = {}

        for strategy_name, entries in strategy_results.items():
            weight = normalized_weights.get(strategy_name, 0.0)
            for rank, entry in enumerate(entries, start=1):
                doc_id = entry.id
                # Entries without a usable ID can't be deduplicated; assign a unique key
                if not doc_id:
                    doc_id = f"_anon_{strategy_name}_{rank}"
                rrf_contribution = weight / (RRF_K + rank)
                doc_scores[doc_id] += rrf_contribution
                # Keep the entry with the best content (first seen wins)
                if doc_id not in doc_entries:
                    doc_entries[doc_id] = entry

        # Update scores on entries
        result = []
        for doc_id, score in doc_scores.items():
            entry = doc_entries[doc_id].model_copy(update={"score": score})
            result.append(entry)

        return result

    async def _store_one(
        self, name: str, strategy: MemoryStrategy, memory: MemoryEntry
    ) -> str:
        """Store in a single strategy with error handling."""
        try:
            return await strategy.store(memory)
        except Exception as e:
            logger.warning(f"Memory store failed for {name}: {e}")
            self._trip_circuit(name)
            raise

    async def _recall_one(
        self,
        name: str,
        strategy: MemoryStrategy,
        query: str,
        limit: int,
        filters: MemoryFilter | None,
    ) -> list[MemoryEntry]:
        """Recall from a single strategy with error handling."""
        try:
            return await strategy.recall(query, limit=limit, filters=filters)
        except Exception as e:
            logger.warning(f"Memory recall failed for {name}: {e}")
            self._trip_circuit(name)
            raise

    def _is_circuit_open(self, name: str) -> bool:
        """Check if a strategy's circuit breaker is open (recently failed)."""
        if name not in self._circuit_breaker:
            return False
        elapsed = time.monotonic() - self._circuit_breaker[name]
        if elapsed >= CIRCUIT_BREAKER_COOLDOWN_SECONDS:
            del self._circuit_breaker[name]
            return False
        return True

    def _trip_circuit(self, name: str) -> None:
        """Trip the circuit breaker for a strategy."""
        self._circuit_breaker[name] = time.monotonic()
        logger.warning(f"Circuit breaker tripped for memory strategy: {name}")
