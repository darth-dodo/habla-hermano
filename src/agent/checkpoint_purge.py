"""Checkpoint TTL purging for LangGraph conversation checkpoints.

Deletes checkpoints older than a configurable retention period to prevent
unbounded growth of the checkpoint tables in Postgres.  When running with
MemorySaver (dev mode) or when purging is disabled (retention_days=0), this
module is a safe no-op.
"""

import logging

from psycopg.sql import SQL, Identifier

from src.agent.checkpointer import _state
from src.config import get_settings

logger = logging.getLogger(__name__)

# LangGraph checkpoint tables managed by AsyncPostgresSaver.
_CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


async def purge_old_checkpoints(retention_days: int | None = None) -> int:
    """Delete LangGraph checkpoints older than *retention_days*.

    Args:
        retention_days: Number of days to retain checkpoints.  Defaults to
            ``Settings.CHECKPOINT_RETENTION_DAYS``.  Pass ``0`` to disable
            purging.

    Returns:
        Total number of rows deleted across all checkpoint tables.
    """
    if retention_days is None:
        retention_days = get_settings().CHECKPOINT_RETENTION_DAYS

    if retention_days == 0:
        logger.info("Checkpoint purging disabled (retention_days=0)")
        return 0

    saver = _state.get("postgres_saver")
    if saver is None:
        logger.info("No Postgres checkpointer active (MemorySaver mode); skipping checkpoint purge")
        return 0

    try:
        pool = saver.conn  # psycopg AsyncConnectionPool
        total_deleted = 0

        async with pool.connection() as conn:
            for table in _CHECKPOINT_TABLES:
                # thread_ts is the checkpoint timestamp column used by
                # langgraph-checkpoint-postgres.  Table names are from our
                # constant tuple; retention_days is parameterised.
                result = await conn.execute(
                    SQL("DELETE FROM {} WHERE thread_ts < NOW() - INTERVAL %s").format(
                        Identifier(table)
                    ),
                    (f"{retention_days} days",),
                )
                deleted = result.rowcount if result.rowcount else 0
                total_deleted += deleted
                logger.debug(
                    "Purged %d rows from %s (older than %d days)",
                    deleted,
                    table,
                    retention_days,
                )

        logger.info(
            "Checkpoint purge complete: %d total rows deleted (retention=%d days)",
            total_deleted,
            retention_days,
        )
        return total_deleted

    except Exception:
        logger.exception("Checkpoint purge failed — continuing without purge")
        return 0
