"""Pytest configuration and fixtures for Habla Hermano tests."""

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from src.api.config import Settings, get_settings
from src.api.dependencies import get_cached_templates


@pytest.fixture
def sample_message() -> str:
    """Sample user message for testing."""
    return "Hola, me llamo Juan"


@pytest.fixture
def sample_ai_response() -> str:
    """Sample AI response for testing."""
    return "Hola Juan! Mucho gusto. Como estas hoy?"


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
def app_with_mocked_graph(mock_compiled_graph: MagicMock) -> Generator[FastAPI, None, None]:
    """Create FastAPI app with mocked LangGraph agent.

    Args:
        mock_compiled_graph: Mock graph to use instead of real agent.

    Yields:
        FastAPI: Application instance with mocked dependencies.
    """
    with patch("src.api.routes.chat.compiled_graph", mock_compiled_graph):
        # Clear caches to ensure fresh app creation
        get_settings.cache_clear()
        get_cached_templates.cache_clear()

        # Import inside patch context to ensure mock is applied
        # This late import is intentional for proper mocking
        from src.api.main import app

        yield app


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
        for key in ["ANTHROPIC_API_KEY", "DEBUG", "APP_NAME", "LLM_MODEL", "PORT", "HOST"]
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
