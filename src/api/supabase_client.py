"""Supabase client — re-exports from src.db.client.

This module re-exports all Supabase client functions from src.db.client
for backward compatibility. New code in inner layers (db, services)
should import directly from ``src.db.client`` instead.
"""

from src.db.client import (
    SupabaseClient,
    clear_supabase_cache,
    get_supabase,
    get_supabase_admin,
    get_supabase_for_user,
)

__all__ = [
    "SupabaseClient",
    "clear_supabase_cache",
    "get_supabase",
    "get_supabase_admin",
    "get_supabase_for_user",
]
