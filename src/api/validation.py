"""Shared input validation — re-exports from src.validation.

This module re-exports all validation constants and helpers from
src.validation for backward compatibility. New code in inner layers
(agent, services) should import directly from ``src.validation`` instead.
"""

from src.validation import (
    DEFAULT_LANGUAGE,
    DEFAULT_LEVEL,
    LANGUAGE_NAMES,
    MAX_DAYS,
    MAX_MESSAGE_LENGTH,
    MIN_DAYS,
    VALID_LANGUAGES,
    VALID_LEVELS,
    get_language_name,
    validate_days,
    validate_language,
    validate_level,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "DEFAULT_LEVEL",
    "LANGUAGE_NAMES",
    "MAX_DAYS",
    "MAX_MESSAGE_LENGTH",
    "MIN_DAYS",
    "VALID_LANGUAGES",
    "VALID_LEVELS",
    "get_language_name",
    "validate_days",
    "validate_language",
    "validate_level",
]
