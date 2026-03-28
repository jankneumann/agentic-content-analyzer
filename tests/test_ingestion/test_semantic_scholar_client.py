"""Tests for Semantic Scholar API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ingestion.semantic_scholar_client import (
    RateLimitExhaustedError,
    S2Author,
    S2Paper,
    S2SearchResult,
    SemanticScholarClient,
)


class TestResolveIdentifier:
    def test_doi(self) -> None:
        assert SemanticScholarClient.resolve_identifier("10.1234/test") == "DOI:10.1234/test"

    def test_doi_prefix(self) -> None:
        assert SemanticScholarClient.resolve_identifier("DOI:10.1234/test") == "DOI:10.1234/test"

    def test_arxiv(self) -> None:
        assert SemanticScholarClient.resolve_identifier("2401.12345") == "ArXiv:2401.12345"

    def test_arxiv_prefix(self) -> None:
        assert SemanticScholarClient.resolve_identifier("arXiv:2401.12345") == "arXiv:2401.12345"

    def test_s2_id(self) -> None:
        s2_id = "a" * 40
        assert SemanticScholarClient.resolve_identifier(s2_id) == s2_id

    def test_s2_url(self) -> None:
        s2_id = "b" * 40
        url = f"https://www.semanticscholar.org/paper/Some-Title/{s2_id}"
        assert SemanticScholarClient.resolve_identifier(url) == s2_id

    def test_arxiv_url(self) -> None:
        assert (
            SemanticScholarClient.resolve_identifier("https://arxiv.org/abs/2401.12345")
            == "ArXiv:2401.12345"
        )

    def test_doi_url(self) -> None:
        assert (
            SemanticScholarClient.resolve_identifier("https://doi.org/10.1234/test")
            == "DOI:10.1234/test"
        )

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized paper identifier"):
            SemanticScholarClient.resolve_identifier("not-a-valid-id")


class TestRateLimitExhaustedError:
    def test_is_exception(self) -> None:
        err = RateLimitExhaustedError("test message")
        assert isinstance(err, Exception)
        assert str(err) == "test message"


class TestS2Models:
    def test_s2_author(self) -> None:
        data = {"name": "Author A", "authorId": "123"}
        author = S2Author.model_validate(data)
        assert author.name == "Author A"
        assert author.author_id == "123"

    def test_s2_paper_from_api(self) -> None:
        data = {
            "paperId": "abc123" + "0" * 34,
            "title": "Test Paper",
            "citationCount": 42,
            "fieldsOfStudy": ["Computer Science"],
            "authors": [{"name": "Author A", "authorId": "123"}],
            "externalIds": {"DOI": "10.1234/test"},
        }
        paper = S2Paper.model_validate(data)
        assert paper.paper_id == "abc123" + "0" * 34
        assert paper.citation_count == 42
        assert paper.fields_of_study == ["Computer Science"]
        assert paper.authors[0].author_id == "123"

    def test_s2_search_result(self) -> None:
        data = {
            "total": 100,
            "offset": 0,
            "data": [{"paperId": "x" * 40, "title": "Test"}],
        }
        result = S2SearchResult.model_validate(data)
        assert result.total == 100
        assert len(result.data) == 1


@pytest.mark.asyncio
class TestSemanticScholarClient:
    async def test_search_papers(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 1,
            "offset": 0,
            "data": [
                {
                    "paperId": "a" * 40,
                    "title": "Test Paper",
                    "citationCount": 5,
                }
            ],
        }
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.search_papers("test query")
        assert result.total == 1
        assert result.data[0].title == "Test Paper"
        await client.close()

    async def test_search_papers_with_filters(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 0,
            "offset": 0,
            "data": [],
        }
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_req:
            result = await client.search_papers(
                "transformers",
                fields_of_study=["Computer Science"],
                year_range="2020-2024",
                paper_types=["JournalArticle"],
                limit=10,
                offset=5,
            )
        assert result.total == 0
        # Verify filters were passed
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params"))
        assert params["fieldsOfStudy"] == "Computer Science"
        assert params["year"] == "2020-2024"
        assert params["publicationTypes"] == "JournalArticle"
        assert params["limit"] == 10
        assert params["offset"] == 5
        await client.close()

    async def test_search_papers_failure(self) -> None:
        client = SemanticScholarClient()
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await client.search_papers("test")
        assert result.total == 0
        assert result.data == []
        await client.close()

    async def test_get_paper_not_found(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_paper("nonexistent")
        assert result is None
        await client.close()

    async def test_get_paper_success(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "paperId": "c" * 40,
            "title": "Found Paper",
        }
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_paper("c" * 40)
        assert result is not None
        assert result.title == "Found Paper"
        await client.close()

    async def test_get_paper_references(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "d" * 40,
                        "title": "Referenced Paper",
                    }
                },
                {"citedPaper": {"paperId": None, "title": "No ID"}},
            ]
        }
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            refs = await client.get_paper_references("a" * 40)
        assert len(refs) == 1
        assert refs[0].title == "Referenced Paper"
        await client.close()

    async def test_get_paper_citations(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "citingPaper": {
                        "paperId": "e" * 40,
                        "title": "Citing Paper",
                    }
                }
            ]
        }
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            cites = await client.get_paper_citations("a" * 40)
        assert len(cites) == 1
        assert cites[0].title == "Citing Paper"
        await client.close()

    async def test_batch_empty(self) -> None:
        client = SemanticScholarClient()
        result = await client.batch_get_papers([])
        assert result == []
        await client.close()

    async def test_batch_get_papers(self) -> None:
        client = SemanticScholarClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"paperId": "f" * 40, "title": "Paper 1"},
            None,
            {"paperId": "0" * 40, "title": "Paper 2"},
        ]
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            results = await client.batch_get_papers(["f" * 40, "missing", "0" * 40])
        assert len(results) == 3
        assert results[0] is not None
        assert results[0].title == "Paper 1"
        assert results[1] is None
        assert results[2] is not None
        assert results[2].title == "Paper 2"
        await client.close()

    async def test_batch_get_papers_failure(self) -> None:
        client = SemanticScholarClient()
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            results = await client.batch_get_papers(["a" * 40, "b" * 40])
        assert len(results) == 2
        assert all(r is None for r in results)
        await client.close()

    async def test_api_key_sets_header(self) -> None:
        client = SemanticScholarClient(api_key="test-key")
        assert client._client.headers["x-api-key"] == "test-key"
        assert client._min_delay == 1.0
        await client.close()

    async def test_no_api_key_slower_rate(self) -> None:
        client = SemanticScholarClient()
        assert client._min_delay == 3.0
        await client.close()
