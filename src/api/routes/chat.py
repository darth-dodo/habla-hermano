"""Chat router for handling conversation interactions.

Provides endpoints for the main chat interface and message handling.
Uses HTMX for partial HTML responses.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from langchain_core.messages import HumanMessage

from src.agent import compiled_graph
from src.api.dependencies import SettingsDep, TemplatesDep

router = APIRouter(tags=["chat"])


@router.get("/", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Render the main chat interface.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.

    Returns:
        HTMLResponse: Rendered chat page.
    """
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "app_name": settings.APP_NAME,
            "debug": settings.DEBUG,
        },
    )


@router.post("/chat", response_class=HTMLResponse)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
) -> HTMLResponse:
    """Process a chat message and return the response as partial HTML.

    This endpoint is designed for HTMX requests. It receives a message,
    invokes the LangGraph agent, and returns a partial HTML fragment
    that HTMX swaps into the chat container.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        message: User's message from form data.
        level: CEFR level (A0, A1, A2, B1). Defaults to A1.
        language: Target language (es, de). Defaults to es (Spanish).

    Returns:
        HTMLResponse: Partial HTML with user message and AI response.
    """
    timestamp = datetime.now().strftime("%H:%M")

    # Invoke LangGraph agent
    result = await compiled_graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "level": level,
            "language": language,
        }
    )

    # Extract AI response from graph result
    ai_response = result["messages"][-1].content

    return templates.TemplateResponse(
        request=request,
        name="partials/message_pair.html",
        context={
            "user_message": message,
            "ai_response": ai_response,
            "timestamp": timestamp,
        },
    )
