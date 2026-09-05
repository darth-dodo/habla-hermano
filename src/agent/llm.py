"""
Shared LLM factory for the Habla Hermano agent nodes.

Provides a single `get_llm()` function with profile-based configuration,
eliminating duplication across node files while preserving each node's
specific temperature and token settings.

Models are served through OpenRouter's OpenAI-compatible API, so the factory
returns a ``ChatOpenAI`` instance pointed at the OpenRouter base URL.

Profiles:
    - "default" / "conversational": temperature from settings, max_tokens=1024
    - "analysis": temperature=0.3, max_tokens=1024
    - "structured": temperature=0.3, max_tokens=512
    - "creative": temperature=0.7, max_tokens=512
    - "enhancement": temperature=0.7, max_tokens=1024
"""

from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

# Profile configurations: (temperature, max_tokens)
# A None temperature means "use the value from application settings".
_PROFILES: dict[str, tuple[float | None, int, int]] = {
    # Each entry: (temperature, max_tokens, timeout_seconds)
    "default": (None, 1024, 60),
    "conversational": (None, 1024, 60),
    "analysis": (0.3, 1024, 60),
    "structured": (0.3, 512, 60),
    "creative": (0.7, 512, 60),
    "enhancement": (0.7, 1024, 60),
    "titling": (0.3, 30, 15),
}


@lru_cache(maxsize=8)
def get_llm(profile: str = "default") -> ChatOpenAI:
    """
    Create and return a ChatOpenAI instance (via OpenRouter) for the given profile.

    Each profile maps to a specific (temperature, max_tokens) pair suited
    to different node responsibilities. The model, API key, and base URL are
    always read from application settings.

    Args:
        profile: Configuration profile name. One of "default",
            "conversational", "analysis", "structured", "creative",
            or "enhancement".

    Returns:
        A configured ChatOpenAI instance pointed at OpenRouter.

    Raises:
        ValueError: If the profile name is not recognised.
    """
    if profile not in _PROFILES:
        raise ValueError(
            f"Unknown LLM profile '{profile}'. Valid profiles: {', '.join(sorted(_PROFILES))}"
        )

    temperature_override, max_tokens, timeout = _PROFILES[profile]

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
        "api_key": settings.OPENROUTER_API_KEY,
        "base_url": settings.OPENROUTER_BASE_URL,
        "timeout": timeout,
    }

    # Optional OpenRouter app-attribution headers (used for usage rankings).
    default_headers: dict[str, str] = {}
    if settings.OPENROUTER_APP_URL:
        default_headers["HTTP-Referer"] = settings.OPENROUTER_APP_URL
    if settings.OPENROUTER_APP_TITLE:
        default_headers["X-Title"] = settings.OPENROUTER_APP_TITLE
    if default_headers:
        kwargs["default_headers"] = default_headers

    # Privacy: restrict routing to providers that do not retain/train on data.
    # OpenRouter exposes this via the request body `provider.data_collection`
    # field, forwarded through the OpenAI-compatible client's `extra_body`.
    if settings.OPENROUTER_ZERO_RETENTION:
        kwargs["extra_body"] = {"provider": {"data_collection": "deny"}}

    return ChatOpenAI(**kwargs)  # type: ignore[call-arg]  # langchain-openai partial stubs


def clear_llm_cache() -> None:
    """Clear the cached LLM instances.

    Useful for testing or when settings change.
    """
    get_llm.cache_clear()
