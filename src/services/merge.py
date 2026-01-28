"""Guest data merge service for transferring progress on authentication.

When a guest signs up or logs in, their session-based progress data
(stored under their session_id) is merged into their authenticated account.
"""

import logging

from src.api.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


class GuestDataMergeService:
    """Merges guest session data into an authenticated user's account.

    All operations use the admin client (service role) to bypass RLS,
    since guest rows have session UUIDs that don't match auth.uid().
    """

    def __init__(self, guest_session_id: str, authenticated_user_id: str) -> None:
        """Initialize merge service.

        Args:
            guest_session_id: Guest's session UUID (from session_id cookie).
            authenticated_user_id: Authenticated user's UUID (from JWT).
        """
        self._guest_id = guest_session_id
        self._auth_id = authenticated_user_id
        self._client = get_supabase_admin()

    def merge_all(self) -> dict[str, int]:
        """Merge all guest data into the authenticated account.

        Returns:
            Dict with counts: {"vocabulary": N, "sessions": N, "lessons": N}
        """
        vocab_count = self._merge_vocabulary()
        session_count = self._merge_sessions()
        lesson_count = self._merge_lessons()
        return {
            "vocabulary": vocab_count,
            "sessions": session_count,
            "lessons": lesson_count,
        }

    def _merge_vocabulary(self) -> int:
        """Transfer vocabulary entries from guest to authenticated user.

        For duplicate words (same word+language), merge counters:
        - times_seen: sum both
        - times_correct: sum both
        - first_seen_at: keep the earliest

        Returns:
            Number of vocabulary entries transferred/merged.
        """
        # Get guest vocabulary
        guest_vocab = (
            self._client.table("vocabulary").select("*").eq("user_id", self._guest_id).execute()
        )
        if not guest_vocab.data:
            return 0

        count = 0
        for entry in guest_vocab.data:
            # Check if authenticated user already has this word+language
            existing = (
                self._client.table("vocabulary")
                .select("*")
                .eq("user_id", self._auth_id)
                .eq("word", entry["word"])
                .eq("language", entry["language"])
                .execute()
            )

            if existing.data:
                # Merge counters into existing entry
                auth_entry = existing.data[0]
                self._client.table("vocabulary").update(
                    {
                        "times_seen": auth_entry["times_seen"] + entry["times_seen"],
                        "times_correct": auth_entry["times_correct"] + entry["times_correct"],
                        "first_seen_at": min(auth_entry["first_seen_at"], entry["first_seen_at"]),
                    }
                ).eq("id", auth_entry["id"]).execute()
                # Delete the guest entry
                self._client.table("vocabulary").delete().eq("id", entry["id"]).execute()
            else:
                # Transfer ownership: update user_id to authenticated user
                self._client.table("vocabulary").update({"user_id": self._auth_id}).eq(
                    "id", entry["id"]
                ).execute()

            count += 1

        return count

    def _merge_sessions(self) -> int:
        """Transfer all learning sessions from guest to authenticated user.

        Sessions are always transferred (no dedup needed -- each session is unique).

        Returns:
            Number of sessions transferred.
        """
        guest_sessions = (
            self._client.table("learning_sessions")
            .select("id")
            .eq("user_id", self._guest_id)
            .execute()
        )
        if not guest_sessions.data:
            return 0

        count = len(guest_sessions.data)
        # Bulk update: change user_id for all guest sessions
        self._client.table("learning_sessions").update({"user_id": self._auth_id}).eq(
            "user_id", self._guest_id
        ).execute()

        return count

    def _merge_lessons(self) -> int:
        """Transfer lesson progress from guest to authenticated user.

        For duplicate lessons (same lesson_id), keep the higher score.

        Returns:
            Number of lesson entries transferred/merged.
        """
        guest_lessons = (
            self._client.table("lesson_progress")
            .select("*")
            .eq("user_id", self._guest_id)
            .execute()
        )
        if not guest_lessons.data:
            return 0

        count = 0
        for entry in guest_lessons.data:
            # Check if authenticated user already completed this lesson
            existing = (
                self._client.table("lesson_progress")
                .select("*")
                .eq("user_id", self._auth_id)
                .eq("lesson_id", entry["lesson_id"])
                .execute()
            )

            if existing.data:
                # Keep higher score
                auth_entry = existing.data[0]
                guest_score = entry.get("score") or 0
                auth_score = auth_entry.get("score") or 0
                if guest_score > auth_score:
                    self._client.table("lesson_progress").update({"score": guest_score}).eq(
                        "user_id", self._auth_id
                    ).eq("lesson_id", entry["lesson_id"]).execute()
                # Delete guest entry
                self._client.table("lesson_progress").delete().eq("user_id", self._guest_id).eq(
                    "lesson_id", entry["lesson_id"]
                ).execute()
            else:
                # Transfer ownership
                self._client.table("lesson_progress").update({"user_id": self._auth_id}).eq(
                    "user_id", self._guest_id
                ).eq("lesson_id", entry["lesson_id"]).execute()

            count += 1

        return count
