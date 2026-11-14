"""
Shared LLM factory for the Habla Hermano agent nodes.

Provides a single `get_llm()` function with profile-based configuration,
eliminating duplication across node files while preserving each node's
specific token and timeout settings.

No profile sets temperature, top_p or top_k. Anthropic API version
2026-10-21 rejects those fields on every model ("Extra inputs are not
permitted"), and newer models reject non-default values on older API
versions too. Tone and consistency are steered by the prompts instead.

Models are served through OpenRouter's OpenAI-compatible API, so the factory
returns a ``ChatOpenAI`` instance pointed at the OpenRouter base URL.

Profiles:
    - "default" / "conversational": max_tokens=1024
    - "analysis": max_tokens=1024
    - "structured": max_tokens=512
    - "creative": max_tokens=512
    - "enhancement": max_tokens=1024
    - "titling": max_tokens=30, timeout=15s
"""

from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

# Each entry: (max_tokens, timeout_seconds)
_PROFILES: dict[str, tuple[int, int]] = {
    "default": (1024, 60),
    "conversational": (1024, 60),
    "analysis": (1024, 60),
    "structured": (512, 60),
    "creative": (512, 60),
    "enhancement": (1024, 60),
    "titling": (30, 15),
}


@lru_cache(maxsize=8)
def get_llm(profile: str = "default") -> ChatOpenAI:
    """
    Create and return a ChatOpenAI instance (via OpenRouter) for the given profile.

    Each profile maps to a (max_tokens, timeout) pair suited to different
    node responsibilities. The model, API key and base URL are always read
    from application settings. Temperature is never sent (see module docstring).

    Args:
        profile: Configuration profile name. One of "default",
            "conversational", "analysis", "structured", "creative",
            "enhancement", or "titling".

    Returns:
        A configured ChatOpenAI instance pointed at OpenRouter.

    Raises:
        ValueError: If the profile name is not recognised.
    """
    if profile not in _PROFILES:
        raise ValueError(
            f"Unknown LLM profile '{profile}'. Valid profiles: {', '.join(sorted(_PROFILES))}"
        )

    max_tokens, timeout = _PROFILES[profile]

    # Import here to avoid circular import through src.api.config
    from src.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    kwargs: dict[str, Any] = {
        "model": settings.LLM_MODEL,
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

    # Turn off hidden reasoning. Reasoning tokens count against max_tokens, so
    # Haiku 5.5 spent ~440 of the analysis profile's 1024 on reasoning and cut
    # its JSON short (found by `make eval`); it also doubled latency.
    extra_body: dict[str, Any] = {"reasoning": {"enabled": False}}

    # Privacy: restrict routing to providers that do not retain/train on data.
    # OpenRouter exposes this via the request body `provider.data_collection`
    # field, forwarded through the OpenAI-compatible client's `extra_body`.
    if settings.OPENROUTER_ZERO_RETENTION:
        extra_body["provider"] = {"data_collection": "deny"}
    kwargs["extra_body"] = extra_body

    return ChatOpenAI(**kwargs)  # type: ignore[call-arg]  # langchain-openai partial stubs


def clear_llm_cache() -> None:
    """Clear the cached LLM instances.

    Useful for testing or when settings change.
    """
    get_llm.cache_clear()
