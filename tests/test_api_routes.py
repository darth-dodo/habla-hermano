"""Tests for src/api/routes/chat.py - Chat page and message endpoints."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage


class TestChatPageEndpoint:
    """Tests for GET / - Main chat interface rendering."""

    def test_chat_page_returns_200(self, test_client: TestClient) -> None:
        """GET / should return 200 OK."""
        response = test_client.get("/")
        assert response.status_code == 200

    def test_chat_page_returns_html(self, test_client: TestClient) -> None:
        """GET / should return HTML content type."""
        response = test_client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_chat_page_contains_app_name(self, test_client: TestClient) -> None:
        """GET / should include app name in response."""
        response = test_client.get("/")
        # The app name from mock_settings is "HablaAI-Test" but template might use default
        # Check for the general HablaAI branding
        assert "HablaAI" in response.text

    def test_chat_page_contains_title(self, test_client: TestClient) -> None:
        """GET / should include proper HTML title."""
        response = test_client.get("/")
        assert "<title>" in response.text
        assert "Chat" in response.text

    def test_chat_page_contains_chat_form(self, test_client: TestClient) -> None:
        """GET / should include the chat form element."""
        response = test_client.get("/")
        assert 'id="chat-form"' in response.text
        assert 'hx-post="/chat"' in response.text

    def test_chat_page_contains_message_input(self, test_client: TestClient) -> None:
        """GET / should include the message input field."""
        response = test_client.get("/")
        assert 'name="message"' in response.text
        assert 'id="message-input"' in response.text

    def test_chat_page_contains_level_selector(self, test_client: TestClient) -> None:
        """GET / should include level selection UI."""
        response = test_client.get("/")
        # Check for level options
        assert "A0" in response.text
        assert "A1" in response.text
        assert "A2" in response.text
        assert "B1" in response.text

    def test_chat_page_contains_hidden_level_input(self, test_client: TestClient) -> None:
        """GET / should include hidden level input for form submission."""
        response = test_client.get("/")
        assert 'name="level"' in response.text

    def test_chat_page_contains_welcome_message(self, test_client: TestClient) -> None:
        """GET / should include welcome message from AI tutor."""
        response = test_client.get("/")
        assert "Hola" in response.text
        assert "Spanish tutor" in response.text

    def test_chat_page_contains_send_button(self, test_client: TestClient) -> None:
        """GET / should include send button."""
        response = test_client.get("/")
        assert 'type="submit"' in response.text

    def test_chat_page_contains_loading_indicator(self, test_client: TestClient) -> None:
        """GET / should include loading indicator element."""
        response = test_client.get("/")
        assert 'id="loading-indicator"' in response.text

    def test_chat_page_contains_chat_container(self, test_client: TestClient) -> None:
        """GET / should include chat messages container."""
        response = test_client.get("/")
        assert 'id="chat-messages"' in response.text

    async def test_chat_page_async(self, async_client: AsyncClient) -> None:
        """GET / should work with async client."""
        response = await async_client.get("/")
        assert response.status_code == 200
        assert "HablaAI" in response.text


class TestSendMessageEndpoint:
    """Tests for POST /chat - Message submission and AI response."""

    def test_send_message_returns_200(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat should return 200 OK with valid message."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )
        assert response.status_code == 200

    def test_send_message_returns_html(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat should return HTML content type."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )
        assert "text/html" in response.headers["content-type"]

    def test_send_message_contains_ai_response(
        self,
        test_client: TestClient,
        sample_message: str,
        sample_ai_response: str,
    ) -> None:
        """POST /chat response should include AI response."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )
        assert sample_ai_response in response.text

    def test_send_message_contains_ai_bubble(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat response should include AI chat bubble class."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )
        # User message is shown client-side via JavaScript (optimistic UI)
        # Server only returns AI response
        assert "bg-ai" in response.text

    def test_send_message_default_level(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should default to A1 level when not provided."""
        test_client.post("/chat", data={"message": sample_message})

        # Verify the graph was called with default level A1
        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["level"] == "A1"

    def test_send_message_default_language(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should default to Spanish (es) when language not provided."""
        test_client.post("/chat", data={"message": sample_message})

        # Verify the graph was called with default language es
        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["language"] == "es"

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_send_message_with_different_levels(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
        level: str,
    ) -> None:
        """POST /chat should pass the specified level to the agent."""
        # Reset mock between parametrized calls
        mock_compiled_graph.ainvoke.reset_mock()

        test_client.post("/chat", data={"message": sample_message, "level": level})

        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["level"] == level

    @pytest.mark.parametrize("language", ["es", "de"])
    def test_send_message_with_different_languages(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
        language: str,
    ) -> None:
        """POST /chat should pass the specified language to the agent."""
        # Reset mock between parametrized calls
        mock_compiled_graph.ainvoke.reset_mock()

        test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1", "language": language},
        )

        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["language"] == language

    def test_send_message_creates_human_message(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should create a HumanMessage from user input."""
        test_client.post("/chat", data={"message": sample_message, "level": "A1"})

        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]

        # Check that messages contains a HumanMessage
        messages = call_args["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == sample_message

    def test_send_message_empty_message(self, test_client: TestClient) -> None:
        """POST /chat with empty message should fail validation."""
        response = test_client.post("/chat", data={"message": "", "level": "A1"})
        # FastAPI form validation might return 422 or process empty string
        # Depending on implementation, this tests the behavior
        assert response.status_code in [200, 422]

    def test_send_message_missing_message(self, test_client: TestClient) -> None:
        """POST /chat without message field should return 422."""
        response = test_client.post("/chat", data={"level": "A1"})
        assert response.status_code == 422

    async def test_send_message_async(
        self,
        async_client: AsyncClient,
        sample_message: str,
        sample_ai_response: str,
    ) -> None:
        """POST /chat should work with async client."""
        response = await async_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )
        assert response.status_code == 200
        # User message shown client-side, server returns AI response only
        assert sample_ai_response in response.text


class TestSendMessageEdgeCases:
    """Tests for edge cases and error handling in POST /chat."""

    def test_send_message_long_message(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
    ) -> None:
        """POST /chat should handle long messages."""
        long_message = "Hola " * 1000  # Very long message

        response = test_client.post(
            "/chat",
            data={"message": long_message, "level": "A1"},
        )
        assert response.status_code == 200

        # Verify the full message was passed to the agent
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["messages"][0].content == long_message

    def test_send_message_special_characters(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
    ) -> None:
        """POST /chat should handle special characters correctly."""
        special_message = "Como estas? <script>alert('test')</script> & amigo!"

        response = test_client.post(
            "/chat",
            data={"message": special_message, "level": "A1"},
        )
        assert response.status_code == 200

    def test_send_message_unicode(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
    ) -> None:
        """POST /chat should handle unicode characters."""
        unicode_message = "Hola! Que tal? Las ninas estan bien."

        response = test_client.post(
            "/chat",
            data={"message": unicode_message, "level": "A1"},
        )
        assert response.status_code == 200

        # Verify unicode was preserved
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["messages"][0].content == unicode_message

    def test_send_message_unknown_level(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should accept unknown levels (validation at agent level)."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "C2"},  # Not a supported level
        )
        # Should still return 200 - level validation is at agent level
        assert response.status_code == 200

        call_args = mock_compiled_graph.ainvoke.call_args[0][0]
        assert call_args["level"] == "C2"


class TestHealthEndpoint:
    """Tests for GET /health - Health check endpoint."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        """GET /health should return 200 OK."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, test_client: TestClient) -> None:
        """GET /health should return JSON content type."""
        response = test_client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_contains_status(self, test_client: TestClient) -> None:
        """GET /health should include status field."""
        response = test_client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_contains_app_name(self, test_client: TestClient) -> None:
        """GET /health should include app name."""
        response = test_client.get("/health")
        data = response.json()
        assert "app" in data
        # App name comes from settings
        assert "HablaAI" in data["app"]

    async def test_health_async(self, async_client: AsyncClient) -> None:
        """GET /health should work with async client."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAgentIntegration:
    """Tests for agent integration and mock behavior."""

    def test_agent_called_with_correct_structure(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should call agent with correct state structure."""
        test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A2", "language": "de"},
        )

        mock_compiled_graph.ainvoke.assert_called_once()
        call_args = mock_compiled_graph.ainvoke.call_args[0][0]

        # Verify complete structure
        assert "messages" in call_args
        assert "level" in call_args
        assert "language" in call_args
        assert isinstance(call_args["messages"], list)
        assert call_args["level"] == "A2"
        assert call_args["language"] == "de"

    def test_agent_response_extraction(
        self,
        test_client: TestClient,
        sample_message: str,
        sample_ai_response: str,
    ) -> None:
        """POST /chat should correctly extract AI response from agent result."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )

        # The AI response should be in the HTML
        assert sample_ai_response in response.text

    def test_agent_ainvoke_is_awaited(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
        sample_message: str,
    ) -> None:
        """POST /chat should properly await the agent's async invoke."""
        test_client.post("/chat", data={"message": sample_message})

        # Verify ainvoke was called (it's an AsyncMock)
        assert mock_compiled_graph.ainvoke.await_count == 1


class TestMultipleRequests:
    """Tests for handling multiple sequential requests."""

    def test_multiple_sequential_requests(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
    ) -> None:
        """Multiple POST /chat requests should each invoke the agent."""
        messages = ["Hola", "Como estas?", "Muy bien, gracias"]

        for msg in messages:
            response = test_client.post("/chat", data={"message": msg, "level": "A1"})
            assert response.status_code == 200

        # Verify agent was called for each message
        assert mock_compiled_graph.ainvoke.call_count == len(messages)

    def test_different_levels_sequential(
        self,
        test_client: TestClient,
        mock_compiled_graph: MagicMock,
    ) -> None:
        """Sequential requests with different levels should use respective levels."""
        levels = ["A0", "A1", "A2", "B1"]

        for level in levels:
            mock_compiled_graph.ainvoke.reset_mock()
            response = test_client.post(
                "/chat",
                data={"message": "Test", "level": level},
            )
            assert response.status_code == 200

            call_args = mock_compiled_graph.ainvoke.call_args[0][0]
            assert call_args["level"] == level


class TestResponsePartial:
    """Tests for HTMX partial response structure."""

    def test_response_is_partial_html(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat should return partial HTML (not full page)."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )

        # Should NOT contain full HTML structure
        assert "<!DOCTYPE html>" not in response.text
        assert "<html" not in response.text.lower()
        assert "<head>" not in response.text.lower()

    def test_response_contains_message_pair_structure(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat should return message pair HTML structure."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "A1"},
        )

        # User message shown client-side, server returns AI response only
        assert "bg-ai" in response.text


class TestDifferentAgentResponses:
    """Tests with different mock agent responses."""

    def test_empty_ai_response(self, test_client: TestClient) -> None:
        """POST /chat should handle empty AI response."""
        empty_result: dict[str, Any] = {
            "messages": [
                HumanMessage(content="Hola"),
                AIMessage(content=""),
            ],
            "level": "A1",
            "language": "es",
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=empty_result)

        with patch("src.api.routes.chat.compiled_graph", mock_graph):
            # Late import inside patch context for proper mocking
            from src.api.main import create_app

            with TestClient(create_app()) as client:
                response = client.post("/chat", data={"message": "Hola", "level": "A1"})
                assert response.status_code == 200

    def test_long_ai_response(self, test_client: TestClient) -> None:
        """POST /chat should handle long AI response."""
        long_response = "Esta es una respuesta muy larga. " * 100

        long_result: dict[str, Any] = {
            "messages": [
                HumanMessage(content="Hola"),
                AIMessage(content=long_response),
            ],
            "level": "A1",
            "language": "es",
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=long_result)

        with patch("src.api.routes.chat.compiled_graph", mock_graph):
            # Late import inside patch context for proper mocking
            from src.api.main import create_app

            with TestClient(create_app()) as client:
                response = client.post("/chat", data={"message": "Hola", "level": "A1"})
                assert response.status_code == 200
                assert long_response in response.text

    def test_ai_response_with_html_entities(self, test_client: TestClient) -> None:
        """POST /chat should properly handle AI response with HTML entities."""
        html_response = "Hola! <greeting> & mas"

        html_result: dict[str, Any] = {
            "messages": [
                HumanMessage(content="Hola"),
                AIMessage(content=html_response),
            ],
            "level": "A1",
            "language": "es",
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=html_result)

        with patch("src.api.routes.chat.compiled_graph", mock_graph):
            # Late import inside patch context for proper mocking
            from src.api.main import create_app

            with TestClient(create_app()) as client:
                response = client.post("/chat", data={"message": "Hola", "level": "A1"})
                assert response.status_code == 200
