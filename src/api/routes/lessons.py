"""Micro-lesson endpoints for structured learning content.

Provides the lesson listing page. The conversational lesson system
(Phase 23) replaces the old step-by-step player routes.
"""

import contextlib
import logging
from typing import Annotated

from fastapi import APIRouter, Cookie
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from src.api.auth import OptionalUserDep
from src.api.cookies import unsign_active_thread
from src.api.dependencies import AccessTokenDep, LessonServiceDep, TemplatesDep
from src.db.client import get_supabase_for_user
from src.lessons.models import LessonLevel
from src.services.threads import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Lesson List
# =============================================================================


@router.get("/", response_class=HTMLResponse)
async def get_lessons_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    sb_token: AccessTokenDep,
    language: str = "es",
    level: str | None = None,
    active_thread: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render the lessons overview page with available micro-lessons.

    Supports filtering by language and CEFR level. Lesson completion
    status is scoped to the current user.
    """
    # Parse level filter if provided
    level_enum = None
    if level:
        with contextlib.suppress(ValueError):
            level_enum = LessonLevel(level)

    # Get lesson metadata for listing
    lessons_metadata = lesson_service.get_lessons_metadata(
        language=language,
        level=level_enum,
    )

    beginner_levels = {LessonLevel.A0, LessonLevel.A1}
    intermediate_levels = {LessonLevel.A2, LessonLevel.B1}

    lessons_grouped = {
        "beginner": [lesson for lesson in lessons_metadata if lesson.level in beginner_levels],
        "intermediate": [
            lesson for lesson in lessons_metadata if lesson.level in intermediate_levels
        ],
    }

    context: dict[str, object] = {
        "lessons": lessons_grouped,
        "language": language,
        "level": level or "A1",
        "user": user,
        "threads": [],
        "active_thread_id": unsign_active_thread(active_thread),
    }

    # Load thread list for sidebar (authenticated users only)
    if user and sb_token:
        try:
            user_client = get_supabase_for_user(sb_token)
            thread_service = ThreadService(user_id=user.id, client=user_client)
            threads = thread_service.list_threads()
            context["threads"] = [
                {
                    "id": t.id,
                    "thread_id": t.thread_id,
                    "title": t.title,
                    "language": t.language,
                    "level": t.level,
                    "updated_at": t.updated_at.isoformat(),
                }
                for t in threads
            ]
        except Exception:
            logger.exception("Failed to load threads for lessons sidebar")

    return templates.TemplateResponse(
        request=request,
        name="lessons.html",
        context=context,
    )
