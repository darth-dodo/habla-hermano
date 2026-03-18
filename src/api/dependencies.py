"""FastAPI dependency injection providers.

Phase 4: Added session and checkpointer dependencies.

Provides reusable dependencies for routes including settings, templates,
session management, and LangGraph checkpointing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

import markupsafe
from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates

from src.api.config import Settings, get_settings
from src.api.sanitize import render_markdown, sanitize_html
from src.api.session import get_thread_id as _get_thread_id
from src.api.supabase_client import get_supabase_for_user
from src.lessons.service import LessonService, get_lesson_service

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient


def _sanitize_filter(value: str) -> markupsafe.Markup:
    """Jinja2 filter that sanitizes HTML and marks it safe for rendering.

    Runs the value through nh3 sanitization, then wraps in Markup so
    Jinja2 does not double-escape the already-sanitized output.

    Args:
        value: Raw HTML string from LLM output.

    Returns:
        markupsafe.Markup: Sanitized HTML that Jinja2 treats as safe.
    """
    return markupsafe.Markup(sanitize_html(value))  # nosec B704 - input sanitized by nh3


def _markdown_filter(value: str) -> markupsafe.Markup:
    """Jinja2 filter that renders Markdown to sanitized HTML.

    Converts Markdown to HTML with fenced_code and tables extensions,
    sanitizes through nh3, then wraps in Markup so Jinja2 does not
    double-escape the output.

    Args:
        value: Raw Markdown string.

    Returns:
        markupsafe.Markup: Sanitized HTML that Jinja2 treats as safe.
    """
    return markupsafe.Markup(render_markdown(value))  # nosec B704 - input sanitized by nh3


def _register_filters(templates: Jinja2Templates) -> Jinja2Templates:
    """Register custom Jinja2 filters on a templates instance.

    Args:
        templates: Jinja2Templates instance to register filters on.

    Returns:
        Jinja2Templates: Same instance with filters registered.
    """
    templates.env.filters["sanitize"] = _sanitize_filter
    templates.env.filters["markdown"] = _markdown_filter
    return templates


def get_templates(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Jinja2Templates:
    """Return Jinja2Templates instance configured with templates directory.

    Args:
        settings: Application settings instance.

    Returns:
        Jinja2Templates: Configured template engine.
    """
    templates = Jinja2Templates(directory=str(settings.templates_dir))
    return _register_filters(templates)


@lru_cache
def get_cached_templates() -> Jinja2Templates:
    """Return cached Jinja2Templates instance.

    Uses lru_cache to avoid recreating templates engine on every request.
    Use this for performance-critical paths.

    Returns:
        Jinja2Templates: Cached template engine instance.
    """
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.templates_dir))
    return _register_filters(templates)


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


def get_deepgram_api_key() -> str:
    """Get the Deepgram API key from settings.

    Raises:
        RuntimeError: If DEEPGRAM_API_KEY is not configured.

    Returns:
        str: The configured Deepgram API key.
    """
    api_key = get_settings().DEEPGRAM_API_KEY
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY not configured")
    return api_key


def get_effective_access_token(request: Request) -> str | None:
    """Return the effective Supabase access token for the current request.

    Prefers the refreshed token stored on ``request.state`` by the auth
    layer (when a near-expiry or expired token was successfully refreshed)
    over the original cookie value which may be stale.

    Returns:
        Access token string, or None if the user is unauthenticated.
    """
    return getattr(request.state, "sb_access_token", None) or request.cookies.get(
        "sb-access-token"
    )


def get_user_supabase_client(request: Request) -> SupabaseClient | None:
    """Return a user-scoped Supabase client using the effective access token.

    Uses the potentially-refreshed token from the auth layer so that
    DB queries succeed even when the original cookie was expired.

    Returns:
        User-authenticated Supabase client, or None if no token.
    """
    token = get_effective_access_token(request)
    if not token:
        return None
    return get_supabase_for_user(token)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_cached_templates)]
ThreadIdDep = Annotated[str, Depends(get_thread_id_dep)]
LessonServiceDep = Annotated[LessonService, Depends(get_lesson_service)]
DeepgramKeyDep = Annotated[str, Depends(get_deepgram_api_key)]
AccessTokenDep = Annotated[str | None, Depends(get_effective_access_token)]
UserClientDep = Annotated["SupabaseClient | None", Depends(get_user_supabase_client)]
