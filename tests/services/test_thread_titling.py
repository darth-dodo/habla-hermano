"""Tests for the thread auto-titling service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.thread_titling import generate_thread_title


@pytest.mark.asyncio
async def test_generate_title_returns_string():
    """LLM returns a title string."""
    mock_result = MagicMock()
    mock_result.content = "Ordering at a restaurant"

    with patch("src.services.thread_titling.ChatAnthropic") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_result
        mock_llm_class.return_value = mock_llm

        title = await generate_thread_title("Hola", "¡Hola! ¿Cómo estás?")
        assert title == "Ordering at a restaurant"


@pytest.mark.asyncio
async def test_generate_title_truncates_long_input():
    """Input messages are truncated to 200 chars before sending to LLM."""
    mock_result = MagicMock()
    mock_result.content = "Long conversation topic"

    long_message = "x" * 500
    long_response = "y" * 500

    with patch("src.services.thread_titling.ChatAnthropic") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_result
        mock_llm_class.return_value = mock_llm

        title = await generate_thread_title(long_message, long_response)
        assert title == "Long conversation topic"

        # Verify the prompt was called with truncated input
        call_args = mock_llm.ainvoke.call_args[0][0]
        # The prompt should not contain the full 500-char strings
        assert "x" * 201 not in call_args
        assert "y" * 201 not in call_args


@pytest.mark.asyncio
async def test_generate_title_handles_error():
    """Returns 'New conversation' when LLM call fails."""
    with patch("src.services.thread_titling.ChatAnthropic") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = RuntimeError("API error")
        mock_llm_class.return_value = mock_llm

        title = await generate_thread_title("Hola", "¡Hola!")
        assert title == "New conversation"


@pytest.mark.asyncio
async def test_generate_title_strips_quotes():
    """Surrounding quotes are removed from LLM output."""
    mock_result = MagicMock()
    mock_result.content = '"Spanish greetings practice"'

    with patch("src.services.thread_titling.ChatAnthropic") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_result
        mock_llm_class.return_value = mock_llm

        title = await generate_thread_title("Hola", "¡Hola!")
        assert title == "Spanish greetings practice"


@pytest.mark.asyncio
async def test_generate_title_returns_default_on_empty():
    """Empty LLM response returns default title."""
    mock_result = MagicMock()
    mock_result.content = "   "

    with patch("src.services.thread_titling.ChatAnthropic") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_result
        mock_llm_class.return_value = mock_llm

        title = await generate_thread_title("Hola", "¡Hola!")
        assert title == "New conversation"
