"""
LangGraph checkpointer for conversation persistence.

Phase 4: Provides checkpointing for conversation memory.
- Uses AsyncPostgresSaver with Supabase Postgres for persistent storage
- Falls back to MemorySaver when Supabase is not configured

The checkpointer enables conversation history to be saved and resumed
across sessions using a thread_id tied to the user.

Dev mode (MemorySaver):
    The MemorySaver instance is cached at module level (singleton pattern)
    so it persists across requests within the same server process. Conversation
    context is maintained between HTTP requests but lost on server restart.

Production mode (AsyncPostgresSaver):
    A single AsyncPostgresSaver is created once at application startup via
    init_checkpointer() and reused for all requests. The connection pool
    and DDL setup happen exactly once, eliminating ~50-100ms overhead per
    request. The instance is closed during shutdown via close_checkpointer().
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config import get_settings

logger = logging.getLogger(__name__)

# Type alias for checkpointer return type
CheckpointerType = AsyncPostgresSaver | MemorySaver

# Module-level state for singletons
# Using a dict to avoid global statement (PLW0603)
_state: dict[str, Any] = {
    "memory_saver": None,
    "postgres_saver": None,
    # The context manager object returned by from_conn_string(), needed for
    # proper shutdown via __aexit__.
    "postgres_cm": None,
}


def _get_memory_saver() -> MemorySaver:
    """Get or create the global MemorySaver instance."""
    if _state["memory_saver"] is None:
        _state["memory_saver"] = MemorySaver()
    # Type is guaranteed non-None after the check above
    return cast("MemorySaver", _state["memory_saver"])


def _is_valid_db_url(db_url: str) -> bool:
    """Check whether a DB URL looks like a real Postgres connection string.

    Returns False for empty strings, placeholder URLs containing bracket
    tokens like ``[PROJECT-REF]``, or non-postgresql schemes.
    """
    return bool(
        db_url
        and "[" not in db_url  # No placeholder brackets
        and db_url.startswith("postgresql://")
    )


async def init_checkpointer() -> None:
    """Initialise the persistent Postgres checkpointer at application startup.

    Creates a single ``AsyncPostgresSaver`` connection pool and runs DDL
    (``CREATE TABLE IF NOT EXISTS``) exactly once.  Subsequent calls to
    :func:`get_checkpointer` will reuse this instance without any setup
    overhead.

    If ``SUPABASE_DB_URL`` is not configured or is a placeholder, this
    function is a no-op (the MemorySaver path does not need initialisation).
    """
    settings = get_settings()
    db_url = settings.SUPABASE_DB_URL

    if not _is_valid_db_url(db_url):
        logger.info("No valid SUPABASE_DB_URL; skipping Postgres checkpointer init")
        return

    logger.info("Initialising persistent Postgres checkpointer")
    # from_conn_string returns an async context manager; we enter it manually
    # so the connection pool stays open for the lifetime of the application.
    cm = AsyncPostgresSaver.from_conn_string(db_url)
    saver = await cm.__aenter__()
    await saver.setup()
    _state["postgres_cm"] = cm
    _state["postgres_saver"] = saver
    logger.info("Postgres checkpointer ready")


async def close_checkpointer() -> None:
    """Close the persistent Postgres checkpointer during application shutdown.

    Exits the async context manager opened by :func:`init_checkpointer`,
    which closes the underlying connection pool.  Safe to call even if the
    checkpointer was never initialised (e.g. MemorySaver path).
    """
    cm = _state.get("postgres_cm")
    if cm is not None:
        logger.info("Closing Postgres checkpointer connection pool")
        await cm.__aexit__(None, None, None)
        _state["postgres_saver"] = None
        _state["postgres_cm"] = None
        logger.info("Postgres checkpointer closed")


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

    If :func:`init_checkpointer` has been called (normal application startup),
    the persistent singleton is yielded without any setup overhead.  Otherwise
    (e.g. in tests) a transient instance is created, set up, and torn down
    within the context manager -- preserving backward compatibility.

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
    # Fast path: persistent instance initialised at startup
    persistent = _state.get("postgres_saver")
    if persistent is not None and isinstance(persistent, AsyncPostgresSaver):
        yield persistent
        return

    # Fallback: create a transient instance (tests / init_checkpointer not called)
    settings = get_settings()

    if not settings.SUPABASE_DB_URL:
        raise ValueError("SUPABASE_DB_URL is not configured")

    logger.warning(
        "Creating transient Postgres checkpointer — "
        "call init_checkpointer() at startup for better performance"
    )
    async with AsyncPostgresSaver.from_conn_string(settings.SUPABASE_DB_URL) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[BaseCheckpointSaver[Any], None]:
    """
    Get checkpointer for LangGraph persistence.

    Automatically selects the appropriate checkpointer based on configuration:
    - AsyncPostgresSaver when SUPABASE_DB_URL is configured (persistent across restarts)
    - MemorySaver as fallback (in-memory, lost on restart)

    In production, the Postgres checkpointer is a long-lived singleton
    initialised once at startup via :func:`init_checkpointer`.  The context
    manager yields the shared instance without per-request setup/teardown.

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

    db_url = settings.SUPABASE_DB_URL
    if _is_valid_db_url(db_url):
        # Use Postgres checkpointer (persistent singleton or transient fallback)
        async with get_postgres_checkpointer() as checkpointer:
            yield checkpointer
    else:
        # Fall back to MemorySaver for local development or when DB URL not set
        yield _get_memory_saver()


def clear_memory_saver() -> None:
    """
    Clear the global MemorySaver instance.

    Useful for testing or when you need to reset all conversations.
    Note: This only affects the in-memory fallback, not Postgres storage.
    """
    _state["memory_saver"] = None
