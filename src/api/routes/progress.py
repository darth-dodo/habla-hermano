"""Progress and statistics endpoints.

Tracks vocabulary learned, session history, and learning statistics.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.api.dependencies import TemplatesDep

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_progress_page(
    request: Request,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Render the progress overview page with learning statistics.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Rendered progress page with stats and vocabulary.
    """
    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "total_words": 0,
            "sessions_count": 0,
            "current_streak": 0,
            "vocabulary": [],
        },
    )


@router.get("/vocabulary", response_class=HTMLResponse)
async def get_vocabulary(
    request: Request,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Render the vocabulary sidebar with learned words.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Rendered vocabulary sidebar partial.
    """
    return templates.TemplateResponse(
        request=request,
        name="partials/vocab_sidebar.html",
        context={"vocabulary": [], "language": "es"},
    )


@router.get("/stats", response_class=HTMLResponse)
async def get_stats(
    request: Request,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Render session statistics summary.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Rendered stats partial with session metrics.
    """
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
    request: Request,
    templates: TemplatesDep,
    word_id: int,
) -> HTMLResponse:
    """Remove a word from the learned vocabulary list.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        word_id: Database ID of the vocabulary word to remove.

    Returns:
        HTMLResponse: Empty response for HTMX swap removal.
    """
    del request, templates, word_id  # Will be used when db module is ready
    return HTMLResponse(content="", status_code=200)
