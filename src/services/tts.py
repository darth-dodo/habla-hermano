"""Text-to-speech through OpenRouter's speech API (Gemini TTS).

OpenRouter exposes an OpenAI-compatible ``POST /audio/speech`` endpoint that
returns raw audio bytes. We always ask for ``pcm``: Gemini TTS only produces
PCM (24kHz, mono, 16-bit little-endian), which the browser plays directly via
the Web Audio API on the WebSocket path and wraps in a WAV header on the REST
fallback path.
"""

from collections.abc import AsyncGenerator
from typing import Any

import httpx

from src.config import get_settings

# Output format of Gemini TTS: 24kHz, mono, signed 16-bit little-endian PCM.
TTS_SAMPLE_RATE = 24000
_BYTES_PER_SAMPLE = 2

_TIMEOUT_SECONDS = 30.0


class TTSError(Exception):
    """Speech synthesis failed (upstream error status or transport failure)."""


def _speech_request(text: str, voice: str) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Build the URL, headers and JSON body for one synthesis request."""
    settings = get_settings()
    body: dict[str, Any] = {
        "model": settings.TTS_MODEL,
        "input": text,
        "voice": voice,
        "response_format": "pcm",
    }
    if settings.OPENROUTER_ZERO_RETENTION:
        # Same policy as the chat LLM: only route to providers that do not
        # retain or train on request data.
        body["provider"] = {"data_collection": "deny"}

    headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/audio/speech"
    return url, headers, body


async def synthesize_pcm(
    text: str,
    voice: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> AsyncGenerator[bytes, None]:
    """Stream synthesized speech as raw PCM chunks as they arrive.

    Every yielded chunk holds a whole number of 16-bit samples, because the
    browser decodes each WebSocket frame with ``new Int16Array(buffer)``,
    which throws on an odd byte length. A trailing odd byte is carried over
    to the next chunk.

    Args:
        text: Text to speak.
        voice: TTS voice name (validated by the caller).
        client: Optional shared HTTP client (one per WebSocket connection).
            When omitted, a client is created and closed for this call.

    Yields:
        Non-empty PCM byte chunks of even length.

    Raises:
        TTSError: If OpenRouter answers with an error status or the
            connection fails. Raised before the first chunk for status errors,
            so callers can still report a clean error.
    """
    url, headers, body = _speech_request(text, voice)
    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        async with http.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code != httpx.codes.OK:
                await response.aread()
                raise TTSError(f"OpenRouter TTS returned HTTP {response.status_code}")

            carry = b""
            async for chunk in response.aiter_bytes():
                data = carry + chunk
                usable = len(data) - (len(data) % _BYTES_PER_SAMPLE)
                carry = data[usable:]
                if usable:
                    yield data[:usable]
    except httpx.HTTPError as exc:
        raise TTSError(f"OpenRouter TTS request failed: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await http.aclose()
