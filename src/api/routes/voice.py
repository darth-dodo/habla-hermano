"""Voice endpoints for Deepgram STT/TTS integration.

Phase 17: Speech-to-Text via WebSocket proxy and Text-to-Speech via WebSocket streaming proxy.
Voice features are optional -- endpoints return errors when DEEPGRAM_API_KEY is not configured.

Security (B1): All endpoints require authentication via JWT token or guest session cookie.
WebSocket endpoints validate identity from cookies before accepting the connection.
JWT tokens are verified server-side via Supabase auth.get_user() in production.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketState

from src.api.auth import EffectiveUserDep
from src.api.config import get_settings
from src.api.cookies import unsign_session_id
from src.api.rate_limit import (
    VOICE_RATE_LIMIT_CALLS,
    VOICE_RATE_LIMIT_PERIOD,
    VOICE_WS_TTS_MESSAGE_RATE,
    WebSocketMessageRateLimiter,
    rate_limited,
)
from src.api.validation import VALID_LANGUAGES
from src.db.client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def _verify_jwt_via_supabase(token: str) -> str | None:
    """Verify a JWT token server-side via Supabase auth.get_user().

    This is the secure verification path used in production. The token
    signature is validated by Supabase's auth service.

    Args:
        token: Raw JWT access token string.

    Returns:
        User ID string if verification succeeds, None otherwise.
    """
    try:
        client = get_supabase()
        response = client.auth.get_user(token)
    except ValueError:
        logger.debug("WebSocket JWT verification skipped: Supabase not configured")
        return None
    except httpx.HTTPError:
        logger.debug("WebSocket JWT verification failed: Supabase request error")
        return None

    if response is None or response.user is None:
        logger.debug("WebSocket JWT verification failed: invalid or expired token")
        return None

    return str(response.user.id)


def _decode_jwt_unverified(token: str) -> str | None:
    """Decode a JWT token WITHOUT signature verification (local dev only).

    WARNING: This does NOT verify the token signature. Forged tokens will
    be accepted. Only used when ALLOW_UNVERIFIED_JWT=true.

    Args:
        token: Raw JWT access token string.

    Returns:
        User ID string if decode succeeds, None otherwise.
    """
    try:
        import jwt as pyjwt

        payload = pyjwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )
        user_id = payload.get("sub")
        if user_id:
            return str(user_id)
    except Exception:
        logger.debug("WebSocket JWT decode failed")

    return None


async def _authenticate_websocket(websocket: WebSocket) -> str | None:
    """Extract and validate user identity from WebSocket cookies or query param.

    WebSocket endpoints cannot use FastAPI's Depends() for auth, so we
    manually extract the identity from cookies before accepting the
    connection.  Checks JWT (``sb-access-token``) first, then falls back
    to a guest session UUID (``session_id``).

    As a final fallback, accepts a signed ``token`` query parameter for
    browsers that do not send cookies with WebSocket upgrade requests
    (notably iOS Safari and Chrome, which use WebKit and may omit
    httponly cookies from the WS handshake).

    Security:
    - Production (Supabase configured): JWT is verified server-side via
      Supabase auth.get_user(), mirroring the HTTP auth path.
    - Local dev (ALLOW_UNVERIFIED_JWT=true): Falls back to unverified
      JWT decode with a WARNING log.
    - Query-param token: Verified via itsdangerous (same as cookie).
    - Neither configured: Returns None (denies access).

    Returns:
        User/session ID string if authenticated, None otherwise.
    """
    settings = get_settings()

    # Try JWT cookie first
    token = websocket.cookies.get("sb-access-token")
    if token:
        if settings.supabase_configured:
            # Production path: verify token server-side via Supabase
            user_id = _verify_jwt_via_supabase(token)
            if user_id:
                return user_id
            # Verification failed -- do not fall through to unverified decode
            logger.debug("WebSocket JWT server-side verification failed")
        elif settings.ALLOW_UNVERIFIED_JWT:
            # Local dev path: unverified decode (insecure)
            logger.warning(
                "SECURITY WARNING: WebSocket JWT signature verification is DISABLED "
                "(ALLOW_UNVERIFIED_JWT=true). Do NOT use this in production."
            )
            user_id = _decode_jwt_unverified(token)
            if user_id:
                return user_id
        else:
            # Supabase not configured and unverified JWT not allowed
            logger.debug(
                "WebSocket JWT rejected: Supabase not configured and "
                "ALLOW_UNVERIFIED_JWT is not enabled"
            )

    # Fall back to guest session cookie (verify signature)
    session_id = websocket.cookies.get("session_id")
    if session_id:
        verified = unsign_session_id(session_id)
        if verified:
            return verified

    # Final fallback: signed token query parameter.
    # iOS Safari/Chrome (WebKit) may not send httponly cookies with WS upgrades.
    ws_token = websocket.query_params.get("token")
    if ws_token:
        verified = unsign_session_id(ws_token)
        if verified:
            logger.debug("WebSocket authenticated via query-param token fallback")
            return verified

    return None


# Allowed Deepgram TTS voice IDs
ALLOWED_VOICES: frozenset[str] = frozenset(
    {
        # Spanish voices
        "aura-2-celeste-es",
        "aura-2-estrella-es",
        "aura-2-nestor-es",
        # German voices
        "aura-2-elara-de",
        "aura-2-julius-de",
        # French voices
        "aura-2-agathe-fr",
        "aura-2-hector-fr",
    }
)

# Default voice per language (masculine — matches Hermano "big brother" persona)
DEFAULT_VOICES: dict[str, str] = {
    "es": "aura-2-nestor-es",
    "de": "aura-2-julius-de",
    "fr": "aura-2-hector-fr",
}

# STT language options (includes "multi" for code-switching)
VALID_STT_LANGUAGES: frozenset[str] = VALID_LANGUAGES | frozenset({"multi"})

MAX_TTS_TEXT_LENGTH = 2000


class SpeakRequest(BaseModel):
    """Request body for TTS endpoint."""

    text: str = Field(..., min_length=1, max_length=MAX_TTS_TEXT_LENGTH)
    voice: str = "aura-2-nestor-es"


@router.websocket("/ws/transcribe")
async def transcribe_stream(  # noqa: PLR0915
    websocket: WebSocket,
    language: str = Query(default="multi"),
) -> None:
    """Proxy browser audio to Deepgram STT and return transcripts.

    Accepts a WebSocket connection from the browser, forwards raw audio
    bytes to Deepgram's real-time STT WebSocket, and relays transcript
    results back to the browser as JSON messages.

    Uses Deepgram Python SDK v6 async WebSocket API.

    Args:
        websocket: WebSocket connection from the browser client.
        language: STT language code ("es", "de", "fr", or "multi" for code-switching).
    """
    # B1: Authenticate before accepting the connection
    user_id = await _authenticate_websocket(websocket)
    if user_id is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    # Validate language
    if language not in VALID_STT_LANGUAGES:
        await websocket.close(code=1008, reason=f"Invalid language: {language}")
        return

    api_key = get_settings().DEEPGRAM_API_KEY
    if not api_key:
        await websocket.close(code=1011, reason="Voice features not configured")
        return

    await websocket.accept()

    try:
        from deepgram import AsyncDeepgramClient
        from deepgram.core.events import EventType

        deepgram = AsyncDeepgramClient(api_key=api_key)

        # Hold references to background tasks to prevent GC
        _bg_tasks: set[asyncio.Task[None]] = set()

        async with deepgram.listen.v1.connect(
            model="nova-3",
            language=language,
            smart_format="true",
            punctuate="true",
            interim_results="true",
            endpointing="300",
            utterance_end_ms="1000",
            vad_events="true",
            encoding="linear16",
            sample_rate="16000",
            mip_opt_out="true",
        ) as dg_ws:
            # Forward transcripts from Deepgram to browser
            # v6 SDK passes typed Pydantic models, not raw JSON dicts
            def on_message(data: Any) -> None:
                try:
                    from deepgram.listen.v1 import ListenV1Results

                    if not isinstance(data, ListenV1Results):
                        return

                    alternatives = data.channel.alternatives if data.channel else []
                    transcript = alternatives[0].transcript if alternatives else ""
                    is_final = data.is_final or False
                    speech_final = data.speech_final or False

                    if transcript:
                        task = asyncio.create_task(
                            websocket.send_json(
                                {
                                    "transcript": transcript,
                                    "is_final": is_final,
                                    "speech_final": speech_final,
                                }
                            )
                        )
                        _bg_tasks.add(task)
                        task.add_done_callback(_bg_tasks.discard)
                except (AttributeError, IndexError, ConnectionError, OSError):
                    logger.exception("Error forwarding transcript")

            dg_ws.on(EventType.MESSAGE, on_message)

            # start_listening() is an infinite loop that reads from Deepgram WS
            # and emits events — run it as a background task so the audio
            # forwarding loop below can execute concurrently.
            listen_task = asyncio.create_task(dg_ws.start_listening())

            # Forward audio from browser to Deepgram
            try:
                while True:
                    audio_data = await websocket.receive_bytes()
                    await dg_ws.send_media(audio_data)
            except WebSocketDisconnect:
                logger.debug("Browser WebSocket disconnected")
            finally:
                listen_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listen_task
                with contextlib.suppress(Exception):
                    await dg_ws.send_finalize()

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected during setup")
    except (ConnectionError, OSError, RuntimeError):
        logger.exception("Error in transcription WebSocket")
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")


@router.post("/api/speak", response_model=None)
@rate_limited(VOICE_RATE_LIMIT_CALLS, VOICE_RATE_LIMIT_PERIOD)
async def speak(request: SpeakRequest, _user: EffectiveUserDep) -> StreamingResponse | JSONResponse:
    """Synthesize speech from text using Deepgram TTS.

    Proxies the request to Deepgram's REST TTS API and streams back
    the audio response as audio/mpeg.

    Args:
        request: TTS request with text and optional voice selection.

    Returns:
        StreamingResponse with audio/mpeg content, or JSONResponse on error.
    """
    # Validate voice
    if request.voice not in ALLOWED_VOICES:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid voice: {request.voice}"},
        )

    api_key = get_settings().DEEPGRAM_API_KEY
    if not api_key:
        return JSONResponse(
            status_code=503,
            content={"detail": "Voice features not configured"},
        )

    async def audio_stream() -> AsyncGenerator[bytes, None]:
        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                f"https://api.deepgram.com/v1/speak?model={request.voice}&encoding=mp3&mip_opt_out=true",
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": request.text},
                timeout=30.0,
            ) as response,
        ):
            response.raise_for_status()
            async for chunk in response.aiter_bytes(1024):
                yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": "inline",
        },
    )


async def _forward_deepgram_to_browser(dg_ws: Any, websocket: WebSocket) -> None:
    """Forward audio chunks and metadata from Deepgram WS to browser WS."""
    import websockets as ws_lib

    try:
        async for message in dg_ws:
            if websocket.client_state != WebSocketState.CONNECTED:
                break
            if isinstance(message, bytes):
                await websocket.send_bytes(message)
            else:
                await websocket.send_text(message)
    except ws_lib.ConnectionClosed:
        pass
    except (ConnectionError, OSError, RuntimeError):
        logger.exception("Error forwarding Deepgram TTS audio")


async def _handle_browser_tts_messages(
    websocket: WebSocket,
    dg_ws: Any,
    msg_limiter: WebSocketMessageRateLimiter,
) -> None:
    """Receive text from browser and forward Speak+Flush commands to Deepgram."""
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "close":
                await dg_ws.send(json.dumps({"type": "Close"}))
                break

            text = msg.get("text", "").strip()
            if not text or len(text) > MAX_TTS_TEXT_LENGTH:
                continue

            # B9: Per-connection message rate limiting
            if not msg_limiter.check():
                logger.warning("TTS WebSocket message rate limit exceeded")
                await websocket.send_text(
                    json.dumps({"error": "Rate limit exceeded", "code": "RATE_LIMITED"})
                )
                continue

            await dg_ws.send(json.dumps({"type": "Speak", "text": text}))
            await dg_ws.send(json.dumps({"type": "Flush"}))
    except WebSocketDisconnect:
        logger.debug("Browser WebSocket disconnected from TTS")


@router.websocket("/ws/speak")
async def speak_stream(
    websocket: WebSocket,
    voice: str = Query(default="aura-2-nestor-es"),
) -> None:
    """Stream TTS audio via WebSocket for low-latency playback.

    Browser sends JSON with text, server proxies to Deepgram's WebSocket TTS
    and forwards binary audio chunks back as they're generated.

    Protocol:
        Client -> {"text": "Hola amigo"} (JSON text message)
        Server -> binary audio chunks (MP3)
        Server -> {"type": "metadata", ...} (JSON when audio is complete)
        Client -> {"type": "close"} or disconnect to end
    """
    # B1: Authenticate before accepting the connection
    user_id = await _authenticate_websocket(websocket)
    if user_id is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    if voice not in ALLOWED_VOICES:
        await websocket.close(code=1008, reason=f"Invalid voice: {voice}")
        return

    api_key = get_settings().DEEPGRAM_API_KEY
    if not api_key:
        await websocket.close(code=1011, reason="Voice features not configured")
        return

    await websocket.accept()

    # B9: Per-connection message rate limiter for TTS text messages
    tts_limiter = WebSocketMessageRateLimiter(VOICE_WS_TTS_MESSAGE_RATE, 60)

    try:
        import websockets

        dg_url = f"wss://api.deepgram.com/v1/speak?model={voice}&encoding=mp3&mip_opt_out=true"
        dg_headers = {"Authorization": f"Token {api_key}"}

        async with websockets.connect(dg_url, additional_headers=dg_headers) as dg_ws:
            forward_task = asyncio.create_task(_forward_deepgram_to_browser(dg_ws, websocket))
            try:
                await _handle_browser_tts_messages(websocket, dg_ws, tts_limiter)
            finally:
                forward_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await forward_task
                with contextlib.suppress(Exception):
                    await dg_ws.close()

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected during TTS setup")
    except (ConnectionError, OSError, RuntimeError):
        logger.exception("Error in TTS WebSocket")
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")
