"""Chat router for handling conversation interactions.

Phase 13: Simplified guest model - guests get chat only, no persistence.
Phase 12: Added review mode support for spaced repetition.
Phase 7: Added vocabulary and session data capture for authenticated users.
Phase 5: Added user authentication with Supabase.
Phase 4: Added conversation persistence with LangGraph checkpointing.

Provides endpoints for the main chat interface and message handling.
Uses HTMX for partial HTML responses.

Authentication:
- GET / supports both authenticated and guest users (OptionalUserDep)
- POST /chat supports both authenticated and guest users (OptionalUserDep)
- POST /new supports both authenticated and guest users (OptionalUserDep)

Thread IDs are user-scoped for authenticated users (persistent across sessions),
and session-based for anonymous users (cookie-based).

Guest users get:
- Full chat functionality (conversation persists via LangGraph checkpointing)
- Grammar feedback and pronunciation tips (returned in response)
- NO vocabulary tracking (requires account)
- NO progress page data (requires account)
- NO spaced repetition (requires account)
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, Response
from langchain_core.messages import HumanMessage

from src.agent.checkpointer import get_checkpointer, get_user_thread_id
from src.agent.graph import build_graph
from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.dependencies import SettingsDep, TemplatesDep
from src.api.supabase_client import get_supabase_for_user
from src.services.progress import ProgressService
from src.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.get("/", response_class=HTMLResponse, response_model=None)
async def chat_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    mode: str | None = None,
    warmup_dismissed: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> HTMLResponse:
    """Render the main chat interface.

    Supports both authenticated and guest users. Authenticated users
    get persistent conversation history and progress tracking; guests get
    session-based conversations via cookies but no progress tracking.

    Phase 12: Added review mode support. When mode=review, shows the
    review session start UI instead of normal chat.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        user: Optional authenticated user (None if guest).
        mode: Optional mode parameter ("review" for review mode).
        warmup_dismissed: Cookie tracking if warmup was dismissed.
        language: Target language for review stats.

    Returns:
        HTMLResponse: Rendered chat page for both authenticated and guest users.
    """
    # Default context
    context = {
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,
        "user": user,
        "review_mode": False,
        "show_warmup": False,
        "review_stats": None,
        "current_language": language,
    }

    # Review features only for authenticated users
    if user:
        try:
            review_service = ReviewService(user.id)
            review_stats = review_service.get_stats(language=language)
            context["review_stats"] = review_stats

            if mode == "review":
                # Review mode - show review start UI
                context["review_mode"] = True
            elif review_stats.due_count > 0 and not warmup_dismissed:
                # Show warmup prompt if words are due and not dismissed
                context["show_warmup"] = True
        except Exception:
            logger.exception("Failed to get review stats for user %s", user.id)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=context,
    )


def _resolve_chat_identity(
    user: AuthenticatedUser | None,
    session_id: str | None,
) -> tuple[str, str | None, str | None]:
    """Resolve thread_id and user_id for chat.

    For authenticated users, returns their user ID for both thread and user tracking.
    For guests, returns session_id for thread (checkpointing) but None for user_id
    (no progress tracking).

    Returns:
        Tuple of (thread_id, user_id_for_progress, new_session_id).
        - thread_id: Used for LangGraph checkpointing (works for both auth and guest)
        - user_id_for_progress: Only set for authenticated users (None for guests)
        - new_session_id: Set only for first-time anonymous users (for cookie)
    """
    if user:
        return get_user_thread_id(user.id), user.id, None
    if session_id:
        # Guest with existing session - thread_id for chat, but NO user_id for progress
        return session_id, None, None
    # First-time anonymous user - generate session for checkpointing only
    new_id = str(uuid.uuid4())
    return new_id, None, new_id


@router.post("/chat", response_class=HTMLResponse)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> HTMLResponse:
    """Process a chat message and return the response as partial HTML.

    This endpoint is designed for HTMX requests. It receives a message,
    invokes the LangGraph agent, and returns a partial HTML fragment
    that HTMX swaps into the chat container.

    Supports both authenticated and anonymous users:
    - Authenticated: Thread ID derived from user ID (persistent across sessions)
    - Anonymous: Thread ID from session cookie (session-based)

    Phase 4: Uses checkpointing for conversation persistence.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (for setting cookies).
        templates: Jinja2 templates instance.
        user: Optional authenticated user (None for anonymous/guest).
        message: User's message from form data.
        level: CEFR level (A0, A1, A2, B1). Defaults to A1.
        language: Target language (es, de). Defaults to es (Spanish).
        session_id: Session cookie for anonymous users.

    Returns:
        HTMLResponse: Partial HTML with user message and AI response.
    """
    # Resolve identity for thread_id and effective user_id
    thread_id, effective_user_id, new_session_id = _resolve_chat_identity(user, session_id)

    # Invoke LangGraph agent with checkpointing
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
                "user_id": effective_user_id,  # Phase 12: For review word weaving
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    # Extract AI response from graph result
    ai_response = result["messages"][-1].content

    # Extract grammar feedback and vocabulary from analyze node (if present)
    # These fields are populated by the analyze node in Phase 2
    grammar_feedback = result.get("grammar_feedback", [])
    new_vocabulary = result.get("new_vocabulary", [])
    pronunciation_tips = result.get("pronunciation_tips", [])

    # Extract scaffolding from scaffold node (Phase 3)
    # Only populated for A0-A1 learners via conditional routing
    scaffolding = result.get("scaffolding", {})

    # Capture vocabulary and session data for authenticated users only
    # Guests get chat but no progress tracking (simplifies architecture, no service key needed)
    if new_vocabulary and effective_user_id and user and sb_access_token:
        try:
            # Use user-authenticated client for RLS to work with auth.uid()
            user_client = get_supabase_for_user(sb_access_token)
            progress_service = ProgressService(effective_user_id, client=user_client)
            progress_service.record_chat_activity(
                language=language,
                level=level,
                new_vocab=new_vocabulary,
            )
        except Exception:
            logger.exception("Failed to capture chat activity for user %s", effective_user_id)

    # Create template response
    template_response = templates.TemplateResponse(
        request=request,
        name="partials/message_pair.html",
        context={
            "user_message": message,
            "ai_response": ai_response,
            "grammar_feedback": grammar_feedback,
            "new_vocabulary": new_vocabulary,
            "pronunciation_tips": pronunciation_tips,
            "scaffolding": scaffolding,
            "level": level,
        },
    )

    # Set session cookie on the actual response being returned (not the injected one)
    if new_session_id:
        template_response.set_cookie(
            key="session_id",
            value=new_session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return template_response


@router.post("/new", response_class=HTMLResponse)
async def new_conversation(
    response: Response,
    user: OptionalUserDep,
) -> Response:
    """Start a new conversation by clearing conversation history.

    Supports both authenticated and anonymous users:
    - Authenticated: Would clear the user's checkpoint in the database
    - Anonymous: Clears the session cookie, generating a new thread on next message

    Note: The actual checkpoint clearing would require additional implementation
    in the checkpointer. For now, this redirects to the chat page. In a future
    enhancement, we could add a delete_thread() method to the checkpointer.

    Args:
        response: FastAPI response object.
        user: Optional authenticated user (None for anonymous/guest).

    Returns:
        Response: Empty response with HX-Redirect header to reload page.
    """
    # TODO: Implement checkpoint deletion for user's thread (Phase 8)

    # For anonymous users, delete the session cookie to start fresh
    if not user:
        response.delete_cookie(key="session_id")

    response.headers["HX-Redirect"] = "/"
    response.status_code = 200
    return response
