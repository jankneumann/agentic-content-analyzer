"""Reranking provider abstraction for search result quality improvement.

Provides an optional cross-encoder reranking step after RRF fusion.
Disabled by default — users opt in via SEARCH_RERANK_ENABLED=true.

Providers:
- CohereRerankProvider: Cohere Rerank API
- JinaRerankProvider: Jina Rerank API
- LocalCrossEncoderProvider: sentence-transformers CrossEncoder (CPU)
- LLMRerankProvider: Uses existing LLM router with structured prompting
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class RerankProvider(Protocol):
    """Protocol for pluggable reranking implementations."""

    @property
    def name(self) -> str: ...

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Rerank documents against query.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Maximum results to return (None = all)

        Returns:
            List of (original_index, relevance_score) sorted by relevance descending.
        """
        ...


class CohereRerankProvider:
    """Cohere Rerank API provider."""

    def __init__(self, model: str = "rerank-english-v3.0") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return "cohere"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        import cohere  # type: ignore[import-untyped]

        settings = get_settings()
        client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)

        response = await client.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_n=top_k or len(documents),
        )
        return [(r.index, r.relevance_score) for r in response.results]


class JinaRerankProvider:
    """Jina Rerank API provider."""

    def __init__(self, model: str = "jina-reranker-v2-base-multilingual") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return "jina"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        import httpx

        settings = get_settings()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.jina.ai/v1/rerank",
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k or len(documents),
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        return [
            (r["index"], r["relevance_score"])
            for r in results
            if "index" in r and "relevance_score" in r
        ]


class LocalCrossEncoderProvider:
    """Local sentence-transformers CrossEncoder (runs on CPU)."""

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2") -> None:
        self._model_name = model
        self._model = None

    @property
    def name(self) -> str:
        return "local"

    def _get_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            self._model = CrossEncoder(self._model_name)
        return self._model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        def _score() -> list[tuple[int, float]]:
            model = self._get_model()
            pairs = [(query, doc) for doc in documents]
            scores = model.predict(pairs)
            indexed = [(i, float(s)) for i, s in enumerate(scores)]
            indexed.sort(key=lambda x: x[1], reverse=True)
            if top_k:
                indexed = indexed[:top_k]
            return indexed

        return await asyncio.to_thread(_score)


class LLMRerankProvider:
    """Uses existing LLM router with structured prompting for reranking.

    Scores each candidate with a relevance rating prompt, then sorts.
    Best quality but highest latency and cost.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return "llm"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        from src.services.llm_router import get_llm_client

        settings = get_settings()
        model = self._model or settings.search_rerank_model or "claude-haiku-4-5"
        client = get_llm_client()

        semaphore = asyncio.Semaphore(10)

        async def _score_one(idx: int, doc: str) -> tuple[int, float]:
            prompt = (
                "Rate the relevance of this document excerpt to the query "
                "on a scale of 0-10. Respond with only the number.\n\n"
                f"Query: {query}\n\n"
                f"Document: {doc[:2000]}"
            )
            async with semaphore:
                try:
                    response = await client.generate(
                        prompt=prompt,
                        model=model,
                        max_tokens=5,
                    )
                    score = int(response.strip())
                    return (idx, float(min(max(score, 0), 10)))
                except (ValueError, TypeError):
                    return (idx, 5.0)  # Default on parse failure
                except Exception:
                    logger.warning(f"LLM rerank failed for doc {idx}", exc_info=True)
                    return (idx, 5.0)

        tasks = [_score_one(i, doc) for i, doc in enumerate(documents)]
        results = await asyncio.gather(*tasks)

        results_list = list(results)
        results_list.sort(key=lambda x: x[1], reverse=True)
        if top_k:
            results_list = results_list[:top_k]
        return results_list


def get_rerank_provider(
    provider_name: str | None = None,
    model: str | None = None,
) -> RerankProvider | None:
    """Factory: create reranking provider if enabled.

    Returns None if reranking is disabled (default).

    Args:
        provider_name: Override provider name
        model: Override model name

    Returns:
        RerankProvider instance, or None if disabled
    """
    settings = get_settings()

    if not settings.search_rerank_enabled:
        return None

    name = (provider_name or settings.search_rerank_provider).lower()
    model_name = model or settings.search_rerank_model

    if name == "cohere":
        return CohereRerankProvider(model_name or "rerank-english-v3.0")
    elif name == "jina":
        return JinaRerankProvider(model_name or "jina-reranker-v2-base-multilingual")
    elif name == "local":
        return LocalCrossEncoderProvider(model_name or "cross-encoder/ms-marco-MiniLM-L-12-v2")
    elif name == "llm":
        return LLMRerankProvider(model_name)
    else:
        raise ValueError(f"Unknown rerank provider: {name}")
