"""FastAPI dependency injection providers.

Phase 4: Added session and checkpointer dependencies.

Provides reusable dependencies for routes including settings, templates,
session management, and LangGraph checkpointing.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates

from src.api.config import Settings, get_settings
from src.api.session import get_thread_id as _get_thread_id
from src.lessons.service import LessonService, get_lesson_service


def get_templates(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Jinja2Templates:
    """Return Jinja2Templates instance configured with templates directory.

    Args:
        settings: Application settings instance.

    Returns:
        Jinja2Templates: Configured template engine.
    """
    return Jinja2Templates(directory=str(settings.templates_dir))


@lru_cache
def get_cached_templates() -> Jinja2Templates:
    """Return cached Jinja2Templates instance.

    Uses lru_cache to avoid recreating templates engine on every request.
    Use this for performance-critical paths.

    Returns:
        Jinja2Templates: Cached template engine instance.
    """
    settings = get_settings()
    return Jinja2Templates(directory=str(settings.templates_dir))


def get_thread_id_dep(request: Request) -> str:
    """
    FastAPI dependency for getting thread_id from request.

    Wraps the session module's get_thread_id function for use
    as a FastAPI dependency.

    Args:
        request: FastAPI request object.

    Returns:
        str: Thread ID from cookie or newly generated UUID.
    """
    return _get_thread_id(request)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_cached_templates)]
ThreadIdDep = Annotated[str, Depends(get_thread_id_dep)]
LessonServiceDep = Annotated[LessonService, Depends(get_lesson_service)]
