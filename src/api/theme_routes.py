"""
Theme Analysis API Routes

Endpoints for analyzing themes across content items.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.models.theme import ThemeAnalysisRequest, ThemeAnalysisResult
from src.processors.theme_analyzer import ThemeAnalyzer
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


# In-memory storage for analysis results (simplified - would use DB in production)
_analysis_results: dict[int, ThemeAnalysisResult] = {}
_analysis_counter = 0
_analysis_status: dict[int, str] = {}


async def run_theme_analysis(
    analysis_id: int,
    request: ThemeAnalysisRequest,
    include_historical: bool,
) -> None:
    """Background task to run theme analysis."""
    global _analysis_results, _analysis_status

    try:
        _analysis_status[analysis_id] = "running"
        logger.info(f"Starting theme analysis {analysis_id}")

        analyzer = ThemeAnalyzer()
        result = await analyzer.analyze_themes(
            request=request,
            include_historical_context=include_historical,
        )

        _analysis_results[analysis_id] = result
        _analysis_status[analysis_id] = "completed"

        logger.info(f"Theme analysis {analysis_id} completed: {result.total_themes} themes found")

    except Exception as e:
        logger.error(f"Theme analysis {analysis_id} failed: {e}", exc_info=True)
        _analysis_status[analysis_id] = f"failed: {e!s}"


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
    global _analysis_counter

    # Set default dates if not provided (use start/end of day)
    now = datetime.utcnow()
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

    # Generate analysis ID
    _analysis_counter += 1
    analysis_id = _analysis_counter

    # Queue background task
    background_tasks.add_task(
        run_theme_analysis,
        analysis_id,
        analysis_request,
        request.include_historical_context,
    )

    _analysis_status[analysis_id] = "queued"

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
    if analysis_id not in _analysis_status:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id} not found",
        )

    status = _analysis_status[analysis_id]

    if status == "completed" and analysis_id in _analysis_results:
        return {
            "status": status,
            "result": _analysis_results[analysis_id],
        }

    return {
        "status": status,
        "result": None,
    }


@router.get("/latest")
async def get_latest_analysis() -> ThemeAnalysisResult | dict:
    """
    Get the most recent completed theme analysis.
    """
    # Find latest completed analysis
    completed_ids = [aid for aid, status in _analysis_status.items() if status == "completed"]

    if not completed_ids:
        return {"message": "No completed analyses found"}

    latest_id = max(completed_ids)
    return _analysis_results[latest_id]


@router.get("")
async def list_analyses(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[dict]:
    """
    List recent theme analyses.
    """
    analyses = []

    for aid in sorted(_analysis_status.keys(), reverse=True)[:limit]:
        status = _analysis_status[aid]
        result = _analysis_results.get(aid)

        analyses.append(
            {
                "id": aid,
                "status": status,
                "newsletter_count": result.newsletter_count if result else None,
                "total_themes": result.total_themes if result else None,
                "analysis_date": result.analysis_date.isoformat() if result else None,
            }
        )

    return analyses
