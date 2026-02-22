"""Supabase client singleton for database and auth operations.

Provides cached client instances for Supabase interactions.
Uses the anon key for regular operations and service key for admin tasks.
"""

from functools import lru_cache

from supabase import Client as SupabaseClient, create_client

from src.api.config import get_settings


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


def get_supabase_for_user(access_token: str) -> SupabaseClient:
    """Get Supabase client authenticated with user's JWT.

    Creates a client that includes the user's access token in requests,
    allowing RLS policies to use auth.uid() for row-level access control.

    Args:
        access_token: User's JWT access token from authentication.

    Returns:
        Client: Supabase client authenticated as the user.

    Raises:
        ValueError: If Supabase is not configured.
    """
    settings = get_settings()

    if not settings.supabase_configured:
        raise ValueError(
            "Supabase is not configured. "
            "Please set SUPABASE_URL, SUPABASE_ANON_KEY, "
            "and SUPABASE_DB_URL in your environment."
        )

    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )
    # Set the user's JWT for authenticated requests
    client.postgrest.auth(access_token)
    return client


def clear_supabase_cache() -> None:
    """Clear the cached Supabase client.

    Useful for testing or when configuration changes.
    """
    get_supabase.cache_clear()
