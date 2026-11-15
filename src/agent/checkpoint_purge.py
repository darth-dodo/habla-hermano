"""Delete idle conversations after CHECKPOINT_RETENTION_DAYS (runs daily, see main.py).

A conversation (thread) is deleted whole once its last message is older than
the retention period: its checkpoints, blobs, writes and sidebar entry. With
MemorySaver (dev mode) or retention_days=0 this is a safe no-op.
"""

import logging

from psycopg.sql import SQL, Identifier

from src.agent.checkpointer import _state
from src.config import get_settings

logger = logging.getLogger(__name__)

# Rows of one conversation, children first; conversation_threads is the sidebar entry.
_THREAD_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "conversation_threads")

# A thread is stale when its NEWEST checkpoint is older than the cutoff. Old
# checkpoints of an active thread are kept: they hold its history chain. The
# only timestamp langgraph-checkpoint-postgres stores is "ts" in the
# checkpoint JSON (plain JSON; channel values live encrypted in the blobs).
_STALE_THREADS_SQL = SQL(
    "SELECT thread_id FROM checkpoints GROUP BY thread_id "
    "HAVING MAX((checkpoint->>'ts')::timestamptz) < NOW() - make_interval(days => %s)"
)


async def purge_old_checkpoints(retention_days: int | None = None) -> int:
    """Delete whole conversations whose last message is older than *retention_days*.

    Args:
        retention_days: Days to keep an idle conversation. Defaults to
            ``Settings.CHECKPOINT_RETENTION_DAYS``. Pass ``0`` to disable.

    Returns:
        Number of conversations (threads) deleted.
    """
    if retention_days is None:
        retention_days = get_settings().CHECKPOINT_RETENTION_DAYS

    if retention_days == 0:
        logger.info("Checkpoint purging disabled (retention_days=0)")
        return 0

    pool = _state.get("postgres_pool")
    if pool is None:
        logger.info("No Postgres checkpointer active (MemorySaver mode); skipping checkpoint purge")
        return 0

    try:
        async with pool.connection() as conn, conn.transaction():
            cur = await conn.execute(_STALE_THREADS_SQL, (retention_days,))
            threads = [row["thread_id"] for row in await cur.fetchall()]
            if threads:
                for table in _THREAD_TABLES:  # names come from the constant above
                    await conn.execute(
                        SQL("DELETE FROM {} WHERE thread_id = ANY(%s)").format(Identifier(table)),
                        (threads,),
                    )
        logger.info(
            "Checkpoint purge complete: %d conversations deleted (retention=%d days)",
            len(threads),
            retention_days,
        )
        return len(threads)
    except Exception:
        logger.exception("Checkpoint purge failed, continuing without purge")
        return 0
