"""Tests for CSRFMiddleware in src/api/middleware.py.

Validates that the CSRF "custom header" pattern correctly protects
state-changing endpoints (POST/PUT/DELETE/PATCH) while allowing:
- Requests with HX-Request: true (HTMX)
- Requests with X-Requested-With: XMLHttpRequest (fetch/XHR)
- Safe methods (GET, OPTIONS)
- Exempt paths (/health, /static/)
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
from src.api.config import get_settings
from src.api.dependencies import get_cached_templates

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def csrf_app() -> Generator[FastAPI, None, None]:
    """Create a minimal FastAPI app with CSRF middleware registered.

    Uses the full create_app() to include all middleware in the correct
    order, then adds a simple test POST route.
    """
    mock_user = AuthenticatedUser(id="csrf-test-user", email="csrf@example.com")

    # Graph must return at least one AI message to avoid IndexError in chat handler
    mock_graph_result = {
        "messages": [
            HumanMessage(content="Hola"),
            AIMessage(content="Hola! Como estas?"),
        ],
        "level": "A1",
        "language": "es",
        "grammar_feedback": [],
        "new_vocabulary": [],
        "scaffolding": {},
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_graph_result)

    async def mock_astream(inputs, config, stream_mode):
        from langchain_core.messages import AIMessageChunk

        yield (
            "messages",
            (
                AIMessageChunk(content="Hola!"),
                {"langgraph_node": "respond"},
            ),
        )
        yield ("updates", {"respond": {}})
        yield (
            "updates",
            {
                "analyze": {
                    "grammar_feedback": [],
                    "pronunciation_tips": [],
                }
            },
        )

    mock_graph.astream = mock_astream

    class MockCheckpointerContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    def mock_get_checkpointer():
        return MockCheckpointerContext()

    def mock_build_graph(checkpointer=None):
        return mock_graph

    async def mock_get_current_user_dep():
        return mock_user

    async def mock_get_current_user_optional_dep():
        return mock_user

    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_execute_result = MagicMock(data=[], count=0)
    for method in (
        "select",
        "insert",
        "update",
        "delete",
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "ilike",
        "like",
        "is_",
        "in_",
        "or_",
        "order",
        "limit",
        "range",
        "single",
    ):
        setattr(mock_table, method, MagicMock(return_value=mock_table))
    mock_table.execute = MagicMock(return_value=mock_execute_result)
    type(mock_table).not_ = PropertyMock(return_value=mock_table)
    mock_supabase.table = MagicMock(return_value=mock_table)

    with (
        patch("src.api.routes.chat.build_graph", mock_build_graph),
        patch("src.api.routes.chat.get_checkpointer", mock_get_checkpointer),
        patch("src.db.repository.get_supabase", return_value=mock_supabase),
        patch("src.services.lesson_completion.get_supabase_admin", return_value=mock_supabase),
        patch("src.api.routes.learn.get_supabase_admin", return_value=mock_supabase),
    ):
        get_settings.cache_clear()
        get_cached_templates.cache_clear()

        from src.api.main import app

        app.dependency_overrides[get_current_user] = mock_get_current_user_dep
        app.dependency_overrides[get_current_user_optional] = mock_get_current_user_optional_dep

        yield app

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def client(csrf_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a raw TestClient that does NOT inject CSRF headers.

    This allows tests to verify that requests without CSRF headers are
    correctly rejected.
    """
    with TestClient(csrf_app) as c:
        yield c


# =============================================================================
# CSRF Rejection Tests
# =============================================================================


class TestCSRFRejection:
    """POST/PUT/DELETE/PATCH without CSRF headers should return 403."""

    def test_post_without_csrf_header_returns_403(self, client: TestClient) -> None:
        """POST without any CSRF header should be rejected."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "CSRF validation failed"}

    def test_delete_without_csrf_header_returns_403(self, client: TestClient) -> None:
        """DELETE without any CSRF header should be rejected."""
        response = client.delete("/progress/vocabulary/1")
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF validation failed"

    def test_post_with_wrong_header_value_returns_403(self, client: TestClient) -> None:
        """POST with HX-Request set to a wrong value should be rejected."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
            headers={"HX-Request": "false"},
        )
        assert response.status_code == 403

    def test_post_with_empty_x_requested_with_returns_403(self, client: TestClient) -> None:
        """POST with empty X-Requested-With should be rejected."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
            headers={"X-Requested-With": ""},
        )
        assert response.status_code == 403


# =============================================================================
# CSRF Pass-Through Tests
# =============================================================================


class TestCSRFPassThrough:
    """Requests with valid CSRF headers should pass through to the handler."""

    def test_post_with_hx_request_passes(self, client: TestClient) -> None:
        """POST with HX-Request: true should pass CSRF check."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
            headers={"HX-Request": "true"},
        )
        # Should NOT be 403 -- may be 200 or 422 depending on other validation
        assert response.status_code != 403

    def test_post_with_x_requested_with_passes(self, client: TestClient) -> None:
        """POST with X-Requested-With: XMLHttpRequest should pass CSRF check."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code != 403

    def test_delete_with_hx_request_passes(self, client: TestClient) -> None:
        """DELETE with HX-Request: true should pass CSRF check."""
        response = client.delete(
            "/progress/vocabulary/1",
            headers={"HX-Request": "true"},
        )
        # May return 401 (no auth cookie) or 200 but NOT 403 (CSRF)
        assert response.status_code != 403

    def test_hx_request_header_is_case_insensitive(self, client: TestClient) -> None:
        """HX-Request header value should be checked case-insensitively."""
        response = client.post(
            "/chat",
            data={"message": "Hola", "level": "A1"},
            headers={"HX-Request": "True"},
        )
        assert response.status_code != 403


# =============================================================================
# Safe Method Tests
# =============================================================================


class TestSafeMethodsBypass:
    """GET, HEAD, OPTIONS should not be affected by CSRF middleware."""

    def test_get_request_passes_without_csrf(self, client: TestClient) -> None:
        """GET requests should not require CSRF headers."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_get_chat_page_passes_without_csrf(self, client: TestClient) -> None:
        """GET / (chat page) should not require CSRF headers."""
        response = client.get("/")
        assert response.status_code == 200

    def test_options_request_passes_without_csrf(self, client: TestClient) -> None:
        """OPTIONS requests should not require CSRF headers."""
        response = client.options("/chat")
        # CORS middleware handles OPTIONS -- should not be 403
        assert response.status_code != 403


# =============================================================================
# Exempt Path Tests
# =============================================================================


class TestExemptPaths:
    """Health check and static file paths should be exempt from CSRF."""

    def test_health_endpoint_exempt(self, client: TestClient) -> None:
        """GET /health should be exempt from CSRF (it's GET, so always exempt)."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("healthy", "degraded", "unhealthy")


# =============================================================================
# Integration: HTMX-style Requests
# =============================================================================


class TestHTMXIntegration:
    """Verify that realistic HTMX request patterns pass CSRF validation."""

    def test_htmx_form_post_passes(self, client: TestClient) -> None:
        """HTMX form submission with HX-Request header should work."""
        response = client.post(
            "/chat",
            data={"message": "Buenos dias", "level": "A1"},
            headers={
                "HX-Request": "true",
                "HX-Target": "chat-container",
                "HX-Trigger": "chat-form",
            },
        )
        assert response.status_code != 403

    def test_fetch_api_post_passes(self, client: TestClient) -> None:
        """JavaScript fetch() POST with X-Requested-With should work."""
        response = client.post(
            "/chat/stream",
            data={"message": "Hola", "level": "A1"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code != 403

    def test_voice_speak_with_xhr_header_passes(self, client: TestClient) -> None:
        """POST /api/speak with X-Requested-With should pass CSRF."""
        response = client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "aura-2-nestor-es"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        # Will likely return 503 (Deepgram not configured) but NOT 403
        assert response.status_code != 403
