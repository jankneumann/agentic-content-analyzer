"""Generated Pydantic models for Mobile Content Capture contracts.

These models mirror the existing models in src/api/save_routes.py.
This file serves as the contract reference — implementation MUST match these shapes.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, StringConstraints

# Maximum HTML payload size (5 MB)
MAX_HTML_SIZE = 5 * 1024 * 1024


class SaveURLRequest(BaseModel):
    """Request body for saving a URL."""

    url: HttpUrl
    title: str | None = Field(None, max_length=1000)
    excerpt: str | None = Field(None, max_length=5000)
    tags: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        default=None, max_length=20
    )
    notes: str | None = Field(None, max_length=10000)
    source: (
        Literal["chrome_extension", "ios_shortcut", "bookmarklet", "web_save_page", "api"] | None
    ) = Field(None, max_length=50)


class SavePageRequest(BaseModel):
    """Request body for saving a page with client-captured HTML."""

    url: HttpUrl
    html: Annotated[str, StringConstraints(max_length=MAX_HTML_SIZE)]
    title: str | None = Field(None, max_length=1000)
    excerpt: str | None = Field(None, max_length=5000)
    tags: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        default=None, max_length=20
    )
    notes: str | None = Field(None, max_length=10000)
    source: str | None = Field(None, max_length=50)


class SaveURLResponse(BaseModel):
    """Response for save URL/page operations."""

    content_id: int
    status: Literal["queued", "exists"]
    message: str
    duplicate: bool = False


class ContentStatusResponse(BaseModel):
    """Response for content status query."""

    content_id: int
    status: Literal["pending", "parsing", "parsed", "failed"]
    title: str | None = None
    word_count: int | None = None
    error: str | None = None


class RateLimitError(BaseModel):
    """429 response body."""

    detail: str
    retry_after: int
