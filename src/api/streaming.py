"""SSE streaming utilities for chat responses.

Phase 15: Provides server-sent event streaming for the chat endpoint.
Streams AI response tokens in real-time, then sends feedback sections
(grammar, pronunciation, scaffolding) as discrete HTML events.

Uses LangGraph's astream(stream_mode=["messages", "updates"]) to intercept
LLM token callbacks from within nodes without modifying node code.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from starlette.templating import Jinja2Templates

logger = logging.getLogger(__name__)


@dataclass
class StreamResult:
    """Container for data captured during streaming that's needed post-stream.

    The streaming generator populates these fields as nodes complete,
    allowing the caller to perform vocabulary capture after the stream ends.
    """

    new_vocabulary: list[Any] = field(default_factory=list)
    review_words_offered: list[Any] = field(default_factory=list)
    review_words_used: list[Any] = field(default_factory=list)
    full_response: str = ""


def render_partial(templates: Jinja2Templates, template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 partial template to an HTML string.

    Uses the Jinja2 environment directly to render without a request object,
    since SSE events don't need request context.

    Args:
        templates: The Jinja2Templates instance from FastAPI.
        template_name: Relative path to the template (e.g., "partials/scaffold.html").
        context: Template variables.

    Returns:
        Rendered HTML string.
    """
    template = templates.get_template(template_name)
    return template.render(context)


def _make_sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    """Format an SSE event as a dict for sse-starlette's EventSourceResponse.

    Args:
        event: SSE event name (e.g., "token", "grammar").
        data: JSON-serializable payload.

    Returns:
        Dict with "event" and "data" keys.
    """
    return {"event": event, "data": json.dumps(data)}


async def stream_chat_events(  # noqa: PLR0912
    graph: Any,
    inputs: dict[str, Any],
    config: dict[str, Any],
    templates: Jinja2Templates,
    level: str,
    result: StreamResult,
) -> Any:
    """Async generator that streams chat events as SSE data.

    Yields SSE events in four phases:
    1. Token events from the respond node's LLM (real-time text streaming)
    2. response_complete with the full accumulated text
    3. Feedback HTML (scaffolding, grammar, pronunciation) rendered server-side
    4. done event to signal stream completion

    Args:
        graph: Compiled LangGraph instance.
        inputs: Graph input dict (messages, level, language, etc.).
        config: LangGraph config with thread_id for checkpointing.
        templates: Jinja2Templates for rendering feedback partials.
        level: CEFR level (A0, A1, A2, B1) for template rendering.
        result: StreamResult container populated during streaming for post-stream use.

    Yields:
        Dicts with "event" and "data" keys for EventSourceResponse.
    """
    accumulated_response = ""

    try:
        async for mode, chunk in graph.astream(
            inputs,
            config=config,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                # chunk is (AIMessageChunk, metadata) tuple
                message_chunk, metadata = chunk
                node_name = metadata.get("langgraph_node", "")

                # Only stream tokens from the respond node
                # Skip scaffold/analyze node LLM tokens
                if (
                    node_name == "respond"
                    and hasattr(message_chunk, "content")
                    and message_chunk.content
                ):
                    accumulated_response += message_chunk.content
                    yield _make_sse_event("token", {"content": message_chunk.content})

            elif mode == "updates":
                # chunk is dict like {"respond": {...}} or {"analyze": {...}}
                for node_name, node_output in chunk.items():
                    if node_name == "respond":
                        result.full_response = accumulated_response
                        yield _make_sse_event(
                            "response_complete", {"content": accumulated_response}
                        )

                        # Capture review words offered
                        offered = node_output.get("review_words_offered", [])
                        if offered:
                            result.review_words_offered = offered

                    elif node_name == "scaffold":
                        scaffolding = node_output.get("scaffolding", {})
                        if scaffolding and scaffolding.get("enabled"):
                            html = render_partial(
                                templates,
                                "partials/scaffold.html",
                                {"scaffolding": scaffolding},
                            )
                            yield _make_sse_event("scaffolding", {"html": html})

                    elif node_name == "analyze":
                        # Grammar feedback
                        grammar = node_output.get("grammar_feedback", [])
                        if grammar:
                            html = render_partial(
                                templates,
                                "partials/grammar_feedback.html",
                                {"grammar_feedback": grammar},
                            )
                            yield _make_sse_event("grammar", {"html": html})

                        # Pronunciation tips
                        pronunciation = node_output.get("pronunciation_tips", [])
                        if pronunciation:
                            html = render_partial(
                                templates,
                                "partials/pronunciation_tips.html",
                                {"pronunciation_tips": pronunciation, "level": level},
                            )
                            yield _make_sse_event("pronunciation", {"html": html})

                        # Capture vocabulary for post-stream persistence
                        vocab = node_output.get("new_vocabulary", [])
                        if vocab:
                            result.new_vocabulary = vocab

                        # Capture review words used
                        used = node_output.get("review_words_used", [])
                        if used:
                            result.review_words_used = used

    except Exception:
        logger.exception("Error during chat streaming")
        yield _make_sse_event("error", {"message": "Sorry, something went wrong. Please try again."})
        return

    yield _make_sse_event("done", {})
