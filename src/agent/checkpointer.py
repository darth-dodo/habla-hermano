"""
LangGraph checkpointer for conversation persistence.

Phase 4: Provides checkpointing for conversation memory.
- Uses AsyncPostgresSaver with Supabase Postgres for persistent storage
- Falls back to MemorySaver when Supabase is not configured

The checkpointer enables conversation history to be saved and resumed
across sessions using a thread_id tied to the user.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.api.config import get_settings

# Database path for checkpoints (legacy, kept for compatibility)
# Located in data/ directory alongside other persistent storage
CHECKPOINT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "checkpoints.db"

# Type alias for checkpointer return type
CheckpointerType = AsyncPostgresSaver | MemorySaver

# Module-level state for MemorySaver singleton
# Using a dict to avoid global statement (PLW0603)
_state: dict[str, MemorySaver | None] = {"memory_saver": None}


def _get_memory_saver() -> MemorySaver:
    """Get or create the global MemorySaver instance."""
    if _state["memory_saver"] is None:
        _state["memory_saver"] = MemorySaver()
    # Type is guaranteed non-None after the check above
    return cast("MemorySaver", _state["memory_saver"])


def get_user_thread_id(user_id: str) -> str:
    """
    Generate a thread ID from user ID.

    User ID is the thread ID (single conversation per user).
    This ensures each user has a persistent conversation thread
    that can be resumed across sessions.

    Args:
        user_id: The unique user identifier (e.g., from Supabase auth).

    Returns:
        Thread ID string in format "user:{user_id}".

    Example:
        thread_id = get_user_thread_id("abc123")
        # Returns: "user:abc123"
    """
    return f"user:{user_id}"


@asynccontextmanager
async def get_postgres_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """
    Get PostgreSQL checkpointer for LangGraph persistence with Supabase.

    Uses AsyncPostgresSaver.from_conn_string() which handles connection
    management and schema setup properly (including CREATE INDEX CONCURRENTLY
    which requires autocommit mode).

    Yields:
        AsyncPostgresSaver: Configured checkpointer for graph compilation.

    Raises:
        ValueError: If SUPABASE_DB_URL is not configured.
        Exception: If database connection fails.

    Example:
        async with get_postgres_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": "user:abc123"}}
            )
    """
    settings = get_settings()

    if not settings.SUPABASE_DB_URL:
        raise ValueError("SUPABASE_DB_URL is not configured")

    # Use from_conn_string which handles connection pool and setup properly
    async with AsyncPostgresSaver.from_conn_string(settings.SUPABASE_DB_URL) as checkpointer:
        # Setup creates the checkpoint tables if they don't exist
        # from_conn_string handles autocommit mode for CREATE INDEX CONCURRENTLY
        await checkpointer.setup()
        yield checkpointer


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[BaseCheckpointSaver[Any], None]:
    """
    Get checkpointer for LangGraph persistence.

    Automatically selects the appropriate checkpointer based on configuration:
    - AsyncPostgresSaver when SUPABASE_DB_URL is configured (persistent across restarts)
    - MemorySaver as fallback (in-memory, lost on restart)

    Yields:
        BaseCheckpointSaver: Configured checkpointer for graph compilation.

    Example:
        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": "user-123"}}
            )
    """
    settings = get_settings()

    # Only use Postgres if DB URL looks like a real connection string
    # (not a placeholder with [PROJECT-REF] or [YOUR-PASSWORD])
    db_url = settings.SUPABASE_DB_URL
    is_valid_db_url = (
        db_url
        and "[" not in db_url  # No placeholder brackets
        and db_url.startswith("postgresql://")
    )

    if is_valid_db_url:
        # Use Postgres checkpointer with Supabase
        async with get_postgres_checkpointer() as checkpointer:
            yield checkpointer
    else:
        # Fall back to MemorySaver for local development or when DB URL not set
        yield _get_memory_saver()


def get_checkpoint_db_path() -> Path:
    """
    Get the path to the checkpoint database file.

    Note: This is kept for backward compatibility. When Supabase is
    configured, checkpoints are stored in Postgres instead.

    Returns:
        Path: Absolute path to checkpoints.db file.
    """
    return CHECKPOINT_DB_PATH


def clear_memory_saver() -> None:
    """
    Clear the global MemorySaver instance.

    Useful for testing or when you need to reset all conversations.
    Note: This only affects the in-memory fallback, not Postgres storage.
    """
    _state["memory_saver"] = None
