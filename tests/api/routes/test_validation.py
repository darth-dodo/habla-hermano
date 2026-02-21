"""Tests for chat endpoint input validation.

Validates message length limits, empty message rejection, whitespace handling,
and level/language parameter validation.
"""

import pytest

from src.api.routes.chat import MAX_MESSAGE_LENGTH, VALID_LANGUAGES, VALID_LEVELS, _make_error_html


class TestValidationConstants:
    """Tests for validation constant values."""

    def test_max_message_length(self) -> None:
        assert MAX_MESSAGE_LENGTH == 2000

    def test_valid_levels(self) -> None:
        assert {"A0", "A1", "A2", "B1"} == VALID_LEVELS

    def test_valid_languages(self) -> None:
        assert {"es", "de", "fr"} == VALID_LANGUAGES


class TestMakeErrorHtml:
    """Tests for _make_error_html helper."""

    def test_returns_422_status(self) -> None:
        response = _make_error_html("test error")
        assert response.status_code == 422

    def test_returns_html_content(self) -> None:
        response = _make_error_html("test error")
        assert b"text-red-500" in response.body
        assert b"test error" in response.body

    def test_returns_html_content_type(self) -> None:
        response = _make_error_html("test error")
        assert "text/html" in response.media_type

    def test_is_fragment_not_full_page(self) -> None:
        response = _make_error_html("test error")
        body = response.body.decode()
        assert "<!DOCTYPE" not in body
        assert "<html" not in body.lower()


class TestMessageLengthValidation:
    """Tests for message length enforcement via the send_message endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create test client with mocked graph."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [MagicMock(content="Hola!")],
                "grammar_feedback": [],
                "new_vocabulary": [],
                "pronunciation_tips": [],
                "scaffolding": {},
            }
        )

        mock_checkpointer = MagicMock()
        mock_checkpointer.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_checkpointer.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=mock_checkpointer),
        ):
            from fastapi.testclient import TestClient

            from src.api.main import app

            yield TestClient(app)

    def test_message_over_limit_rejected(self, test_client) -> None:
        long_message = "a" * (MAX_MESSAGE_LENGTH + 1)
        response = test_client.post(
            "/chat",
            data={"message": long_message, "level": "A1", "language": "es"},
        )
        assert response.status_code == 422
        assert "too long" in response.text

    def test_empty_message_rejected(self, test_client) -> None:
        # FastAPI treats empty-string form fields as missing, so the framework
        # itself returns 422 before our handler runs.  We verify the request is
        # still rejected at the HTTP level.
        response = test_client.post(
            "/chat",
            data={"message": "", "level": "A1", "language": "es"},
        )
        assert response.status_code == 422

    def test_whitespace_only_rejected(self, test_client) -> None:
        response = test_client.post(
            "/chat",
            data={"message": "   \t\n  ", "level": "A1", "language": "es"},
        )
        assert response.status_code == 422
        assert "empty" in response.text.lower()

    def test_invalid_level_rejected(self, test_client) -> None:
        response = test_client.post(
            "/chat",
            data={"message": "Hola", "level": "C2", "language": "es"},
        )
        assert response.status_code == 422
        assert "Invalid level" in response.text

    def test_invalid_language_rejected(self, test_client) -> None:
        response = test_client.post(
            "/chat",
            data={"message": "Hola", "level": "A1", "language": "jp"},
        )
        assert response.status_code == 422
        assert "Invalid language" in response.text

    def test_valid_message_accepted(self, test_client) -> None:
        response = test_client.post(
            "/chat",
            data={"message": "Hola amigo", "level": "A1", "language": "es"},
        )
        assert response.status_code == 200

    def test_message_at_exact_limit_accepted(self, test_client) -> None:
        exact_message = "a" * MAX_MESSAGE_LENGTH
        response = test_client.post(
            "/chat",
            data={"message": exact_message, "level": "A1", "language": "es"},
        )
        assert response.status_code == 200
