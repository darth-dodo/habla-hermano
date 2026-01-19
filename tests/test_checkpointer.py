"""
Tests for src/agent/checkpointer.py - LangGraph persistence checkpointer.

This module tests the checkpointer functionality for conversation persistence:
- AsyncPostgresSaver with Supabase Postgres (when configured)
- MemorySaver as fallback (when Supabase not configured)
- Helper functions for thread ID generation
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


class TestGetCheckpointDbPath:
    """Tests for get_checkpoint_db_path function."""

    def test_returns_path_object(self) -> None:
        """get_checkpoint_db_path should return a Path object."""
        from src.agent.checkpointer import get_checkpoint_db_path

        result = get_checkpoint_db_path()
        assert isinstance(result, Path)

    def test_returns_absolute_path(self) -> None:
        """get_checkpoint_db_path should return an absolute path."""
        from src.agent.checkpointer import get_checkpoint_db_path

        result = get_checkpoint_db_path()
        assert result.is_absolute()

    def test_path_ends_with_checkpoints_db(self) -> None:
        """get_checkpoint_db_path should return path ending with checkpoints.db."""
        from src.agent.checkpointer import get_checkpoint_db_path

        result = get_checkpoint_db_path()
        assert result.name == "checkpoints.db"

    def test_path_parent_is_data_directory(self) -> None:
        """get_checkpoint_db_path should place database in data directory."""
        from src.agent.checkpointer import get_checkpoint_db_path

        result = get_checkpoint_db_path()
        assert result.parent.name == "data"

    def test_path_is_consistent_across_calls(self) -> None:
        """get_checkpoint_db_path should return same path on repeated calls."""
        from src.agent.checkpointer import get_checkpoint_db_path

        path1 = get_checkpoint_db_path()
        path2 = get_checkpoint_db_path()
        assert path1 == path2

    def test_module_constant_matches_function(self) -> None:
        """CHECKPOINT_DB_PATH constant should match get_checkpoint_db_path result."""
        from src.agent.checkpointer import CHECKPOINT_DB_PATH, get_checkpoint_db_path

        assert get_checkpoint_db_path() == CHECKPOINT_DB_PATH


class TestGetUserThreadId:
    """Tests for get_user_thread_id helper function."""

    def test_returns_string(self) -> None:
        """get_user_thread_id should return a string."""
        from src.agent.checkpointer import get_user_thread_id

        result = get_user_thread_id("abc123")
        assert isinstance(result, str)

    def test_formats_with_user_prefix(self) -> None:
        """get_user_thread_id should prefix with 'user:'."""
        from src.agent.checkpointer import get_user_thread_id

        result = get_user_thread_id("abc123")
        assert result == "user:abc123"

    def test_handles_uuid_format(self) -> None:
        """get_user_thread_id should handle UUID-style user IDs."""
        from src.agent.checkpointer import get_user_thread_id

        user_id = "550e8400-e29b-41d4-a716-446655440000"
        result = get_user_thread_id(user_id)
        assert result == f"user:{user_id}"

    def test_handles_empty_string(self) -> None:
        """get_user_thread_id should handle empty string."""
        from src.agent.checkpointer import get_user_thread_id

        result = get_user_thread_id("")
        assert result == "user:"

    def test_is_deterministic(self) -> None:
        """get_user_thread_id should return same result for same input."""
        from src.agent.checkpointer import get_user_thread_id

        result1 = get_user_thread_id("test-user")
        result2 = get_user_thread_id("test-user")
        assert result1 == result2


class TestGetCheckpointerContextManagerWithoutSupabase:
    """Tests for get_checkpointer when Supabase is not configured."""

    @pytest.fixture(autouse=True)
    def mock_settings_no_supabase(self) -> None:
        """Mock settings to simulate Supabase not being configured."""
        from src.api.config import Settings

        # Create a mock settings with supabase_configured = False
        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_DB_URL="",
        )
        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            yield

    @pytest.mark.asyncio
    async def test_returns_memory_saver_when_supabase_not_configured(self) -> None:
        """get_checkpointer should yield MemorySaver when Supabase is not configured."""
        from src.agent.checkpointer import clear_memory_saver, get_checkpointer

        clear_memory_saver()

        async with get_checkpointer() as checkpointer:
            assert isinstance(checkpointer, MemorySaver)

    @pytest.mark.asyncio
    async def test_context_manager_properly_exits(self) -> None:
        """get_checkpointer should properly exit the context."""
        from src.agent.checkpointer import get_checkpointer

        checkpointer_ref = None
        async with get_checkpointer() as checkpointer:
            checkpointer_ref = checkpointer
            # Checkpointer should be usable inside context
            assert checkpointer_ref is not None

        # After context exits, we should have exited cleanly
        # (no explicit check needed - if it raised, test would fail)

    @pytest.mark.asyncio
    async def test_multiple_context_managers_return_same_instance(self) -> None:
        """Multiple sequential get_checkpointer calls should return same MemorySaver instance."""
        from src.agent.checkpointer import clear_memory_saver, get_checkpointer

        # Clear to start fresh
        clear_memory_saver()

        async with get_checkpointer() as cp1:
            assert cp1 is not None

        async with get_checkpointer() as cp2:
            assert cp2 is not None
            # Should be the same global instance
            assert cp1 is cp2


class TestMemorySaverGlobal:
    """Tests for the global MemorySaver instance management."""

    @pytest.mark.asyncio
    async def test_get_memory_saver_creates_instance(self) -> None:
        """_get_memory_saver should create instance on first call."""
        from src.agent.checkpointer import _get_memory_saver, clear_memory_saver

        clear_memory_saver()
        saver = _get_memory_saver()
        assert isinstance(saver, MemorySaver)

    @pytest.mark.asyncio
    async def test_get_memory_saver_returns_same_instance(self) -> None:
        """_get_memory_saver should return same instance on repeated calls."""
        from src.agent.checkpointer import _get_memory_saver, clear_memory_saver

        clear_memory_saver()
        saver1 = _get_memory_saver()
        saver2 = _get_memory_saver()
        assert saver1 is saver2

    def test_clear_memory_saver_resets_instance(self) -> None:
        """clear_memory_saver should reset the global instance."""
        from src.agent.checkpointer import _get_memory_saver, clear_memory_saver

        # Get first instance
        saver1 = _get_memory_saver()
        # Clear it
        clear_memory_saver()
        # Get new instance
        saver2 = _get_memory_saver()
        # Should be different instances
        assert saver1 is not saver2


class TestCheckpointerIntegrationWithoutSupabase:
    """Integration tests for checkpointer without Supabase."""

    @pytest.fixture(autouse=True)
    def mock_settings_no_supabase(self) -> None:
        """Mock settings to simulate Supabase not being configured."""
        from src.api.config import Settings

        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_DB_URL="",
        )
        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            yield

    @pytest.mark.asyncio
    async def test_checkpointer_is_base_checkpoint_saver(self) -> None:
        """Checkpointer should be a valid BaseCheckpointSaver."""
        from src.agent.checkpointer import get_checkpointer

        async with get_checkpointer() as checkpointer:
            assert isinstance(checkpointer, BaseCheckpointSaver)

    @pytest.mark.asyncio
    async def test_checkpointer_can_be_used_with_graph(self) -> None:
        """Checkpointer should be compatible with LangGraph graph compilation."""
        from src.agent.checkpointer import get_checkpointer

        async with get_checkpointer() as checkpointer:
            # Checkpointer should have the methods LangGraph expects
            assert hasattr(checkpointer, "get")
            assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_checkpointer_persists_within_session(self) -> None:
        """Checkpointer should persist data within the same session."""
        from src.agent.checkpointer import clear_memory_saver, get_checkpointer

        clear_memory_saver()

        # Store something via first context
        async with get_checkpointer() as cp1:
            first_id = id(cp1)

        # Get it back via second context
        async with get_checkpointer() as cp2:
            second_id = id(cp2)
            # Same instance means same data
            assert first_id == second_id


class TestCheckpointerEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.fixture(autouse=True)
    def mock_settings_no_supabase(self) -> None:
        """Mock settings to simulate Supabase not being configured."""
        from src.api.config import Settings

        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_DB_URL="",
        )
        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            yield

    @pytest.mark.asyncio
    async def test_handles_nested_context_managers(self) -> None:
        """Nested get_checkpointer calls should return same instance."""
        from src.agent.checkpointer import clear_memory_saver, get_checkpointer

        clear_memory_saver()

        async with get_checkpointer() as outer:
            async with get_checkpointer() as inner:
                assert outer is not None
                assert inner is not None
                # They should be the same global instance
                assert outer is inner

    @pytest.mark.asyncio
    async def test_checkpointer_docstring_exists(self) -> None:
        """get_checkpointer should have proper documentation."""
        from src.agent.checkpointer import get_checkpointer

        assert get_checkpointer.__doc__ is not None
        assert "checkpointer" in get_checkpointer.__doc__.lower()

    def test_module_exports(self) -> None:
        """Module should export expected symbols."""
        from src.agent import checkpointer

        assert hasattr(checkpointer, "get_checkpointer")
        assert hasattr(checkpointer, "get_checkpoint_db_path")
        assert hasattr(checkpointer, "CHECKPOINT_DB_PATH")
        assert hasattr(checkpointer, "clear_memory_saver")
        assert hasattr(checkpointer, "get_user_thread_id")
        assert hasattr(checkpointer, "get_postgres_checkpointer")

    @pytest.mark.asyncio
    async def test_checkpointer_yields_inside_context(self) -> None:
        """get_checkpointer should properly yield checkpointer inside context."""
        from src.agent.checkpointer import get_checkpointer

        entered = False
        async with get_checkpointer() as checkpointer:
            entered = True
            assert checkpointer is not None
            assert isinstance(checkpointer, MemorySaver)

        assert entered


class TestDataDirectoryConstants:
    """Tests for data directory path constants."""

    def test_checkpoint_path_under_data(self) -> None:
        """CHECKPOINT_DB_PATH should be under a 'data' directory."""
        from src.agent.checkpointer import CHECKPOINT_DB_PATH

        # Path should have 'data' as parent directory name
        assert CHECKPOINT_DB_PATH.parent.name == "data"

    def test_checkpoint_path_is_db_file(self) -> None:
        """CHECKPOINT_DB_PATH should have .db extension."""
        from src.agent.checkpointer import CHECKPOINT_DB_PATH

        assert CHECKPOINT_DB_PATH.suffix == ".db"


class TestGetPostgresCheckpointer:
    """Tests for get_postgres_checkpointer function."""

    @pytest.mark.asyncio
    async def test_raises_when_supabase_not_configured(self) -> None:
        """get_postgres_checkpointer should raise ValueError when SUPABASE_DB_URL is empty."""
        from src.agent.checkpointer import get_postgres_checkpointer
        from src.api.config import Settings

        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_DB_URL="",
        )
        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            with pytest.raises(ValueError, match="SUPABASE_DB_URL is not configured"):
                async with get_postgres_checkpointer():
                    pass

    def test_postgres_checkpointer_docstring_exists(self) -> None:
        """get_postgres_checkpointer should have proper documentation."""
        from src.agent.checkpointer import get_postgres_checkpointer

        assert get_postgres_checkpointer.__doc__ is not None
        assert "PostgreSQL" in get_postgres_checkpointer.__doc__
        assert "Supabase" in get_postgres_checkpointer.__doc__


class TestCheckpointerSupabaseSelection:
    """Tests for checkpointer selection based on configuration."""

    @pytest.mark.asyncio
    async def test_selects_memory_saver_when_supabase_not_configured(self) -> None:
        """get_checkpointer should select MemorySaver when Supabase is not configured."""
        from src.agent.checkpointer import clear_memory_saver, get_checkpointer
        from src.api.config import Settings

        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_DB_URL="",
        )

        clear_memory_saver()

        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            async with get_checkpointer() as checkpointer:
                assert isinstance(checkpointer, MemorySaver)

    @pytest.mark.asyncio
    async def test_attempts_postgres_when_supabase_configured(self) -> None:
        """get_checkpointer should attempt PostgresSaver when Supabase is configured."""
        from src.agent.checkpointer import get_checkpointer
        from src.api.config import Settings

        # Mock settings with Supabase configured (but invalid URL to test selection)
        mock_settings = Settings(
            ANTHROPIC_API_KEY="test-key",
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-anon-key",
            SUPABASE_DB_URL="postgresql://user:pass@localhost:5432/test",
        )

        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            # Mock the postgres checkpointer to avoid actual connection
            with patch(
                "src.agent.checkpointer.get_postgres_checkpointer"
            ) as mock_postgres:
                from unittest.mock import AsyncMock

                mock_checkpointer = AsyncMock()
                mock_postgres.return_value.__aenter__ = AsyncMock(
                    return_value=mock_checkpointer
                )
                mock_postgres.return_value.__aexit__ = AsyncMock(return_value=None)

                async with get_checkpointer() as checkpointer:
                    # Should have called get_postgres_checkpointer
                    mock_postgres.assert_called_once()
                    assert checkpointer is mock_checkpointer
