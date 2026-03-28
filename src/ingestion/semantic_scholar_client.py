"""Semantic Scholar API client with proactive rate limiting."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# API field set for paper queries
S2_FIELDS = (
    "paperId,externalIds,title,abstract,year,venue,citationCount,"
    "influentialCitationCount,fieldsOfStudy,authors,publicationTypes,"
    "openAccessPdf,tldr"
)


class RateLimitExhaustedError(Exception):
    """Raised when rate limit retries are exhausted."""


# Pydantic models with alias support for camelCase API responses
class S2Author(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    author_id: str | None = Field(None, alias="authorId")


class S2Paper(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    paper_id: str = Field(alias="paperId")
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    citation_count: int = Field(0, alias="citationCount")
    influential_citation_count: int = Field(0, alias="influentialCitationCount")
    fields_of_study: list[str] = Field(default_factory=list, alias="fieldsOfStudy")
    authors: list[S2Author] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list, alias="publicationTypes")
    external_ids: dict[str, str] = Field(default_factory=dict, alias="externalIds")
    open_access_pdf: dict[str, str] | None = Field(None, alias="openAccessPdf")
    tldr: dict[str, str] | None = None


class S2SearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    total: int
    offset: int = 0
    data: list[S2Paper] = Field(default_factory=list)


class SemanticScholarClient:
    """Async client for Semantic Scholar API with proactive rate limiting."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )
        self._semaphore = asyncio.Semaphore(1)
        self._last_request_time = 0.0
        # Authenticated clients get higher rate limits
        self._min_delay = 1.0 if api_key else 3.0

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        """Core request with rate limiting and retry."""
        async with self._semaphore:
            # Proactive delay between requests
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_delay:
                await asyncio.sleep(self._min_delay - elapsed)

            max_retries = 3
            backoff_base = 1.0 if self._api_key else 2.0
            backoff_max = 30.0 if self._api_key else 60.0
            consecutive_429s = 0
            last_response: httpx.Response | None = None

            for attempt in range(max_retries + 1):
                self._last_request_time = time.monotonic()
                try:
                    response = await self._client.request(method, path, **kwargs)
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    if attempt == max_retries:
                        logger.warning(
                            "S2 API %s %s failed after %d retries: %s",
                            method,
                            path,
                            max_retries,
                            exc,
                        )
                        return None
                    wait = min(backoff_base * (2**attempt), backoff_max)
                    logger.debug(
                        "S2 API timeout, retrying in %.1fs (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code == 429:
                    consecutive_429s += 1
                    if consecutive_429s >= 3:
                        raise RateLimitExhaustedError(
                            f"Rate limit exhausted after {consecutive_429s} "
                            f"consecutive 429 responses on {path}"
                        )
                    wait = min(backoff_base * (2**attempt), backoff_max)
                    logger.warning("S2 API rate limited (429), waiting %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                # Reset 429 counter on any non-429 response
                consecutive_429s = 0

                if response.status_code >= 500:
                    last_response = response
                    if attempt == max_retries:
                        logger.warning(
                            "S2 API server error %d on %s after %d retries",
                            response.status_code,
                            path,
                            max_retries,
                        )
                        return response
                    wait = min(backoff_base * (2**attempt), backoff_max)
                    logger.debug("S2 API 5xx, retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                return response

            # Fallback: return last response if loop completes without return
            return last_response

    async def search_papers(
        self,
        query: str,
        fields_of_study: list[str] | None = None,
        year_range: str | None = None,
        paper_types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> S2SearchResult:
        """Search for papers by query string with optional filters."""
        params: dict[str, Any] = {
            "query": query,
            "fields": S2_FIELDS,
            "limit": min(limit, 100),
            "offset": offset,
        }
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        if year_range:
            params["year"] = year_range
        if paper_types:
            params["publicationTypes"] = ",".join(paper_types)

        response = await self._request("GET", "/paper/search", params=params)
        if response is None or response.status_code != 200:
            return S2SearchResult(total=0, offset=offset, data=[])
        return S2SearchResult.model_validate(response.json())

    async def get_paper(self, paper_id: str) -> S2Paper | None:
        """Fetch a single paper by its Semantic Scholar ID or external ID."""
        response = await self._request("GET", f"/paper/{paper_id}", params={"fields": S2_FIELDS})
        if response is None or response.status_code == 404:
            logger.warning("Paper not found: %s", paper_id)
            return None
        if response.status_code != 200:
            logger.warning(
                "Failed to fetch paper %s: HTTP %d",
                paper_id,
                response.status_code,
            )
            return None
        return S2Paper.model_validate(response.json())

    async def get_paper_references(self, paper_id: str, limit: int = 100) -> list[S2Paper]:
        """Get papers referenced by the given paper."""
        response = await self._request(
            "GET",
            f"/paper/{paper_id}/references",
            params={"fields": S2_FIELDS, "limit": min(limit, 1000)},
        )
        if response is None or response.status_code != 200:
            return []
        data = response.json().get("data", [])
        papers: list[S2Paper] = []
        for item in data:
            cited = item.get("citedPaper")
            if cited and cited.get("paperId"):
                try:
                    papers.append(S2Paper.model_validate(cited))
                except Exception:
                    logger.debug("Skipping malformed reference entry: %s", cited.get("paperId"))
        return papers

    async def get_paper_citations(self, paper_id: str, limit: int = 100) -> list[S2Paper]:
        """Get papers that cite the given paper."""
        response = await self._request(
            "GET",
            f"/paper/{paper_id}/citations",
            params={"fields": S2_FIELDS, "limit": min(limit, 1000)},
        )
        if response is None or response.status_code != 200:
            return []
        data = response.json().get("data", [])
        papers: list[S2Paper] = []
        for item in data:
            citing = item.get("citingPaper")
            if citing and citing.get("paperId"):
                try:
                    papers.append(S2Paper.model_validate(citing))
                except Exception:
                    logger.debug("Skipping malformed citation entry: %s", citing.get("paperId"))
        return papers

    async def batch_get_papers(self, paper_ids: list[str]) -> list[S2Paper | None]:
        """Fetch multiple papers in a single request (max 500)."""
        if not paper_ids:
            return []
        # API limit: 500 per request
        ids_batch = paper_ids[:500]
        response = await self._request(
            "POST",
            "/paper/batch",
            params={"fields": S2_FIELDS},
            json={"ids": ids_batch},
        )
        if response is None or response.status_code != 200:
            return [None] * len(ids_batch)
        results: list[S2Paper | None] = []
        for item in response.json():
            if item and item.get("paperId"):
                results.append(S2Paper.model_validate(item))
            else:
                results.append(None)
        return results

    @staticmethod
    def resolve_identifier(identifier: str) -> str:
        """Resolve a paper identifier to a Semantic Scholar API-compatible format.

        Supports DOI, arXiv ID, S2 paper ID, and URLs from
        semanticscholar.org, arxiv.org, and doi.org.
        """
        identifier = identifier.strip()
        # DOI format: 10.xxxx/...
        if re.match(r"^10\.\d{4,}/", identifier):
            return f"DOI:{identifier}"
        if identifier.lower().startswith("doi:"):
            return identifier
        # arXiv format: YYMM.NNNNN or arXiv:YYMM.NNNNN
        if re.match(r"^\d{4}\.\d{4,}", identifier):
            return f"ArXiv:{identifier}"
        if identifier.lower().startswith("arxiv:"):
            return identifier
        # S2 paper ID (40-char hex)
        if re.match(r"^[0-9a-f]{40}$", identifier):
            return identifier
        # Semantic Scholar URL
        s2_url = re.match(
            r"https?://(?:www\.)?semanticscholar\.org/paper/[^/]+/([0-9a-f]{40})",
            identifier,
        )
        if s2_url:
            return s2_url.group(1)
        # arXiv URL
        arxiv_url = re.match(r"https?://arxiv\.org/abs/(\d{4}\.\d{4,})", identifier)
        if arxiv_url:
            return f"ArXiv:{arxiv_url.group(1)}"
        # DOI URL
        doi_url = re.match(r"https?://doi\.org/(10\.\d{4,}/.+)", identifier)
        if doi_url:
            return f"DOI:{doi_url.group(1)}"

        raise ValueError(
            f"Unrecognized paper identifier format: {identifier}. "
            "Expected DOI (10.xxx/...), arXiv (YYMM.NNNNN), "
            "S2 paper ID (40-char hex), "
            "or URL (semanticscholar.org, arxiv.org, doi.org)"
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
