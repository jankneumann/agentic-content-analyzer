"""
Theme Analysis API Routes

Endpoints for analyzing themes across content items.
Results are persisted to PostgreSQL for temporal evolution tracking.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.models.theme import (
    AnalysisStatus,
    ThemeAnalysis,
    ThemeAnalysisRequest,
)
from src.processors.theme_analyzer import ThemeAnalyzer
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/themes", tags=["themes"])


class AnalyzeThemesRequest(BaseModel):
    """Request to trigger theme analysis."""

    start_date: datetime | None = Field(
        None,
        description="Start date for analysis (defaults to 7 days ago)",
    )
    end_date: datetime | None = Field(
        None,
        description="End date for analysis (defaults to yesterday)",
    )
    max_themes: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Maximum number of themes to return",
    )
    min_newsletters: int = Field(
        default=2,
        ge=1,
        description="Minimum content items required for analysis",
    )
    relevance_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score (0-1)",
    )
    include_historical_context: bool = Field(
        default=True,
        description="Include historical context for themes",
    )


class AnalyzeThemesResponse(BaseModel):
    """Response from theme analysis request."""

    status: str
    message: str
    analysis_id: int | None = None


def _orm_to_response(record: ThemeAnalysis) -> dict:
    """Convert a ThemeAnalysis ORM record to an API response dict."""
    return {
        "id": record.id,
        "status": record.status.value
        if isinstance(record.status, AnalysisStatus)
        else record.status,
        "analysis_date": record.analysis_date.isoformat() if record.analysis_date else None,
        "start_date": record.start_date.isoformat() if record.start_date else None,
        "end_date": record.end_date.isoformat() if record.end_date else None,
        "content_count": record.content_count,
        "content_ids": record.content_ids or [],
        "themes": record.themes or [],
        "total_themes": record.total_themes,
        "emerging_themes_count": record.emerging_themes_count,
        "top_theme": record.top_theme,
        "agent_framework": record.agent_framework,
        "model_used": record.model_used,
        "model_version": record.model_version,
        "processing_time_seconds": record.processing_time_seconds,
        "token_usage": record.token_usage,
        "cross_theme_insights": record.cross_theme_insights or [],
        "error_message": record.error_message,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


async def run_theme_analysis(
    analysis_id: int,
    request: ThemeAnalysisRequest,
    include_historical: bool,
) -> None:
    """Background task to run theme analysis and persist results to DB."""
    try:
        # Mark as running
        with get_db() as db:
            record = db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
            if not record:
                logger.error(f"Theme analysis {analysis_id} not found in DB")
                return
            record.status = AnalysisStatus.RUNNING
            db.commit()

        logger.info(f"Starting theme analysis {analysis_id}")

        analyzer = ThemeAnalyzer()
        result = await analyzer.analyze_themes(
            request=request,
            include_historical_context=include_historical,
        )

        # Persist completed result
        with get_db() as db:
            record = db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
            if not record:
                logger.error(f"Theme analysis {analysis_id} disappeared from DB")
                return

            record.status = AnalysisStatus.COMPLETED
            record.content_count = result.content_count
            record.content_ids = result.content_ids
            record.themes = [t.model_dump(mode="json") for t in result.themes]
            record.total_themes = result.total_themes
            record.emerging_themes_count = result.emerging_themes_count
            record.top_theme = result.top_theme
            record.agent_framework = result.agent_framework
            record.model_used = result.model_used
            record.model_version = result.model_version
            record.processing_time_seconds = result.processing_time_seconds
            record.token_usage = result.token_usage
            record.cross_theme_insights = result.cross_theme_insights
            record.analysis_date = result.analysis_date
            db.commit()

        logger.info(f"Theme analysis {analysis_id} completed: {result.total_themes} themes found")

        # Neo4j episode writeback (fail-safe)
        try:
            from src.storage.graphiti_client import GraphitiClient

            client = GraphitiClient()
            try:
                await client.add_theme_analysis_episode(result)
                logger.info(f"Theme analysis {analysis_id} written to Neo4j")
            finally:
                client.close()
        except Exception as e:
            logger.warning(f"Neo4j writeback failed for analysis {analysis_id}: {e}")

    except Exception as e:
        logger.error(f"Theme analysis {analysis_id} failed: {e}", exc_info=True)
        try:
            with get_db() as db:
                record = db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
                if record:
                    record.status = AnalysisStatus.FAILED
                    record.error_message = "Analysis failed due to an internal error"
                    db.commit()
        except Exception as db_err:
            logger.error(f"Failed to record error for analysis {analysis_id}: {db_err}")


@router.post("/analyze", response_model=AnalyzeThemesResponse)
async def analyze_themes(
    request: AnalyzeThemesRequest,
    background_tasks: BackgroundTasks,
) -> AnalyzeThemesResponse:
    """
    Trigger theme analysis across content items in a date range.

    Analysis runs in the background. Use GET /themes/analysis/{id} to check status
    and retrieve results.
    """
    # Set default dates if not provided
    now = datetime.now(UTC)
    if request.end_date:
        end_date = request.end_date
    else:
        yesterday = now - timedelta(days=1)
        end_date = yesterday.replace(hour=23, minute=59, second=59)

    if request.start_date:
        start_date = request.start_date
    else:
        week_ago = end_date - timedelta(days=7)
        start_date = week_ago.replace(hour=0, minute=0, second=0)

    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date",
        )

    # Create analysis request
    analysis_request = ThemeAnalysisRequest(
        start_date=start_date,
        end_date=end_date,
        min_newsletters=request.min_newsletters,
        max_themes=request.max_themes,
        relevance_threshold=request.relevance_threshold,
    )

    # Create DB record with QUEUED status
    with get_db() as db:
        record = ThemeAnalysis(
            status=AnalysisStatus.QUEUED,
            analysis_date=now,
            start_date=start_date,
            end_date=end_date,
            created_at=now,
        )
        db.add(record)
        db.flush()
        analysis_id = record.id
        db.commit()

    # Queue background task
    background_tasks.add_task(
        run_theme_analysis,
        analysis_id,
        analysis_request,
        request.include_historical_context,
    )

    logger.info(f"Theme analysis {analysis_id} queued: {start_date.date()} to {end_date.date()}")

    return AnalyzeThemesResponse(
        status="queued",
        message=f"Theme analysis started for {start_date.date()} to {end_date.date()}",
        analysis_id=analysis_id,
    )


@router.get("/analysis/{analysis_id}")
async def get_analysis_status(analysis_id: int):
    """
    Get the status and results of a theme analysis.
    """
    with get_db() as db:
        record = db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {analysis_id} not found",
            )

        status_value = (
            record.status.value if isinstance(record.status, AnalysisStatus) else record.status
        )

        if status_value == "completed":
            return {
                "status": status_value,
                "result": _orm_to_response(record),
            }

        return {
            "status": status_value,
            "result": None,
            "error_message": record.error_message if status_value == "failed" else None,
        }


@router.get("/latest")
async def get_latest_analysis() -> dict:
    """
    Get the most recent completed theme analysis.
    """
    with get_db() as db:
        record = (
            db.query(ThemeAnalysis)
            .filter(ThemeAnalysis.status == AnalysisStatus.COMPLETED)
            .order_by(ThemeAnalysis.created_at.desc())
            .first()
        )

        if not record:
            return {"message": "No completed analyses found"}

        return _orm_to_response(record)


@router.get("")
async def list_analyses(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    """
    List recent theme analyses with offset pagination.
    """
    with get_db() as db:
        records = (
            db.query(ThemeAnalysis)
            .order_by(ThemeAnalysis.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": r.id,
                "status": r.status.value if isinstance(r.status, AnalysisStatus) else r.status,
                "content_count": r.content_count,
                "total_themes": r.total_themes,
                "analysis_date": r.analysis_date.isoformat() if r.analysis_date else None,
                "start_date": r.start_date.isoformat() if r.start_date else None,
                "end_date": r.end_date.isoformat() if r.end_date else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
