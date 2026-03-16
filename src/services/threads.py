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

from src.db.models import ConversationThread

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

logger = logging.getLogger(__name__)


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
        data = {
            "user_id": self._user_id,
            "thread_id": thread_id,
            "language": language,
            "level": level,
        }
        result = self._client.table(self.TABLE).insert(data).execute()
        return ConversationThread(**cast(dict[str, Any], result.data[0]))

    def list_threads(self) -> list[ConversationThread]:
        """List all threads for user, ordered by updated_at DESC."""
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("user_id", self._user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [ConversationThread(**cast(dict[str, Any], row)) for row in result.data]

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
        return ConversationThread(**cast(dict[str, Any], result.data[0]))

    def update_title(self, thread_id: str, title: str) -> None:
        """Rename a thread."""
        (
            self._client.table(self.TABLE)
            .update({"title": title, "updated_at": datetime.now(UTC).isoformat()})
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
        """Delete thread metadata row. Checkpoints are orphaned, not deleted."""
        (
            self._client.table(self.TABLE)
            .delete()
            .eq("user_id", self._user_id)
            .eq("thread_id", thread_id)
            .execute()
        )
