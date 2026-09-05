"""Shared input validation constants and helpers.

Centralizes validation rules for language codes, CEFR levels, and other
user-supplied parameters to prevent inconsistent validation across routes.

This module lives at the ``src`` level so that inner layers (agent, services)
can import it without depending on the API layer.
"""

VALID_LANGUAGES: frozenset[str] = frozenset({"es", "de", "fr", "hi"})
VALID_LEVELS: frozenset[str] = frozenset({"A0", "A1", "A2", "B1"})
LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "hi": "Hinglish",
}
MAX_MESSAGE_LENGTH: int = 2000
MAX_DAYS: int = 365
MIN_DAYS: int = 1
DEFAULT_LANGUAGE: str = "es"
DEFAULT_LEVEL: str = "A1"


def get_language_name(code: str) -> str:
    """Convert a language code to its human-readable name.

    Args:
        code: Language code (es, de, fr, hi).

    Returns:
        Human-readable language name, defaulting to "Spanish".
    """
    return LANGUAGE_NAMES.get(code, "Spanish")


def validate_language(language: str) -> str:
    """Return the language if valid, otherwise the default.

    Args:
        language: Raw language code from user input.

    Returns:
        Validated language code, falling back to DEFAULT_LANGUAGE.
    """
    return language if language in VALID_LANGUAGES else DEFAULT_LANGUAGE


def validate_level(level: str) -> str:
    """Return the level if valid, otherwise the default.

    Args:
        level: Raw CEFR level from user input.

    Returns:
        Validated CEFR level, falling back to DEFAULT_LEVEL.
    """
    return level if level in VALID_LEVELS else DEFAULT_LEVEL


def validate_days(days: int) -> int:
    """Clamp days to the valid range [MIN_DAYS, MAX_DAYS].

    Args:
        days: Raw number of days from user input.

    Returns:
        Days clamped to the valid range.
    """
    return max(MIN_DAYS, min(days, MAX_DAYS))
