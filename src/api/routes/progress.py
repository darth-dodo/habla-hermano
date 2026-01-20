"""Progress and statistics endpoints.

Phase 5: Added user authentication with Supabase.

Tracks vocabulary learned, session history, and learning statistics.
All endpoints require authentication and scope data to the current user.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.api.auth import CurrentUserDep
from src.api.dependencies import TemplatesDep

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_progress_page(
    request: Request,
    templates: TemplatesDep,
    user: CurrentUserDep,
) -> HTMLResponse:
    """Render the progress overview page with learning statistics.

    Phase 5: Requires authentication. Stats are scoped to the current user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user (required).

    Returns:
        HTMLResponse: Rendered progress page with stats and vocabulary.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: stats = await get_user_stats(user.id)
    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "total_words": 0,
            "sessions_count": 0,
            "current_streak": 0,
            "vocabulary": [],
            "user": user,
        },
    )


@router.get("/vocabulary", response_class=HTMLResponse)
async def get_vocabulary(
    request: Request,
    templates: TemplatesDep,
    _user: CurrentUserDep,  # Used for auth enforcement, data fetching in Phase 8
) -> HTMLResponse:
    """Render the vocabulary sidebar with learned words.

    Phase 5: Requires authentication. Vocabulary is scoped to current user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: Authenticated user (required). Used in Phase 8 for data fetching.

    Returns:
        HTMLResponse: Rendered vocabulary sidebar partial.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: vocabulary = await get_user_vocabulary(_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/vocab_sidebar.html",
        context={"vocabulary": [], "language": "es"},
    )


@router.get("/stats", response_class=HTMLResponse)
async def get_stats(
    request: Request,
    templates: TemplatesDep,
    _user: CurrentUserDep,  # Used for auth enforcement, data fetching in Phase 8
) -> HTMLResponse:
    """Render session statistics summary.

    Phase 5: Requires authentication. Stats are scoped to current user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: Authenticated user (required). Used in Phase 8 for data fetching.

    Returns:
        HTMLResponse: Rendered stats partial with session metrics.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: stats = await get_user_daily_stats(_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/stats_summary.html",
        context={
            "messages_today": 0,
            "words_learned_today": 0,
            "accuracy_rate": 0.0,
        },
    )


@router.delete("/vocabulary/{word_id}", response_class=HTMLResponse)
async def remove_vocabulary_word(
    _user: CurrentUserDep,  # Used for auth enforcement, data mutation in Phase 8
    word_id: int,  # noqa: ARG001 - Used in Phase 8
) -> HTMLResponse:
    """Remove a word from the learned vocabulary list.

    Phase 5: Requires authentication. Only removes words belonging to
    the current user (enforced at database level).

    Args:
        _user: Authenticated user (required). Used in Phase 8 for data mutation.
        word_id: Database ID of the vocabulary word to remove.

    Returns:
        HTMLResponse: Empty response for HTMX swap removal.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: await delete_user_vocabulary_word(_user.id, word_id)
    return HTMLResponse(content="", status_code=200)
