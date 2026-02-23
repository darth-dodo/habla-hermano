"""Centralized language metadata and validation utilities.

Single source of truth for supported languages, language names, and
validation constants used across the codebase.
"""

# Supported language codes
VALID_LANGUAGES: set[str] = {"es", "de", "fr"}

# Language code to full name mapping
LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "de": "German",
    "fr": "French",
}


def get_language_name(code: str) -> str:
    """Convert a language code to its full display name.

    Args:
        code: ISO 639-1 language code (e.g. "es", "de", "fr").

    Returns:
        Full language name, defaulting to "Spanish" for unknown codes.
    """
    return LANGUAGE_NAMES.get(code, "Spanish")
