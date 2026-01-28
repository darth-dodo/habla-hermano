"""Progress and statistics endpoints.

Phase 7: Added real progress tracking with ProgressService.
Phase 8: Supports both authenticated and guest users via session_id cookie.

Tracks vocabulary learned, session history, and learning statistics.
Supports both authenticated and guest users. Guests are identified
by session_id cookie and use the admin Supabase client to bypass RLS.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import SupabaseClient, get_supabase_admin
from src.db.repository import VocabularyRepository
from src.services.progress import ProgressService

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_identity(
    user: AuthenticatedUser | None,
    session_id: str | None,
) -> tuple[str | None, SupabaseClient | None]:
    """Resolve effective user ID and Supabase client for auth or guest users.

    Returns (effective_id, client) where client is the admin client for guests
    or None for authenticated users. If the admin client cannot be created
    (e.g. missing env var), returns (None, None) so callers fall through
    to the empty-state path.
    """
    if user:
        return user.id, None
    if session_id:
        try:
            return session_id, get_supabase_admin()
        except Exception:
            logger.warning("Admin client unavailable; guest progress disabled")
            return None, None
    return None, None


@router.get("/", response_class=HTMLResponse)
async def get_progress_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render the progress overview page with learning statistics.

    Phase 7: Uses ProgressService for real dashboard stats.
    Phase 8: Supports guest users via session_id cookie.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        session_id: Guest session cookie for unauthenticated users.

    Returns:
        HTMLResponse: Rendered progress page with stats and vocabulary.
    """
    effective_id, client = _resolve_identity(user, session_id)
    is_guest = user is None

    if not effective_id:
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
            },
        )

    service = ProgressService(effective_id, client=client)
    stats = service.get_dashboard_stats()

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
            "is_guest": is_guest,
        },
    )


@router.get("/vocabulary", response_class=HTMLResponse)
async def get_vocabulary(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> HTMLResponse:
    """Render the vocabulary list with learned words.

    Phase 7: Uses VocabularyRepository for real vocabulary data.
    Phase 8: Supports guest users via session_id cookie.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        session_id: Guest session cookie for unauthenticated users.
        language: Target language to filter vocabulary by. Defaults to "es".

    Returns:
        HTMLResponse: Rendered vocabulary partial.
    """
    effective_id, client = _resolve_identity(user, session_id)

    if not effective_id:
        return templates.TemplateResponse(
            request=request,
            name="partials/progress_vocab.html",
            context={"vocabulary": [], "language": language},
        )

    repo = VocabularyRepository(effective_id, client=client)
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
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render session statistics summary.

    Phase 7: Uses ProgressService for real dashboard stats.
    Phase 8: Supports guest users via session_id cookie.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        session_id: Guest session cookie for unauthenticated users.

    Returns:
        HTMLResponse: Rendered stats partial with session metrics.
    """
    effective_id, client = _resolve_identity(user, session_id)

    if not effective_id:
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

    service = ProgressService(effective_id, client=client)
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
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
    days: int = 30,
) -> JSONResponse:
    """Return chart data as JSON for frontend chart rendering.

    Provides vocabulary growth and accuracy trend data over the
    specified number of days.

    Phase 8: Supports guest users via session_id cookie.

    Args:
        user: Authenticated user or None.
        session_id: Guest session cookie for unauthenticated users.
        language: Target language to filter by. Defaults to "es".
        days: Number of days of history to include. Defaults to 30.

    Returns:
        JSONResponse: Chart data with vocab_growth and accuracy_trend arrays.
    """
    effective_id, client = _resolve_identity(user, session_id)

    if not effective_id:
        return JSONResponse(content={"vocab_growth": [], "accuracy_trend": []})

    service = ProgressService(effective_id, client=client)
    chart = service.get_chart_data(language=language, days=days)
    return JSONResponse(content=chart.to_dict())


@router.delete("/vocabulary/{word_id}", response_class=HTMLResponse)
async def remove_vocabulary_word(
    user: OptionalUserDep,
    word_id: int,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Remove a word from the learned vocabulary list.

    Phase 7: Uses VocabularyRepository for real deletion.
    Phase 8: Supports guest users via session_id cookie.
    Only removes words belonging to the current user (enforced at database level).

    Args:
        user: Authenticated user or None.
        word_id: Database ID of the vocabulary word to remove.
        session_id: Guest session cookie for unauthenticated users.

    Returns:
        HTMLResponse: Empty response for HTMX swap removal.
    """
    effective_id, client = _resolve_identity(user, session_id)

    if not effective_id:
        return HTMLResponse(content="", status_code=200)

    repo = VocabularyRepository(effective_id, client=client)
    repo.delete(word_id)
    return HTMLResponse(content="", status_code=200)
