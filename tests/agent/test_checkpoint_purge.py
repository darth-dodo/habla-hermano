"""Tests for src/agent/checkpoint_purge.py - Checkpoint TTL purging.

Verifies that stale LangGraph checkpoints are purged correctly when a
Postgres saver is active, and that the function is a safe no-op when
running with MemorySaver or when purging is disabled.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPurgeMemorySaverMode:
    """Purge should be a no-op when no Postgres saver is active."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_memory_saver_active(self) -> None:
        """purge_old_checkpoints returns 0 when postgres_saver is None."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": None}):
            result = await purge_old_checkpoints(retention_days=30)

        assert result == 0

    @pytest.mark.asyncio
    async def test_logs_info_when_memory_saver_active(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should log an informational message when skipping purge."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": None}):
            with caplog.at_level(logging.INFO):
                await purge_old_checkpoints(retention_days=30)

        assert "MemorySaver mode" in caplog.text


class TestPurgeDisabled:
    """Purge should be a no-op when retention_days is 0."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_disabled(self) -> None:
        """purge_old_checkpoints returns 0 when retention_days=0."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        result = await purge_old_checkpoints(retention_days=0)

        assert result == 0

    @pytest.mark.asyncio
    async def test_logs_info_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log that purging is disabled."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        with caplog.at_level(logging.INFO):
            await purge_old_checkpoints(retention_days=0)

        assert "disabled" in caplog.text


class TestPurgeWithPostgresSaver:
    """Purge should execute SQL when a Postgres saver is active."""

    @pytest.mark.asyncio
    async def test_executes_delete_on_all_tables(self) -> None:
        """Should execute DELETE queries on all three checkpoint tables."""
        from src.agent.checkpoint_purge import _CHECKPOINT_TABLES, purge_old_checkpoints

        mock_result = MagicMock()
        mock_result.rowcount = 5

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            result = await purge_old_checkpoints(retention_days=30)

        assert result == 5 * len(_CHECKPOINT_TABLES)
        assert mock_conn.execute.call_count == len(_CHECKPOINT_TABLES)

        # Verify all three tables were targeted
        assert mock_conn.execute.call_count == len(_CHECKPOINT_TABLES)

    @pytest.mark.asyncio
    async def test_returns_total_deleted_rows(self) -> None:
        """Should return the sum of deleted rows across all tables."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        # Simulate different row counts per table
        row_counts = iter([10, 3, 7])

        def make_result() -> MagicMock:
            result = MagicMock()
            result.rowcount = next(row_counts)
            return result

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=lambda *_args, **_kwargs: make_result())
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            result = await purge_old_checkpoints(retention_days=7)

        assert result == 20

    @pytest.mark.asyncio
    async def test_uses_correct_retention_interval(self) -> None:
        """Should use the specified retention_days in the SQL interval."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            await purge_old_checkpoints(retention_days=14)

        # retention_days is now a parameterised value, not in the SQL string
        first_call = mock_conn.execute.call_args_list[0]
        params = first_call.args[1]
        assert params == ("14 days",)


class TestPurgeDefaultSettings:
    """Purge should use Settings.CHECKPOINT_RETENTION_DAYS as default."""

    @pytest.mark.asyncio
    async def test_default_retention_is_30_days(self) -> None:
        """Settings.CHECKPOINT_RETENTION_DAYS should default to 30."""
        from src.config import Settings

        settings = Settings(ANTHROPIC_API_KEY="test-key")
        assert settings.CHECKPOINT_RETENTION_DAYS == 30

    @pytest.mark.asyncio
    async def test_uses_settings_default_when_no_arg(self) -> None:
        """Should read retention_days from settings when not passed."""
        from src.agent.checkpoint_purge import purge_old_checkpoints
        from src.config import Settings

        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            CHECKPOINT_RETENTION_DAYS=15,
        )

        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with (
            patch(
                "src.agent.checkpoint_purge._state",
                {"postgres_saver": mock_saver},
            ),
            patch(
                "src.agent.checkpoint_purge.get_settings",
                return_value=mock_settings,
            ),
        ):
            await purge_old_checkpoints()

        first_call = mock_conn.execute.call_args_list[0]
        params = first_call.args[1]
        assert params == ("15 days",)


class TestPurgeErrorHandling:
    """Purge errors should be caught and logged, not raised."""

    @pytest.mark.asyncio
    async def test_catches_database_errors(self) -> None:
        """Should catch exceptions and return 0 without raising."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(side_effect=RuntimeError("connection failed"))

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            result = await purge_old_checkpoints(retention_days=30)

        assert result == 0

    @pytest.mark.asyncio
    async def test_logs_error_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log the exception details when purge fails."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(side_effect=RuntimeError("connection failed"))

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            with caplog.at_level(logging.ERROR):
                await purge_old_checkpoints(retention_days=30)

        assert "Checkpoint purge failed" in caplog.text

    @pytest.mark.asyncio
    async def test_handles_none_rowcount(self) -> None:
        """Should handle result.rowcount being None gracefully."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        mock_result = MagicMock()
        mock_result.rowcount = None

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)

        mock_saver = MagicMock()
        mock_saver.conn = mock_pool

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": mock_saver}):
            result = await purge_old_checkpoints(retention_days=30)

        assert result == 0


class TestCustomRetentionOverride:
    """Custom retention_days parameter should override settings default."""

    @pytest.mark.asyncio
    async def test_explicit_retention_overrides_settings(self) -> None:
        """Passing retention_days explicitly should bypass settings lookup."""
        from src.agent.checkpoint_purge import purge_old_checkpoints

        with patch("src.agent.checkpoint_purge._state", {"postgres_saver": None}):
            # Should not call get_settings() since we pass the arg
            with patch("src.agent.checkpoint_purge.get_settings") as mock_get_settings:
                await purge_old_checkpoints(retention_days=7)
                mock_get_settings.assert_not_called()
