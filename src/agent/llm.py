"""
Shared LLM factory for the Habla Hermano agent nodes.

Provides a single `get_llm()` function with profile-based configuration,
eliminating duplication across node files while preserving each node's
specific temperature and token settings.

Profiles:
    - "default" / "conversational": temperature from settings, max_tokens=1024
    - "analysis": temperature=0.3, max_tokens=1024
    - "structured": temperature=0.3, max_tokens=512
    - "creative": temperature=0.7, max_tokens=512
    - "enhancement": temperature=0.7, max_tokens=1024
"""

from functools import lru_cache
from typing import Any

from langchain_anthropic import ChatAnthropic

# Profile configurations: (temperature, max_tokens)
# A None temperature means "use the value from application settings".
_PROFILES: dict[str, tuple[float | None, int]] = {
    "default": (None, 1024),
    "conversational": (None, 1024),
    "analysis": (0.3, 1024),
    "structured": (0.3, 512),
    "creative": (0.7, 512),
    "enhancement": (0.7, 1024),
}


@lru_cache(maxsize=8)
def get_llm(profile: str = "default") -> ChatAnthropic:
    """
    Create and return a ChatAnthropic instance configured for the given profile.

    Each profile maps to a specific (temperature, max_tokens) pair suited
    to different node responsibilities. The model and API key are always
    read from application settings.

    Args:
        profile: Configuration profile name. One of "default",
            "conversational", "analysis", "structured", "creative",
            or "enhancement".

    Returns:
        A configured ChatAnthropic instance.

    Raises:
        ValueError: If the profile name is not recognised.
    """
    if profile not in _PROFILES:
        raise ValueError(
            f"Unknown LLM profile '{profile}'. Valid profiles: {', '.join(sorted(_PROFILES))}"
        )

    temperature_override, max_tokens = _PROFILES[profile]

    # Import here to avoid circular import through src.api.config
    from src.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    temperature: Any = (
        temperature_override if temperature_override is not None else settings.LLM_TEMPERATURE
    )

    kwargs: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": settings.ANTHROPIC_API_KEY,
    }

    if settings.ANTHROPIC_ZERO_RETENTION:
        kwargs["default_headers"] = {"x-no-store": "true"}

    return ChatAnthropic(**kwargs)  # type: ignore[call-arg]  # langchain-anthropic lacks stubs


def clear_llm_cache() -> None:
    """Clear the cached LLM instances.

    Useful for testing or when settings change.
    """
    get_llm.cache_clear()
