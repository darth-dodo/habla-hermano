"""Micro-lesson endpoints for structured learning content.

Provides lesson listing, content delivery, and progress tracking.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.api.dependencies import TemplatesDep

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_lessons_page(
    request: Request,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Render the lessons overview page with available micro-lessons.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Rendered lessons page with lesson cards.
    """
    return templates.TemplateResponse(
        request=request,
        name="lessons.html",
        context={"lessons": [], "language": "es", "level": "A1"},
    )


@router.get("/{lesson_id}", response_class=HTMLResponse)
async def get_lesson(
    request: Request,
    templates: TemplatesDep,
    lesson_id: str,
) -> HTMLResponse:
    """Render a specific micro-lesson content.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        lesson_id: Unique identifier for the lesson.

    Returns:
        HTMLResponse: Rendered lesson content page.
    """
    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_content.html",
        context={"lesson_id": lesson_id, "content": {}, "exercises": []},
    )


@router.post("/{lesson_id}/complete", response_class=HTMLResponse)
async def complete_lesson(
    request: Request,
    templates: TemplatesDep,
    lesson_id: str,
) -> HTMLResponse:
    """Mark a lesson as completed and update progress.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        lesson_id: Unique identifier for the completed lesson.

    Returns:
        HTMLResponse: Updated lesson card showing completion status.
    """
    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_card.html",
        context={"lesson_id": lesson_id, "completed": True},
    )
