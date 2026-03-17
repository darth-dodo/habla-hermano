"""Security tests for chat endpoints — C1: thread_id ownership verification.

Verifies that authenticated users cannot supply a thread_id belonging to
another user to /chat or /chat/stream (horizontal privilege escalation).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import AuthenticatedUser, get_current_user_optional
from src.api.dependencies import get_lesson_service
from src.db.models import ConversationThread
from tests.conftest import CSRF_HEADERS

# =============================================================================
# Helpers
# =============================================================================

_OWN_THREAD_ID = "user:test-user-123:own-uuid"
_OTHER_THREAD_ID = "user:other-user-999:stolen-uuid"


def _make_app(mock_user: AuthenticatedUser, mock_graph: MagicMock) -> FastAPI:
    """Create a minimal FastAPI app for chat security tests."""
    from src.api.main import create_app

    class _CheckpointerCtx:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *_):
            pass

    app = create_app()
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user

    mock_lesson_svc = MagicMock()
    mock_lesson_svc.get_lesson.return_value = None
    app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_svc

    return app


# =============================================================================
# C1 — /chat (POST) thread_id ownership
# =============================================================================


class TestChatThreadOwnership:
    """POST /chat must reject thread_ids that don't belong to the caller."""

    def _client(self, mock_user: AuthenticatedUser, mock_graph: MagicMock) -> TestClient:
        app = _make_app(mock_user, mock_graph)
        return TestClient(app, headers=CSRF_HEADERS)

    def test_rejects_unowned_thread_id(self) -> None:
        """POST /chat with another user's thread_id returns an error response."""
        mock_user = AuthenticatedUser(id="test-user-123", email="test@example.com")

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [MagicMock(content="¡Hola!")],
                "level": "A1",
                "language": "es",
                "grammar_feedback": [],
                "new_vocabulary": [],
                "pronunciation_tips": [],
                "scaffolding": {},
            }
        )
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))

        # ThreadService.get_thread returns None — simulating a foreign thread_id
        mock_thread_service = MagicMock()
        mock_thread_service.get_thread.return_value = None

        class _Ctx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *_):
                pass

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=_Ctx()),
            patch("src.api.routes.chat.ThreadService", return_value=mock_thread_service),
            patch("src.api.routes.chat.get_supabase_for_user", return_value=MagicMock()),
        ):
            client = self._client(mock_user, mock_graph)
            client.cookies.set("sb-access-token", "test-token")
            resp = client.post(
                "/chat",
                data={
                    "message": "Hola",
                    "level": "A1",
                    "language": "es",
                    "thread_id": _OTHER_THREAD_ID,
                },
            )

        # Should be an error, not a successful chat response
        assert "error" in resp.text.lower() or resp.status_code in (403, 404, 422), (
            f"Expected error for unowned thread_id, got {resp.status_code}: {resp.text[:200]}"
        )
        # The graph must NOT have been invoked
        mock_graph.ainvoke.assert_not_called()

    def test_accepts_own_thread_id(self) -> None:
        """POST /chat with the user's own thread_id succeeds."""
        mock_user = AuthenticatedUser(id="test-user-123", email="test@example.com")

        from datetime import UTC, datetime

        _now = datetime(2026, 3, 17, tzinfo=UTC)
        owned_thread = ConversationThread(
            id="row-1",
            user_id="test-user-123",
            thread_id=_OWN_THREAD_ID,
            title="My chat",
            language="es",
            level="A1",
            created_at=_now,
            updated_at=_now,
        )

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [MagicMock(content="¡Hola!")],
                "level": "A1",
                "language": "es",
                "grammar_feedback": [],
                "new_vocabulary": [],
                "pronunciation_tips": [],
                "scaffolding": {},
            }
        )
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))

        # ThreadService.get_thread returns the owned thread
        mock_thread_service = MagicMock()
        mock_thread_service.get_thread.return_value = owned_thread

        class _Ctx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *_):
                pass

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=_Ctx()),
            patch("src.api.routes.chat.ThreadService", return_value=mock_thread_service),
            patch("src.api.routes.chat.get_supabase_for_user", return_value=MagicMock()),
        ):
            client = self._client(mock_user, mock_graph)
            client.cookies.set("sb-access-token", "test-token")
            resp = client.post(
                "/chat",
                data={
                    "message": "Hola",
                    "level": "A1",
                    "language": "es",
                    "thread_id": _OWN_THREAD_ID,
                },
            )

        assert resp.status_code == 200
        mock_thread_service.get_thread.assert_called_once_with(_OWN_THREAD_ID)


# =============================================================================
# C1 — /chat/stream (POST) thread_id ownership
# =============================================================================


class TestStreamThreadOwnership:
    """POST /chat/stream must reject thread_ids that don't belong to the caller."""

    def test_stream_rejects_unowned_thread_id(self) -> None:
        """POST /chat/stream with another user's thread_id returns an error SSE event."""
        mock_user = AuthenticatedUser(id="test-user-123", email="test@example.com")

        mock_graph = MagicMock()

        async def _no_stream(*_, **__):
            return
            yield  # pragma: no cover

        mock_graph.astream = _no_stream
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))

        mock_thread_service = MagicMock()
        mock_thread_service.get_thread.return_value = None

        class _Ctx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *_):
                pass

        app = _make_app(mock_user, mock_graph)

        with (
            patch("src.api.routes.chat_stream.build_lesson_chat_graph", return_value=mock_graph),
            patch("src.api.routes.chat_stream.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat_stream.get_checkpointer", return_value=_Ctx()),
            patch("src.api.routes.chat_stream.ThreadService", return_value=mock_thread_service),
            patch("src.api.routes.chat_stream.get_supabase_for_user", return_value=MagicMock()),
        ):
            with TestClient(app, headers=CSRF_HEADERS) as client:
                client.cookies.set("sb-access-token", "test-token")
                resp = client.post(
                    "/chat/stream",
                    data={
                        "message": "Hola",
                        "level": "A1",
                        "language": "es",
                        "thread_id": _OTHER_THREAD_ID,
                    },
                )

        # SSE stream returns 200 but must contain an error event, not chat content
        assert resp.status_code == 200
        assert "error" in resp.text.lower(), (
            f"Expected error event in SSE stream, got: {resp.text[:300]}"
        )
