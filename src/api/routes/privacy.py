"""Privacy & Security page and data management endpoints.

Provides endpoints for viewing privacy information and managing user data,
including conversation history deletion and account deletion.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.auth import OptionalUserDep
from src.api.cookies import delete_secure_cookie
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import get_supabase_admin, get_supabase_for_user
from src.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=None)
async def get_privacy_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
) -> HTMLResponse:
    """Render the privacy & security page.

    Displays privacy information for all users, with data management
    options for authenticated users.

    Args:
        request: FastAPI request object.
        templates: Jinja2 template engine.
        user: Authenticated user or None.

    Returns:
        HTMLResponse: Rendered privacy page.
    """
    return templates.TemplateResponse(
        request=request,
        name="privacy.html",
        context={"user": user},
    )


@router.post("/delete-history", response_model=None)
async def delete_history(
    request: Request,  # noqa: ARG001
    user: OptionalUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> Response:
    """Delete all conversation threads and checkpoint data for the user.

    Removes all conversation_threads rows (RLS scoped) and checkpoint
    data matching the user's thread pattern.

    Args:
        request: FastAPI request object.
        user: Authenticated user (required).
        sb_access_token: Supabase access token from cookie.

    Returns:
        Response: HX-Redirect to home page on success, or 401.
    """
    if not user or not sb_access_token:
        return RedirectResponse(url="/auth/login", status_code=302)

    user_client = get_supabase_for_user(sb_access_token)

    # Delete all conversation threads for this user
    try:
        user_client.table("conversation_threads").delete().eq("user_id", user.id).execute()
    except Exception:
        logger.exception("Failed to delete conversation threads for user %s", user.id)

    # Delete checkpoint data from all 3 checkpoint tables (RLS scopes to user).
    # Covers both freeform conversation threads (user:{id}:%) and lesson threads
    # (lesson:{id}:%) to ensure complete erasure for GDPR right-to-erasure.
    for pattern in (f"user:{user.id}:%", f"lesson:{user.id}:%"):
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                user_client.table(table).delete().like("thread_id", pattern).execute()
            except Exception:
                logger.exception(
                    "Failed to delete %s (pattern %s) for user %s", table, pattern, user.id
                )

    # Clear the active_thread cookie since threads are gone
    response = Response(status_code=200)
    response.headers["HX-Redirect"] = "/"
    delete_secure_cookie(response, key="active_thread")
    return response


@router.post("/delete-account", response_model=None)
async def delete_account(
    request: Request,  # noqa: ARG001
    user: OptionalUserDep,
    confirm: Annotated[str, Form()] = "",
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> Response:
    """Delete the user's account entirely.

    Requires the user to type 'DELETE' as confirmation. Uses the Supabase
    admin client to delete the auth user; ON DELETE CASCADE handles all
    related data cleanup.

    Args:
        request: FastAPI request object.
        user: Authenticated user (required).
        confirm: Must be exactly 'DELETE' to proceed.
        sb_access_token: Supabase access token from cookie.

    Returns:
        Response: Redirect to home page on success, or error.
    """
    if not user or not sb_access_token:
        return RedirectResponse(url="/auth/login", status_code=302)

    if confirm != "DELETE":
        return HTMLResponse(
            content='<div class="text-red-500 text-sm p-2">Please type DELETE to confirm.</div>',
            status_code=422,
        )

    # Use admin client to delete auth user (cascades to all user data)
    try:
        settings = get_settings()
        if not settings.SUPABASE_SERVICE_KEY:
            return HTMLResponse(
                content='<div class="text-red-500 text-sm p-2">Account deletion is not available at this time.</div>',
                status_code=503,
            )

        admin_client = get_supabase_admin()
        admin_client.auth.admin.delete_user(user.id)
    except Exception:
        logger.exception("Failed to delete account for user %s", user.id)
        return HTMLResponse(
            content='<div class="text-red-500 text-sm p-2">Failed to delete account. Please try again.</div>',
            status_code=500,
        )

    # Clear all auth cookies and redirect
    from src.api.routes.auth import clear_auth_cookie  # noqa: PLC0415

    response = RedirectResponse(url="/", status_code=302)
    clear_auth_cookie(response)
    delete_secure_cookie(response, key="active_thread")
    delete_secure_cookie(response, key="session_id")
    delete_secure_cookie(response, key="conversation_version")
    return response
