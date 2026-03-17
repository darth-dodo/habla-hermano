"""Tests for thread management API endpoints (src/api/routes/threads.py).

Validates CRUD operations for conversation threads with authentication,
CSRF compliance, and proper error handling.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.db.models import ConversationThread
from tests.conftest import CSRF_HEADERS

# =============================================================================
# Fixtures
# =============================================================================

_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

_SAMPLE_THREAD = ConversationThread(
    id="row-1",
    user_id="test-user-123",
    thread_id="user:test-user-123:abc-def",
    title="New conversation",
    language="es",
    level="A1",
    created_at=_NOW,
    updated_at=_NOW,
)


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    return AuthenticatedUser(id="test-user-123", email="test@example.com")


@pytest.fixture
def mock_thread_service() -> MagicMock:
    """Pre-configured mock ThreadService."""
    svc = MagicMock()
    svc.list_threads.return_value = []
    svc.create_thread.return_value = _SAMPLE_THREAD
    svc.get_thread.return_value = _SAMPLE_THREAD
    svc.update_title.return_value = None
    svc.delete_thread.return_value = None
    return svc


@pytest.fixture
def app(mock_user: AuthenticatedUser, mock_thread_service: MagicMock) -> FastAPI:
    """Create a FastAPI app with mocked auth and ThreadService."""

    async def override_auth():
        return mock_user

    with patch(
        "src.api.routes.threads._get_thread_service",
        return_value=mock_thread_service,
    ):
        from src.api.main import create_app

        application = create_app()
        application.dependency_overrides[get_current_user] = override_auth
        yield application
        application.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app, headers=CSRF_HEADERS) as c:
        yield c


@pytest.fixture
def unauthed_app() -> FastAPI:
    """Create a FastAPI app WITHOUT auth override (unauthenticated)."""
    from src.api.main import create_app

    return create_app()


@pytest.fixture
def unauthed_client(unauthed_app: FastAPI) -> TestClient:
    with TestClient(unauthed_app) as c:
        yield c


# =============================================================================
# Authentication Tests
# =============================================================================


class TestThreadAuth:
    """Unauthenticated requests should be rejected."""

    def test_list_threads_unauthenticated(self, unauthed_client: TestClient) -> None:
        """GET /threads/ without auth returns 401."""
        resp = unauthed_client.get("/threads/")
        assert resp.status_code == 401


# =============================================================================
# List Threads
# =============================================================================


class TestListThreads:
    """GET /threads/ endpoint."""

    def test_list_threads_empty(self, client: TestClient, mock_thread_service: MagicMock) -> None:
        """Returns empty list when user has no threads."""
        mock_thread_service.list_threads.return_value = []
        resp = client.get("/threads/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_threads_with_data(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """Returns serialised thread list."""
        mock_thread_service.list_threads.return_value = [_SAMPLE_THREAD]
        resp = client.get("/threads/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["thread_id"] == "user:test-user-123:abc-def"
        assert data[0]["title"] == "New conversation"
        assert data[0]["language"] == "es"
        assert data[0]["level"] == "A1"
        assert "created_at" in data[0]
        assert "updated_at" in data[0]


# =============================================================================
# Create Thread
# =============================================================================


class TestCreateThread:
    """POST /threads/ endpoint."""

    def test_create_thread(self, client: TestClient, mock_thread_service: MagicMock) -> None:
        """Creates thread with default language/level and returns 201."""
        resp = client.post("/threads/", data={})
        assert resp.status_code == 201
        body = resp.json()
        assert body["thread_id"] == _SAMPLE_THREAD.thread_id
        assert body["language"] == "es"
        assert body["level"] == "A1"
        mock_thread_service.create_thread.assert_called_once_with(language="es", level="A1")

    def test_create_thread_with_language(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """Respects explicit language and level params."""
        de_thread = ConversationThread(
            id="row-2",
            user_id="test-user-123",
            thread_id="user:test-user-123:xyz",
            title="New conversation",
            language="de",
            level="A2",
            created_at=_NOW,
            updated_at=_NOW,
        )
        mock_thread_service.create_thread.return_value = de_thread
        resp = client.post("/threads/", data={"language": "de", "level": "A2"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["language"] == "de"
        assert body["level"] == "A2"
        mock_thread_service.create_thread.assert_called_with(language="de", level="A2")


# =============================================================================
# Rename Thread
# =============================================================================


class TestRenameThread:
    """PATCH /threads/{thread_id} endpoint."""

    def test_rename_thread(self, client: TestClient, mock_thread_service: MagicMock) -> None:
        """Renames thread and returns updated title."""
        resp = client.patch(
            f"/threads/{_SAMPLE_THREAD.thread_id}",
            data={"title": "My Spanish Chat"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "My Spanish Chat"
        assert body["thread_id"] == _SAMPLE_THREAD.thread_id
        mock_thread_service.get_thread.assert_called_once_with(_SAMPLE_THREAD.thread_id)
        mock_thread_service.update_title.assert_called_once()

    def test_rename_thread_not_found(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """Returns 404 when thread does not exist."""
        mock_thread_service.get_thread.return_value = None
        resp = client.patch(
            "/threads/nonexistent-thread",
            data={"title": "New Title"},
        )
        assert resp.status_code == 404


# =============================================================================
# Delete Thread
# =============================================================================


class TestDeleteThread:
    """DELETE /threads/{thread_id} endpoint."""

    def test_delete_thread(self, client: TestClient, mock_thread_service: MagicMock) -> None:
        """Deletes thread and returns 204."""
        resp = client.delete(f"/threads/{_SAMPLE_THREAD.thread_id}")
        assert resp.status_code == 204
        assert resp.content == b""
        mock_thread_service.delete_thread.assert_called_once_with(_SAMPLE_THREAD.thread_id)

    def test_delete_thread_idempotent(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """Deleting a nonexistent thread still returns 204 (idempotent)."""
        # delete_thread doesn't raise when thread doesn't exist
        resp = client.delete("/threads/nonexistent-thread")
        assert resp.status_code == 204


# =============================================================================
# M7 — language/level validation
# =============================================================================


class TestCreateThreadValidation:
    """POST /threads/ validates language and level against allowed sets."""

    def test_create_thread_rejects_invalid_language(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """POST /threads/ with invalid language returns 422."""
        resp = client.post("/threads/", data={"language": "xx", "level": "A1"})
        assert resp.status_code == 422

    def test_create_thread_rejects_invalid_level(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """POST /threads/ with invalid level returns 422."""
        resp = client.post("/threads/", data={"language": "es", "level": "Z9"})
        assert resp.status_code == 422

    def test_create_thread_accepts_valid_language_and_level(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """POST /threads/ with valid params returns 201."""
        resp = client.post("/threads/", data={"language": "es", "level": "A1"})
        assert resp.status_code == 201

    def test_create_thread_rejects_sql_injection_language(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """POST /threads/ rejects SQL injection attempt in language."""
        resp = client.post("/threads/", data={"language": "'; DROP TABLE--", "level": "A1"})
        assert resp.status_code == 422

    def test_create_thread_rejects_long_language(
        self, client: TestClient, mock_thread_service: MagicMock
    ) -> None:
        """POST /threads/ rejects excessively long language string."""
        resp = client.post("/threads/", data={"language": "x" * 1000, "level": "A1"})
        assert resp.status_code == 422


# =============================================================================
# M3 — Bearer token support
# =============================================================================


class TestBearerTokenSupport:
    """Thread endpoints should accept Authorization: Bearer token when no cookie is set."""

    def test_list_threads_with_bearer_token(
        self, mock_user: AuthenticatedUser, mock_thread_service: MagicMock
    ) -> None:
        """GET /threads/ with Bearer token (no cookie) should return 200, not 401."""
        mock_supabase_client = MagicMock()

        async def override_auth():
            return mock_user

        with patch(
            "src.api.routes.threads.get_supabase_for_user",
            return_value=mock_supabase_client,
        ):
            with patch(
                "src.api.routes.threads.ThreadService",
                return_value=mock_thread_service,
            ):
                from src.api.main import create_app

                application = create_app()
                application.dependency_overrides[get_current_user] = override_auth
                try:
                    with TestClient(
                        application,
                        headers={**CSRF_HEADERS, "Authorization": "Bearer test-token"},
                    ) as c:
                        resp = c.get("/threads/")
                        assert resp.status_code == 200
                finally:
                    application.dependency_overrides.pop(get_current_user, None)

    def test_list_threads_no_token_returns_401(self, mock_user: AuthenticatedUser) -> None:
        """GET /threads/ with no token (cookie or Bearer) returns 401."""

        async def override_auth():
            return mock_user

        with patch(
            "src.api.routes.threads.get_supabase_for_user",
            return_value=None,
        ):
            from src.api.main import create_app

            application = create_app()
            application.dependency_overrides[get_current_user] = override_auth
            try:
                with TestClient(application, headers=CSRF_HEADERS) as c:
                    resp = c.get("/threads/")
                    assert resp.status_code == 401
            finally:
                application.dependency_overrides.pop(get_current_user, None)
