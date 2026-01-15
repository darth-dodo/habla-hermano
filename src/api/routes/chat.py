"""Chat endpoints for conversational language learning.

Handles message exchange, conversation state, and HTMX partial responses.
"""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from src.api.dependencies import Templates, ThreadId

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_chat_page(
    request: Request,
    templates: Templates,
) -> HTMLResponse:
    """Render the main chat interface.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Rendered chat page.
    """
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"level": "A1", "language": "es"},
    )


@router.post("/send", response_class=HTMLResponse)
async def send_message(
    request: Request,
    templates: Templates,
    thread_id: ThreadId,
    message: Annotated[str, Form()],
) -> HTMLResponse:
    """Process user message and return AI response with scaffolding.

    Invokes the LangGraph conversation graph and returns HTMX partial.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        thread_id: Conversation thread identifier for persistence.
        message: User's message text.

    Returns:
        HTMLResponse: Rendered message partial with AI response and scaffolding.
    """
    del thread_id  # Will be used for graph invocation when agent module is ready
    return templates.TemplateResponse(
        request=request,
        name="partials/message.html",
        context={
            "user_message": message,
            "ai_message": "",
            "scaffolding": {},
            "feedback": [],
            "new_vocab": [],
        },
    )


@router.post("/new", response_class=HTMLResponse)
async def new_conversation(
    request: Request,
    templates: Templates,
) -> HTMLResponse:
    """Start a new conversation, clearing previous thread state.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.

    Returns:
        HTMLResponse: Empty chat container for fresh conversation.
    """
    return templates.TemplateResponse(
        request=request,
        name="partials/chat_container.html",
        context={"messages": []},
    )


@router.post("/settings/level", response_class=HTMLResponse)
async def set_level(
    request: Request,
    templates: Templates,
    level: Annotated[str, Form()],
) -> HTMLResponse:
    """Update the user's CEFR proficiency level.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        level: CEFR level code (A0, A1, A2, B1).

    Returns:
        HTMLResponse: Updated level indicator partial.
    """
    return templates.TemplateResponse(
        request=request,
        name="partials/level_indicator.html",
        context={"level": level},
    )
