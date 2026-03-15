"""Tests for thread message history extraction.

Verifies that get_thread_messages correctly extracts messages from
LangGraph checkpoint state with proper role mapping and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.services.thread_messages import get_thread_messages

THREAD_ID = "user:test-abc:thread-1"


@pytest.fixture
def mock_state_empty():
    """State snapshot with no messages."""
    state = MagicMock()
    state.values = {}
    return state


@pytest.fixture
def mock_state_with_messages():
    """State snapshot containing a typical conversation."""
    state = MagicMock()
    state.values = {
        "messages": [
            HumanMessage(content="Hola"),
            AIMessage(content="¡Hola! ¿Cómo estás?"),
            HumanMessage(content="Bien, gracias"),
            AIMessage(content="¡Qué bueno!"),
        ]
    }
    return state


@pytest.fixture
def mock_state_with_system_messages():
    """State snapshot that includes system messages alongside user messages."""
    state = MagicMock()
    state.values = {
        "messages": [
            SystemMessage(content="You are a Spanish tutor."),
            HumanMessage(content="Hola"),
            AIMessage(content="¡Hola!"),
            SystemMessage(content="Remember to scaffold."),
            HumanMessage(content="Adiós"),
            AIMessage(content="¡Hasta luego!"),
        ]
    }
    return state


def _patch_graph_and_checkpointer(mock_state):
    """Return a stack of patches for get_checkpointer and build_graph.

    The mock graph's aget_state returns the provided mock_state.
    """
    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=mock_state)

    mock_checkpointer = MagicMock()

    # get_checkpointer is an async context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    patches = (
        patch(
            "src.services.thread_messages.get_checkpointer",
            return_value=mock_cm,
        ),
        patch(
            "src.services.thread_messages.build_graph",
            return_value=mock_graph,
        ),
    )
    return patches, mock_graph


@pytest.mark.asyncio
async def test_get_messages_empty_thread(mock_state_empty):
    """Returns empty list when checkpoint has no messages."""
    patches, _ = _patch_graph_and_checkpointer(mock_state_empty)
    with patches[0], patches[1]:
        result = await get_thread_messages(THREAD_ID)

    assert result == []


@pytest.mark.asyncio
async def test_get_messages_no_state():
    """Returns empty list when aget_state returns None."""
    patches, _ = _patch_graph_and_checkpointer(None)
    with patches[0], patches[1]:
        result = await get_thread_messages(THREAD_ID)

    assert result == []


@pytest.mark.asyncio
async def test_get_messages_with_history(mock_state_with_messages):
    """Returns messages in order with correct roles."""
    patches, mock_graph = _patch_graph_and_checkpointer(mock_state_with_messages)
    with patches[0], patches[1]:
        result = await get_thread_messages(THREAD_ID)

    assert len(result) == 4
    assert result[0] == {"role": "human", "content": "Hola"}
    assert result[1] == {"role": "ai", "content": "¡Hola! ¿Cómo estás?"}
    assert result[2] == {"role": "human", "content": "Bien, gracias"}
    assert result[3] == {"role": "ai", "content": "¡Qué bueno!"}

    # Verify aget_state was called with the right thread_id
    call_args = mock_graph.aget_state.call_args
    config = call_args[0][0]
    assert config.get("configurable", {}).get("thread_id") == THREAD_ID


@pytest.mark.asyncio
async def test_get_messages_filters_system_messages(mock_state_with_system_messages):
    """System messages are excluded from the result."""
    patches, _ = _patch_graph_and_checkpointer(mock_state_with_system_messages)
    with patches[0], patches[1]:
        result = await get_thread_messages(THREAD_ID)

    assert len(result) == 4
    roles = [m["role"] for m in result]
    assert "system" not in roles
    assert roles == ["human", "ai", "human", "ai"]
    assert result[0]["content"] == "Hola"
    assert result[3]["content"] == "¡Hasta luego!"


@pytest.mark.asyncio
async def test_get_messages_handles_error():
    """Returns empty list and logs when an exception occurs."""
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("DB connection failed"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "src.services.thread_messages.get_checkpointer",
        return_value=mock_cm,
    ):
        result = await get_thread_messages(THREAD_ID)

    assert result == []
