"""Voice endpoints: Deepgram STT and Gemini TTS (via OpenRouter).

Phase 17: Speech-to-Text via a WebSocket proxy to Deepgram, and Text-to-Speech
via REST and WebSocket endpoints backed by OpenRouter's speech API (Gemini TTS,
see src/services/tts.py). STT is optional and returns an error when
DEEPGRAM_API_KEY is not configured; TTS uses the required OPENROUTER_API_KEY.

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
from src.services.tts import TTS_SAMPLE_RATE, TTSError, synthesize_pcm

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def _capture_sentry_exception(exc: BaseException) -> None:
    """Report an exception to Sentry if configured, otherwise no-op."""
    try:
        import sentry_sdk

        if sentry_sdk.is_initialized():
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass


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


# Gemini TTS voices (as listed by OpenRouter for google/gemini-3.8-flash-tts).
# Gemini voices are not tied to a language: the model detects the language of
# the text, so one voice speaks Spanish, German, French and Hinglish.
ALLOWED_VOICES: frozenset[str] = frozenset(
    {
        "Zephyr",
        "Puck",
        "Charon",
        "Kore",
        "Fenrir",
        "Leda",
        "Orus",
        "Aoede",
        "Callirrhoe",
        "Autonoe",
        "Enceladus",
        "Iapetus",
        "Umbriel",
        "Algieba",
        "Despina",
        "Erinome",
        "Algenib",
        "Rasalgethi",
        "Laomedeia",
        "Achernar",
        "Alnilam",
        "Schedar",
        "Gacrux",
        "Pulcherrima",
        "Achird",
        "Zubenelgenubi",
        "Vindemiatrix",
        "Sadachbia",
        "Sadaltager",
        "Sulafat",
    }
)

# The voice the app uses for each language. Achird is Gemini's "friendly"
# male voice, matching the Hermano "big brother" persona. Using one voice
# everywhere keeps Hermano sounding like the same person in every language,
# including Hinglish (Roman-script Hindi-English, which Gemini reads natively).
HERMANO_VOICE = "Achird"
DEFAULT_VOICES: dict[str, str] = {
    "es": HERMANO_VOICE,
    "de": HERMANO_VOICE,
    "fr": HERMANO_VOICE,
    "hi": HERMANO_VOICE,
}

# STT language options (includes "multi" for code-switching)
VALID_STT_LANGUAGES: frozenset[str] = VALID_LANGUAGES | frozenset({"multi"})

MAX_TTS_TEXT_LENGTH = 2000


class SpeakRequest(BaseModel):
    """Request body for TTS endpoint."""

    text: str = Field(..., min_length=1, max_length=MAX_TTS_TEXT_LENGTH)
    voice: str = HERMANO_VOICE


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
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.exception("Error in transcription WebSocket")
        _capture_sentry_exception(exc)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")


@router.post("/api/speak", response_model=None)
@rate_limited(VOICE_RATE_LIMIT_CALLS, VOICE_RATE_LIMIT_PERIOD)
async def speak(request: SpeakRequest, _user: EffectiveUserDep) -> StreamingResponse | JSONResponse:
    """Synthesize speech from text with Gemini TTS (via OpenRouter).

    REST fallback for browsers where the WebSocket path is unavailable.
    Streams back raw PCM (24kHz, mono, 16-bit LE) as ``audio/pcm``; the
    browser joins the chunks and wraps them in a WAV header for playback.

    Args:
        request: TTS request with text and optional voice selection.

    Returns:
        StreamingResponse with audio/pcm content, or JSONResponse on error.
    """
    if request.voice not in ALLOWED_VOICES:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid voice: {request.voice}"},
        )

    # Pull the first chunk before answering, so an upstream failure becomes a
    # clean 502 instead of a 200 response that breaks halfway through.
    pcm = synthesize_pcm(request.text, request.voice)
    try:
        first_chunk = await anext(pcm)
    except StopAsyncIteration:
        first_chunk = b""
    except TTSError:
        logger.exception("TTS synthesis failed")
        return JSONResponse(status_code=502, content={"detail": "Speech synthesis failed"})

    async def audio_stream() -> AsyncGenerator[bytes, None]:
        try:
            if first_chunk:
                yield first_chunk
            async for chunk in pcm:
                yield chunk
        finally:
            # Close the upstream request even if the browser disconnects early.
            await pcm.aclose()

    return StreamingResponse(
        audio_stream(),
        media_type="audio/pcm",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": "inline",
            "X-Sample-Rate": str(TTS_SAMPLE_RATE),
        },
    )


async def _speak_text(
    websocket: WebSocket, client: httpx.AsyncClient, text: str, voice: str
) -> None:
    """Synthesize one text chunk and stream its PCM frames to the browser.

    Sends a ``{"type": "Flushed"}`` message when the chunk is complete, which
    tells the browser to send the next chunk.
    """
    async for pcm_chunk in synthesize_pcm(text, voice, client=client):
        await websocket.send_bytes(pcm_chunk)
    await websocket.send_text(json.dumps({"type": "Flushed"}))


@router.websocket("/ws/speak")
async def speak_stream(
    websocket: WebSocket,
    voice: str = Query(default=HERMANO_VOICE),
) -> None:
    """Stream TTS audio via WebSocket for low-latency playback.

    Browser sends JSON with text; the server synthesizes it with Gemini TTS
    (via OpenRouter) and forwards PCM audio frames as they arrive.

    Protocol:
        Client -> {"text": "Hola amigo"} (JSON text message)
        Server -> binary audio chunks (raw linear16 PCM, 24kHz mono)
        Server -> {"type": "Flushed"} (JSON when the chunk's audio is complete)
        Client -> {"type": "close"} or disconnect to end

    If synthesis fails the socket closes with code 1011; the browser then
    falls back to the REST endpoint.
    """
    # B1: Authenticate before accepting the connection
    user_id = await _authenticate_websocket(websocket)
    if user_id is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    if voice not in ALLOWED_VOICES:
        await websocket.close(code=1008, reason=f"Invalid voice: {voice}")
        return

    await websocket.accept()

    # B9: Per-connection message rate limiter for TTS text messages
    tts_limiter = WebSocketMessageRateLimiter(VOICE_WS_TTS_MESSAGE_RATE, 60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                msg = json.loads(await websocket.receive_text())

                if msg.get("type") == "close":
                    break

                text = msg.get("text", "").strip()
                if not text or len(text) > MAX_TTS_TEXT_LENGTH:
                    continue

                if not tts_limiter.check():
                    logger.warning("TTS WebSocket message rate limit exceeded")
                    await websocket.send_text(
                        json.dumps({"error": "Rate limit exceeded", "code": "RATE_LIMITED"})
                    )
                    continue

                await _speak_text(websocket, client, text, voice)

    except WebSocketDisconnect:
        logger.debug("Browser WebSocket disconnected from TTS")
    except TTSError as exc:
        logger.exception("TTS synthesis failed")
        _capture_sentry_exception(exc)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Speech synthesis failed")
    except (json.JSONDecodeError, RuntimeError) as exc:
        # Malformed client message, or a send after the browser went away.
        logger.debug("TTS WebSocket closed: %s", type(exc).__name__)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")
