"""Learning path routes for structured lesson progression.

Provides endpoints for the learning path overview page and lazy-loaded
recommendation card. Supports both authenticated users (with full progress
and adaptive recommendations) and guests (with empty progress).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from src.api.auth import OptionalUserDep
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import SupabaseClient, get_supabase_admin, get_supabase_for_user
from src.db.models import LessonProgress, Vocabulary
from src.db.repository import LessonProgressRepository, VocabularyRepository
from src.services.adaptive import get_adaptive_service
from src.services.paths import get_path_service
from src.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_user_learning_data(
    effective_id: str,
    is_guest: bool,
    language: str,
    sb_access_token: str | None,
) -> tuple[list[LessonProgress], list[Vocabulary], int]:
    """Fetch completed lessons, vocabulary, and review due count for a user.

    Args:
        effective_id: User UUID or guest session UUID.
        is_guest: Whether the identity is a guest session.
        language: Target language code (es, de, fr).
        sb_access_token: JWT access token for authenticated users.

    Returns:
        Tuple of (completed_lessons, vocab_data, review_due_count).
    """
    client: SupabaseClient | None
    if is_guest:
        client = get_supabase_admin()
    else:
        client = get_supabase_for_user(sb_access_token) if sb_access_token else None

    lesson_repo = LessonProgressRepository(effective_id, client=client)
    completed_lessons = lesson_repo.get_completed()

    vocab_repo = VocabularyRepository(effective_id, client=client)
    vocab_data = vocab_repo.get_all(language=language)

    review_service = ReviewService(effective_id, client=client)
    review_stats = review_service.get_stats(language=language)
    review_due_count = review_stats.due_count

    return completed_lessons, vocab_data, review_due_count


@router.get("/", response_class=HTMLResponse)
async def get_learn_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    language: str = "es",
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> HTMLResponse:
    """Render the learning path overview page.

    Shows the structured path with units and lessons, overlaid with the
    user's completion progress. Authenticated users see full progress and
    an adaptive recommendation; guests see the path structure with no
    progress data.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        language: Target language code. Defaults to "es".
        session_id: Guest session cookie.
        sb_access_token: Supabase JWT from cookie.

    Returns:
        HTMLResponse: Rendered learning path page.
    """
    path_service = get_path_service()
    adaptive_service = get_adaptive_service()

    path = path_service.get_path(language)
    if not path:
        # Language has no path defined; redirect to lessons list
        return HTMLResponse(
            status_code=302,
            headers={"Location": "/lessons"},
        )

    # Resolve effective identity
    effective_id: str | None = None
    is_guest = False

    if user:
        effective_id = user.id
    elif session_id:
        effective_id = session_id
        is_guest = True

    path_progress = None
    recommendation = None

    if effective_id:
        try:
            completed_lessons, vocab_data, review_due_count = _get_user_learning_data(
                effective_id=effective_id,
                is_guest=is_guest,
                language=language,
                sb_access_token=sb_access_token,
            )
            path_progress = path_service.get_path_progress(language, completed_lessons)
            recommendation = adaptive_service.get_daily_recommendation(
                language=language,
                completed_lessons=completed_lessons,
                vocab_data=vocab_data,
                review_due_count=review_due_count,
            )
        except APIError:
            logger.exception("Failed to load learning data for user %s", effective_id)

    # Fall back to empty progress when no user or on error
    if path_progress is None:
        path_progress = path_service.get_path_progress(language, [])

    return templates.TemplateResponse(
        request=request,
        name="learn.html",
        context={
            "path": path,
            "path_progress": path_progress,
            "recommendation": recommendation,
            "user": user,
            "language": language,
            "is_guest": is_guest,
        },
    )


@router.get("/recommendation", response_class=HTMLResponse)
async def get_recommendation(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    language: str = "es",
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> HTMLResponse:
    """Return the recommendation card as an HTMX partial.

    Designed for lazy loading via hx-get. Computes the adaptive daily
    recommendation and returns just the card HTML fragment.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user or None.
        language: Target language code. Defaults to "es".
        session_id: Guest session cookie.
        sb_access_token: Supabase JWT from cookie.

    Returns:
        HTMLResponse: Rendered recommendation partial.
    """
    adaptive_service = get_adaptive_service()

    # Resolve effective identity
    effective_id: str | None = None
    is_guest = False

    if user:
        effective_id = user.id
    elif session_id:
        effective_id = session_id
        is_guest = True

    recommendation = None

    if effective_id:
        try:
            completed_lessons, vocab_data, review_due_count = _get_user_learning_data(
                effective_id=effective_id,
                is_guest=is_guest,
                language=language,
                sb_access_token=sb_access_token,
            )
            recommendation = adaptive_service.get_daily_recommendation(
                language=language,
                completed_lessons=completed_lessons,
                vocab_data=vocab_data,
                review_due_count=review_due_count,
            )
        except APIError:
            logger.exception("Failed to load recommendation for user %s", effective_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/learn_recommendation.html",
        context={
            "recommendation": recommendation,
            "language": language,
            "is_guest": is_guest,
        },
    )
