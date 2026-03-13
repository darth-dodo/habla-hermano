"""Micro-lesson endpoints for structured learning content.

Provides the lesson listing page. The conversational lesson system
(Phase 23) replaces the old step-by-step player routes.
"""

import contextlib
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from src.api.auth import OptionalUserDep
from src.api.dependencies import LessonServiceDep, TemplatesDep
from src.lessons.models import LessonLevel

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
    language: str = "es",
    level: str | None = None,
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

    return templates.TemplateResponse(
        request=request,
        name="lessons.html",
        context={
            "lessons": lessons_grouped,
            "language": language,
            "level": level or "A1",
            "user": user,
        },
    )
