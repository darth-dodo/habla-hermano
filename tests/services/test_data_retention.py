"""Tests for data retention service.

Verifies conversation purging logic with mocked Supabase client.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.services.data_retention import purge_old_conversations


def _make_mock_supabase() -> MagicMock:
    """Create a mock Supabase client with chained PostgREST methods."""
    mock_client = MagicMock()
    mock_table = MagicMock()

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
        "order",
        "limit",
        "range",
        "single",
    ):
        setattr(mock_table, method, MagicMock(return_value=mock_table))

    mock_execute_result = MagicMock(data=[])
    mock_table.execute = MagicMock(return_value=mock_execute_result)
    type(mock_table).not_ = PropertyMock(return_value=mock_table)
    mock_client.table = MagicMock(return_value=mock_table)

    return mock_client


class TestPurgeOldConversations:
    """Tests for purge_old_conversations function."""

    @pytest.mark.asyncio
    async def test_returns_zeros_when_disabled(self) -> None:
        """When retention_days=0, no deletion occurs and zeros are returned."""
        result = await purge_old_conversations(retention_days=0)

        assert result == {"learning_sessions": 0, "vocabulary": 0}

    @pytest.mark.asyncio
    async def test_returns_zeros_when_negative(self) -> None:
        """Negative retention_days is treated as disabled."""
        result = await purge_old_conversations(retention_days=-1)

        assert result == {"learning_sessions": 0, "vocabulary": 0}

    @pytest.mark.asyncio
    async def test_defaults_to_settings_value(self) -> None:
        """When retention_days is None, uses CONVERSATION_RETENTION_DAYS from settings."""
        from src.config import Settings

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            OPENROUTER_API_KEY="test-key",  # pragma: allowlist secret
            SECRET_KEY="test-secret",  # pragma: allowlist secret
            CONVERSATION_RETENTION_DAYS=0,
        )
        with patch("src.services.data_retention.get_settings", return_value=settings):
            result = await purge_old_conversations(retention_days=None)

        assert result == {"learning_sessions": 0, "vocabulary": 0}

    @pytest.mark.asyncio
    async def test_calls_supabase_delete_when_enabled(self) -> None:
        """When retention_days > 0, Supabase delete operations are called."""
        mock_client = _make_mock_supabase()

        # Simulate some deleted rows
        mock_table = mock_client.table.return_value
        sessions_result = MagicMock(data=[{"id": "1"}, {"id": "2"}])
        vocab_result = MagicMock(data=[{"id": "3"}])
        mock_table.execute = MagicMock(side_effect=[sessions_result, vocab_result])

        with patch("src.services.data_retention.get_supabase", return_value=mock_client):
            result = await purge_old_conversations(retention_days=30)

        assert result == {"learning_sessions": 2, "vocabulary": 1}

        # Verify table was called for both tables
        table_calls = [call.args[0] for call in mock_client.table.call_args_list]
        assert "learning_sessions" in table_calls
        assert "vocabulary" in table_calls

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self) -> None:
        """When Supabase raises an error, returns zeros and logs warning."""
        with patch(
            "src.services.data_retention.get_supabase",
            side_effect=ValueError("Supabase not configured"),
        ):
            result = await purge_old_conversations(retention_days=30)

        assert result == {"learning_sessions": 0, "vocabulary": 0}

    @pytest.mark.asyncio
    async def test_handles_none_data_in_response(self) -> None:
        """When Supabase returns data=None, counts as zero."""
        mock_client = _make_mock_supabase()
        mock_table = mock_client.table.return_value
        mock_table.execute = MagicMock(return_value=MagicMock(data=None))

        with patch("src.services.data_retention.get_supabase", return_value=mock_client):
            result = await purge_old_conversations(retention_days=7)

        assert result == {"learning_sessions": 0, "vocabulary": 0}
