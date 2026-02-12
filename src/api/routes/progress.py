"""Progress and statistics endpoints.

Phase 12: Added review stats for spaced repetition.
Phase 7: Added real progress tracking with ProgressService.

Tracks vocabulary learned, session history, and learning statistics.
Requires authentication - unauthenticated users see a sign-up prompt.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.api.auth import OptionalUserDep
from src.api.dependencies import TemplatesDep
from src.db.repository import VocabularyRepository
from src.services.progress import ProgressService
from src.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_progress_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    language: str = "es",
) -> HTMLResponse:
    """Render the progress overview page with learning statistics.

    Phase 12: Added review stats for spaced repetition display.
    Phase 7: Uses ProgressService for real dashboard stats.

    Requires authentication. Unauthenticated users see empty stats
    with a sign-up prompt.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        language: Target language for review stats. Defaults to "es".

    Returns:
        HTMLResponse: Rendered progress page with stats and vocabulary.
    """
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="progress.html",
            context={
                "total_words": 0,
                "sessions_count": 0,
                "current_streak": 0,
                "lessons_completed": 0,
                "vocabulary": [],
                "user": None,
                "is_guest": True,
                "review_stats": None,
            },
        )

    service = ProgressService(user.id)
    stats = service.get_dashboard_stats()

    # Get review stats for spaced repetition
    review_stats = None
    try:
        review_service = ReviewService(user.id)
        review_stats = review_service.get_stats(language=language)
    except Exception:
        logger.exception("Failed to get review stats for user %s", user.id)

    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "total_words": stats.total_words,
            "sessions_count": stats.total_sessions,
            "current_streak": stats.current_streak,
            "lessons_completed": stats.lessons_completed,
            "vocabulary": [],  # Loaded via HTMX partial
            "user": user,
            "is_guest": False,
            "review_stats": review_stats,
        },
    )


@router.get("/vocabulary", response_class=HTMLResponse)
async def get_vocabulary(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    language: str = "es",
) -> HTMLResponse:
    """Render the vocabulary list with learned words.

    Phase 7: Uses VocabularyRepository for real vocabulary data.

    Requires authentication. Unauthenticated users see an empty list.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        language: Target language to filter vocabulary by. Defaults to "es".

    Returns:
        HTMLResponse: Rendered vocabulary partial.
    """
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="partials/progress_vocab.html",
            context={"vocabulary": [], "language": language},
        )

    repo = VocabularyRepository(user.id)
    vocabulary = repo.get_all(language=language)

    return templates.TemplateResponse(
        request=request,
        name="partials/progress_vocab.html",
        context={"vocabulary": vocabulary, "language": language},
    )


@router.get("/stats", response_class=HTMLResponse)
async def get_stats(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
) -> HTMLResponse:
    """Render session statistics summary.

    Phase 7: Uses ProgressService for real dashboard stats.

    Requires authentication. Unauthenticated users see zeroed stats.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.

    Returns:
        HTMLResponse: Rendered stats partial with session metrics.
    """
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="partials/stats_summary.html",
            context={
                "total_words": 0,
                "total_sessions": 0,
                "lessons_completed": 0,
                "current_streak": 0,
                "accuracy_rate": 0.0,
                "words_learned_today": 0,
                "messages_today": 0,
            },
        )

    service = ProgressService(user.id)
    stats = service.get_dashboard_stats()

    return templates.TemplateResponse(
        request=request,
        name="partials/stats_summary.html",
        context={
            "total_words": stats.total_words,
            "total_sessions": stats.total_sessions,
            "lessons_completed": stats.lessons_completed,
            "current_streak": stats.current_streak,
            "accuracy_rate": stats.accuracy_rate,
            "words_learned_today": stats.words_learned_today,
            "messages_today": stats.messages_today,
        },
    )


@router.get("/chart-data")
async def get_chart_data(
    user: OptionalUserDep,
    language: str = "es",
    days: int = 30,
) -> JSONResponse:
    """Return chart data as JSON for frontend chart rendering.

    Provides vocabulary growth and accuracy trend data over the
    specified number of days.

    Requires authentication. Unauthenticated users receive empty arrays.

    Args:
        user: Authenticated user or None.
        language: Target language to filter by. Defaults to "es".
        days: Number of days of history to include. Defaults to 30.

    Returns:
        JSONResponse: Chart data with vocab_growth and accuracy_trend arrays.
    """
    if not user:
        return JSONResponse(content={"vocab_growth": [], "accuracy_trend": []})

    service = ProgressService(user.id)
    chart = service.get_chart_data(language=language, days=days)
    return JSONResponse(content=chart.to_dict())


@router.delete("/vocabulary/{word_id}", response_class=HTMLResponse)
async def remove_vocabulary_word(
    user: OptionalUserDep,
    word_id: int,
) -> HTMLResponse:
    """Remove a word from the learned vocabulary list.

    Phase 7: Uses VocabularyRepository for real deletion.

    Requires authentication. Only removes words belonging to the
    current user (enforced at database level via RLS).

    Args:
        user: Authenticated user or None.
        word_id: Database ID of the vocabulary word to remove.

    Returns:
        HTMLResponse: Empty response for HTMX swap removal.
    """
    if not user:
        return HTMLResponse(content="", status_code=200)

    repo = VocabularyRepository(user.id)
    repo.delete(word_id)
    return HTMLResponse(content="", status_code=200)
