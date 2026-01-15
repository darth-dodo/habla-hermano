"""Dependency injection for FastAPI routes.

Provides graph instance, database sessions, and template engine access.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import Settings, get_settings


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the request lifecycle.

    Args:
        settings: Application settings with database URL.

    Yields:
        AsyncSession: Database session that auto-commits on success.
    """
    del settings  # Will be used when db module is ready
    raise NotImplementedError


def get_templates(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Jinja2Templates:
    """Get configured Jinja2 templates instance.

    Args:
        settings: Application settings with templates directory path.

    Returns:
        Jinja2Templates: Configured template engine.
    """
    return Jinja2Templates(directory=str(settings.templates_dir))


def get_thread_id(request: Request) -> str:
    """Extract or generate conversation thread ID from request.

    Thread IDs enable LangGraph checkpointing for conversation persistence.

    Args:
        request: FastAPI request with session/cookie data.

    Returns:
        str: Unique thread identifier for the conversation.
    """
    session_id = request.cookies.get("habla_session", "")
    if session_id:
        return f"thread-{session_id}"
    return "thread-anonymous"


async def get_graph() -> AsyncGenerator[object, None]:
    """Yield the compiled LangGraph instance for conversation processing.

    Yields:
        CompiledGraph: The LangGraph conversation graph with checkpointing.
    """
    raise NotImplementedError


# Type aliases for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Templates = Annotated[Jinja2Templates, Depends(get_templates)]
ThreadId = Annotated[str, Depends(get_thread_id)]
AppSettings = Annotated[Settings, Depends(get_settings)]
