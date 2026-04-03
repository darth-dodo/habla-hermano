"""Thread management service for conversation threads.

Provides CRUD operations for the conversation_threads table,
which stores metadata (title, language, timestamps) for each
conversation thread. Actual conversation data lives in LangGraph
checkpoint tables; the thread_id column bridges the two systems.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from src.db.encryption import decrypt_field, encrypt_field
from src.db.models import ConversationThread

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

logger = logging.getLogger(__name__)


def _decrypt_title(title: str | None) -> str | None:
    """Decrypt a thread title, falling back to the raw value for legacy rows.

    Unlike ``decrypt_field_safe`` (which returns "[encrypted]" on failure),
    this preserves the original plaintext for pre-encryption rows that were
    never encrypted.
    """
    if title is None or title == "":
        return title
    try:
        return decrypt_field(title)
    except Exception:
        # Legacy unencrypted title — return as-is
        return title


def _decrypt_thread_row(row: dict[str, Any]) -> dict[str, Any]:
    """Decrypt the title field in a thread row from the database."""
    row["title"] = _decrypt_title(row.get("title"))
    return row


class ThreadService:
    """CRUD operations for conversation thread metadata."""

    TABLE = "conversation_threads"

    def __init__(self, user_id: str, client: SupabaseClient) -> None:
        self._user_id = user_id
        self._client = client

    def create_thread(self, language: str = "es", level: str = "A1") -> ConversationThread:
        """Create a new thread with a generated thread_id.

        Thread ID format: user:{user_id}:{uuid4}
        """
        thread_id = f"user:{self._user_id}:{uuid.uuid4()}"
        default_title = "New conversation"
        data = {
            "user_id": self._user_id,
            "thread_id": thread_id,
            "title": encrypt_field(default_title) or default_title,
            "language": language,
            "level": level,
        }
        result = self._client.table(self.TABLE).insert(data).execute()
        row = _decrypt_thread_row(cast("dict[str, Any]", result.data[0]))
        return ConversationThread(**row)

    def list_threads(self) -> list[ConversationThread]:
        """List all threads for user, ordered by updated_at DESC."""
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("user_id", self._user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [
            ConversationThread(**_decrypt_thread_row(cast("dict[str, Any]", row)))
            for row in result.data
        ]

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Get a single thread by its LangGraph thread_id."""
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )
        if not result.data:
            return None
        row = _decrypt_thread_row(cast("dict[str, Any]", result.data[0]))
        return ConversationThread(**row)

    def update_title(self, thread_id: str, title: str) -> None:
        """Rename a thread. The title is encrypted before storage."""
        encrypted_title = encrypt_field(title) or title
        (
            self._client.table(self.TABLE)
            .update({"title": encrypted_title, "updated_at": datetime.now(UTC).isoformat()})
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )

    def update_language(self, thread_id: str, language: str) -> None:
        """Update a thread's language."""
        (
            self._client.table(self.TABLE)
            .update({"language": language, "updated_at": datetime.now(UTC).isoformat()})
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )

    def touch(self, thread_id: str) -> None:
        """Update updated_at timestamp (called on each message)."""
        (
            self._client.table(self.TABLE)
            .update({"updated_at": datetime.now(UTC).isoformat()})
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )

    def delete_thread(self, thread_id: str) -> None:
        """Delete thread metadata row and all associated checkpoint data.

        Checkpoints are deleted first so that if any step fails, the metadata
        row still exists and a retry can clean up remaining checkpoint data.
        """
        # Delete checkpoint data first (LangGraph checkpoint tables).
        # RLS on these tables uses checkpoint_owner() which validates ownership via the
        # user JWT already present in self._client, so no additional user_id filter needed.
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                self._client.table(table).delete().eq("thread_id", thread_id).execute()
            except Exception:
                logger.exception("Failed to delete %s for thread %s", table, thread_id)

        # Delete thread metadata last
        (
            self._client.table(self.TABLE)
            .delete()
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )
