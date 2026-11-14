"""Optional Langfuse tracing for chat turns.

Off unless LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set. In production
the traces carry metadata only (graph node, model, tokens, cost, latency,
level, language): learner and Hermano text is removed before export, which
keeps the privacy page's promise that learning data is never shared. With
DEBUG on (local development) full content is traced.
"""

import hashlib
import hmac
import logging
from typing import Any

from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

from src.config import get_settings

logger = logging.getLogger(__name__)

_CONTENT_ATTRIBUTES = frozenset({"langfuse.observation.input", "langfuse.observation.output"})
_METADATA_PREFIXES = ("langfuse.observation.metadata.", "langfuse.trace.metadata.")
# Metadata that describes the run, not the learner. Everything else (for
# example thread_id, which embeds the user's UUID) is dropped.
_KEEP_METADATA = frozenset(
    {
        "langgraph_node",
        "langgraph_step",
        "ls_provider",
        "ls_model_name",
        "ls_model_type",
        "ls_max_tokens",
        "level",
        "language",
    }
)

_handler: Any = None


def mask_content(*, params: MaskOtelSpansParams) -> MaskOtelSpansResult | None:
    """Delete message text and non-allowlisted metadata from exported spans."""
    patches = {}
    for identifier, span in params.spans.items():
        drop = [key for key in span.attributes if _is_private(key)]
        if drop:
            patches[identifier] = OtelSpanPatch(delete_attributes=tuple(drop))
    return MaskOtelSpansResult(span_patches=patches) if patches else None


def _is_private(key: str) -> bool:
    if key in _CONTENT_ATTRIBUTES:
        return True
    for prefix in _METADATA_PREFIXES:
        if key.startswith(prefix):
            return key.removeprefix(prefix) not in _KEEP_METADATA
    return False


def _get_handler() -> Any:
    """Return the shared LangChain callback handler, or None when tracing is off."""
    global _handler  # noqa: PLW0603 - one client and handler per process
    settings = get_settings()
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        return None
    if _handler is None:
        from langfuse import Langfuse  # noqa: PLC0415 - only loaded when tracing is on
        from langfuse.langchain import CallbackHandler  # noqa: PLC0415

        Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            base_url=settings.LANGFUSE_BASE_URL,
            environment="development" if settings.DEBUG else "production",
            mask_otel_spans=None if settings.DEBUG else mask_content,
        )
        _handler = CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY)
        logger.info("Langfuse tracing enabled (content %s)", "on" if settings.DEBUG else "masked")
    return _handler


def tracing_config(thread_id: str, *, level: str | None, language: str | None) -> dict[str, Any]:
    """Callbacks and metadata to merge into a LangGraph run config; empty when off.

    The Langfuse session groups one conversation's turns. It is an HMAC of the
    thread ID, so the user's UUID never leaves the server.
    """
    handler = _get_handler()
    if handler is None:
        return {}
    secret = get_settings().SECRET_KEY.encode()
    session_id = hmac.new(secret, thread_id.encode(), hashlib.sha256).hexdigest()[:16]
    return {
        "callbacks": [handler],
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["chat"],
            "level": level,
            "language": language,
        },
    }


def shutdown_tracing() -> None:
    """Flush pending traces on app shutdown (no-op when tracing is off)."""
    if _handler is None:
        return
    from langfuse import get_client  # noqa: PLC0415

    get_client(public_key=get_settings().LANGFUSE_PUBLIC_KEY).shutdown()
