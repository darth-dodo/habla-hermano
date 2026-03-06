"""Tests for src/api/routes/voice.py - Voice STT/TTS endpoints.

Phase 17: WebSocket STT proxy via Deepgram and REST TTS proxy endpoint.
B1: WebSocket endpoints require authentication via cookies.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
from src.api.config import Settings, get_settings
from src.api.routes.voice import (
    ALLOWED_VOICES,
    DEFAULT_VOICES,
    MAX_TTS_TEXT_LENGTH,
    VALID_STT_LANGUAGES,
    SpeakRequest,
)
from tests.conftest import CSRF_HEADERS

# Guest session UUID used for WebSocket authentication in tests
GUEST_SESSION_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create mock authenticated user."""
    return AuthenticatedUser(id="user-voice-123", email="voice@example.com")


@pytest.fixture
def ws_cookies() -> dict[str, str]:
    """Cookies dict with a valid guest session_id for WebSocket auth."""
    return {"session_id": GUEST_SESSION_ID}


@pytest.fixture
def voice_app(mock_user: AuthenticatedUser) -> Generator[FastAPI, None, None]:
    """Create FastAPI app with mocked dependencies for voice testing.

    Patches external services (LangGraph, Supabase) to prevent real connections.
    Voice-specific mocking (Deepgram, httpx) is done per-test.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": [], "level": "A1", "language": "es"})

    # Minimal astream mock
    async def mock_astream(inputs, config, stream_mode):
        return
        yield  # pragma: no cover

    mock_graph.astream = mock_astream

    class MockCheckpointerContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    def mock_get_checkpointer():
        return MockCheckpointerContext()

    def mock_build_graph(checkpointer=None):
        return mock_graph

    async def mock_get_current_user_dep():
        return mock_user

    async def mock_get_current_user_optional_dep():
        return mock_user

    mock_supabase = MagicMock()

    with (
        patch("src.api.routes.chat.build_graph", mock_build_graph),
        patch("src.api.routes.chat.get_checkpointer", mock_get_checkpointer),
        patch("src.db.repository.get_supabase", return_value=mock_supabase),
        patch("src.services.lesson_completion.get_supabase_admin", return_value=mock_supabase),
        patch("src.api.routes.learn.get_supabase_admin", return_value=mock_supabase),
    ):
        get_settings.cache_clear()
        from src.api.main import app

        app.dependency_overrides[get_current_user] = mock_get_current_user_dep
        app.dependency_overrides[get_current_user_optional] = mock_get_current_user_optional_dep

        yield app

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def test_client(voice_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create synchronous test client for WebSocket and sync tests."""
    with TestClient(voice_app, headers=CSRF_HEADERS) as client:
        yield client


@pytest.fixture
async def async_client(voice_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Create async test client for HTTP endpoint tests."""
    transport = ASGITransport(app=voice_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=CSRF_HEADERS,
    ) as client:
        yield client


@pytest.fixture
def mock_settings_with_deepgram() -> Generator[MagicMock, None, None]:
    """Provide settings with DEEPGRAM_API_KEY configured.

    Patches get_settings at the voice module level so the endpoint
    sees a settings object with a valid Deepgram key.
    """
    with patch("src.api.routes.voice.get_settings") as mock_fn:
        settings = MagicMock(spec=Settings)
        settings.DEEPGRAM_API_KEY = "test-deepgram-key-abc123"  # pragma: allowlist secret
        settings.voice_enabled = True
        mock_fn.return_value = settings
        yield settings


@pytest.fixture
def mock_settings_no_deepgram() -> Generator[MagicMock, None, None]:
    """Provide settings without DEEPGRAM_API_KEY (empty string).

    Simulates the default state where voice features are not configured.
    """
    with patch("src.api.routes.voice.get_settings") as mock_fn:
        settings = MagicMock(spec=Settings)
        settings.DEEPGRAM_API_KEY = ""
        settings.voice_enabled = False
        mock_fn.return_value = settings
        yield settings


@pytest.fixture
def mock_httpx_stream() -> Generator[MagicMock, None, None]:
    """Mock httpx.AsyncClient for TTS streaming response.

    Creates a mock chain: AsyncClient() context -> client.stream() context -> response.
    The response yields fake audio bytes to simulate Deepgram TTS output.
    """
    with patch("src.api.routes.voice.httpx.AsyncClient") as mock_client_cls:
        # Build the response mock with async byte iteration
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def fake_aiter_bytes(chunk_size: int = 1024) -> AsyncIterator[bytes]:
            yield b"fake-audio-chunk-1"
            yield b"fake-audio-chunk-2"

        mock_response.aiter_bytes = fake_aiter_bytes
        mock_response.raise_for_status = MagicMock()

        # stream() returns an async context manager yielding the response
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        # The client instance has a .stream() method
        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

        # AsyncClient() returns an async context manager yielding the client instance
        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_client_cls.return_value = mock_client_ctx
        yield mock_client_cls


@pytest.fixture
def mock_deepgram_sdk() -> Generator[dict[str, MagicMock], None, None]:
    """Mock the Deepgram SDK v6 that is lazily imported inside transcribe_stream.

    The v6 SDK uses an async context manager pattern:
        async with deepgram.listen.v1.connect(**options) as dg_ws:
            dg_ws.on(EventType.MESSAGE, callback)
            listen_task = asyncio.create_task(dg_ws.start_listening())
            await dg_ws.send_media(audio_data)
            await dg_ws.send_finalize()

    Returns a dict with keys for each mock component so tests can make
    assertions on the mock objects. The 'connect_kwargs' key stores the
    keyword arguments passed to connect() for assertion in tests.
    """
    # Track connect() kwargs for test assertions
    connect_kwargs: dict[str, object] = {}

    # The dg_ws object returned by the async context manager
    mock_dg_ws = AsyncMock()
    mock_dg_ws.on = MagicMock()
    mock_dg_ws.send_media = AsyncMock()
    mock_dg_ws.send_finalize = AsyncMock()

    # start_listening() returns a coroutine that we wrap in create_task;
    # make it a future that never completes (simulates infinite listen loop)
    async def _noop_listen() -> None:
        # Block forever until cancelled, simulating the real listen loop
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(3600)

    mock_dg_ws.start_listening = _noop_listen

    # listen.v1.connect(**options) is an async context manager
    mock_connect_ctx = MagicMock()

    async def _connect_aenter(self: object) -> AsyncMock:
        return mock_dg_ws

    async def _connect_aexit(
        self: object, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        return None

    mock_connect_ctx.__aenter__ = _connect_aenter
    mock_connect_ctx.__aexit__ = _connect_aexit

    mock_v1 = MagicMock()

    def _connect(**kwargs: object) -> MagicMock:
        connect_kwargs.update(kwargs)
        return mock_connect_ctx

    mock_v1.connect = _connect

    mock_listen = MagicMock()
    mock_listen.v1 = mock_v1

    mock_deepgram_instance = MagicMock()
    mock_deepgram_instance.listen = mock_listen

    mock_async_client_cls = MagicMock(return_value=mock_deepgram_instance)

    # Mock EventType from deepgram.core.events
    mock_event_type = MagicMock()
    mock_event_type.MESSAGE = "message"

    # Create fake modules to inject via sys.modules
    mock_deepgram_module = MagicMock()
    mock_deepgram_module.AsyncDeepgramClient = mock_async_client_cls

    mock_events_module = MagicMock()
    mock_events_module.EventType = mock_event_type

    mock_core_module = MagicMock()
    mock_core_module.events = mock_events_module

    import sys

    with patch.dict(
        sys.modules,
        {
            "deepgram": mock_deepgram_module,
            "deepgram.core": mock_core_module,
            "deepgram.core.events": mock_events_module,
        },
    ):
        yield {
            "dg_ws": mock_dg_ws,
            "client_cls": mock_async_client_cls,
            "event_type": mock_event_type,
            "instance": mock_deepgram_instance,
            "connect_kwargs": connect_kwargs,
        }


# =============================================================================
# Model Validation Tests
# =============================================================================


class TestSpeakRequestModel:
    """Tests for the SpeakRequest Pydantic model."""

    def test_valid_request(self) -> None:
        """SpeakRequest accepts valid text and voice."""
        req = SpeakRequest(text="Hola, como estas?", voice="aura-2-celeste-es")
        assert req.text == "Hola, como estas?"
        assert req.voice == "aura-2-celeste-es"

    def test_default_voice(self) -> None:
        """SpeakRequest defaults to aura-2-nestor-es voice (masculine Hermano persona)."""
        req = SpeakRequest(text="Hola")
        assert req.voice == "aura-2-nestor-es"

    def test_empty_text_rejected(self) -> None:
        """SpeakRequest rejects empty text via min_length=1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SpeakRequest(text="")
        errors = exc_info.value.errors()
        assert any("text" in str(err.get("loc", "")) for err in errors)

    def test_text_max_length_boundary(self) -> None:
        """SpeakRequest accepts text at exactly MAX_TTS_TEXT_LENGTH."""
        long_text = "a" * MAX_TTS_TEXT_LENGTH
        req = SpeakRequest(text=long_text)
        assert len(req.text) == MAX_TTS_TEXT_LENGTH

    def test_text_over_max_length_rejected(self) -> None:
        """SpeakRequest rejects text exceeding MAX_TTS_TEXT_LENGTH."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SpeakRequest(text="a" * (MAX_TTS_TEXT_LENGTH + 1))


# =============================================================================
# Voice Constants Tests
# =============================================================================


class TestVoiceConstants:
    """Tests for voice-related constants and configuration."""

    def test_allowed_voices_is_frozenset(self) -> None:
        """ALLOWED_VOICES should be an immutable frozenset."""
        assert isinstance(ALLOWED_VOICES, frozenset)

    def test_allowed_voices_contains_spanish(self) -> None:
        """ALLOWED_VOICES should contain Spanish voice options."""
        spanish_voices = [v for v in ALLOWED_VOICES if v.endswith("-es")]
        assert len(spanish_voices) >= 1

    def test_allowed_voices_contains_german(self) -> None:
        """ALLOWED_VOICES should contain German voice options."""
        german_voices = [v for v in ALLOWED_VOICES if v.endswith("-de")]
        assert len(german_voices) >= 1

    def test_allowed_voices_contains_french(self) -> None:
        """ALLOWED_VOICES should contain French voice options."""
        french_voices = [v for v in ALLOWED_VOICES if v.endswith("-fr")]
        assert len(french_voices) >= 1

    def test_default_voices_cover_all_languages(self) -> None:
        """DEFAULT_VOICES should have entries for es, de, fr."""
        assert "es" in DEFAULT_VOICES
        assert "de" in DEFAULT_VOICES
        assert "fr" in DEFAULT_VOICES

    def test_default_voices_are_in_allowed(self) -> None:
        """Every default voice must be in the ALLOWED_VOICES set."""
        for lang, voice in DEFAULT_VOICES.items():
            assert voice in ALLOWED_VOICES, (
                f"Default voice {voice} for {lang} not in ALLOWED_VOICES"
            )

    def test_valid_stt_languages_includes_multi(self) -> None:
        """VALID_STT_LANGUAGES should include 'multi' for code-switching."""
        assert "multi" in VALID_STT_LANGUAGES

    def test_valid_stt_languages_includes_app_languages(self) -> None:
        """VALID_STT_LANGUAGES should include es, de, fr."""
        assert "es" in VALID_STT_LANGUAGES
        assert "de" in VALID_STT_LANGUAGES
        assert "fr" in VALID_STT_LANGUAGES

    def test_valid_stt_languages_is_frozenset(self) -> None:
        """VALID_STT_LANGUAGES should be immutable."""
        assert isinstance(VALID_STT_LANGUAGES, frozenset)

    def test_max_tts_text_length_is_2000(self) -> None:
        """MAX_TTS_TEXT_LENGTH should be 2000."""
        assert MAX_TTS_TEXT_LENGTH == 2000


# =============================================================================
# Config Property Tests
# =============================================================================


class TestVoiceConfig:
    """Tests for voice-related configuration properties on Settings."""

    def test_deepgram_key_default_empty(self) -> None:
        """DEEPGRAM_API_KEY defaults to empty string."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SECRET_KEY="test",
        )
        assert settings.DEEPGRAM_API_KEY == ""

    def test_voice_enabled_with_key(self) -> None:
        """voice_enabled returns True when DEEPGRAM_API_KEY is set."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SECRET_KEY="test",
            DEEPGRAM_API_KEY="dg-test-key-123",  # pragma: allowlist secret
        )
        assert settings.voice_enabled is True

    def test_voice_enabled_without_key(self) -> None:
        """voice_enabled returns False when DEEPGRAM_API_KEY is empty."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SECRET_KEY="test",
            DEEPGRAM_API_KEY="",
        )
        assert settings.voice_enabled is False

    def test_deepgram_key_from_environment(self) -> None:
        """DEEPGRAM_API_KEY should be loadable from environment variables."""
        import os

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",  # pragma: allowlist secret
                "SECRET_KEY": "test",
                "DEEPGRAM_API_KEY": "env-dg-key",  # pragma: allowlist secret
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.DEEPGRAM_API_KEY == "env-dg-key"  # pragma: allowlist secret
            assert settings.voice_enabled is True


# =============================================================================
# TTS Endpoint Tests (POST /api/speak)
# =============================================================================


class TestSpeakEndpoint:
    """Tests for POST /api/speak TTS endpoint."""

    async def test_speak_returns_audio(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Valid request returns audio/mpeg streaming response."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola, como estas?", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert len(response.content) > 0

    async def test_speak_returns_cache_control_header(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Response includes Cache-Control: no-cache header."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"

    async def test_speak_default_voice(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Default voice is aura-2-nestor-es when not specified in request."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Buenos dias"},
        )
        assert response.status_code == 200

        # Verify the mock was called with the default voice in the URL
        mock_client_ctx = mock_httpx_stream.return_value
        mock_client_instance = mock_client_ctx.__aenter__.return_value
        mock_client_instance.stream.assert_called_once()
        call_args = mock_client_instance.stream.call_args
        url = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("url", "")
        assert "aura-2-nestor-es" in url

    async def test_speak_sends_text_to_deepgram(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Request text is forwarded to Deepgram API in JSON body."""
        test_text = "Me llamo Carlos"
        response = await async_client.post(
            "/api/speak",
            json={"text": test_text, "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200

        mock_client_ctx = mock_httpx_stream.return_value
        mock_client_instance = mock_client_ctx.__aenter__.return_value
        call_kwargs = mock_client_instance.stream.call_args
        # Check the json body passed to stream()
        json_body = call_kwargs[1].get("json", {}) if call_kwargs[1] else {}
        assert json_body.get("text") == test_text

    async def test_speak_sends_auth_header(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Deepgram API call includes the authorization token header."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200

        mock_client_ctx = mock_httpx_stream.return_value
        mock_client_instance = mock_client_ctx.__aenter__.return_value
        call_kwargs = mock_client_instance.stream.call_args
        headers = call_kwargs[1].get("headers", {}) if call_kwargs[1] else {}
        assert "Token test-deepgram-key-abc123" in headers.get("Authorization", "")

    async def test_speak_empty_text_returns_422(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Empty text returns 422 validation error (Pydantic min_length=1)."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 422

    async def test_speak_missing_text_returns_422(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Missing text field returns 422 validation error."""
        response = await async_client.post(
            "/api/speak",
            json={"voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 422

    async def test_speak_text_too_long_returns_422(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Text over 2000 chars returns 422 validation error."""
        long_text = "a" * (MAX_TTS_TEXT_LENGTH + 1)
        response = await async_client.post(
            "/api/speak",
            json={"text": long_text, "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 422

    async def test_speak_text_at_max_length_returns_200(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Text at exactly MAX_TTS_TEXT_LENGTH is accepted."""
        text = "a" * MAX_TTS_TEXT_LENGTH
        response = await async_client.post(
            "/api/speak",
            json={"text": text, "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200

    async def test_speak_invalid_voice_returns_400(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Invalid voice ID returns 400 with descriptive error."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "nonexistent-voice-id"},
        )
        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
        assert "nonexistent-voice-id" in body["detail"]

    async def test_speak_no_api_key_returns_503(
        self,
        async_client: AsyncClient,
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Returns 503 when DEEPGRAM_API_KEY is not configured."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 503
        body = response.json()
        assert "detail" in body
        assert "not configured" in body["detail"].lower()

    @pytest.mark.parametrize("voice", sorted(ALLOWED_VOICES))
    async def test_speak_all_allowed_voices_accepted(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
        voice: str,
    ) -> None:
        """Every voice in ALLOWED_VOICES should be accepted."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Test", "voice": voice},
        )
        assert response.status_code == 200, f"Voice {voice} was rejected"

    async def test_speak_validation_order_voice_before_key(
        self,
        async_client: AsyncClient,
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Invalid voice check happens before API key check (returns 400, not 503)."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "invalid-voice"},
        )
        # Voice validation runs first in the endpoint code
        assert response.status_code == 400

    async def test_speak_content_disposition_header(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Response includes Content-Disposition: inline header."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-disposition") == "inline"


# =============================================================================
# WebSocket STT Tests (WS /ws/transcribe)
# =============================================================================


class TestTranscribeWebSocket:
    """Tests for WebSocket /ws/transcribe STT endpoint.

    WebSocket tests use the synchronous TestClient which supports
    the websocket_connect() context manager. Starlette raises
    WebSocketDisconnect with a .code attribute when the server
    closes the connection before or after accept.

    B1: All WebSocket tests pass a session_id cookie for authentication.
    """

    def test_unauthenticated_closes_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """No auth cookies closes WebSocket with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=es"):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_session_id_closes_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Invalid session_id cookie (not UUID v4) closes with 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies={"session_id": "not-a-valid-uuid"},
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_language_closes_connection(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Invalid language param closes WebSocket with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=xx", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_language_japanese_closes_connection(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Japanese (ja) is not a supported STT language and should close with 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=ja", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_empty_language_closes_connection(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Empty string language param closes WebSocket with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_no_api_key_closes_connection(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Missing DEEPGRAM_API_KEY closes WebSocket with code 1011."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1011

    def test_no_api_key_default_language_closes_connection(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Default language (multi) still closes with 1011 when no API key."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1011

    @pytest.mark.parametrize("language", ["es", "de", "fr", "multi"])
    def test_valid_language_accepted_with_api_key(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
        language: str,
    ) -> None:
        """Valid languages (es, de, fr, multi) pass initial validation."""
        with test_client.websocket_connect(
            f"/ws/transcribe?language={language}", cookies=ws_cookies
        ) as ws:
            ws.close()

    def test_default_language_is_multi(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """When no language param is provided, default is 'multi'."""
        with test_client.websocket_connect("/ws/transcribe", cookies=ws_cookies) as ws:
            ws.close()

        connect_kwargs = mock_deepgram_sdk["connect_kwargs"]
        assert connect_kwargs["language"] == "multi"

    def test_websocket_accepts_binary_audio(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """WebSocket accepts binary audio data after connection."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01\x02\x03")
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_media.assert_awaited()
        mock_dg_ws.send_finalize.assert_awaited()

    def test_websocket_forwards_language_to_deepgram(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Selected language is passed through to the Deepgram connect() kwargs."""
        with test_client.websocket_connect("/ws/transcribe?language=de", cookies=ws_cookies) as ws:
            ws.close()

        connect_kwargs = mock_deepgram_sdk["connect_kwargs"]
        assert connect_kwargs["language"] == "de"

    def test_websocket_registers_transcript_handler(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Endpoint registers a transcript event handler on the Deepgram connection."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.on.assert_called_once()
        call_args = mock_dg_ws.on.call_args
        assert call_args[0][0] == mock_deepgram_sdk["event_type"].MESSAGE

    def test_websocket_connect_exception_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """When Deepgram connect() raises an exception, server closes with 1011."""
        mock_deepgram_sdk["dg_ws"]  # fixture needed for sys.modules patching

        mock_failing_ctx = MagicMock()

        async def _failing_aenter(self: object) -> None:
            raise ConnectionError("Deepgram connection failed")

        async def _failing_aexit(
            self: object, exc_type: object, exc_val: object, exc_tb: object
        ) -> None:
            return None

        mock_failing_ctx.__aenter__ = _failing_aenter
        mock_failing_ctx.__aexit__ = _failing_aexit

        mock_deepgram_sdk["instance"].listen.v1.connect = MagicMock(return_value=mock_failing_ctx)

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=es", cookies=ws_cookies
            ) as ws:
                ws.receive_json()
        assert exc_info.value.code == 1011

    def test_websocket_passes_model_to_connect(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Deepgram connect() is called with model='nova-3'."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        connect_kwargs = mock_deepgram_sdk["connect_kwargs"]
        assert connect_kwargs["model"] == "nova-3"

    def test_websocket_passes_encoding_to_connect(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Deepgram connect() is called with encoding='linear16' and sample_rate='16000'."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        connect_kwargs = mock_deepgram_sdk["connect_kwargs"]
        assert connect_kwargs["encoding"] == "linear16"
        assert connect_kwargs["sample_rate"] == "16000"


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestVoiceEdgeCases:
    """Edge case tests covering boundary conditions and unusual inputs."""

    async def test_speak_whitespace_only_text_accepted(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Whitespace-only text is accepted (min_length counts whitespace).

        Pydantic's min_length counts whitespace characters, so a single space
        passes the min_length=1 check. The endpoint itself does not strip text.
        """
        response = await async_client.post(
            "/api/speak",
            json={"text": " ", "voice": "aura-2-celeste-es"},
        )
        # Single space passes min_length=1
        assert response.status_code == 200

    async def test_speak_unicode_text_accepted(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """Unicode text (accented characters) is accepted for TTS."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Buenos dias! Como estas tu?", "voice": "aura-2-celeste-es"},
        )
        assert response.status_code == 200

    async def test_speak_german_text_with_german_voice(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """German text with German voice is accepted."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Guten Tag, wie geht es Ihnen?", "voice": "aura-2-elara-de"},
        )
        assert response.status_code == 200

    async def test_speak_french_text_with_french_voice(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
        mock_httpx_stream: MagicMock,
    ) -> None:
        """French text with French voice is accepted."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Bonjour, comment allez-vous?", "voice": "aura-2-agathe-fr"},
        )
        assert response.status_code == 200

    async def test_speak_invalid_json_returns_422(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Invalid JSON body returns 422."""
        response = await async_client.post(
            "/api/speak",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    async def test_speak_voice_case_sensitive(
        self,
        async_client: AsyncClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Voice ID matching is case-sensitive (uppercase variant rejected)."""
        response = await async_client.post(
            "/api/speak",
            json={"text": "Hola", "voice": "AURA-2-CELESTE-ES"},
        )
        assert response.status_code == 400
