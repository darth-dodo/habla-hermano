"""Seed data utilities for Habla Hermano.

With Supabase integration, database tables are managed via Supabase migrations
and user_profiles are auto-created via database triggers on auth.users.

This module provides utilities for initializing user data if needed.
"""

from src.api.supabase_client import get_supabase
from src.db.repository import UserProfileRepository

# Default settings for new users (stored in user_profiles)
DEFAULT_USER_SETTINGS = {
    "preferred_language": "es",
    "current_level": "A1",
}


def ensure_user_profile(user_id: str) -> None:
    """Ensure user profile exists with default settings.

    Note: User profiles are normally auto-created via Supabase trigger
    when a user signs up. This function is for edge cases or testing.

    Args:
        user_id: Supabase auth user UUID.
    """
    repo = UserProfileRepository(user_id)
    profile = repo.get()

    if profile is None:
        # Profile should be auto-created by trigger, but create if missing
        client = get_supabase()
        client.table("user_profiles").insert({
            "id": user_id,
            "preferred_language": DEFAULT_USER_SETTINGS["preferred_language"],
            "current_level": DEFAULT_USER_SETTINGS["current_level"],
        }).execute()


def reset_user_data(user_id: str) -> None:
    """Reset all user data except profile.

    Useful for testing or when user wants to start fresh.

    Args:
        user_id: Supabase auth user UUID.
    """
    client = get_supabase()

    # Delete all vocabulary
    client.table("vocabulary").delete().eq("user_id", user_id).execute()

    # Delete all learning sessions
    client.table("learning_sessions").delete().eq("user_id", user_id).execute()

    # Delete all lesson progress
    client.table("lesson_progress").delete().eq("user_id", user_id).execute()


__all__ = [
    "DEFAULT_USER_SETTINGS",
    "ensure_user_profile",
    "reset_user_data",
]
