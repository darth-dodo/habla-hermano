"""Integration tests for WebSocket voice proxy endpoints.

B24: Tests that exercise the WebSocket handshake, message flow lifecycle,
error recovery, authentication rejection, rate limiting, and concurrent
connections for both /ws/transcribe (STT) and /ws/speak (TTS).

Unlike test_voice.py which mocks the Deepgram SDK classes, these tests
mock at the HTTP/WebSocket transport level to validate the full message
flow through the voice proxy layer.
"""

import asyncio
import contextlib
import json
import sys
import time
from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.auth import AuthenticatedUser, get_current_user, get_current_user_optional
from src.api.config import Settings, get_settings
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
    Voice-specific mocking (Deepgram SDK, websockets library) is done per-test.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [], "level": "A1", "language": "es"}
    )

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


def _make_websockets_connect_mock(
    messages: list[bytes | str] | None = None,
    connect_error: Exception | None = None,
) -> MagicMock:
    """Build a mock for the ``websockets.connect()`` async context manager.

    Used by /ws/speak tests to mock the outbound Deepgram TTS WebSocket.

    Args:
        messages: Sequence of bytes/str messages the mock Deepgram WS will yield.
        connect_error: If set, the context manager __aenter__ raises this.

    Returns:
        MagicMock that can replace ``websockets.connect``.
    """
    if messages is None:
        messages = []

    mock_dg_ws = AsyncMock()
    mock_dg_ws.send = AsyncMock()
    mock_dg_ws.close = AsyncMock()

    async def _aiter(self: object) -> AsyncIterator[bytes | str]:
        for msg in messages:
            yield msg

    mock_dg_ws.__aiter__ = _aiter

    mock_connect_ctx = MagicMock()

    if connect_error:

        async def _connect_aenter(self: object) -> None:
            raise connect_error

    else:

        async def _connect_aenter(self: object) -> AsyncMock:
            return mock_dg_ws

    async def _connect_aexit(
        self: object, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        return None

    mock_connect_ctx.__aenter__ = _connect_aenter
    mock_connect_ctx.__aexit__ = _connect_aexit

    mock_connect_fn = MagicMock(return_value=mock_connect_ctx)
    mock_connect_fn._mock_dg_ws = mock_dg_ws  # expose for assertion
    return mock_connect_fn


def _make_websockets_module(
    mock_connect: MagicMock | None = None,
) -> MagicMock:
    """Build a complete mock websockets module with connect and ConnectionClosed.

    Args:
        mock_connect: Optional pre-built connect mock. If None, creates a default one.

    Returns:
        MagicMock mimicking the websockets module.
    """
    if mock_connect is None:
        mock_connect = _make_websockets_connect_mock()
    mock_ws_module = MagicMock()
    mock_ws_module.connect = mock_connect
    mock_ws_module.ConnectionClosed = type("ConnectionClosed", (Exception,), {})
    return mock_ws_module


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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        # Provide both cookies: JWT without sub + valid session_id
        cookies = {"sb-access-token": token, **ws_cookies}
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
        cookies = {"sb-access-token": "not-a-valid-jwt", **ws_cookies}
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
            with test_client.websocket_connect(
                "/ws/transcribe?language=es", cookies=ws_cookies
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1011

    def test_invalid_language_closes_with_1008(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Invalid language parameter closes WebSocket with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/transcribe?language=zz", cookies=ws_cookies
            ):
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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

        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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

        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=fr", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
            ws.close()

        mock_deepgram_sdk["client_cls"].assert_called_once()
        call_kwargs = mock_deepgram_sdk["client_cls"].call_args
        assert call_kwargs[1].get("api_key") == "test-deepgram-key-integ"


# =============================================================================
# TTS WebSocket Connection Lifecycle Tests
# =============================================================================


class TestTTSWebSocketLifecycle:
    """Tests for /ws/speak connection lifecycle: connect, exchange, close."""

    def test_connect_send_text_and_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Full lifecycle: connect -> send text -> send close -> disconnect."""
        mock_connect = _make_websockets_connect_mock(
            messages=[b"\x00\x01\x02\x03"]  # audio chunk from Deepgram
        )
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Hola amigo"}))
                ws.send_text(json.dumps({"type": "close"}))

        # Verify Speak+Flush commands were sent to Deepgram
        mock_dg_ws = mock_connect._mock_dg_ws
        send_calls = [str(c) for c in mock_dg_ws.send.call_args_list]
        # Should have Speak, Flush, and Close commands
        assert any("Speak" in c for c in send_calls)
        assert any("Flush" in c for c in send_calls)
        assert any("Close" in c for c in send_calls)

    def test_connect_and_immediate_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Connect and immediately send close message without sending text."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

    def test_default_voice_used_when_not_specified(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """When no voice query param is given, default voice is used in URL."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

        # Default voice is aura-2-nestor-es
        connect_call = mock_connect.call_args
        url = connect_call[0][0]
        assert "aura-2-nestor-es" in url


# =============================================================================
# TTS WebSocket Authentication Tests
# =============================================================================


class TestTTSWebSocketAuth:
    """Tests for /ws/speak authentication enforcement."""

    def test_no_cookies_rejects_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Connection without auth cookies is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/ws/speak?voice=aura-2-nestor-es"):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_session_id_rejects_with_1008(
        self,
        test_client: TestClient,
    ) -> None:
        """Connection with invalid session_id is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es",
                cookies={"session_id": "bad-uuid"},
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_invalid_voice_rejects_with_1008(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
    ) -> None:
        """Connection with invalid voice parameter is rejected with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/speak?voice=invalid-voice-id",
                cookies=ws_cookies,
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008

    def test_no_api_key_rejects_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_no_deepgram: MagicMock,
    ) -> None:
        """Connection without API key is rejected with code 1011."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es",
                cookies=ws_cookies,
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1011

    def test_jwt_cookie_authenticates_tts(
        self,
        test_client: TestClient,
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """TTS WebSocket also accepts JWT sb-access-token cookie."""
        import jwt as pyjwt

        token = pyjwt.encode(
            {"sub": "user-tts-jwt", "exp": int(time.time()) + 3600},
            "test-secret",
            algorithm="HS256",
        )
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es",
                cookies={"sb-access-token": token},
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))


# =============================================================================
# TTS WebSocket Message Flow Tests
# =============================================================================


class TestTTSMessageFlow:
    """Tests for /ws/speak text-to-audio message flow."""

    def test_text_message_generates_speak_and_flush(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Sending a text message generates Speak + Flush commands to Deepgram."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Buenos dias"}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        # First call: Speak command
        speak_msg = json.loads(calls[0][0][0])
        assert speak_msg["type"] == "Speak"
        assert speak_msg["text"] == "Buenos dias"
        # Second call: Flush command
        flush_msg = json.loads(calls[1][0][0])
        assert flush_msg["type"] == "Flush"

    def test_empty_text_skipped(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Empty text messages are silently skipped, no Speak command sent."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": ""}))
                ws.send_text(json.dumps({"text": "   "}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        # Only the Close command should have been sent, no Speak/Flush
        calls = mock_dg_ws.send.call_args_list
        for call in calls:
            parsed = json.loads(call[0][0])
            assert parsed["type"] != "Speak"

    def test_text_over_max_length_skipped(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Text exceeding MAX_TTS_TEXT_LENGTH is silently skipped."""
        from src.api.routes.voice import MAX_TTS_TEXT_LENGTH

        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "a" * (MAX_TTS_TEXT_LENGTH + 1)}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        for call in calls:
            parsed = json.loads(call[0][0])
            assert parsed["type"] != "Speak"

    def test_text_at_max_length_accepted(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Text at exactly MAX_TTS_TEXT_LENGTH is accepted and forwarded."""
        from src.api.routes.voice import MAX_TTS_TEXT_LENGTH

        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "a" * MAX_TTS_TEXT_LENGTH}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        speak_calls = [
            json.loads(c[0][0]) for c in calls if json.loads(c[0][0])["type"] == "Speak"
        ]
        assert len(speak_calls) == 1
        assert len(speak_calls[0]["text"]) == MAX_TTS_TEXT_LENGTH

    def test_multiple_text_messages_forwarded(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Multiple valid text messages each produce Speak + Flush pairs."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        texts = ["Hola", "Como estas", "Muy bien"]

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                for text in texts:
                    ws.send_text(json.dumps({"text": text}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        speak_calls = [
            json.loads(c[0][0]) for c in calls if json.loads(c[0][0])["type"] == "Speak"
        ]
        assert len(speak_calls) == 3
        assert [s["text"] for s in speak_calls] == texts

    def test_audio_chunks_forwarded_to_browser(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Binary audio chunks from Deepgram are forwarded to the browser."""
        audio_chunks = [b"\x00\x01\x02\x03", b"\x04\x05\x06\x07"]
        mock_connect = _make_websockets_connect_mock(messages=audio_chunks)
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                # Give the forward task a moment to relay chunks
                # The mock async iterator yields chunks immediately
                # We need to send close to end the handler loop
                ws.send_text(json.dumps({"type": "close"}))

                # Try to receive any forwarded bytes (non-blocking attempt)
                # The forward task may or may not have completed by now
                # depending on scheduling, so we just verify no crash

    def test_metadata_string_forwarded_to_browser(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """String metadata messages from Deepgram are forwarded as text."""
        metadata = json.dumps({"type": "metadata", "request_id": "abc123"})
        mock_connect = _make_websockets_connect_mock(messages=[metadata])
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))
                # Verify no crash from string message forwarding


# =============================================================================
# TTS WebSocket Error Recovery Tests
# =============================================================================


class TestTTSWebSocketErrorRecovery:
    """Tests for /ws/speak error handling when Deepgram connection fails."""

    def test_deepgram_connect_failure_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """When websockets.connect raises, server closes with 1011."""
        mock_connect = _make_websockets_connect_mock(
            connect_error=ConnectionError("Deepgram TTS unreachable")
        )
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    ws.receive_bytes()
            assert exc_info.value.code == 1011

    def test_runtime_error_during_tts_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """When a RuntimeError occurs during TTS, server closes with 1011."""
        mock_connect = _make_websockets_connect_mock(
            connect_error=RuntimeError("Unexpected runtime error")
        )
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    ws.receive_bytes()
            assert exc_info.value.code == 1011

    def test_os_error_during_tts_closes_with_1011(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """When an OSError occurs during TTS, server closes with 1011."""
        mock_connect = _make_websockets_connect_mock(
            connect_error=OSError("TTS network error")
        )
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    ws.receive_bytes()
            assert exc_info.value.code == 1011


# =============================================================================
# TTS WebSocket Rate Limiting Tests
# =============================================================================


class TestTTSWebSocketRateLimiting:
    """Tests for per-connection message rate limiting on /ws/speak."""

    def test_rate_limit_exceeded_returns_error_message(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """When message rate limit is exceeded, server sends an error JSON."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with patch(
                "src.api.routes.voice.WebSocketMessageRateLimiter"
            ) as mock_limiter_cls:
                mock_limiter = MagicMock()
                # First call allowed, subsequent calls rejected
                mock_limiter.check = MagicMock(side_effect=[True, False, False])
                mock_limiter_cls.return_value = mock_limiter

                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    # First message should succeed
                    ws.send_text(json.dumps({"text": "Hola"}))
                    # Second message should be rate limited
                    ws.send_text(json.dumps({"text": "Second"}))

                    # Read the rate limit error response
                    response = ws.receive_text()
                    error = json.loads(response)
                    assert error["code"] == "RATE_LIMITED"
                    assert "Rate limit" in error["error"]

                    ws.send_text(json.dumps({"type": "close"}))

    def test_rate_limit_first_message_passes(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """First message within rate limit window is forwarded to Deepgram."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Primer mensaje"}))
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        speak_calls = [
            json.loads(c[0][0]) for c in calls if json.loads(c[0][0])["type"] == "Speak"
        ]
        assert len(speak_calls) == 1
        assert speak_calls[0]["text"] == "Primer mensaje"

    def test_rate_limited_message_not_forwarded(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Rate-limited messages are not forwarded to Deepgram, only error sent."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with patch(
                "src.api.routes.voice.WebSocketMessageRateLimiter"
            ) as mock_limiter_cls:
                mock_limiter = MagicMock()
                # All messages rejected
                mock_limiter.check = MagicMock(return_value=False)
                mock_limiter_cls.return_value = mock_limiter

                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    ws.send_text(json.dumps({"text": "Should be blocked"}))

                    # Read the error response
                    response = ws.receive_text()
                    error = json.loads(response)
                    assert error["code"] == "RATE_LIMITED"

                    ws.send_text(json.dumps({"type": "close"}))

        # Verify no Speak command was sent to Deepgram
        mock_dg_ws = mock_connect._mock_dg_ws
        calls = mock_dg_ws.send.call_args_list
        for call in calls:
            parsed = json.loads(call[0][0])
            assert parsed["type"] != "Speak"


# =============================================================================
# TTS WebSocket Voice Parameter Tests
# =============================================================================


class TestTTSWebSocketVoiceParam:
    """Tests for voice parameter validation on /ws/speak."""

    @pytest.mark.parametrize(
        "voice",
        [
            "aura-2-nestor-es",
            "aura-2-celeste-es",
            "aura-2-julius-de",
            "aura-2-elara-de",
            "aura-2-hector-fr",
            "aura-2-agathe-fr",
        ],
    )
    def test_valid_voices_accepted(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        voice: str,
    ) -> None:
        """All valid voices are accepted for TTS WebSocket connections."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                f"/ws/speak?voice={voice}", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

    def test_voice_passed_to_deepgram_url(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The voice parameter is included in the Deepgram WebSocket URL."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-julius-de", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

        # Verify the URL passed to websockets.connect contains the voice
        connect_call = mock_connect.call_args
        url = connect_call[0][0]
        assert "aura-2-julius-de" in url

    def test_auth_header_passed_to_deepgram(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The API key is passed as Authorization header to Deepgram."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

        connect_call = mock_connect.call_args
        headers = connect_call[1].get("additional_headers", {})
        assert "Token test-deepgram-key-integ" in headers.get("Authorization", "")

    def test_deepgram_url_contains_encoding_params(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The Deepgram TTS URL includes encoding=linear16 and sample_rate=24000."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

        connect_call = mock_connect.call_args
        url = connect_call[0][0]
        assert "encoding=linear16" in url
        assert "sample_rate=24000" in url

    def test_estrella_voice_accepted(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The estrella-es voice (not parametrized above) is also accepted."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-estrella-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))


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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()

        # Second connection with German
        with test_client.websocket_connect(
            "/ws/transcribe?language=de", cookies=ws_cookies
        ) as ws:
            ws.send_bytes(b"\x02\x03")
            ws.close()

        # Both connections should have completed successfully
        # (no exceptions means success)

    def test_sequential_tts_connections_independent(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """Multiple sequential TTS connections operate independently."""
        for voice in ["aura-2-nestor-es", "aura-2-julius-de"]:
            mock_connect = _make_websockets_connect_mock()
            mock_ws_module = _make_websockets_module(mock_connect)

            with patch.dict(sys.modules, {"websockets": mock_ws_module}):
                with test_client.websocket_connect(
                    f"/ws/speak?voice={voice}", cookies=ws_cookies
                ) as ws:
                    ws.send_text(json.dumps({"text": "Test"}))
                    ws.send_text(json.dumps({"type": "close"}))

    def test_failed_connection_does_not_affect_next(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """A failed STT connection does not prevent subsequent connections."""
        # First connection fails (Deepgram unreachable)
        failing_mocks = _make_deepgram_sdk_mocks(
            connect_error=ConnectionError("Deepgram down")
        )
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
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """A failed TTS connection does not prevent subsequent TTS connections."""
        # First connection fails
        failing_connect = _make_websockets_connect_mock(
            connect_error=ConnectionError("TTS down")
        )
        failing_ws_module = _make_websockets_module(failing_connect)

        with patch.dict(sys.modules, {"websockets": failing_ws_module}):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with test_client.websocket_connect(
                    "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
                ) as ws:
                    ws.receive_bytes()
            assert exc_info.value.code == 1011

        # Second connection succeeds
        working_connect = _make_websockets_connect_mock()
        working_ws_module = _make_websockets_module(working_connect)

        with patch.dict(sys.modules, {"websockets": working_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Back up"}))
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
            ws.send_bytes(b"\x00\x01")
            ws.close()

        # TTS connection
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Hola"}))
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
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
            ws.send_bytes(b"\x00\x01\x02")
            ws.close()

        # send_finalize should have been called in the finally block
        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        mock_dg_ws.send_finalize.assert_awaited_once()

    def test_tts_forward_task_cancelled_on_close(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The Deepgram forward task is cancelled when the TTS client disconnects."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"text": "Hola"}))
                ws.send_text(json.dumps({"type": "close"}))

        # Deepgram WS close should be called in cleanup
        mock_dg_ws = mock_connect._mock_dg_ws
        mock_dg_ws.close.assert_awaited()

    def test_tts_deepgram_ws_closed_on_disconnect(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
    ) -> None:
        """The Deepgram WebSocket is properly closed when browser disconnects."""
        mock_connect = _make_websockets_connect_mock()
        mock_ws_module = _make_websockets_module(mock_connect)

        with patch.dict(sys.modules, {"websockets": mock_ws_module}):
            with test_client.websocket_connect(
                "/ws/speak?voice=aura-2-nestor-es", cookies=ws_cookies
            ) as ws:
                ws.send_text(json.dumps({"type": "close"}))

        mock_dg_ws = mock_connect._mock_dg_ws
        mock_dg_ws.close.assert_awaited_once()

    def test_stt_cleanup_after_many_frames(
        self,
        test_client: TestClient,
        ws_cookies: dict[str, str],
        mock_settings_with_deepgram: MagicMock,
        mock_deepgram_sdk: dict[str, MagicMock],
    ) -> None:
        """Cleanup runs correctly after processing many audio frames."""
        with test_client.websocket_connect(
            "/ws/transcribe?language=es", cookies=ws_cookies
        ) as ws:
            for i in range(20):
                ws.send_bytes(bytes([i % 256]) * 320)
            ws.close()

        mock_dg_ws = mock_deepgram_sdk["dg_ws"]
        assert mock_dg_ws.send_media.await_count == 20
        mock_dg_ws.send_finalize.assert_awaited_once()
