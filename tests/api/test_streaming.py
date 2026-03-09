"""Tests for src/api/streaming.py and POST /chat/stream endpoint.

Phase 15: Validates SSE streaming for chat responses — token streaming,
feedback section rendering, error handling, and endpoint integration.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from src.api.streaming import (
    StreamResult,
    _make_sse_event,
    render_partial,
    stream_chat_events,
)

# =============================================================================
# Unit Tests: _make_sse_event
# =============================================================================


class TestMakeSSEEvent:
    """Tests for the SSE event formatting helper."""

    def test_formats_token_event(self) -> None:
        """Should format a token event with JSON data."""
        result = _make_sse_event("token", {"content": "Hola"})
        assert result == {"event": "token", "data": '{"content": "Hola"}'}

    def test_formats_done_event(self) -> None:
        """Should format a done event with empty data."""
        result = _make_sse_event("done", {})
        assert result == {"event": "done", "data": "{}"}

    def test_formats_error_event(self) -> None:
        """Should format an error event with message."""
        result = _make_sse_event("error", {"message": "Something went wrong."})
        assert result["event"] == "error"
        data = json.loads(result["data"])
        assert data["message"] == "Something went wrong."

    def test_data_is_valid_json(self) -> None:
        """The data field should always be valid JSON."""
        result = _make_sse_event("scaffolding", {"html": "<div>test</div>"})
        parsed = json.loads(result["data"])
        assert parsed["html"] == "<div>test</div>"


# =============================================================================
# Unit Tests: render_partial
# =============================================================================


class TestRenderPartial:
    """Tests for the Jinja2 partial rendering helper."""

    def test_renders_template_with_context(self) -> None:
        """Should render a template using the Jinja2 environment."""
        mock_template = MagicMock()
        mock_template.render.return_value = "<div>rendered</div>"

        mock_templates = MagicMock()
        mock_templates.get_template.return_value = mock_template

        result = render_partial(mock_templates, "partials/test.html", {"key": "value"})

        mock_templates.get_template.assert_called_once_with("partials/test.html")
        mock_template.render.assert_called_once_with({"key": "value"})
        assert result == "<div>rendered</div>"


# =============================================================================
# CSP Compliance: scaffold template uses data attributes, not inline handlers
# =============================================================================


class TestScaffoldTemplateCSPCompliance:
    """Verify scaffold.html uses data-* attributes instead of inline onclick.

    The P2 audit (B8) moved from 'unsafe-inline' to nonce-based CSP.
    Inline event handlers (onclick) are blocked by nonce-based CSP and
    must be replaced with data-* attributes + delegated JS listeners.
    """

    @pytest.fixture
    def rendered_scaffold(self) -> str:
        """Render the scaffold template with sample data."""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(
            loader=FileSystemLoader("src/templates"),
            autoescape=True,
        )
        template = env.get_template("partials/scaffold.html")
        return template.render(
            scaffolding={
                "enabled": True,
                "word_bank": ["hola (hello)", "gracias (thank you)"],
                "hint_text": "Try saying hello!",
                "sentence_starter": "Me llamo",
                "auto_expand": True,
            }
        )

    def test_no_inline_onclick_handlers(self, rendered_scaffold: str) -> None:
        """Scaffold buttons must NOT use onclick (blocked by nonce CSP)."""
        assert "onclick=" not in rendered_scaffold

    def test_word_bank_uses_data_attributes(self, rendered_scaffold: str) -> None:
        """Word bank buttons use data-insert-word for CSP-safe delegation."""
        assert "data-insert-word=" in rendered_scaffold
        assert 'data-insert-word="hola (hello)"' in rendered_scaffold
        assert 'data-insert-word="gracias (thank you)"' in rendered_scaffold

    def test_sentence_starter_uses_data_attribute(self, rendered_scaffold: str) -> None:
        """Sentence starter button uses data-insert-starter for CSP-safe delegation."""
        assert "data-insert-starter=" in rendered_scaffold
        assert 'data-insert-starter="Me llamo"' in rendered_scaffold

    def test_scaffold_not_rendered_when_disabled(self) -> None:
        """Scaffold HTML is empty when scaffolding is disabled."""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(
            loader=FileSystemLoader("src/templates"),
            autoescape=True,
        )
        template = env.get_template("partials/scaffold.html")
        result = template.render(scaffolding={"enabled": False})
        assert result.strip() == ""


# =============================================================================
# Unit Tests: StreamResult
# =============================================================================


class TestStreamResult:
    """Tests for the StreamResult dataclass."""

    def test_defaults_to_empty(self) -> None:
        """Should initialize with empty defaults."""
        result = StreamResult()
        assert result.new_vocabulary == []
        assert result.review_words_offered == []
        assert result.review_words_used == []
        assert result.full_response == ""

    def test_mutable_fields_are_independent(self) -> None:
        """Each instance should have independent list fields."""
        r1 = StreamResult()
        r2 = StreamResult()
        r1.new_vocabulary.append("hola")
        assert r2.new_vocabulary == []


# =============================================================================
# Unit Tests: stream_chat_events
# =============================================================================


async def _make_mock_graph(stream_events: list[tuple[str, Any]]) -> MagicMock:
    """Create a mock graph with an astream method yielding given events."""
    mock_graph = MagicMock()

    async def mock_astream(inputs, config, stream_mode):
        for event in stream_events:
            yield event

    mock_graph.astream = mock_astream
    return mock_graph


class TestStreamChatEvents:
    """Tests for the core SSE streaming generator."""

    @pytest.fixture
    def mock_templates(self) -> MagicMock:
        """Create a mock Jinja2Templates instance."""
        mock_tmpl = MagicMock()
        mock_template = MagicMock()
        mock_template.render.return_value = "<div>feedback</div>"
        mock_tmpl.get_template.return_value = mock_template
        return mock_tmpl

    @pytest.mark.asyncio
    async def test_streams_token_events_from_respond_node(self, mock_templates: MagicMock) -> None:
        """Should yield token events for chunks from the respond node."""
        chunk1 = AIMessageChunk(content="Hola")
        chunk2 = AIMessageChunk(content=" amigo")

        stream_events = [
            ("messages", (chunk1, {"langgraph_node": "respond"})),
            ("messages", (chunk2, {"langgraph_node": "respond"})),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        # Should have 2 tokens + 1 done
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 2
        assert json.loads(token_events[0]["data"])["content"] == "Hola"
        assert json.loads(token_events[1]["data"])["content"] == " amigo"

    @pytest.mark.asyncio
    async def test_filters_non_respond_node_tokens(self, mock_templates: MagicMock) -> None:
        """Should NOT yield tokens from scaffold or analyze nodes."""
        chunk = AIMessageChunk(content="scaffold internal")
        stream_events = [
            ("messages", (chunk, {"langgraph_node": "scaffold"})),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 0

    @pytest.mark.asyncio
    async def test_yields_response_complete_on_respond_update(
        self, mock_templates: MagicMock
    ) -> None:
        """Should yield response_complete when respond node finishes."""
        chunk = AIMessageChunk(content="Full response")
        stream_events = [
            ("messages", (chunk, {"langgraph_node": "respond"})),
            ("updates", {"respond": {"review_words_offered": ["hola"]}}),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        complete_events = [e for e in events if e["event"] == "response_complete"]
        assert len(complete_events) == 1
        data = json.loads(complete_events[0]["data"])
        assert data["content"] == "Full response"

    @pytest.mark.asyncio
    async def test_captures_review_words_offered(self, mock_templates: MagicMock) -> None:
        """Should capture review_words_offered in StreamResult."""
        stream_events = [
            ("updates", {"respond": {"review_words_offered": ["hola", "amigo"]}}),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        async for _ in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            pass

        assert result.review_words_offered == ["hola", "amigo"]

    @pytest.mark.asyncio
    async def test_yields_scaffolding_for_enabled_scaffold(self, mock_templates: MagicMock) -> None:
        """Should yield scaffolding event when scaffold node returns enabled scaffolding."""
        stream_events = [
            ("updates", {"scaffold": {"scaffolding": {"enabled": True, "word_bank": []}}}),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A0",
            result=result,
        ):
            events.append(event)

        scaffold_events = [e for e in events if e["event"] == "scaffolding"]
        assert len(scaffold_events) == 1
        mock_templates.get_template.assert_any_call("partials/scaffold.html")

    @pytest.mark.asyncio
    async def test_skips_scaffolding_when_not_enabled(self, mock_templates: MagicMock) -> None:
        """Should NOT yield scaffolding when scaffolding is disabled or empty."""
        stream_events = [
            ("updates", {"scaffold": {"scaffolding": {"enabled": False}}}),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        scaffold_events = [e for e in events if e["event"] == "scaffolding"]
        assert len(scaffold_events) == 0

    @pytest.mark.asyncio
    async def test_yields_grammar_feedback(self, mock_templates: MagicMock) -> None:
        """Should yield grammar event when analyze node returns grammar feedback."""
        stream_events = [
            (
                "updates",
                {
                    "analyze": {
                        "grammar_feedback": [{"text": "good"}],
                        "pronunciation_tips": [],
                    }
                },
            ),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        grammar_events = [e for e in events if e["event"] == "grammar"]
        assert len(grammar_events) == 1

    @pytest.mark.asyncio
    async def test_yields_pronunciation_tips(self, mock_templates: MagicMock) -> None:
        """Should yield pronunciation event when analyze node returns tips."""
        stream_events = [
            (
                "updates",
                {
                    "analyze": {
                        "grammar_feedback": [],
                        "pronunciation_tips": [{"word": "hola", "tip": "oh-la"}],
                    }
                },
            ),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        pronunciation_events = [e for e in events if e["event"] == "pronunciation"]
        assert len(pronunciation_events) == 1

    @pytest.mark.asyncio
    async def test_skips_empty_grammar_and_pronunciation(self, mock_templates: MagicMock) -> None:
        """Should NOT yield grammar/pronunciation events when lists are empty."""
        stream_events = [
            (
                "updates",
                {
                    "analyze": {
                        "grammar_feedback": [],
                        "pronunciation_tips": [],
                    }
                },
            ),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        feedback_events = [e for e in events if e["event"] in ("grammar", "pronunciation")]
        assert len(feedback_events) == 0

    @pytest.mark.asyncio
    async def test_captures_vocabulary_from_analyze_node(self, mock_templates: MagicMock) -> None:
        """Should capture new_vocabulary and review_words_used in StreamResult."""
        stream_events = [
            (
                "updates",
                {
                    "analyze": {
                        "grammar_feedback": [],
                        "pronunciation_tips": [],
                        "new_vocabulary": [{"word": "hola", "translation": "hello"}],
                        "review_words_used": ["amigo"],
                    }
                },
            ),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        async for _ in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            pass

        assert len(result.new_vocabulary) == 1
        assert result.new_vocabulary[0]["word"] == "hola"
        assert result.review_words_used == ["amigo"]

    @pytest.mark.asyncio
    async def test_always_yields_done_event(self, mock_templates: MagicMock) -> None:
        """Should always end with a done event."""
        graph = await _make_mock_graph([])
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        assert len(events) >= 1
        assert events[-1]["event"] == "done"

    @pytest.mark.asyncio
    async def test_yields_error_event_on_exception(self, mock_templates: MagicMock) -> None:
        """Should yield error event when graph.astream raises an exception."""
        mock_graph = MagicMock()

        async def failing_astream(inputs, config, stream_mode):
            raise RuntimeError("LLM unavailable")
            yield  # make this a generator

        mock_graph.astream = failing_astream
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=mock_graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A1",
            result=result,
        ):
            events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        data = json.loads(error_events[0]["data"])
        assert "wrong" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_full_stream_sequence(self, mock_templates: MagicMock) -> None:
        """Should produce the correct event sequence for a full conversation turn."""
        chunk1 = AIMessageChunk(content="Hola")
        chunk2 = AIMessageChunk(content=" Juan")

        stream_events = [
            ("messages", (chunk1, {"langgraph_node": "respond"})),
            ("messages", (chunk2, {"langgraph_node": "respond"})),
            ("updates", {"respond": {}}),
            ("updates", {"scaffold": {"scaffolding": {"enabled": True, "word_bank": []}}}),
            (
                "updates",
                {
                    "analyze": {
                        "grammar_feedback": [{"text": "good"}],
                        "pronunciation_tips": [{"word": "hola"}],
                        "new_vocabulary": [{"word": "hola"}],
                    }
                },
            ),
        ]
        graph = await _make_mock_graph(stream_events)
        result = StreamResult()

        events = []
        async for event in stream_chat_events(
            graph=graph,
            inputs={},
            config={},
            templates=mock_templates,
            level="A0",
            result=result,
        ):
            events.append(event)

        event_types = [e["event"] for e in events]

        # Verify sequence: tokens → response_complete → scaffolding → grammar → pronunciation → done
        assert event_types[0] == "token"
        assert event_types[1] == "token"
        assert "response_complete" in event_types
        assert "scaffolding" in event_types
        assert "grammar" in event_types
        assert "pronunciation" in event_types
        assert event_types[-1] == "done"

        # Verify accumulated response
        assert result.full_response == "Hola Juan"


# =============================================================================
# Integration Tests: POST /chat/stream endpoint
# =============================================================================


class TestStreamMessageEndpoint:
    """Tests for POST /chat/stream — the SSE streaming endpoint."""

    def _make_stream_graph(self, response_text: str = "Hola") -> MagicMock:
        """Create a mock graph with astream that yields a simple response."""
        mock_graph = MagicMock()

        chunk = AIMessageChunk(content=response_text)

        async def mock_astream(inputs, config, stream_mode):
            yield ("messages", (chunk, {"langgraph_node": "respond"}))
            yield ("updates", {"respond": {}})

        mock_graph.astream = mock_astream
        # Keep ainvoke for the non-streaming endpoint
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [AIMessageChunk(content=response_text)],
                "level": "A1",
                "language": "es",
            }
        )
        return mock_graph

    def test_stream_returns_200(self, test_client: TestClient) -> None:
        """POST /chat/stream should return 200 OK."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1"},
        )
        assert response.status_code == 200

    def test_stream_returns_event_stream_content_type(self, test_client: TestClient) -> None:
        """POST /chat/stream should return text/event-stream content type."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1"},
        )
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_empty_message_returns_error_event(self, test_client: TestClient) -> None:
        """POST /chat/stream with whitespace-only message should return error SSE event."""
        # Send whitespace (not empty string) — FastAPI's Form() rejects truly empty
        # strings with 422, but our handler catches whitespace via strip().
        response = test_client.post(
            "/chat/stream",
            data={"message": "   ", "level": "A1"},
        )
        assert response.status_code == 200
        assert "error" in response.text
        assert "empty" in response.text.lower()

    def test_stream_too_long_message_returns_error_event(self, test_client: TestClient) -> None:
        """POST /chat/stream with too-long message should return error SSE event."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "x" * 2001, "level": "A1"},
        )
        assert response.status_code == 200
        assert "error" in response.text
        assert "long" in response.text.lower()

    def test_stream_invalid_level_returns_error_event(self, test_client: TestClient) -> None:
        """POST /chat/stream with invalid level should return error SSE event."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "C2"},
        )
        assert response.status_code == 200
        assert "error" in response.text

    def test_stream_invalid_language_returns_error_event(self, test_client: TestClient) -> None:
        """POST /chat/stream with invalid language should return error SSE event."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1", "language": "xx"},
        )
        assert response.status_code == 200
        assert "error" in response.text

    def test_stream_contains_sse_events(self, test_client: TestClient) -> None:
        """POST /chat/stream response body should contain SSE-formatted events."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1"},
        )
        # SSE responses contain event: and data: lines
        body = response.text
        # Should contain at least some event or data content
        assert "event:" in body or "data:" in body

    def test_stream_default_level(
        self, test_client: TestClient, mock_compiled_graph: MagicMock
    ) -> None:
        """POST /chat/stream should default to A1 level."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola"},
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_stream_accepts_valid_levels(self, test_client: TestClient, level: str) -> None:
        """POST /chat/stream should accept all valid CEFR levels."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": level},
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("language", ["es", "de"])
    def test_stream_accepts_valid_languages(self, test_client: TestClient, language: str) -> None:
        """POST /chat/stream should accept all valid languages."""
        response = test_client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1", "language": language},
        )
        assert response.status_code == 200
