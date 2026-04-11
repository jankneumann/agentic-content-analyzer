"""Knowledge base REST API (D8).

Exposes topic CRUD, notes, compilation, index retrieval, and Q&A at
``/api/v1/kb``. All endpoints require admin authentication. Synchronous
compile is guarded by the KB compile advisory lock — a concurrent
compile attempt returns 409.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.dependencies import verify_admin_key
from src.models.theme import ThemeCategory
from src.models.topic import KBIndex, Topic, TopicNote, TopicNoteType, TopicStatus
from src.services.kb_qa import KBQAService
from src.services.knowledge_base import (
    KBCompileLockError,
    KnowledgeBaseService,
    slugify,
)
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/kb",
    tags=["knowledge-base"],
    dependencies=[Depends(verify_admin_key)],
)


# =========================================================================
# Pydantic schemas
# =========================================================================


class TopicResponse(BaseModel):
    """Full topic response including article markdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    category: str
    status: str
    summary: str | None = None
    article_md: str | None = None
    article_version: int
    trend: str | None = None
    relevance_score: float
    novelty_score: float
    mention_count: int
    source_content_ids: list[int] = Field(default_factory=list)
    source_theme_ids: list[int] = Field(default_factory=list)
    related_topic_ids: list[int] = Field(default_factory=list)
    last_compiled_at: datetime | None = None
    last_evidence_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TopicSummary(BaseModel):
    """Lightweight topic entry for list endpoints."""

    slug: str
    name: str
    category: str
    status: str
    trend: str | None = None
    relevance_score: float
    mention_count: int
    last_compiled_at: datetime | None = None


def _validate_category(value: str) -> str:
    """Validate a category against the ThemeCategory enum."""
    try:
        return ThemeCategory(value).value
    except ValueError as exc:
        valid = [c.value for c in ThemeCategory]
        raise ValueError(f"Invalid category '{value}'. Must be one of: {valid}") from exc


def _validate_note_type(value: str) -> str:
    """Validate a note_type against the TopicNoteType enum."""
    try:
        return TopicNoteType(value).value
    except ValueError as exc:
        valid = [t.value for t in TopicNoteType]
        raise ValueError(f"Invalid note_type '{value}'. Must be one of: {valid}") from exc


class TopicCreate(BaseModel):
    """Body for POST /topics."""

    name: str = Field(..., min_length=1, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)
    summary: str | None = None
    trend: str | None = None

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        return _validate_category(v)


class TopicUpdate(BaseModel):
    """Body for PATCH /topics/{slug}. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    summary: str | None = None
    status: str | None = None
    trend: str | None = None
    # Spec bounds: relevance score 0..1
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    article_md: str | None = None

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_category(v)


class TopicNoteResponse(BaseModel):
    """Response shape for a TopicNote."""

    id: int
    topic_id: int
    note_type: str
    content: str
    author: str
    filed_back: bool
    created_at: datetime | None = None


class TopicNoteCreate(BaseModel):
    """Body for POST /topics/{slug}/notes."""

    content: str = Field(..., min_length=1)
    note_type: str = Field(default="observation")
    author: str | None = None

    @field_validator("note_type")
    @classmethod
    def _check_note_type(cls, v: str) -> str:
        return _validate_note_type(v)


class CompileResponse(BaseModel):
    """Aggregate compile summary returned by POST /compile."""

    started_at: str
    finished_at: str | None
    topics_found: int
    topics_compiled: int
    topics_skipped: int
    topics_failed: int
    merge_candidates: list[dict[str, str]]
    per_topic: list[dict[str, Any]]
    error: str | None


class KBQueryRequest(BaseModel):
    """Body for POST /query."""

    question: str = Field(..., min_length=1)
    file_back: bool = False


class KBQueryResponse(BaseModel):
    """Response shape for POST /query."""

    answer: str
    topics: list[str]
    truncated: bool = False
    message: str | None = None


# =========================================================================
# Serializers
# =========================================================================


def _topic_to_response(topic: Topic) -> TopicResponse:
    """Convert an ORM Topic to a TopicResponse."""
    return TopicResponse(
        id=topic.id,
        slug=topic.slug,
        name=topic.name,
        category=topic.category,
        status=_status_value(topic.status),
        summary=topic.summary,
        article_md=topic.article_md,
        article_version=topic.article_version or 1,
        trend=topic.trend,
        relevance_score=float(topic.relevance_score or 0.0),
        novelty_score=float(topic.novelty_score or 0.0),
        mention_count=int(topic.mention_count or 0),
        source_content_ids=list(topic.source_content_ids or []),
        source_theme_ids=list(topic.source_theme_ids or []),
        related_topic_ids=list(topic.related_topic_ids or []),
        last_compiled_at=topic.last_compiled_at,
        last_evidence_at=topic.last_evidence_at,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
    )


def _topic_to_summary(topic: Topic) -> TopicSummary:
    """Convert an ORM Topic to a TopicSummary entry."""
    return TopicSummary(
        slug=topic.slug,
        name=topic.name,
        category=topic.category,
        status=_status_value(topic.status),
        trend=topic.trend,
        relevance_score=float(topic.relevance_score or 0.0),
        mention_count=int(topic.mention_count or 0),
        last_compiled_at=topic.last_compiled_at,
    )


def _note_to_response(note: TopicNote) -> TopicNoteResponse:
    """Convert an ORM TopicNote to a response model."""
    return TopicNoteResponse(
        id=note.id,
        topic_id=note.topic_id,
        note_type=_status_value(note.note_type),
        content=note.content,
        author=note.author,
        filed_back=bool(note.filed_back),
        created_at=note.created_at,
    )


def _status_value(value: Any) -> str:
    """Return the string value of a StrEnum or pass through strings."""
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _unique_slug_for(db, name: str) -> str:
    """Pick a non-colliding slug for a new topic."""
    base = slugify(name)
    candidate = base
    suffix = 2
    while db.query(Topic).filter_by(slug=candidate).first() is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


# =========================================================================
# Topic endpoints
# =========================================================================


@router.get("/topics", response_model=list[TopicSummary])
async def list_topics(
    category: str | None = Query(default=None, description="Filter by category"),
    trend: str | None = Query(default=None, description="Filter by trend"),
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TopicSummary]:
    """List knowledge base topics with optional filters and pagination."""
    with get_db() as db:
        query = db.query(Topic)
        if category:
            query = query.filter(Topic.category == category)
        if trend:
            query = query.filter(Topic.trend == trend)
        if status:
            query = query.filter(Topic.status == status)
        else:
            # Exclude both ARCHIVED and MERGED from the default view.
            # MERGED topics are folded into another topic and shouldn't
            # appear alongside active results. Users can still query them
            # explicitly via ?status=merged.
            query = query.filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))

        rows = (
            query.order_by(Topic.relevance_score.desc(), Topic.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_topic_to_summary(t) for t in rows]


@router.get("/topics/{slug}", response_model=TopicResponse)
async def get_topic(slug: str) -> TopicResponse:
    """Fetch a single topic including its compiled article."""
    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Topic not found: {slug}")
        return _topic_to_response(topic)


@router.post(
    "/topics",
    response_model=TopicResponse,
    status_code=201,
)
async def create_topic(body: TopicCreate) -> TopicResponse:
    """Create a new topic (status=draft) with an auto-generated slug."""
    with get_db() as db:
        slug = _unique_slug_for(db, body.name)
        topic = Topic(
            slug=slug,
            name=body.name,
            category=body.category,
            status=TopicStatus.DRAFT,
            summary=body.summary,
            trend=body.trend,
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return _topic_to_response(topic)


@router.patch("/topics/{slug}", response_model=TopicResponse)
async def update_topic(slug: str, body: TopicUpdate) -> TopicResponse:
    """Update mutable fields on a topic."""
    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Topic not found: {slug}")

        if body.name is not None:
            topic.name = body.name
        if body.category is not None:
            topic.category = body.category
        if body.summary is not None:
            topic.summary = body.summary
        if body.trend is not None:
            topic.trend = body.trend
        if body.relevance_score is not None:
            topic.relevance_score = float(body.relevance_score)
        if body.article_md is not None:
            topic.article_md = body.article_md
            topic.article_version = (topic.article_version or 0) + 1
        if body.status is not None:
            try:
                topic.status = TopicStatus(body.status)
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid status: {body.status}",
                ) from None

        db.commit()
        db.refresh(topic)
        return _topic_to_response(topic)


@router.delete("/topics/{slug}", status_code=204)
async def archive_topic(slug: str) -> Response:
    """Soft-delete a topic by setting status=archived."""
    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Topic not found: {slug}")
        topic.status = TopicStatus.ARCHIVED
        db.commit()
    return Response(status_code=204)


# =========================================================================
# Topic note endpoints
# =========================================================================


@router.get(
    "/topics/{slug}/notes",
    response_model=list[TopicNoteResponse],
)
async def list_topic_notes(slug: str) -> list[TopicNoteResponse]:
    """List all notes attached to a topic."""
    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Topic not found: {slug}")
        notes = (
            db.query(TopicNote)
            .filter_by(topic_id=topic.id)
            .order_by(TopicNote.created_at.asc())
            .all()
        )
        return [_note_to_response(n) for n in notes]


@router.post(
    "/topics/{slug}/notes",
    response_model=TopicNoteResponse,
    status_code=201,
)
async def create_topic_note(
    slug: str,
    body: TopicNoteCreate,
) -> TopicNoteResponse:
    """Create a new note on a topic."""
    with get_db() as db:
        service = KnowledgeBaseService(db)
        try:
            note = service.add_note(
                topic_slug=slug,
                content=body.content,
                note_type=body.note_type,
                author=body.author or "user",
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _note_to_response(note)


# =========================================================================
# Compile + index + query
# =========================================================================


@router.post("/compile", response_model=CompileResponse)
async def compile_kb() -> CompileResponse:
    """Trigger a synchronous incremental KB compile."""
    with get_db() as db:
        service = KnowledgeBaseService(db)
        try:
            summary = await service.compile()
        except KBCompileLockError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc) or "A KB compilation is already in progress.",
            ) from exc
        except Exception as exc:
            logger.exception("KB compile failed")
            raise HTTPException(
                status_code=500,
                detail=f"KB compile failed: {exc}",
            ) from exc

        return CompileResponse(**summary.to_dict())


@router.get("/index")
async def get_index(
    category: str | None = Query(
        default=None,
        description="Return the category-specific index for this category",
    ),
) -> dict[str, Any]:
    """Return a cached KB index as markdown."""
    index_type = f"category_{category}" if category else "master"
    with get_db() as db:
        row = db.query(KBIndex).filter_by(index_type=index_type).first()
        if row is None:
            return {
                "index_type": index_type,
                "content": "",
                "generated_at": None,
            }
        return {
            "index_type": row.index_type,
            "content": row.content,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }


@router.post("/query", response_model=KBQueryResponse)
async def query_kb(body: KBQueryRequest) -> KBQueryResponse:
    """Answer a natural-language question against the compiled KB."""
    with get_db() as db:
        service = KBQAService(db)
        try:
            result = await service.query(
                body.question,
                file_back=body.file_back,
            )
        except Exception as exc:
            logger.warning("KB Q&A failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="KB Q&A LLM call failed.",
            ) from exc
        return KBQueryResponse(**result)
