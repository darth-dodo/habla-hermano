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
    An AsyncConnectionPool (psycopg_pool) is created at application startup
    via init_checkpointer() and wrapped in AsyncPostgresSaver. The pool
    allows concurrent graph operations without connection conflicts. DDL
    setup happens exactly once. Shutdown via close_checkpointer().
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.db.encryption import FernetCipher

logger = logging.getLogger(__name__)

# Type alias for checkpointer return type
CheckpointerType = AsyncPostgresSaver | MemorySaver

# Module-level state for singletons
# Using a dict to avoid global statement (PLW0603)
_state: dict[str, Any] = {
    "memory_saver": None,
    "postgres_saver": None,
    # The AsyncConnectionPool, closed during shutdown via close_checkpointer().
    "postgres_pool": None,
}


def _get_encrypted_serde() -> EncryptedSerializer:
    """Build an ``EncryptedSerializer`` using the application Fernet key.

    Wraps the default ``JsonPlusSerializer`` so checkpoint state blobs are
    encrypted at rest.  Old unencrypted checkpoints are read transparently
    (the ``EncryptedSerializer`` falls back when the type field has no
    ``+cipher`` suffix).
    """
    return EncryptedSerializer(cipher=FernetCipher())


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

    Creates an ``AsyncConnectionPool`` (min 2, max 20 connections) and wraps
    it in ``AsyncPostgresSaver``.  Using a pool instead of a single connection
    allows concurrent ``graph.astream()`` calls without "another command is
    already in progress" errors.  DDL runs exactly once.

    If ``SUPABASE_DB_URL`` is not configured or is a placeholder, this
    function is a no-op (the MemorySaver path does not need initialisation).
    """
    settings = get_settings()
    db_url = settings.SUPABASE_DB_URL

    if not _is_valid_db_url(db_url):
        logger.info("No valid SUPABASE_DB_URL; skipping Postgres checkpointer init")
        return

    logger.info("Initialising persistent Postgres checkpointer")
    # Use AsyncConnectionPool instead of from_conn_string() (which creates a
    # single AsyncConnection).  A pool lets concurrent requests each get their
    # own connection, avoiding "another command is already in progress" errors
    # when multiple graph.astream() calls overlap.
    encrypted_serde = _get_encrypted_serde()
    pool = AsyncConnectionPool(
        conninfo=db_url,
        max_size=20,
        min_size=2,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    saver = AsyncPostgresSaver(conn=pool, serde=encrypted_serde)  # type: ignore[arg-type]  # row_factory=dict_row in kwargs satisfies runtime contract
    await saver.setup()
    _state["postgres_pool"] = pool
    _state["postgres_saver"] = saver
    logger.info("Postgres checkpointer ready (pool max_size=20, encryption enabled)")


async def close_checkpointer() -> None:
    """Close the persistent Postgres checkpointer during application shutdown.

    Exits the async context manager opened by :func:`init_checkpointer`,
    which closes the underlying connection pool.  Safe to call even if the
    checkpointer was never initialised (e.g. MemorySaver path).
    """
    pool = _state.get("postgres_pool")
    if pool is not None:
        logger.info("Closing Postgres checkpointer connection pool")
        await pool.close()
        _state["postgres_saver"] = None
        _state["postgres_pool"] = None
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
    encrypted_serde = _get_encrypted_serde()
    async with AsyncPostgresSaver.from_conn_string(
        settings.SUPABASE_DB_URL, serde=encrypted_serde
    ) as checkpointer:
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
