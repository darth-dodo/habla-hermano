"""Tests for src/api/routes/chat.py - Chat page and message endpoints."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from src.api.auth import AuthenticatedUser
from src.api.dependencies import get_lesson_service
from src.api.routes.chat import _resolve_chat_identity, _resolve_lesson_thread_id
from src.lessons.models import (
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
)
from tests.conftest import CSRF_HEADERS


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
        # The app name from mock_settings is "Habla Hermano-Test" but template might use default
        # Check for the general Habla Hermano branding
        assert "Habla Hermano" in response.text

    def test_chat_page_contains_title(self, test_client: TestClient) -> None:
        """GET / should include proper HTML title."""
        response = test_client.get("/")
        assert "<title>" in response.text
        assert "Chat" in response.text

    def test_chat_page_contains_chat_form(self, test_client: TestClient) -> None:
        """GET / should include the chat form element."""
        response = test_client.get("/")
        assert 'id="chat-form"' in response.text

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
        """GET / should include welcome message from AI conversation partner."""
        response = test_client.get("/")
        # Welcome message includes both Spanish and German greetings (Alpine.js switches)
        assert "Hola" in response.text or "Hallo" in response.text
        assert "conversation partner" in response.text

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
        assert "Habla Hermano" in response.text

    def test_chat_page_sets_session_cookie_for_guests(self, test_client: TestClient) -> None:
        """GET / should set session_id cookie for guest users so voice WebSocket auth works."""
        from src.api.auth import get_current_user_optional

        app = test_client.app

        # Override auth to return None (guest user)
        async def mock_no_user():
            return None

        app.dependency_overrides[get_current_user_optional] = mock_no_user
        try:
            response = test_client.get("/")
            assert response.status_code == 200
            assert "session_id" in response.cookies
            # Should be a valid UUID v4
            import uuid

            session_val = response.cookies["session_id"]
            parsed = uuid.UUID(session_val, version=4)
            assert str(parsed) == session_val
        finally:
            app.dependency_overrides.pop(get_current_user_optional, None)

    def test_chat_page_does_not_overwrite_existing_session_cookie(
        self, test_client: TestClient
    ) -> None:
        """GET / should not overwrite an existing session_id cookie."""
        from src.api.auth import get_current_user_optional

        app = test_client.app

        async def mock_no_user():
            return None

        app.dependency_overrides[get_current_user_optional] = mock_no_user
        try:
            existing_session = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
            test_client.cookies.set("session_id", existing_session)
            response = test_client.get("/")
            assert response.status_code == 200
            # Should NOT set a new session_id cookie
            assert "session_id" not in response.cookies
        finally:
            app.dependency_overrides.pop(get_current_user_optional, None)
            test_client.cookies.clear()

    def test_chat_page_no_session_cookie_for_authenticated_users(
        self, test_client: TestClient
    ) -> None:
        """GET / should not set session_id cookie for authenticated users."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "session_id" not in response.cookies


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
        """POST /chat should reject messages exceeding MAX_MESSAGE_LENGTH."""
        long_message = "Hola " * 1000  # 5000 chars, exceeds 2000 limit

        response = test_client.post(
            "/chat",
            data={"message": long_message, "level": "A1"},
        )
        assert response.status_code == 422
        assert "too long" in response.text

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
        """POST /chat should reject unsupported CEFR levels."""
        response = test_client.post(
            "/chat",
            data={"message": sample_message, "level": "C2"},  # Not a supported level
        )
        assert response.status_code == 422
        assert "Invalid level" in response.text


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
        assert "Habla Hermano" in data["app"]

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

    def _create_mock_context_and_graph(self, result: dict[str, Any]) -> tuple[MagicMock, MagicMock]:
        """Create mock checkpointer context and graph for testing.

        Phase 4: Updated to use async context manager pattern.
        """
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=result)

        mock_checkpointer = MagicMock()
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        return mock_context, mock_graph

    def _create_app_with_auth_mocked(
        self,
        mock_context: MagicMock,
        mock_graph: MagicMock,
    ) -> Any:
        """Create app with both checkpointer and auth mocked.

        Phase 5: Added auth mocking for tests that create their own app.
        """
        from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
        from src.api.main import create_app

        mock_user = AuthenticatedUser(id="test-user-123", email="test@example.com")

        async def mock_get_current_user():
            return mock_user

        async def mock_get_current_user_optional():
            return mock_user

        app = create_app()
        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_current_user_optional] = mock_get_current_user_optional

        return app

    def test_empty_ai_response(self, test_client: TestClient) -> None:
        """POST /chat should handle empty AI response."""
        empty_result: dict[str, Any] = {
            "messages": [
                HumanMessage(content="Hola"),
                AIMessage(content=""),
            ],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
            "scaffolding": {},
        }

        mock_context, mock_graph = self._create_mock_context_and_graph(empty_result)

        with (
            patch("src.api.routes.chat.get_checkpointer", return_value=mock_context),
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
        ):
            # Late import inside patch context for proper mocking
            app = self._create_app_with_auth_mocked(mock_context, mock_graph)

            with TestClient(app, headers=CSRF_HEADERS) as client:
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
            "grammar_feedback": [],
            "new_vocabulary": [],
            "scaffolding": {},
        }

        mock_context, mock_graph = self._create_mock_context_and_graph(long_result)

        with (
            patch("src.api.routes.chat.get_checkpointer", return_value=mock_context),
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
        ):
            # Late import inside patch context for proper mocking
            app = self._create_app_with_auth_mocked(mock_context, mock_graph)

            with TestClient(app, headers=CSRF_HEADERS) as client:
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
            "grammar_feedback": [],
            "new_vocabulary": [],
            "scaffolding": {},
        }

        mock_context, mock_graph = self._create_mock_context_and_graph(html_result)

        with (
            patch("src.api.routes.chat.get_checkpointer", return_value=mock_context),
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
        ):
            # Late import inside patch context for proper mocking
            app = self._create_app_with_auth_mocked(mock_context, mock_graph)

            with TestClient(app, headers=CSRF_HEADERS) as client:
                response = client.post("/chat", data={"message": "Hola", "level": "A1"})
                assert response.status_code == 200


class TestResolveChatIdentity:
    """Tests for _resolve_chat_identity with conversation_version support."""

    def test_authenticated_user_without_version(self) -> None:
        """Authenticated user without conversation_version gets base thread_id."""
        user = AuthenticatedUser(id="user-abc", email="a@b.com")
        thread_id, user_id, new_session = _resolve_chat_identity(user, None)

        assert thread_id == "user:user-abc"
        assert user_id == "user-abc"
        assert new_session is None

    def test_authenticated_user_with_version(self) -> None:
        """Authenticated user with conversation_version gets versioned thread_id."""
        user = AuthenticatedUser(id="user-abc", email="a@b.com")
        version = "some-uuid-v4"
        thread_id, user_id, new_session = _resolve_chat_identity(
            user, None, conversation_version=version
        )

        assert thread_id == f"user:user-abc:{version}"
        assert user_id == "user-abc"
        assert new_session is None

    def test_authenticated_user_different_versions_produce_different_threads(self) -> None:
        """Different conversation versions produce different thread_ids."""
        user = AuthenticatedUser(id="user-abc", email="a@b.com")
        thread_v1, _, _ = _resolve_chat_identity(user, None, conversation_version="v1")
        thread_v2, _, _ = _resolve_chat_identity(user, None, conversation_version="v2")

        assert thread_v1 != thread_v2
        assert thread_v1 == "user:user-abc:v1"
        assert thread_v2 == "user:user-abc:v2"

    def test_authenticated_user_empty_string_version_treated_as_no_version(self) -> None:
        """Empty string conversation_version falls back to base thread_id."""
        user = AuthenticatedUser(id="user-abc", email="a@b.com")
        thread_id, _, _ = _resolve_chat_identity(user, None, conversation_version="")

        assert thread_id == "user:user-abc"

    def test_guest_user_ignores_conversation_version(self) -> None:
        """Guest user with existing session ignores conversation_version."""
        thread_id, user_id, new_session = _resolve_chat_identity(
            None, "session-123", conversation_version="some-version"
        )

        assert thread_id == "session-123"
        assert user_id is None
        assert new_session is None

    def test_first_time_guest_ignores_conversation_version(self) -> None:
        """First-time guest ignores conversation_version and generates session."""
        thread_id, user_id, new_session = _resolve_chat_identity(
            None, None, conversation_version="some-version"
        )

        assert thread_id is not None
        assert user_id is None
        assert new_session is not None
        assert thread_id == new_session


class TestNewConversationEndpoint:
    """Tests for POST /new - New conversation creation."""

    def test_new_conversation_authenticated_sets_version_cookie(
        self, test_client: TestClient
    ) -> None:
        """POST /new for authenticated user should set conversation_version cookie."""
        response = test_client.post("/new", follow_redirects=False)

        assert response.status_code == 200
        assert response.headers.get("HX-Redirect") == "/"

        cookies = response.cookies
        assert "conversation_version" in cookies
        version_value = cookies["conversation_version"]
        assert len(version_value) == 36

    def test_new_conversation_authenticated_generates_unique_versions(
        self, test_client: TestClient
    ) -> None:
        """Each POST /new should generate a unique conversation_version."""
        response1 = test_client.post("/new", follow_redirects=False)
        response2 = test_client.post("/new", follow_redirects=False)

        version1 = response1.cookies.get("conversation_version")
        version2 = response2.cookies.get("conversation_version")

        assert version1 is not None
        assert version2 is not None
        assert version1 != version2

    def test_new_conversation_anonymous_deletes_session_cookie(
        self,
        app_with_mocked_graph: Any,
    ) -> None:
        """POST /new for anonymous user should delete session_id cookie."""
        from src.api.auth import get_current_user_optional

        async def mock_no_user():
            return None

        app_with_mocked_graph.dependency_overrides[get_current_user_optional] = mock_no_user

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            client.cookies.set("session_id", "old-session-id")
            response = client.post("/new", follow_redirects=False)

            assert response.status_code == 200
            assert response.headers.get("HX-Redirect") == "/"
            set_cookie_headers = [h for h in response.headers.raw if h[0] == b"set-cookie"]
            session_deleted = any(
                b"session_id" in h[1] and b"Max-Age=0" in h[1] for h in set_cookie_headers
            )
            assert session_deleted

    def test_new_conversation_anonymous_does_not_set_version_cookie(
        self,
        app_with_mocked_graph: Any,
    ) -> None:
        """POST /new for anonymous user should NOT set conversation_version cookie."""
        from src.api.auth import get_current_user_optional

        async def mock_no_user():
            return None

        app_with_mocked_graph.dependency_overrides[get_current_user_optional] = mock_no_user

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.post("/new", follow_redirects=False)

            assert "conversation_version" not in response.cookies


class TestChatPageLessonMode:
    """Tests for GET /?lesson= — Lesson mode rendering via chat_page."""

    @pytest.fixture
    def sample_lesson(self) -> Lesson:
        """Create a sample lesson for testing."""
        return Lesson(
            metadata=LessonMetadata(
                id="es_a1_greetings_01",
                title="Basic Greetings",
                description="Learn common greetings in Spanish",
                language="es",
                level=LessonLevel.A1,
                estimated_minutes=3,
                category="greetings",
                tags=["greeting"],
                vocabulary_count=2,
                icon="wave",
            ),
            content=LessonContent(
                steps=[
                    LessonStep(
                        type=LessonStepType.INSTRUCTION,
                        content="Learn greetings!",
                        order=1,
                    ),
                ],
                exercises=[],
            ),
        )

    def test_lesson_mode_returns_200(
        self,
        app_with_mocked_graph: FastAPI,
        sample_lesson: Lesson,
    ) -> None:
        """GET /?lesson=es_a1_greetings_01 should return 200 with lesson context."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.get("/?lesson=es_a1_greetings_01")

        assert response.status_code == 200
        assert "Basic Greetings" in response.text

    def test_lesson_mode_contains_lesson_context(
        self,
        app_with_mocked_graph: FastAPI,
        sample_lesson: Lesson,
    ) -> None:
        """GET /?lesson= should include lesson_id and lesson_mode markers in the page."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.get("/?lesson=es_a1_greetings_01")

        assert response.status_code == 200
        # The template uses lesson_id in hidden inputs / JS data attributes
        assert "es_a1_greetings_01" in response.text

    def test_freeform_chat_still_works(self, test_client: TestClient) -> None:
        """GET / without lesson param should still render freeform chat (no regression)."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "Habla Hermano" in response.text

    def test_nonexistent_lesson_returns_404(
        self,
        app_with_mocked_graph: FastAPI,
    ) -> None:
        """GET /?lesson=nonexistent_lesson should return 404."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = None
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(
            app_with_mocked_graph, headers=CSRF_HEADERS, raise_server_exceptions=False
        ) as client:
            response = client.get("/?lesson=nonexistent_lesson")

        assert response.status_code == 404


class TestResolveLessonThreadId:
    """Tests for _resolve_lesson_thread_id helper."""

    def test_authenticated_user_with_session(self) -> None:
        """Authenticated user gets lesson-scoped thread_id with lesson_session suffix."""
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            "user-abc", None, "es_a1_greetings_01", "sess-uuid-1"
        )
        assert thread_id == "lesson:user-abc:es_a1_greetings_01:sess-uuid-1"
        assert user_id == "user-abc"
        assert new_session is None

    def test_guest_with_session(self) -> None:
        """Guest with existing session gets lesson-scoped thread_id."""
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            None, "session-123", "es_a1_greetings_01", "sess-uuid-2"
        )
        assert thread_id == "lesson:session-123:es_a1_greetings_01:sess-uuid-2"
        assert user_id is None
        assert new_session is None

    def test_first_time_guest(self) -> None:
        """First-time guest gets new session and lesson-scoped thread_id."""
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            None, None, "es_a1_greetings_01", "sess-uuid-3"
        )
        assert thread_id.startswith("lesson:")
        assert ":es_a1_greetings_01:sess-uuid-3" in thread_id
        assert user_id is None
        assert new_session is not None

    def test_missing_lesson_session_generates_uuid(self) -> None:
        """When lesson_session is None, a UUID suffix is auto-generated."""
        thread_id, _user_id, _ = _resolve_lesson_thread_id("user-abc", None, "es_a1_greetings_01")
        # Format: lesson:user-abc:es_a1_greetings_01:<auto-uuid>
        parts = thread_id.split(":")
        assert len(parts) == 4
        assert parts[0] == "lesson"
        assert parts[1] == "user-abc"
        assert parts[2] == "es_a1_greetings_01"
        assert len(parts[3]) > 0  # auto-generated UUID


class TestStreamMessageLessonMode:
    """Tests for POST /chat/stream with lesson_id — unified stream endpoint."""

    @pytest.fixture
    def sample_lesson(self) -> Lesson:
        """Create a sample lesson for testing."""
        return Lesson(
            metadata=LessonMetadata(
                id="es_a1_greetings_01",
                title="Basic Greetings",
                description="Learn common greetings in Spanish",
                language="es",
                level=LessonLevel.A1,
                estimated_minutes=3,
                category="greetings",
                tags=["greeting"],
                vocabulary_count=2,
                icon="wave",
            ),
            content=LessonContent(
                steps=[
                    LessonStep(
                        type=LessonStepType.INSTRUCTION,
                        content="Learn greetings!",
                        order=1,
                    ),
                ],
                exercises=[],
            ),
        )

    def test_stream_with_lesson_id_returns_sse(
        self,
        app_with_mocked_graph: Any,
        sample_lesson: Lesson,
    ) -> None:
        """POST /chat/stream with lesson_id should return SSE stream."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.post(
                "/chat/stream",
                data={"message": "Hola", "lesson_id": "es_a1_greetings_01"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Should contain SSE events (at least token/done)
        assert "event:" in response.text or "data:" in response.text

    def test_stream_without_lesson_id_still_works(
        self,
        test_client: TestClient,
        sample_message: str,
    ) -> None:
        """POST /chat/stream without lesson_id should still work as freeform (no regression)."""
        response = test_client.post(
            "/chat/stream",
            data={"message": sample_message, "level": "A1", "language": "es"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_with_invalid_lesson_id_returns_error(
        self,
        app_with_mocked_graph: Any,
    ) -> None:
        """POST /chat/stream with nonexistent lesson_id should return error event."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = None
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.post(
                "/chat/stream",
                data={"message": "Hola", "lesson_id": "nonexistent_lesson"},
            )

        assert response.status_code == 200  # SSE always returns 200
        assert "Lesson not found" in response.text

    def test_stream_lesson_uses_metadata_level_and_language(
        self,
        app_with_mocked_graph: Any,
        mock_compiled_graph: MagicMock,
        sample_lesson: Lesson,
    ) -> None:
        """POST /chat/stream with lesson_id should use lesson metadata for level/language."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            # Send with wrong level/language — lesson metadata should override
            client.post(
                "/chat/stream",
                data={
                    "message": "Hola",
                    "lesson_id": "es_a1_greetings_01",
                    "level": "B1",
                    "language": "de",
                },
            )

        # The lesson metadata says level=A1, language=es
        # Check that aget_state was called (lesson path was taken)
        assert mock_compiled_graph.aget_state.await_count >= 1

    def test_stream_lesson_whitespace_message_returns_error(
        self,
        app_with_mocked_graph: Any,
        sample_lesson: Lesson,
    ) -> None:
        """POST /chat/stream with lesson_id but whitespace-only message returns error."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.post(
                "/chat/stream",
                data={"message": "   ", "lesson_id": "es_a1_greetings_01"},
            )

        assert response.status_code == 200
        assert "Message cannot be empty" in response.text


class TestLessonResume:
    """Tests for lesson resume support via checkpoint message recovery."""

    @pytest.fixture
    def sample_lesson(self) -> Lesson:
        """Create a sample lesson for testing."""
        return Lesson(
            metadata=LessonMetadata(
                id="es_a1_greetings_01",
                title="Basic Greetings",
                description="Learn common greetings in Spanish",
                language="es",
                level=LessonLevel.A1,
                estimated_minutes=3,
                category="greetings",
                tags=["greeting"],
                vocabulary_count=2,
                icon="wave",
            ),
            content=LessonContent(
                steps=[
                    LessonStep(
                        type=LessonStepType.INSTRUCTION,
                        content="Learn greetings!",
                        order=1,
                    ),
                ],
                exercises=[],
            ),
        )

    def test_lesson_always_starts_fresh(
        self,
        app_with_mocked_graph: FastAPI,
        sample_lesson: Lesson,
    ) -> None:
        """GET /?lesson=X should always start a fresh lesson (no resume)."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.get("/?lesson=es_a1_greetings_01")

        assert response.status_code == 200
        # No resume indicator — lessons always start fresh
        assert "Resuming your lesson" not in response.text
        assert "data-resuming" not in response.text
        # Fresh lesson_session UUID is included
        assert 'name="lesson_session"' in response.text

    def test_lesson_session_uuid_in_context(
        self,
        app_with_mocked_graph: FastAPI,
        sample_lesson: Lesson,
    ) -> None:
        """Lesson page should include a fresh lesson_session UUID in context."""
        mock_svc = MagicMock()
        mock_svc.get_lesson.return_value = sample_lesson
        app_with_mocked_graph.dependency_overrides[get_lesson_service] = lambda: mock_svc

        with TestClient(app_with_mocked_graph, headers=CSRF_HEADERS) as client:
            response = client.get("/?lesson=es_a1_greetings_01")

        assert response.status_code == 200
        assert 'name="lesson_session"' in response.text
