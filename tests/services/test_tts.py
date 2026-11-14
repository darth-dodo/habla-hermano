"""Tests for src/services/tts.py - Gemini TTS through OpenRouter's speech API.

Requests go through httpx.MockTransport, so these tests check the exact
request sent to OpenRouter and how the PCM byte stream is handled, without
any network access.
"""

import json
from collections.abc import AsyncIterator, Callable, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.config import Settings
from src.services.tts import TTSError, synthesize_pcm


@pytest.fixture
def tts_settings() -> Iterator[MagicMock]:
    """Settings with an OpenRouter key and the default Gemini TTS model."""
    settings = MagicMock(spec=Settings)
    settings.OPENROUTER_API_KEY = "test-openrouter-key"  # pragma: allowlist secret
    settings.OPENROUTER_BASE_URL = "https://openrouter.test/api/v1/"
    settings.OPENROUTER_ZERO_RETENTION = False
    settings.TTS_MODEL = "google/gemini-3.8-flash-tts"
    with patch("src.services.tts.get_settings", return_value=settings):
        yield settings


class ChunkedStream(httpx.AsyncByteStream):
    """Response body delivered in the exact chunks given, like a real stream."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _collect(text: str, voice: str, client: httpx.AsyncClient) -> list[bytes]:
    return [chunk async for chunk in synthesize_pcm(text, voice, client=client)]


class TestSpeechRequest:
    """The request sent to OpenRouter."""

    async def test_posts_gemini_pcm_request_to_speech_endpoint(
        self, tts_settings: MagicMock
    ) -> None:
        """POSTs model, text, voice and pcm format to /audio/speech with a Bearer key."""
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"\x00\x01")

        async with _client(handler) as client:
            await _collect("Hola amigo", "Achird", client)

        (request,) = seen
        assert request.method == "POST"
        assert str(request.url) == "https://openrouter.test/api/v1/audio/speech"
        assert request.headers["Authorization"] == "Bearer test-openrouter-key"
        assert json.loads(request.content) == {
            "model": "google/gemini-3.8-flash-tts",
            "input": "Hola amigo",
            "voice": "Achird",
            "response_format": "pcm",
        }

    async def test_zero_retention_restricts_provider_data_collection(
        self, tts_settings: MagicMock
    ) -> None:
        """With zero retention on, providers that keep data are excluded."""
        tts_settings.OPENROUTER_ZERO_RETENTION = True
        bodies: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content))
            return httpx.Response(200, content=b"")

        async with _client(handler) as client:
            await _collect("Hola", "Achird", client)

        assert bodies[0]["provider"] == {"data_collection": "deny"}

    async def test_model_comes_from_settings(self, tts_settings: MagicMock) -> None:
        """TTS_MODEL can be switched (e.g. to the Flash Lite tier) via settings."""
        tts_settings.TTS_MODEL = "google/gemini-3.8-flash-lite-tts"
        models: list[object] = []

        def handler(request: httpx.Request) -> httpx.Response:
            models.append(json.loads(request.content)["model"])
            return httpx.Response(200, content=b"")

        async with _client(handler) as client:
            await _collect("Hola", "Kore", client)

        assert models == ["google/gemini-3.8-flash-lite-tts"]


class TestPcmStream:
    """How the PCM byte stream is passed on."""

    async def test_chunks_are_yielded_as_they_arrive(self, tts_settings: MagicMock) -> None:
        """Even-length chunks pass straight through, in order."""
        body = [b"\x01\x00\x02\x00", b"\x03\x00"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, stream=ChunkedStream(body))

        async with _client(handler) as client:
            assert await _collect("Hola", "Kore", client) == body

    async def test_odd_byte_carried_so_every_chunk_holds_whole_samples(
        self, tts_settings: MagicMock
    ) -> None:
        """A sample split across network chunks is never cut in half.

        The browser decodes each frame with new Int16Array(buffer), which
        throws on an odd byte length.
        """
        body = [b"\x01\x00\x02", b"\x00\x03", b"\x00"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, stream=ChunkedStream(body))

        async with _client(handler) as client:
            chunks = await _collect("Hola", "Kore", client)

        assert all(len(c) % 2 == 0 and c for c in chunks)
        assert b"".join(chunks) == b"".join(body)

    async def test_single_byte_chunks_are_regrouped(self, tts_settings: MagicMock) -> None:
        """Even a byte-at-a-time stream comes out as whole 16-bit samples."""
        body = [b"\x01", b"\x00", b"\x02", b"\x00"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, stream=ChunkedStream(body))

        async with _client(handler) as client:
            assert await _collect("Hola", "Kore", client) == [b"\x01\x00", b"\x02\x00"]


class TestErrors:
    """Failures surface as TTSError."""

    @pytest.mark.parametrize("status", [400, 401, 402, 429, 500, 503])
    async def test_error_status_raises_before_any_audio(
        self, tts_settings: MagicMock, status: int
    ) -> None:
        """An OpenRouter error status raises TTSError and yields no audio."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"error": {"message": "nope"}})

        received: list[bytes] = []
        async with _client(handler) as client:
            with pytest.raises(TTSError, match=str(status)):
                async for chunk in synthesize_pcm("Hola", "Kore", client=client):
                    received.append(chunk)

        assert received == []

    async def test_transport_error_raises_tts_error(self, tts_settings: MagicMock) -> None:
        """Connection failures are wrapped in TTSError."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable", request=request)

        async with _client(handler) as client:
            with pytest.raises(TTSError, match="ConnectError"):
                await _collect("Hola", "Kore", client)

    async def test_error_message_does_not_leak_api_key(self, tts_settings: MagicMock) -> None:
        """The exception text never includes the OpenRouter key."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        async with _client(handler) as client:
            with pytest.raises(TTSError) as exc_info:
                await _collect("Hola", "Kore", client)

        assert "test-openrouter-key" not in str(exc_info.value)


class TestClientOwnership:
    """synthesize_pcm only closes the HTTP client it created itself."""

    async def test_shared_client_left_open(self, tts_settings: MagicMock) -> None:
        """A caller's client (one per WebSocket) is reused, not closed."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"\x00\x00")

        async with _client(handler) as client:
            await _collect("Uno", "Kore", client)
            await _collect("Dos", "Kore", client)
            assert not client.is_closed

    async def test_own_client_closed_after_use(self, tts_settings: MagicMock) -> None:
        """Without a client argument, the one created internally is closed."""
        created: list[httpx.AsyncClient] = []
        real_client = httpx.AsyncClient

        def factory(**kwargs: object) -> httpx.AsyncClient:
            client = real_client(
                transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"\x00\x00"))
            )
            created.append(client)
            return client

        with patch("src.services.tts.httpx.AsyncClient", side_effect=factory):
            chunks = [c async for c in synthesize_pcm("Hola", "Kore")]

        assert chunks == [b"\x00\x00"]
        assert created[0].is_closed
