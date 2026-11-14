"""Integration tests for WebSocket voice proxy endpoints.

B24: Tests that exercise the WebSocket handshake, message flow lifecycle,
error recovery, authentication rejection, rate limiting, and concurrent
connections for both /ws/transcribe (STT) and /ws/speak (TTS).

STT tests mock the Deepgram SDK; TTS tests replace Gemini TTS synthesis
(src.services.tts.synthesize_pcm) with a fake, so they exercise the full
browser-facing message flow without calling OpenRouter.
"""

import asyncio
import contextlib
import json
import sys
import time
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
from src.api.config import Settings, get_settings
from src.api.routes.voice import HERMANO_VOICE, MAX_TTS_TEXT_LENGTH
from src.services.tts import TTSError
from tests.api.routes.tts_fakes import FAKE_PCM_CHUNKS, FakeSynthesizer
from tests.conftest import CSRF_HEADERS

# Valid guest session UUID for WebSocket authentication
GUEST_SESSION_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create mock authenticated user for integration tests."""
    return AuthenticatedUser(id="user-integ-456", email="integ@example.com")


@pytest.fixture
def ws_cookies() -> dict[str, str]:
    """Cookies dict with a valid guest session_id for WebSocket auth."""
    return {"session_id": GUEST_SESSION_ID}


@pytest.fixture
def voice_app(mock_user: AuthenticatedUser) -> Generator[FastAPI, None, None]:
    """Create FastAPI app with mocked dependencies for voice integration testing.

    Patches external services (LangGraph, Supabase) to prevent real connections.
    Voice-specific mocking (Deepgram SDK, TTS synthesis) is done per-test.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": [], "level": "A1", "language": "es"})

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
    """Create synchronous test client for WebSocket tests."""
    with TestClient(voice_app, headers=CSRF_HEADERS) as client:
        yield client


@pytest.fixture
def mock_settings_with_deepgram() -> Generator[MagicMock, None, None]:
    """Provide settings with DEEPGRAM_API_KEY configured."""
    with patch("src.api.routes.voice.get_settings") as mock_fn:
        settings = MagicMock(spec=Settings)
        settings.DEEPGRAM_API_KEY = "test-deepgram-key-integ"  # pragma: allowlist secret
        settings.voice_enabled = True
        mock_fn.return_value = settings
        yield settings


@pytest.fixture
def mock_settings_no_deepgram() -> Generator[MagicMock, None, None]:
    """Provide settings without DEEPGRAM_API_KEY."""
    with patch("src.api.routes.voice.get_settings") as mock_fn:
        settings = MagicMock(spec=Settings)
        settings.DEEPGRAM_API_KEY = ""
        settings.voice_enabled = False
        mock_fn.return_value = settings
        yield settings


def _make_deepgram_sdk_mocks(
    on_message_side_effect: object = None,
    connect_error: Exception | None = None,
) -> dict[str, MagicMock]:
    """Build Deepgram SDK v6 mock objects and inject them into sys.modules.

    Args:
        on_message_side_effect: Optional side effect for the on() callback.
            If a callable, it will be stored and can be invoked by tests to
            simulate Deepgram sending transcript results.
        connect_error: If set, the async context manager __aenter__ raises
            this exception to simulate a failed Deepgram connection.

    Returns:
        dict with keys: dg_ws, instance, connect_kwargs, on_handler_ref
    """
    connect_kwargs: dict[str, object] = {}

    mock_dg_ws = AsyncMock()
    # Store the registered on_message handler so tests can invoke it
    on_handler_ref: dict[str, object] = {}

    def _on_impl(event_type: str, handler: object) -> None:
        on_handler_ref["handler"] = handler

    mock_dg_ws.on = MagicMock(side_effect=_on_impl)
    mock_dg_ws.send_media = AsyncMock()
    mock_dg_ws.send_finalize = AsyncMock()

    async def _noop_listen() -> None:
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(3600)

    mock_dg_ws.start_listening = _noop_listen

    mock_connect_ctx = MagicMock()

    if connect_error:

        async def _failing_aenter(self: object) -> None:
            raise connect_error

    else:

        async def _failing_aenter(self: object) -> AsyncMock:
            return mock_dg_ws

    async def _connect_aexit(
        self: object, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        return None

    mock_connect_ctx.__aenter__ = _failing_aenter
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

    mock_event_type = MagicMock()
    mock_event_type.MESSAGE = "message"

    mock_deepgram_module = MagicMock()
    mock_deepgram_module.AsyncDeepgramClient = mock_async_client_cls

    mock_events_module = MagicMock()
    mock_events_module.EventType = mock_event_type

    mock_core_module = MagicMock()
    mock_core_module.events = mock_events_module

    return {
        "dg_ws": mock_dg_ws,
        "instance": mock_deepgram_instance,
        "client_cls": mock_async_client_cls,
        "event_type": mock_event_type,
        "connect_kwargs": connect_kwargs,
        "on_handler_ref": on_handler_ref,
        "modules": {
            "deepgram": mock_deepgram_module,
            "deepgram.core": mock_core_module,
            "deepgram.core.events": mock_events_module,
        },
    }


@pytest.fixture
def mock_deepgram_sdk() -> Generator[dict[str, MagicMock], None, None]:
    """Standard Deepgram SDK mock injected into sys.modules."""
    mocks = _make_deepgram_sdk_mocks()
    with patch.dict(sys.modules, mocks["modules"]):
        yield mocks


@pytest.fixture
def mock_deepgram_sdk_failing() -> Generator[dict[str, MagicMock], None, None]:
    """Deepgram SDK mock that raises ConnectionError on connect."""
    mocks = _make_deepgram_sdk_mocks(connect_error=ConnectionError("Deepgram unreachable"))
    with patch.dict(sys.modules, mocks["modules"]):
        yield mocks


# =============================================================================
# STT WebSocket Connection Lifecycle Tests
# =============================================================================


class TestSTTWebSocketLifecycle:
    """Tests for /ws/transcribe connection lifecycle: connect, exchange, close."""

    def test_connect_exchange_audio_and_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Full lifecycle: connect -> send audio bytes -> client-initiated close."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            # Send multiple audio frames
            ws.send_bytes(b"\x00\x01\x02\x03")
            ws.send_bytes(b"\x04\x05\x06\x07")
            ws.send_bytes(b"\x08\x09\x0a\x0b")
            ws.close()

        # Verify all audio was forwarded to Deepgram
        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        assert mock_dg_ws.send_media.await_count == 3
        mock_dg_ws.send_finalize.assert_awaited()

    def test_connect_and_immediate_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Connect and immediately close without sending any audio."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        # send_media should not have been called
        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_media.assert_not_awaited()
        # send_finalize should still be called during cleanup
        mock_dg_ws.send_finalize.assert_awaited()

    def test_multiple_sequential_connections(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Multiple sequential connections each complete their lifecycle cleanly."""
        for i in range(3):
            with test_client.websocket_connect(
                "/ws/transcribe?language=es", cookies=ws_cookies
            ) as ws:
                ws.send_bytes(f"audio-{i}".encode())
                ws.close()

    def test_single_byte_audio_frame_forwarded(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """A single-byte audio frame is forwarded to Deepgram without error."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x42")
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_media.assert_awaited_once_with(b"\x42")


# =============================================================================
# STT WebSocket Authentication Tests
# =============================================================================


class TestSTTWebSocketAuth:
    """Tests for /ws/transcribe authentication enforcement."""

    def test_no_cookies_rejects_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Connection without any auth cookies is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=es"):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_uuid_session_rejects_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Connection with malformed session_id is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies={"session_id": "not-a-uuid"},
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_empty_session_id_rejects_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Connection with empty session_id cookie is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies={"session_id": ""},
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_jwt_cookie_authenticates_successfully(
        self,
        test_client: TestClient,
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Connection with valid JWT sb-access-token cookie is accepted."""
        import jwt as pyjwt

        token = pyjwt.encode(
            {"sub": "user-jwt-789", "exp": int(time.time()) + 3600},
            "test-secret",
            algorithm="HS256",
        )
        # Mock server-side JWT verification to accept test tokens
        with patch(
            "src.api.routes.voice._verify_jwt_via_supabase",
            return_value="user-jwt-789",
        ):
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies={"sb-access-token": token},
            ) as ws:
                ws.close()

    def test_jwt_without_sub_claim_falls_back_to_session(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """JWT without 'sub' claim falls back to session_id cookie for auth."""
        import jwt as pyjwt

        # JWT without sub claim -- should not authenticate via JWT path
        token = pyjwt.encode(
            {"email": "test@example.com", "exp": int(time.time()) + 3600},
            "test-secret",
            algorithm="HS256",
        )
        # Mock server-side verification to return None (no sub → no user_id)
        cookies = {"sb-access-token": token, **ws_cookies}
        with patch(
            "src.api.routes.voice._verify_jwt_via_supabase",
            return_value=None,
        ):
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies=cookies,
            ) as ws:
                ws.close()

    def test_jwt_without_sub_and_no_session_rejects(
        self,
        test_client: TestClient,
    ) -> None:
        """JWT without 'sub' and no session_id falls through to rejection."""
        import jwt as pyjwt

        token = pyjwt.encode(
            {"email": "test@example.com", "exp": int(time.time()) + 3600},
            "test-secret",
            algorithm="HS256",
        )
        # Mock server-side verification to return None (invalid token)
        with patch(
            "src.api.routes.voice._verify_jwt_via_supabase",
            return_value=None,
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/transcribe?language=es",
                    cookies={"sb-access-token": token},
                ):
                    pass  # pragma: no cover
            assert exc_info.value.code == 1008

    def test_malformed_jwt_falls_back_to_session(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Malformed JWT token falls back to session_id cookie for auth."""
        # Mock server-side verification to return None (malformed token)
        cookies = {"sb-access-token": "not-a-valid-jwt", **ws_cookies}
        with patch(
            "src.api.routes.voice._verify_jwt_via_supabase",
            return_value=None,
        ):
            with test_client.websocket_connect(
                "/ws/transcribe?language=es",
                cookies=cookies,
            ) as ws:
                ws.close()


# =============================================================================
# STT WebSocket Error Recovery Tests
# =============================================================================


class TestSTTWebSocketErrorRecovery:
    """Tests for /ws/transcribe error handling and recovery scenarios."""

    def test_deepgram_connect_failure_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk_failing: dict[str, MagicMock],
    ) -> None:
        """When Deepgram connection fails, server closes with 1011."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=es", cookies=ws_cookies
            ) as ws:
                # Server should close the connection after failed Deepgram connect
                ws.receive_json()
        assert exc_info.value.code == 1011

    def test_no_api_key_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Missing API key closes WebSocket with code 1011 before accept."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1011

    def test_invalid_language_closes_with_1008(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Invalid language parameter closes WebSocket with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/transcribe?language=zz", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_os_error_during_stt_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """OSError during STT connection results in close code 1011."""
        mocks = _make_deepgram_sdk_mocks(connect_error=OSError("Network unreachable"))
        with patch.dict(sys.modules, mocks["modules"]):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/transcribe?language=es", cookies=ws_cookies
                ) as ws:
                    ws.receive_json()
            assert exc_info.value.code == 1011

    def test_send_finalize_exception_suppressed(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Exception in send_finalize during cleanup is suppressed gracefully."""
        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_finalize = AsyncMock(side_effect=RuntimeError("finalize failed"))

        # Should not raise despite send_finalize failure
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()


# =============================================================================
# STT WebSocket Message Forwarding Tests
# =============================================================================


class TestSTTMessageForwarding:
    """Tests for audio data forwarding from client to Deepgram STT."""

    def test_binary_audio_forwarded_to_deepgram(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Binary audio frames are forwarded via send_media to Deepgram."""
        audio_frames = [b"\x00" * 320, b"\x01" * 320, b"\x02" * 320]

        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            for frame in audio_frames:
                ws.send_bytes(frame)
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        assert mock_dg_ws.send_media.await_count == len(audio_frames)

        # Verify the actual bytes were forwarded
        for i, call in enumerate(mock_dg_ws.send_media.call_args_list):
            assert call[0][0] == audio_frames[i]

    def test_large_audio_frame_forwarded(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Large audio frames (simulating longer audio segments) are forwarded."""
        large_frame = b"\xff" * 16384  # 16KB audio frame

        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(large_frame)
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_media.assert_awaited_once_with(large_frame)

    def test_finalize_sent_on_disconnect(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """send_finalize is called during cleanup when client disconnects."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_finalize.assert_awaited_once()

    def test_language_forwarded_to_deepgram_connect(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """The language parameter is passed through to Deepgram connect kwargs."""
        with test_client.websocket_connect("/ws/transcribe?language=fr", cookies=ws_cookies) as ws:
            ws.close()

        assert mock_deepgram_sdk["connect_kwargs"]["language"] == "fr"

    def test_deepgram_connect_model_and_encoding(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Deepgram is connected with nova-3 model and linear16 encoding."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        kwargs = mock_deepgram_sdk["connect_kwargs"]
        assert kwargs["model"] == "nova-3"
        assert kwargs["encoding"] == "linear16"
        assert kwargs["sample_rate"] == "16000"

    def test_transcript_handler_registered(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """A transcript event handler is registered after connect."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        # The on_handler_ref should have been populated by our mock
        assert "handler" in mock_deepgram_sdk["on_handler_ref"]

    @pytest.mark.parametrize("language", ["es", "de", "fr", "multi"])
    def test_all_valid_languages_connect_successfully(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
        language: str,
    ) -> None:
        """All supported STT languages connect without error."""
        with test_client.websocket_connect(
            f"/ws/transcribe?language={language}", cookies=ws_cookies
        ) as ws:
            ws.close()

        assert mock_deepgram_sdk["connect_kwargs"]["language"] == language

    def test_deepgram_api_key_passed_to_client(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """The Deepgram API key from settings is passed to AsyncDeepgramClient."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.close()

        mock_deepgram_sdk["client_cls"].assert_called_once()
        call_kwargs = mock_deepgram_sdk["client_cls"].call_args
        assert call_kwargs[1].get("api_key") == "test-deepgram-key-integ"


# =============================================================================
# TTS WebSocket Tests (/ws/speak, Gemini TTS via OpenRouter)
# =============================================================================


@pytest.fixture
def mock_tts() -> Generator[FakeSynthesizer, None, None]:
    """Replace Gemini TTS synthesis with a fake that yields fixed PCM chunks."""
    fake = FakeSynthesizer()
    with patch("src.api.routes.voice.synthesize_pcm", fake):
        yield fake


@pytest.fixture
def mock_tts_failing() -> Generator[FakeSynthesizer, None, None]:
    """Replace Gemini TTS synthesis with a fake that fails like an upstream error."""
    fake = FakeSynthesizer(error=TTSError("OpenRouter TTS returned HTTP 503"))
    with patch("src.api.routes.voice.synthesize_pcm", fake):
        yield fake


def _receive_chunk_audio(ws: object) -> list[bytes]:
    """Read binary frames until the Flushed message that ends one text chunk."""
    frames: list[bytes] = []
    while True:
        message = ws.receive()  # type: ignore[attr-defined]
        if message.get("bytes") is not None:
            frames.append(message["bytes"])
            continue
        assert json.loads(message["text"]) == {"type": "Flushed"}
        return frames


class TestTTSWebSocketLifecycle:
    """Tests for /ws/speak connection lifecycle: connect, exchange, close."""

    def test_text_streams_pcm_frames_then_flushed(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Full lifecycle: text in, PCM frames out, Flushed, then close."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "Hola amigo"}))
            assert _receive_chunk_audio(ws) == list(FAKE_PCM_CHUNKS)
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Hola amigo", "Kore")]

    def test_connect_and_immediate_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Connect and close without text: nothing is synthesized."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == []

    def test_default_voice_used_when_not_specified(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Without a voice query param, the Hermano voice is used."""
        with test_client.websocket_connect("/ws/speak", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "Hola"}))
            _receive_chunk_audio(ws)
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Hola", HERMANO_VOICE)]

    def test_works_without_deepgram_key(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_no_deepgram: MagicMock,
        mock_tts: FakeSynthesizer,
    ) -> None:
        """TTS no longer depends on Deepgram: it uses the OpenRouter key."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "Hola"}))
            assert _receive_chunk_audio(ws) == list(FAKE_PCM_CHUNKS)
            ws.send_text(json.dumps({"type": "close"}))


class TestTTSWebSocketAuth:
    """Tests for /ws/speak authentication enforcement."""

    def test_no_cookies_rejects_with_1008(self, test_client: TestClient) -> None:
        """Connection without auth cookies is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/speak?voice=Kore"):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_session_id_rejects_with_1008(self, test_client: TestClient) -> None:
        """Connection with invalid session_id is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/speak?voice=Kore", cookies={"session_id": "bad-uuid"}
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    @pytest.mark.parametrize("voice", ["invalid-voice-id", "aura-2-nestor-es", "achird"])
    def test_invalid_voice_rejects_with_1008(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        voice: str,
    ) -> None:
        """Unknown voices, old Deepgram IDs and wrong-case names are rejected."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(f"/ws/speak?voice={voice}", cookies=ws_cookies):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_jwt_cookie_authenticates_tts(
        self,
        test_client: TestClient,
        mock_settings_with_deepgram: MagicMock,
        mock_tts: FakeSynthesizer,
    ) -> None:
        """TTS WebSocket also accepts JWT sb-access-token cookie.

        The mocked settings report Supabase as configured, which routes the
        JWT through _verify_jwt_via_supabase (patched below).
        """
        import jwt as pyjwt

        token = pyjwt.encode(
            {"sub": "user-tts-jwt", "exp": int(time.time()) + 3600},
            "test-secret",
            algorithm="HS256",
        )
        with patch("src.api.routes.voice._verify_jwt_via_supabase", return_value="user-tts-jwt"):
            with test_client.websocket_connect(
                "/ws/speak?voice=Kore", cookies={"sb-access-token": token}
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))


class TestTTSMessageFlow:
    """Tests for /ws/speak text-to-audio message flow."""

    def test_multiple_chunks_each_end_with_flushed(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Each text chunk is synthesized in order and ends with its own Flushed."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            for text in ["Primero.", "Segundo.", "Tercero."]:
                ws.send_text(json.dumps({"text": text}))
                assert _receive_chunk_audio(ws) == list(FAKE_PCM_CHUNKS)
            ws.send_text(json.dumps({"type": "close"}))

        assert [text for text, _ in mock_tts.calls] == ["Primero.", "Segundo.", "Tercero."]

    @pytest.mark.parametrize("text", ["", "   ", "a" * (MAX_TTS_TEXT_LENGTH + 1)])
    def test_empty_or_too_long_text_skipped(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
        text: str,
    ) -> None:
        """Empty, whitespace-only and over-long text never reaches synthesis."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": text}))
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == []

    def test_text_at_max_length_accepted(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Text at exactly MAX_TTS_TEXT_LENGTH is synthesized."""
        text = "a" * MAX_TTS_TEXT_LENGTH
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": text}))
            _receive_chunk_audio(ws)
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [(text, "Kore")]

    def test_text_is_stripped_before_synthesis(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Surrounding whitespace is trimmed before the text is sent to Gemini."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "  Hola  "}))
            _receive_chunk_audio(ws)
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Hola", "Kore")]


class TestTTSWebSocketErrorRecovery:
    """Tests for /ws/speak error handling."""

    def test_synthesis_failure_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts_failing: FakeSynthesizer,
    ) -> None:
        """An OpenRouter TTS failure closes the socket with 1011 so the browser falls back."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "Hola"}))
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_bytes()
        assert exc_info.value.code == 1011

    def test_malformed_json_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """A non-JSON client message closes the socket with 1011."""
        with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
            ws.send_text("not-json")
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_bytes()
        assert exc_info.value.code == 1011
        assert mock_tts.calls == []


class TestTTSWebSocketRateLimiting:
    """Tests for per-connection message rate limiting on /ws/speak."""

    def test_rate_limit_exceeded_returns_error_message(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """When the message rate limit is exceeded, the server sends an error JSON."""
        with patch("src.api.routes.voice.WebSocketMessageRateLimiter") as mock_limiter_cls:
            mock_limiter_cls.return_value.check = MagicMock(side_effect=[True, False])

            with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
                ws.send_text(json.dumps({"text": "Hola"}))
                _receive_chunk_audio(ws)
                ws.send_text(json.dumps({"text": "Second"}))
                error = json.loads(ws.receive_text())
                assert error["code"] == "RATE_LIMITED"
                assert "Rate limit" in error["error"]
                ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Hola", "Kore")]

    def test_rate_limited_message_not_synthesized(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Rate-limited messages are never sent to OpenRouter."""
        with patch("src.api.routes.voice.WebSocketMessageRateLimiter") as mock_limiter_cls:
            mock_limiter_cls.return_value.check = MagicMock(return_value=False)

            with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
                ws.send_text(json.dumps({"text": "Should be blocked"}))
                assert json.loads(ws.receive_text())["code"] == "RATE_LIMITED"
                ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == []


class TestTTSWebSocketVoiceParam:
    """Tests for voice parameter validation on /ws/speak."""

    @pytest.mark.parametrize("voice", ["Achird", "Kore", "Puck", "Charon", "Sulafat"])
    def test_gemini_voice_passed_to_synthesis(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
        voice: str,
    ) -> None:
        """Valid Gemini voices are accepted and forwarded to synthesis."""
        with test_client.websocket_connect(f"/ws/speak?voice={voice}", cookies=ws_cookies) as ws:
            ws.send_text(json.dumps({"text": "Hola"}))
            _receive_chunk_audio(ws)
            ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Hola", voice)]


# =============================================================================
# Concurrent Connection Tests
# =============================================================================


class TestConcurrentConnections:
    """Tests for handling multiple WebSocket connections."""

    def test_sequential_stt_connections_independent(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Multiple sequential STT connections operate independently."""
        # First connection with Spanish
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()

        # Second connection with German
        with test_client.websocket_connect("/ws/transcribe?language=de", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x02\x03")
            ws.close()

        # Both connections should have completed successfully
        # (no exceptions means success)

    def test_sequential_tts_connections_independent(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_tts: FakeSynthesizer,
    ) -> None:
        """Multiple sequential TTS connections operate independently."""
        for voice in ["Achird", "Kore"]:
            with test_client.websocket_connect(
                f"/ws/speak?voice={voice}", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Test"}))
                _receive_chunk_audio(ws)
                ws.send_text(json.dumps({"type": "close"}))

        assert mock_tts.calls == [("Test", "Achird"), ("Test", "Kore")]

    def test_failed_connection_does_not_affect_next(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """A failed STT connection does not prevent subsequent connections."""
        # First connection fails (Deepgram unreachable)
        failing_mocks = _make_deepgram_sdk_mocks(connect_error=ConnectionError("Deepgram down"))
        with patch.dict(sys.modules, failing_mocks["modules"]):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/transcribe?language=es", cookies=ws_cookies
                ) as ws:
                    ws.receive_json()
            assert exc_info.value.code == 1011

        # Second connection succeeds (Deepgram back up)
        working_mocks = _make_deepgram_sdk_mocks()
        with patch.dict(sys.modules, working_mocks["modules"]):
            with test_client.websocket_connect(
                "/ws/transcribe?language=es", cookies=ws_cookies
            ) as ws:
                ws.send_bytes(b"\x00\x01")
                ws.close()

    def test_failed_tts_connection_does_not_affect_next(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """A failed TTS synthesis does not prevent subsequent TTS connections."""
        failing = FakeSynthesizer(error=TTSError("OpenRouter TTS returned HTTP 503"))
        with patch("src.api.routes.voice.synthesize_pcm", failing):
            with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
                ws.send_text(json.dumps({"text": "Hola"}))
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_bytes()
            assert exc_info.value.code == 1011

        working = FakeSynthesizer()
        with patch("src.api.routes.voice.synthesize_pcm", working):
            with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
                ws.send_text(json.dumps({"text": "Back up"}))
                assert _receive_chunk_audio(ws) == list(FAKE_PCM_CHUNKS)
                ws.send_text(json.dumps({"type": "close"}))

    def test_mixed_stt_and_tts_sequential(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """STT and TTS connections can be opened sequentially without interference."""
        # STT connection
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()

        # TTS connection
        with patch("src.api.routes.voice.synthesize_pcm", FakeSynthesizer()):
            with test_client.websocket_connect("/ws/speak?voice=Kore", cookies=ws_cookies) as ws:
                ws.send_text(json.dumps({"text": "Hola"}))
                _receive_chunk_audio(ws)
                ws.send_text(json.dumps({"type": "close"}))


# =============================================================================
# Cleanup and Resource Management Tests
# =============================================================================


class TestCleanupOnDisconnect:
    """Tests for proper resource cleanup when WebSocket connections close."""

    def test_stt_listen_task_cancelled_on_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """The Deepgram listen task is cancelled when the client disconnects."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            ws.send_bytes(b"\x00\x01\x02")
            ws.close()

        # send_finalize should have been called in the finally block
        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_finalize.assert_awaited_once()

    def test_stt_cleanup_after_many_frames(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Cleanup runs correctly after processing many audio frames."""
        with test_client.websocket_connect("/ws/transcribe?language=es", cookies=ws_cookies) as ws:
            for i in range(20):
                ws.send_bytes(bytes([i % 256]) * 320)
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        assert mock_dg_ws.send_media.await_count == 20
        mock_dg_ws.send_finalize.assert_awaited_once()
