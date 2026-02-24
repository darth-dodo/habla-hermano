"""Voice endpoints for Deepgram STT/TTS integration.

Phase 17: Speech-to-Text via WebSocket proxy and Text-to-Speech via REST proxy.
Voice features are optional -- endpoints return errors when DEEPGRAM_API_KEY is not configured.
"""

import contextlib
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.api.config import get_settings
from src.api.validation import VALID_LANGUAGES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

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

# Default voice per language
DEFAULT_VOICES: dict[str, str] = {
    "es": "aura-2-celeste-es",
    "de": "aura-2-elara-de",
    "fr": "aura-2-agathe-fr",
}

# STT language options (includes "multi" for code-switching)
VALID_STT_LANGUAGES: frozenset[str] = VALID_LANGUAGES | frozenset({"multi"})

MAX_TTS_TEXT_LENGTH = 2000


class SpeakRequest(BaseModel):
    """Request body for TTS endpoint."""

    text: str = Field(..., min_length=1, max_length=MAX_TTS_TEXT_LENGTH)
    voice: str = "aura-2-celeste-es"


@router.websocket("/ws/transcribe")
async def transcribe_stream(
    websocket: WebSocket,
    language: str = Query(default="multi"),
) -> None:
    """Proxy browser audio to Deepgram STT and return transcripts.

    Accepts a WebSocket connection from the browser, forwards raw audio
    bytes to Deepgram's real-time STT WebSocket, and relays transcript
    results back to the browser as JSON messages.

    Args:
        websocket: WebSocket connection from the browser client.
        language: STT language code ("es", "de", "fr", or "multi" for code-switching).
    """
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
        from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents

        config = DeepgramClientOptions(api_key=api_key)
        deepgram = DeepgramClient("", config)

        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        options: dict[str, Any] = {
            "model": "nova-3",
            "language": language,
            "smart_format": True,
            "punctuate": True,
            "interim_results": True,
            "endpointing": 300,
            "utterance_end_ms": 1000,
            "vad_events": True,
            "encoding": "linear16",
            "sample_rate": 16000,
        }

        # Set up transcript handler before starting
        async def on_transcript(_self: Any, result: Any, **_kwargs: Any) -> None:
            try:
                transcript: str = result.channel.alternatives[0].transcript
                is_final: bool = result.is_final
                speech_final: bool = getattr(result, "speech_final", False)

                if transcript:
                    await websocket.send_json(
                        {
                            "transcript": transcript,
                            "is_final": is_final,
                            "speech_final": speech_final,
                        }
                    )
            except Exception:
                logger.exception("Error forwarding transcript")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

        started: bool = await dg_connection.start(options)
        if not started:
            await websocket.close(code=1011, reason="Failed to connect to Deepgram")
            return

        # Forward audio from browser to Deepgram
        try:
            while True:
                audio_data = await websocket.receive_bytes()
                await dg_connection.send(audio_data)
        except WebSocketDisconnect:
            logger.debug("Browser WebSocket disconnected")
        finally:
            await dg_connection.finish()

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected during setup")
    except Exception:
        logger.exception("Error in transcription WebSocket")
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")


@router.post("/api/speak", response_model=None)
async def speak(request: SpeakRequest) -> StreamingResponse | JSONResponse:
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
                f"https://api.deepgram.com/v1/speak?model={request.voice}&encoding=mp3",
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
