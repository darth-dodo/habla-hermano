"""Data retention service for automatic conversation cleanup.

Provides purging of old conversation data (learning sessions, vocabulary)
based on configurable retention periods.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from src.config import get_settings
from src.db.client import get_supabase

logger = logging.getLogger(__name__)


async def purge_old_conversations(retention_days: int | None = None) -> dict[str, int]:
    """Delete conversation data older than retention_days.

    When retention_days is 0 or None, no data is deleted (feature disabled).

    Args:
        retention_days: Number of days to retain data. Falls back to
            CONVERSATION_RETENTION_DAYS from settings if not provided.

    Returns:
        Dict with counts of deleted rows per table, e.g.
        ``{"learning_sessions": 5, "vocabulary": 3}``.
    """
    if retention_days is None:
        retention_days = get_settings().CONVERSATION_RETENTION_DAYS

    if retention_days <= 0:
        return {"learning_sessions": 0, "vocabulary": 0}

    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    counts: dict[str, int] = {"learning_sessions": 0, "vocabulary": 0}

    try:
        client = get_supabase()

        # Delete old learning sessions
        result = await asyncio.to_thread(
            lambda: client.table("learning_sessions")
            .delete()
            .lt("started_at", cutoff_iso)
            .execute()
        )
        counts["learning_sessions"] = len(result.data) if result.data else 0

        # Delete old vocabulary where both review timestamps are past cutoff
        result = await asyncio.to_thread(
            lambda: client.table("vocabulary")
            .delete()
            .lt("last_reviewed_at", cutoff_iso)
            .lt("next_review_at", cutoff_iso)
            .execute()
        )
        counts["vocabulary"] = len(result.data) if result.data else 0

    except Exception:
        logger.warning("Failed to purge old conversation data", exc_info=True)

    return counts
