"""Shared fake for Gemini TTS synthesis used by the voice route tests.

Route tests replace ``src.api.routes.voice.synthesize_pcm`` with
``FakeSynthesizer`` so no request reaches OpenRouter. The real HTTP request
is covered by tests/services/test_tts.py.
"""

from collections.abc import AsyncIterator

FAKE_PCM_CHUNKS = (b"\x01\x00\x02\x00", b"\x03\x00\x04\x00")


class FakeSynthesizer:
    """Stands in for src.services.tts.synthesize_pcm and records each call."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error = error

    async def __call__(self, text: str, voice: str, **_: object) -> AsyncIterator[bytes]:
        self.calls.append((text, voice))
        if self.error is not None:
            raise self.error
        for chunk in FAKE_PCM_CHUNKS:
            yield chunk
