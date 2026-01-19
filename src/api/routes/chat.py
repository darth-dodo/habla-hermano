"""Chat router for handling conversation interactions.

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
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, Response
from langchain_core.messages import HumanMessage

from src.agent.checkpointer import get_checkpointer, get_user_thread_id
from src.agent.graph import build_graph
from src.api.auth import OptionalUserDep
from src.api.dependencies import SettingsDep, TemplatesDep

router = APIRouter(tags=["chat"])


@router.get("/", response_class=HTMLResponse, response_model=None)
async def chat_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
) -> HTMLResponse:
    """Render the main chat interface.

    Supports both authenticated and guest users. Authenticated users
    get persistent conversation history; guests get session-based
    conversations via cookies.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        user: Optional authenticated user (None if guest).

    Returns:
        HTMLResponse: Rendered chat page for both authenticated and guest users.
    """
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "app_name": settings.APP_NAME,
            "debug": settings.DEBUG,
            "user": user,
        },
    )


@router.post("/chat", response_class=HTMLResponse)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    session_id: Annotated[str | None, Cookie()] = None,
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
    # Determine thread_id based on authentication status
    # Track if we need to set a new session cookie for anonymous users
    new_session_id: str | None = None

    if user:
        # Authenticated: use user-scoped thread_id for persistence
        thread_id = get_user_thread_id(user.id)
    elif session_id:
        # Anonymous: use session-based thread_id from cookie
        thread_id = session_id
    else:
        # Generate new session_id for first-time anonymous users
        thread_id = str(uuid.uuid4())
        new_session_id = thread_id  # Will be set on template_response

    # Invoke LangGraph agent with checkpointing
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    # Extract AI response from graph result
    ai_response = result["messages"][-1].content

    # Extract grammar feedback and vocabulary from analyze node (if present)
    # These fields are populated by the analyze node in Phase 2
    grammar_feedback = result.get("grammar_feedback", [])
    new_vocabulary = result.get("new_vocabulary", [])

    # Extract scaffolding from scaffold node (Phase 3)
    # Only populated for A0-A1 learners via conditional routing
    scaffolding = result.get("scaffolding", {})

    # Create template response
    template_response = templates.TemplateResponse(
        request=request,
        name="partials/message_pair.html",
        context={
            "user_message": message,
            "ai_response": ai_response,
            "grammar_feedback": grammar_feedback,
            "new_vocabulary": new_vocabulary,
            "scaffolding": scaffolding,
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
