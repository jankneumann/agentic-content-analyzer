"""Embedding provider abstraction for document chunk search.

Provides a pluggable EmbeddingProvider protocol with implementations for
OpenAI, Voyage AI, Cohere, and local sentence-transformers models.
Provider selection is configuration-driven via Settings.

Usage:
    provider = get_embedding_provider()
    vectors = await provider.embed_batch(["text1", "text2"])
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Protocol, runtime_checkable

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text before embedding: collapse whitespace, strip."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for pluggable embedding providers."""

    @property
    def name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def max_tokens(self) -> int: ...

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings in a single API call."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3-small/large provider."""

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

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        response = await client.embeddings.create(
            model=self._model,
            input=normalized,
        )
        return [item.embedding for item in response.data]


class VoyageEmbeddingProvider:
    """Voyage AI embedding provider (optimized for retrieval)."""

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

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        response = await client.embed(
            normalized,
            model=self._model,
            input_type="document",
        )
        return response.embeddings


class CohereEmbeddingProvider:
    """Cohere embed-english-v3.0 provider with input_type handling."""

    def __init__(self, model: str = "embed-english-v3.0") -> None:
        self._model = model
        self._client = None
        self._input_type = "search_document"  # Set to "search_query" for queries

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

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        normalized = [_normalize_text(t) for t in texts]

        response = await client.embed(
            texts=normalized,
            model=self._model,
            input_type=self._input_type,
            embedding_types=["float"],
        )
        # Cohere SDK v2 uses .float_ (with underscore to avoid Python keyword collision)
        # but some versions may use .float — handle both
        embeddings = getattr(response.embeddings, "float_", None) or getattr(
            response.embeddings, "float", []
        )
        return [list(e) for e in embeddings]


class LocalEmbeddingProvider:
    """Local sentence-transformers provider (runs on CPU, no API costs)."""

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model
        self._model = None
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
        return self._dimensions_map.get(self._model_name, 384)

    @property
    def max_tokens(self) -> int:
        return 256

    def _get_model(self):  # type: ignore[no-untyped-def]
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        normalized = [_normalize_text(t) for t in texts]

        def _encode() -> list[list[float]]:
            model = self._get_model()
            embeddings = model.encode(normalized)
            return [e.tolist() for e in embeddings]

        return await asyncio.to_thread(_encode)


def get_embedding_provider(
    provider_name: str | None = None,
    model: str | None = None,
) -> EmbeddingProvider:
    """Factory function to create the configured embedding provider.

    Args:
        provider_name: Override provider name (default: from settings)
        model: Override model name (default: from settings)

    Returns:
        Configured EmbeddingProvider instance
    """
    settings = get_settings()
    name = (provider_name or settings.embedding_provider).lower()
    model_name = model or settings.embedding_model

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
