"""Embedding provider abstraction for document chunk search.

Provides a pluggable EmbeddingProvider protocol with implementations for
OpenAI, Voyage AI, Cohere, and local sentence-transformers models.
Provider selection is configuration-driven via Settings.

All providers support asymmetric embedding via ``is_query`` parameter:
- ``is_query=False`` (default): embed documents for indexing
- ``is_query=True``: embed search queries for retrieval

Usage:
    provider = get_embedding_provider()
    vectors = await provider.embed_batch(["text1", "text2"])
    query_vec = await provider.embed("search query", is_query=True)
"""

from __future__ import annotations

import asyncio
import logging
import re
from functools import lru_cache
from typing import Protocol, runtime_checkable

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text before embedding: collapse whitespace, strip."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for pluggable embedding providers.

    All implementations must support the ``is_query`` parameter for
    asymmetric embedding (different encoding for queries vs documents).
    """

    @property
    def name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def max_tokens(self) -> int: ...

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        """Embed a single text string.

        Args:
            text: Text to embed.
            is_query: If True, use query-optimized encoding.
        """
        ...

    async def embed_batch(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """Embed multiple text strings in a single API call.

        Args:
            texts: Texts to embed.
            is_query: If True, use query-optimized encoding.
        """
        ...


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3-small/large provider.

    OpenAI embeddings are symmetric (same encoding for queries and documents),
    so ``is_query`` is accepted but ignored.
    """

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self._model = model
        self._client = None
        self._dimensions_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Lazy-initialize the OpenAI client for connection reuse."""
        if self._client is None:
            from openai import AsyncOpenAI

            settings = get_settings()
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def dimensions(self) -> int:
        return self._dimensions_map.get(self._model, 1536)

    @property
    def max_tokens(self) -> int:
        return 8191

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        results = await self.embed_batch([text], is_query=is_query)
        return results[0]

    async def embed_batch(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        response = await client.embeddings.create(
            model=self._model,
            input=normalized,
        )
        return [item.embedding for item in response.data]


class VoyageEmbeddingProvider:
    """Voyage AI embedding provider (optimized for retrieval).

    Voyage uses asymmetric embedding: ``input_type="query"`` for search queries,
    ``input_type="document"`` for indexing.
    """

    def __init__(self, model: str = "voyage-3") -> None:
        self._model = model
        self._client = None
        self._dimensions_map = {
            "voyage-3": 1024,
            "voyage-3-lite": 512,
            "voyage-2": 1024,
        }

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Lazy-initialize the Voyage AI client for connection reuse."""
        if self._client is None:
            import voyageai  # type: ignore[import-untyped]

            settings = get_settings()
            self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        return self._client

    @property
    def name(self) -> str:
        return "voyage"

    @property
    def dimensions(self) -> int:
        return self._dimensions_map.get(self._model, 1024)

    @property
    def max_tokens(self) -> int:
        return 32000

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        results = await self.embed_batch([text], is_query=is_query)
        return results[0]

    async def embed_batch(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        response = await client.embed(
            normalized,
            model=self._model,
            input_type="query" if is_query else "document",
        )
        return response.embeddings


class CohereEmbeddingProvider:
    """Cohere embed-english-v3.0 provider with input_type handling.

    Cohere uses asymmetric embedding: ``input_type="search_query"`` for queries,
    ``input_type="search_document"`` for indexing.
    """

    def __init__(self, model: str = "embed-english-v3.0") -> None:
        self._model = model
        self._client = None

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Lazy-initialize the Cohere client for connection reuse."""
        if self._client is None:
            import cohere  # type: ignore[import-untyped]

            settings = get_settings()
            self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
        return self._client

    @property
    def name(self) -> str:
        return "cohere"

    @property
    def dimensions(self) -> int:
        return 1024

    @property
    def max_tokens(self) -> int:
        return 512

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        results = await self.embed_batch([text], is_query=is_query)
        return results[0]

    async def embed_batch(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        input_type = "search_query" if is_query else "search_document"

        response = await client.embed(
            texts=normalized,
            model=self._model,
            input_type=input_type,
            embedding_types=["float"],
        )
        # Cohere SDK v2 uses .float_ (with underscore to avoid Python keyword collision)
        # but some versions may use .float — handle both
        embeddings = getattr(response.embeddings, "float_", None) or getattr(
            response.embeddings, "float", []
        )
        return [list(e) for e in embeddings]


class LocalEmbeddingProvider:
    """Local sentence-transformers provider (runs on CPU, no API costs).

    Supports arbitrary sentence-transformers models including instruction-tuned
    models like ``gte-Qwen2-1.5B-instruct`` that use asymmetric query/document
    prompts and require ``trust_remote_code=True``.

    Auto-detects model dimensions and query prompt support after loading.
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model
        self._model = None
        self._detected_dimensions: int | None = None
        self._supports_query_prompt: bool = False
        self._dimensions_map = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
        }

    @property
    def name(self) -> str:
        return "local"

    @property
    def dimensions(self) -> int:
        # Priority: detected from loaded model > known model map > settings fallback
        if self._detected_dimensions is not None:
            return self._detected_dimensions
        known = self._dimensions_map.get(self._model_name)
        if known is not None:
            return known
        settings = get_settings()
        return settings.embedding_dimensions

    @property
    def max_tokens(self) -> int:
        if self._model is not None:
            return self._model.max_seq_length
        return 256

    def _get_model(self):  # type: ignore[no-untyped-def]
        """Lazy-load the sentence-transformers model.

        After loading, auto-detects embedding dimensions and query prompt
        support from the model instance.
        """
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            settings = get_settings()
            self._model = SentenceTransformer(
                self._model_name,
                trust_remote_code=settings.embedding_trust_remote_code,
            )

            # Override max_seq_length if configured
            if settings.embedding_max_seq_length is not None:
                self._model.max_seq_length = settings.embedding_max_seq_length

            # Auto-detect dimensions from loaded model
            dim = getattr(self._model, "get_sentence_embedding_dimension", None)
            if callable(dim):
                self._detected_dimensions = dim()
                if self._model_name not in self._dimensions_map:
                    logger.info(
                        f"Auto-detected {self._detected_dimensions} dimensions "
                        f"for model '{self._model_name}'"
                    )

            # Auto-detect query prompt support
            prompts = getattr(self._model, "prompts", {})
            if isinstance(prompts, dict) and "query" in prompts:
                self._supports_query_prompt = True
                logger.info(f"Model '{self._model_name}' supports query prompts")

        return self._model

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        results = await self.embed_batch([text], is_query=is_query)
        return results[0]

    async def embed_batch(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        normalized = [_normalize_text(t) for t in texts]

        def _encode() -> list[list[float]]:
            model = self._get_model()
            kwargs: dict = {}
            if is_query and self._supports_query_prompt:
                kwargs["prompt_name"] = "query"
            embeddings = model.encode(normalized, **kwargs)
            return [e.tolist() for e in embeddings]

        return await asyncio.to_thread(_encode)


@lru_cache(maxsize=8)
def _get_cached_embedding_provider(name: str, model_name: str) -> EmbeddingProvider:
    """Cached factory for embedding providers.

    Prevents reloading heavy models (LocalEmbeddingProvider) or re-initializing
    API clients on every request.
    """
    if name == "openai":
        return OpenAIEmbeddingProvider(model_name)
    elif name == "voyage":
        return VoyageEmbeddingProvider(model_name)
    elif name == "cohere":
        return CohereEmbeddingProvider(model_name)
    elif name == "local":
        return LocalEmbeddingProvider(model_name)
    else:
        raise ValueError(f"Unknown embedding provider: {name}")


def get_embedding_provider(
    provider_name: str | None = None,
    model: str | None = None,
) -> EmbeddingProvider:
    """Factory function to get the configured embedding provider (cached).

    Args:
        provider_name: Override provider name (default: from settings)
        model: Override model name (default: from settings)

    Returns:
        Configured EmbeddingProvider instance
    """
    settings = get_settings()
    name = (provider_name or settings.embedding_provider).lower()
    model_name = model or settings.embedding_model

    return _get_cached_embedding_provider(name, model_name)


async def embed_chunks(
    chunks: list,  # list[DocumentChunk] — avoid circular import
    provider: EmbeddingProvider | None = None,
) -> list:
    """Convenience method to generate embeddings for a list of chunks.

    Embeds chunk texts in batch and returns chunks (embedding vectors
    are returned separately since DocumentChunk doesn't map the column).

    Args:
        chunks: List of DocumentChunk instances
        provider: Optional provider override

    Returns:
        List of embedding vectors (same order as chunks)
    """
    if not chunks:
        return []

    if provider is None:
        provider = get_embedding_provider()

    texts = [chunk.chunk_text for chunk in chunks]
    return await provider.embed_batch(texts)
