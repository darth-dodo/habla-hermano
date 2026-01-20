"""Pytest configuration and fixtures for Habla Hermano tests."""

import os
import time
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
from src.api.config import Settings, get_settings
from src.api.dependencies import get_cached_templates

# =============================================================================
# User and Authentication Fixtures
# =============================================================================


@pytest.fixture
def sample_message() -> str:
    """Sample user message for testing."""
    return "Hola, me llamo Juan"


@pytest.fixture
def sample_ai_response() -> str:
    """Sample AI response for testing."""
    return "Hola Juan! Mucho gusto. Como estas hoy?"


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create a mock authenticated user for testing.

    Returns:
        AuthenticatedUser: Test user instance.
    """
    return AuthenticatedUser(
        id="test-user-123",
        email="test@example.com",
    )


@pytest.fixture
def auth_token(mock_user: AuthenticatedUser) -> str:
    """Create a valid JWT token for authenticated requests.

    Args:
        mock_user: The mock user to create a token for.

    Returns:
        str: JWT token string.
    """
    payload = {
        "sub": mock_user.id,
        "email": mock_user.email,
        "exp": int(time.time()) + 3600,  # 1 hour from now
        "aud": "authenticated",
        "role": "authenticated",
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Create authorization headers with a valid token.

    Args:
        auth_token: JWT token to include.

    Returns:
        dict: Headers with Authorization bearer token.
    """
    return {"Authorization": f"Bearer {auth_token}"}


# =============================================================================
# Supabase Client Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Create a mock Supabase client for testing.

    Returns:
        MagicMock: Mock Supabase client with common methods stubbed.
    """
    mock_client = MagicMock()

    # Mock auth module
    mock_client.auth = MagicMock()
    mock_client.auth.get_user = MagicMock(return_value=MagicMock(user=None))
    mock_client.auth.sign_in_with_password = AsyncMock()
    mock_client.auth.sign_up = AsyncMock()
    mock_client.auth.sign_out = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_table.select = MagicMock(return_value=mock_table)
    mock_table.insert = MagicMock(return_value=mock_table)
    mock_table.update = MagicMock(return_value=mock_table)
    mock_table.delete = MagicMock(return_value=mock_table)
    mock_table.eq = MagicMock(return_value=mock_table)
    mock_table.single = MagicMock(return_value=mock_table)
    mock_table.execute = MagicMock(return_value=MagicMock(data=[], count=0))
    mock_client.table = MagicMock(return_value=mock_table)

    # Mock storage module
    mock_storage = MagicMock()
    mock_client.storage = mock_storage

    return mock_client


@pytest.fixture
def mock_supabase(mock_supabase_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Patch the Supabase client globally for testing.

    Args:
        mock_supabase_client: The mock client to use.

    Yields:
        MagicMock: The patched mock client.
    """
    with patch("src.api.supabase_client.get_supabase", return_value=mock_supabase_client):
        yield mock_supabase_client


# =============================================================================
# Settings Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings with test values.

    Returns:
        Settings: Test settings instance with ANTHROPIC_API_KEY set.
    """
    # Use _env_file=None to prevent loading from .env
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ANTHROPIC_API_KEY="test-api-key-12345",  # pragma: allowlist secret
        APP_NAME="Habla Hermano-Test",
        DEBUG=True,
        LLM_MODEL="claude-test-model",
        LLM_TEMPERATURE=0.5,
        HOST="127.0.0.1",
        PORT=8000,
    )


@pytest.fixture
def env_vars() -> dict[str, str]:
    """Return environment variables for testing.

    Returns:
        dict: Environment variable key-value pairs.
    """
    return {
        "ANTHROPIC_API_KEY": "test-anthropic-api-key",  # pragma: allowlist secret
        "APP_NAME": "TestApp",
        "DEBUG": "true",
        "LLM_MODEL": "claude-test",
        "LLM_TEMPERATURE": "0.5",
        "HOST": "0.0.0.0",
        "PORT": "9000",
    }


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Fixture to run tests with a clean environment (no .env file interference).

    This clears relevant environment variables to test default behavior.
    """
    # Save original environment
    original_env = {
        key: os.environ.get(key)
        for key in [
            "ANTHROPIC_API_KEY",
            "DEBUG",
            "APP_NAME",
            "LLM_MODEL",
            "PORT",
            "HOST",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_DB_URL",
        ]
    }

    # Clear the environment variables
    for key in original_env:
        if key in os.environ:
            del os.environ[key]

    get_settings.cache_clear()
    get_cached_templates.cache_clear()

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]

    get_settings.cache_clear()
    get_cached_templates.cache_clear()


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Reset settings cache before and after each test.

    This ensures each test starts with fresh settings.
    """
    get_settings.cache_clear()
    get_cached_templates.cache_clear()
    yield
    get_settings.cache_clear()
    get_cached_templates.cache_clear()


# =============================================================================
# LangGraph Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_graph_result(sample_ai_response: str) -> dict[str, Any]:
    """Create mock LangGraph result structure.

    Args:
        sample_ai_response: AI response text to include in the result.

    Returns:
        dict: Mock graph result with messages list.
    """
    return {
        "messages": [
            HumanMessage(content="Hola, me llamo Juan"),
            AIMessage(content=sample_ai_response),
        ],
        "level": "A1",
        "language": "es",
    }


@pytest.fixture
def mock_compiled_graph(mock_graph_result: dict[str, Any]) -> MagicMock:
    """Create mock compiled graph with ainvoke method.

    Args:
        mock_graph_result: Result to return from ainvoke.

    Returns:
        MagicMock: Mock graph with async ainvoke method.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_graph_result)
    return mock_graph


@pytest.fixture
def mock_checkpointer() -> MagicMock:
    """Create mock checkpointer for testing.

    Returns:
        MagicMock: Mock checkpointer that does nothing.
    """
    return MagicMock()


# =============================================================================
# FastAPI App Fixtures
# =============================================================================


@pytest.fixture
def app_with_mocked_graph(
    mock_compiled_graph: MagicMock,
    mock_checkpointer: MagicMock,
    mock_user: AuthenticatedUser,
) -> Generator[FastAPI, None, None]:
    """Create FastAPI app with mocked LangGraph agent, checkpointer, and auth.

    Phase 5: Added authentication mocking for protected routes.
    Phase 4: Updated to mock build_graph and get_checkpointer instead of
    the removed compiled_graph global.

    Args:
        mock_compiled_graph: Mock graph to use instead of real agent.
        mock_checkpointer: Mock checkpointer for persistence.
        mock_user: Mock authenticated user for auth.

    Yields:
        FastAPI: Application instance with mocked dependencies.
    """

    # Create an async context manager class for get_checkpointer
    class MockCheckpointerContext:
        """Async context manager that yields mock checkpointer."""

        async def __aenter__(self):
            return mock_checkpointer

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    def mock_get_checkpointer():
        """Return async context manager for checkpointer."""
        return MockCheckpointerContext()

    # Mock build_graph to return our mock compiled graph
    def mock_build_graph(checkpointer=None):
        """Return mock graph regardless of checkpointer."""
        return mock_compiled_graph

    # Mock auth dependencies
    async def mock_get_current_user():
        """Return mock user for authenticated routes."""
        return mock_user

    async def mock_get_current_user_optional():
        """Return mock user for optional auth routes."""
        return mock_user

    with (
        patch("src.api.routes.chat.build_graph", mock_build_graph),
        patch("src.api.routes.chat.get_checkpointer", mock_get_checkpointer),
    ):
        # Clear caches to ensure fresh app creation
        get_settings.cache_clear()
        get_cached_templates.cache_clear()

        # Import inside patch context to ensure mock is applied
        # This late import is intentional for proper mocking
        from src.api.main import app

        # Override auth dependencies
        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_current_user_optional] = mock_get_current_user_optional

        yield app

        # Clean up dependency overrides
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def test_client(app_with_mocked_graph: FastAPI) -> Generator[TestClient, None, None]:
    """Create synchronous test client for FastAPI app.

    Args:
        app_with_mocked_graph: FastAPI app with mocked dependencies.

    Yields:
        TestClient: Synchronous test client for route testing.
    """
    with TestClient(app_with_mocked_graph) as client:
        yield client


@pytest.fixture
async def async_client(
    app_with_mocked_graph: FastAPI,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for FastAPI app.

    Args:
        app_with_mocked_graph: FastAPI app with mocked dependencies.

    Yields:
        AsyncClient: Async HTTP client for route testing.
    """
    transport = ASGITransport(app=app_with_mocked_graph)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def levels() -> list[str]:
    """Return list of valid CEFR levels.

    Returns:
        list[str]: Valid levels (A0, A1, A2, B1).
    """
    return ["A0", "A1", "A2", "B1"]


@pytest.fixture
def languages() -> list[str]:
    """Return list of supported languages.

    Returns:
        list[str]: Supported language codes.
    """
    return ["es", "de"]
