"""Micro-lesson endpoints for structured learning content.

Phase 5: Added user authentication with Supabase.

Provides lesson listing, content delivery, and progress tracking.
All endpoints require authentication and scope data to the current user.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.api.auth import CurrentUserDep
from src.api.dependencies import TemplatesDep

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_lessons_page(
    request: Request,
    templates: TemplatesDep,
    user: CurrentUserDep,
) -> HTMLResponse:
    """Render the lessons overview page with available micro-lessons.

    Phase 5: Requires authentication. Lesson completion status is
    scoped to the current user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user (required).

    Returns:
        HTMLResponse: Rendered lessons page with lesson cards.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: lessons = await get_lessons_for_user(user.id)
    return templates.TemplateResponse(
        request=request,
        name="lessons.html",
        context={"lessons": [], "language": "es", "level": "A1", "user": user},
    )


@router.get("/{lesson_id}", response_class=HTMLResponse)
async def get_lesson(
    request: Request,
    templates: TemplatesDep,
    _user: CurrentUserDep,  # Used for auth enforcement, data fetching in Phase 8
    lesson_id: str,
) -> HTMLResponse:
    """Render a specific micro-lesson content.

    Phase 5: Requires authentication. User progress on this lesson
    is tracked per user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: Authenticated user (required). Used in Phase 8 for data fetching.
        lesson_id: Unique identifier for the lesson.

    Returns:
        HTMLResponse: Rendered lesson content page.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: lesson = await get_lesson_for_user(_user.id, lesson_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_content.html",
        context={"lesson_id": lesson_id, "content": {}, "exercises": []},
    )


@router.post("/{lesson_id}/complete", response_class=HTMLResponse)
async def complete_lesson(
    request: Request,
    templates: TemplatesDep,
    _user: CurrentUserDep,  # Used for auth enforcement, data mutation in Phase 8
    lesson_id: str,
) -> HTMLResponse:
    """Mark a lesson as completed and update progress.

    Phase 5: Requires authentication. Completion is recorded for
    the current user only.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: Authenticated user (required). Used in Phase 8 for data mutation.
        lesson_id: Unique identifier for the completed lesson.

    Returns:
        HTMLResponse: Updated lesson card showing completion status.

    Raises:
        HTTPException: 401 if user is not authenticated.
    """
    # Phase 8: await mark_lesson_complete(_user.id, lesson_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_card.html",
        context={"lesson_id": lesson_id, "completed": True},
    )
