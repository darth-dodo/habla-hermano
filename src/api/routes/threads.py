"""Thread management API endpoints.

Provides CRUD endpoints for conversation threads (authenticated users only).
Threads store metadata; actual conversation data lives in LangGraph checkpoints.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Form, HTTPException, Response

from src.api.auth import CurrentUserDep
from src.api.supabase_client import get_supabase_for_user
from src.services.threads import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["threads"])


def _get_thread_service(user_id: str, access_token: str | None) -> ThreadService:
    """Create a ThreadService with a user-scoped Supabase client."""
    client = get_supabase_for_user(access_token) if access_token else None
    if not client:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ThreadService(user_id=user_id, client=client)


@router.get("/")
async def list_threads(
    user: CurrentUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> list[dict[str, Any]]:
    """List user's conversation threads, ordered by most recent."""
    service = _get_thread_service(user.id, sb_access_token)
    threads = service.list_threads()
    return [
        {
            "id": t.id,
            "thread_id": t.thread_id,
            "title": t.title,
            "language": t.language,
            "level": t.level,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in threads
    ]


@router.post("/", status_code=201)
async def create_thread(
    user: CurrentUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    language: Annotated[str, Form()] = "es",
    level: Annotated[str, Form()] = "A1",
) -> dict[str, Any]:
    """Create a new conversation thread."""
    service = _get_thread_service(user.id, sb_access_token)
    thread = service.create_thread(language=language, level=level)
    return {
        "id": thread.id,
        "thread_id": thread.thread_id,
        "title": thread.title,
        "language": thread.language,
        "level": thread.level,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


@router.patch("/{thread_id}")
async def update_thread(
    thread_id: str,
    user: CurrentUserDep,
    title: Annotated[str | None, Form()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> dict[str, str]:
    """Update a conversation thread's title."""
    service = _get_thread_service(user.id, sb_access_token)
    existing = service.get_thread(thread_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Thread not found")
    result: dict[str, str] = {"thread_id": thread_id}
    if title is not None:
        service.update_title(thread_id, title.strip()[:100])
        result["title"] = title.strip()[:100]
    return result


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    user: CurrentUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> Response:
    """Delete a conversation thread (idempotent)."""
    service = _get_thread_service(user.id, sb_access_token)
    service.delete_thread(thread_id)
    return Response(status_code=204)
