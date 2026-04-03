"""Thread management API endpoints.

Provides CRUD endpoints for conversation threads (authenticated users only).
Threads store metadata; actual conversation data lives in LangGraph checkpoints.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Form, HTTPException, Request, Response

from src.api.auth import CurrentUserDep
from src.api.cookies import set_secure_cookie, sign_cookie_value, unsign_active_thread
from src.api.supabase_client import get_supabase_for_user
from src.api.validation import VALID_LANGUAGES, VALID_LEVELS
from src.services.threads import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["threads"])


def _get_access_token(
    request: Request,
    sb_access_token: str | None,
) -> str | None:
    """Extract access token from cookie or Authorization: Bearer header."""
    if sb_access_token:
        return sb_access_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _get_thread_service(user_id: str, access_token: str | None) -> ThreadService:
    """Create a ThreadService with a user-scoped Supabase client."""
    client = get_supabase_for_user(access_token) if access_token else None
    if not client:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ThreadService(user_id=user_id, client=client)


@router.get("/")
async def list_threads(
    request: Request,
    user: CurrentUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> list[dict[str, Any]]:
    """List user's conversation threads, ordered by most recent."""
    service = _get_thread_service(user.id, _get_access_token(request, sb_access_token))
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
    request: Request,
    user: CurrentUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    language: Annotated[str, Form()] = "es",
    level: Annotated[str, Form()] = "A1",
) -> dict[str, Any]:
    """Create a new conversation thread."""
    if language not in VALID_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Invalid language '{language}'")
    if level not in VALID_LEVELS:
        raise HTTPException(status_code=422, detail=f"Invalid level '{level}'")
    service = _get_thread_service(user.id, _get_access_token(request, sb_access_token))
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
    request: Request,
    user: CurrentUserDep,
    title: Annotated[str | None, Form()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> dict[str, str]:
    """Update a conversation thread's title."""
    service = _get_thread_service(user.id, _get_access_token(request, sb_access_token))
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
    request: Request,
    user: CurrentUserDep,
    response: Response,
    active_thread: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> Response:
    """Delete a conversation thread (idempotent). Clears active_thread cookie if it matches."""
    service = _get_thread_service(user.id, _get_access_token(request, sb_access_token))
    service.delete_thread(thread_id)
    if unsign_active_thread(active_thread) == thread_id:
        response.delete_cookie("active_thread")
    return Response(status_code=204)


@router.post("/select")
async def select_thread(
    request: Request,
    response: Response,
    user: CurrentUserDep,
    thread_id: Annotated[str, Form()],
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> dict[str, str]:
    """Set the active thread via a signed cookie (keeps thread IDs out of URLs)."""
    service = _get_thread_service(user.id, _get_access_token(request, sb_access_token))
    thread = service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    signed = sign_cookie_value({"tid": thread_id})
    set_secure_cookie(response, key="active_thread", value=signed, max_age=60 * 60 * 24 * 30)
    return {"status": "ok"}
