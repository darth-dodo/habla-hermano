"""Application configuration — re-exports from src.config.

This module re-exports Settings and get_settings from src.config for
backward compatibility. New code in inner layers (agent, services, db)
should import directly from ``src.config`` instead.
"""

from src.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
