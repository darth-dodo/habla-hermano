"""Supabase client singleton for database and auth operations.

Provides cached client instances for Supabase interactions.
Uses the anon key for regular operations and service key for admin tasks.
"""

from functools import lru_cache
from typing import Any

from src.api.config import get_settings

# Type alias - actual Client import deferred to avoid import errors when unconfigured
SupabaseClient = Any


@lru_cache
def get_supabase() -> SupabaseClient:
    """Get Supabase client singleton using anon key.

    The anon key is safe for client-side use and respects RLS policies.
    Use this for regular user operations.

    Returns:
        Client: Configured Supabase client instance.

    Raises:
        ValueError: If Supabase is not configured.
    """
    from supabase import create_client  # noqa: PLC0415

    settings = get_settings()

    if not settings.supabase_configured:
        raise ValueError(
            "Supabase is not configured. "
            "Please set SUPABASE_URL, SUPABASE_ANON_KEY, "
            "and SUPABASE_DB_URL in your environment."
        )

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )


def get_supabase_admin() -> SupabaseClient:
    """Get Supabase client with service role key for admin operations.

    The service key bypasses RLS policies - use only for server-side
    admin operations that require elevated privileges.

    WARNING: Never expose this client to client-side code.

    Returns:
        Client: Supabase client with service role privileges.

    Raises:
        ValueError: If Supabase is not configured or service key is missing.
    """
    from supabase import create_client  # noqa: PLC0415

    settings = get_settings()

    if not settings.supabase_configured:
        raise ValueError(
            "Supabase is not configured. Please set all required Supabase environment variables."
        )

    if not settings.SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY is required for admin operations.")

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY,
    )


def clear_supabase_cache() -> None:
    """Clear the cached Supabase client.

    Useful for testing or when configuration changes.
    """
    get_supabase.cache_clear()
