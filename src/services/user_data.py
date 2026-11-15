"""Delete a user's rows that do not cascade from auth.users."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

NON_CASCADING_TABLES = ("vocabulary", "learning_sessions", "lesson_progress")
CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


def delete_user_rows(admin: Any, user_id: str) -> None:
    """Delete vocabulary, sessions, lesson progress and checkpoints for one user.

    Each table is tried on its own and failures are logged, so one bad table
    does not stop the rest. Deleting the auth user afterwards cascades
    user_profiles and conversation_threads.
    """
    for table in NON_CASCADING_TABLES:
        try:
            admin.table(table).delete().eq("user_id", user_id).execute()
        except Exception:
            logger.exception("Failed to delete %s for user %s", table, user_id)
    # Freeform (user:{id}:...) and lesson (lesson:{id}:...) threads.
    for pattern in (f"user:{user_id}:%", f"lesson:{user_id}:%"):
        for table in CHECKPOINT_TABLES:
            try:
                admin.table(table).delete().like("thread_id", pattern).execute()
            except Exception:
                logger.exception(
                    "Failed to delete %s (pattern %s) for user %s", table, pattern, user_id
                )
