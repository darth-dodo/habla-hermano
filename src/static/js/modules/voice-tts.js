/**
 * Habla Hermano - TTS (Text-to-Speech) Module
 * Phase 21: Extracted from voice.js for modularity.
 *
 * WebSocket path: streams PCM audio via Web Audio API for low-latency
 * playback — audio plays as frames arrive, no waiting for full synthesis.
 * REST fallback: uses hidden <audio> element with blob URL for iOS Safari
 * compatibility when WebSocket is unavailable.
 */

import { createMachine } from './fsm.js';
import { chunkTextForTTS, WS_SPEAK_PATH, TTS_WS_SAMPLE_RATE } from './voice-constants.js';

// ============================================
// TTS State Machine Definition
// ============================================

export var ttsMachine = createMachine({
    initial: 'idle',
    states: {
        idle: { on: { PLAY: 'loading' } },
        loading: { on: { STREAMING: 'playing', ALL_ENDED: 'idle', ERROR: 'idle', CANCEL: 'idle' } },
        playing: { on: { ALL_ENDED: 'idle', ERROR: 'idle', CANCEL: 'idle' } },
    },
});

// ============================================
// Module-scoped TTS Resources
// ============================================

// References to the hidden <audio> and <source> elements (set in initTtsPlayer)
var ttsPlayer = null;
var ttsSource = null;

// Current blob URL (must be revoked on cleanup)
var currentBlobUrl = null;

// iOS audio session stream — kept alive during TTS playback to prevent
// iOS Safari from routing audio back to earpiece. Released on cleanup.
var iosSessionStream = null;

// Set to true after STT mic usage. Only then do we need getUserMedia
// before TTS to counteract iOS earpiece routing.
var micWasUsed = false;

// Web Audio streaming state (for WebSocket TTS path)
var streamAudioCtx = null;
var streamNextStartTime = 0;
var streamSources = [];
var streamLastSource = null;

/**
 * Initialize TTS player references. Called once from voice.js initVoice().
 * Grabs the hidden <audio id="tts-player"> and <source id="tts-player-src">
 * elements that are pre-initialized in chat.html with a silent MP3.
 */
export function initTtsPlayer() {
    ttsPlayer = document.getElementById('tts-player');
    ttsSource = document.getElementById('tts-player-src');
}

/**
 * Mark that the microphone was used (STT session started).
 * After mic usage, iOS Safari routes audio to the earpiece, so TTS
 * needs getUserMedia to reactivate the speaker audio session.
 */
export function notifyMicUsed() {
    micWasUsed = true;
}

/**
 * Audio-element TTS — POST fetch to /api/speak, receive audio blob,
 * play through hidden <audio> element for reliable iOS Safari playback.
 *
 * Uses Deepgram's recommended pattern:
 *   1. POST text → receive audio/mpeg blob
 *   2. Create blob URL → set source.src → player.load() → player.play()
 *   3. player.load() is critical for iOS to recognize the new source
 *
 * @param {HTMLElement} btn - speaker button for error tooltips
 * @param {string} text - text to synthesize
 * @param {string} voice - Deepgram voice ID
 * @param {number} speed - playback rate (0.25–2.0)
 * @param {AbortSignal} signal - cancellation signal
 * @param {object} ttsService - FSM service to send events
 * @param {function(HTMLElement, string): void} showError - error display callback
 */
export function audioElementTTS(btn, text, voice, speed, signal, ttsService, showError) {
    if (!ttsPlayer || !ttsSource) {
        showError(btn, 'Audio player not available');
        ttsService.send('ERROR');
        return;
    }

    // iOS Safari: after getUserMedia (STT), audio routes to the earpiece.
    // Reactivate the speaker session by requesting the mic again and keeping
    // the stream alive during playback. Only needed after mic was used.
    //
    // Fires in PARALLEL with the fetch to avoid adding latency.
    if (micWasUsed && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                if (signal.aborted) {
                    stream.getTracks().forEach(function(t) { t.stop(); });
                    return;
                }
                // Keep stream alive — will be stopped in cleanupTtsResources()
                releaseIosSessionStream();
                iosSessionStream = stream;
            })
            .catch(function() {
                // Mic permission denied or unavailable — TTS will still work
                // on non-iOS or with Bluetooth.
            });
    }

    // Start WebSocket TTS immediately (parallel with getUserMedia),
    // falling back to REST fetch if WebSocket fails to connect.
    doWebSocketTTS(btn, text, voice, speed, signal, ttsService, showError);
}

/**
 * WebSocket-based TTS with streaming playback: plays PCM audio frames
 * immediately as they arrive via Web Audio API for minimal latency.
 * Falls back to REST doFetch() if the WebSocket fails to connect.
 */
function doWebSocketTTS(btn, text, voice, speed, signal, ttsService, showError) {
    // Unlock the audio element for iOS Safari (must happen synchronously
    // in the user-gesture call stack — same as doFetch).
    if (ttsPlayer) {
        ttsPlayer.play().catch(function() {});
        ttsPlayer.pause();
    }

    var textChunks = chunkTextForTTS(text);
    var chunkIndex = 0;
    var wsConnected = false;
    var ws = null;
    var streamingStarted = false;
    var allDone = false;

    // Create AudioContext for streaming PCM playback
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
        cleanupStreamAudio();
        streamAudioCtx = new Ctx({ sampleRate: TTS_WS_SAMPLE_RATE });
        streamNextStartTime = 0;
        streamSources = [];
        streamLastSource = null;
    }

    // Build WebSocket URL
    var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = wsProtocol + '//' + location.host + WS_SPEAK_PATH + '?voice=' + encodeURIComponent(voice);

    // iOS Safari/Chrome (WebKit) may not send httponly cookies with WS
    // upgrade requests. Pass the signed session token as a query param.
    var micBtn = document.getElementById('mic-btn');
    var wsToken = micBtn && micBtn.dataset.wsToken;
    if (wsToken) {
        wsUrl += '&token=' + encodeURIComponent(wsToken);
    }

    function cleanup() {
        if (ws) {
            ws.onopen = null;
            ws.onmessage = null;
            ws.onerror = null;
            ws.onclose = null;
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                ws.close(1000, 'Done');
            }
            ws = null;
        }
    }

    function onAbort() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            try { ws.send(JSON.stringify({ type: 'close' })); } catch (_) {}
        }
        cleanup();
        cleanupStreamAudio();
    }

    if (signal.aborted) return;
    signal.addEventListener('abort', onAbort);

    try {
        ws = new WebSocket(wsUrl);
        ws.binaryType = 'arraybuffer';
    } catch (_) {
        signal.removeEventListener('abort', onAbort);
        cleanupStreamAudio();
        doFetch(btn, text, voice, speed, signal, ttsService, showError);
        return;
    }

    ws.onopen = function() {
        if (signal.aborted) { cleanup(); return; }
        wsConnected = true;
        // Resume AudioContext (may be suspended on iOS)
        if (streamAudioCtx && streamAudioCtx.state === 'suspended') {
            streamAudioCtx.resume();
        }
        if (textChunks.length > 0) {
            ws.send(JSON.stringify({ text: textChunks[chunkIndex] }));
        }
    };

    ws.onmessage = function(event) {
        if (signal.aborted) { cleanup(); return; }

        // Binary frame — play PCM immediately via Web Audio API
        if (event.data instanceof ArrayBuffer) {
            if (!streamAudioCtx) return;

            // Convert Int16 PCM to Float32 for Web Audio
            var int16 = new Int16Array(event.data);
            var float32 = new Float32Array(int16.length);
            for (var i = 0; i < int16.length; i++) {
                float32[i] = int16[i] / 32768;
            }

            var audioBuffer = streamAudioCtx.createBuffer(1, float32.length, TTS_WS_SAMPLE_RATE);
            audioBuffer.getChannelData(0).set(float32);

            var source = streamAudioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.playbackRate.value = speed;
            source.connect(streamAudioCtx.destination);

            // Schedule for gapless playback
            var startTime = Math.max(streamAudioCtx.currentTime, streamNextStartTime);
            source.start(startTime);
            streamNextStartTime = startTime + (audioBuffer.duration / speed);

            streamSources.push(source);
            streamLastSource = source;

            // Transition to playing on first audio frame
            if (!streamingStarted) {
                streamingStarted = true;
                ttsService.send('STREAMING');
            }
            return;
        }

        // Text frame — parse JSON (Flushed event signals chunk complete)
        var msg;
        try { msg = JSON.parse(event.data); } catch (_) { return; }

        if (msg.type === 'Flushed') {
            chunkIndex++;
            if (chunkIndex < textChunks.length) {
                ws.send(JSON.stringify({ text: textChunks[chunkIndex] }));
            } else {
                // All chunks sent and flushed — close WS, wait for audio to finish
                allDone = true;
                signal.removeEventListener('abort', onAbort);
                cleanup();

                if (streamLastSource) {
                    streamLastSource.onended = function() {
                        if (signal.aborted) return;
                        cleanupStreamAudio();
                        ttsService.send('ALL_ENDED');
                    };
                } else {
                    // No audio was received
                    cleanupStreamAudio();
                    ttsService.send('ERROR');
                }
            }
        }
    };

    ws.onerror = function() {
        if (!wsConnected) {
            signal.removeEventListener('abort', onAbort);
            cleanup();
            cleanupStreamAudio();
            doFetch(btn, text, voice, speed, signal, ttsService, showError);
            return;
        }
        if (!signal.aborted) {
            signal.removeEventListener('abort', onAbort);
            cleanup();
            cleanupStreamAudio();
            showError(btn, 'Could not play audio');
            ttsService.send('ERROR');
        }
    };

    ws.onclose = function(event) {
        if (signal.aborted) return;
        if (!wsConnected) {
            signal.removeEventListener('abort', onAbort);
            cleanup();
            cleanupStreamAudio();
            doFetch(btn, text, voice, speed, signal, ttsService, showError);
            return;
        }
        // Unexpected close while still streaming chunks
        if (chunkIndex < textChunks.length && !allDone) {
            signal.removeEventListener('abort', onAbort);
            cleanup();
            cleanupStreamAudio();
            doFetch(btn, text, voice, speed, signal, ttsService, showError);
        }
    };
}

/**
 * Play an audio blob through the hidden TTS player element.
 * Extracted so both WebSocket and REST paths can share it.
 */
function playAudioFromBlob(audioBlob, speed, signal, ttsService, btn, showError) {
    if (signal.aborted) return;

    // Revoke any previous blob URL
    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
    }

    var blobUrl = URL.createObjectURL(audioBlob);
    currentBlobUrl = blobUrl;

    // Deepgram pattern: update source, load(), then play()
    ttsSource.src = blobUrl;
    ttsSource.type = audioBlob.type || 'audio/mpeg';
    ttsPlayer.playbackRate = speed;

    // .load() is critical for iOS to recognize the new source
    ttsPlayer.load();

    ttsService.send('STREAMING');

    ttsPlayer.onended = function() {
        if (signal.aborted) return;
        revokeBlobUrl();
        ttsService.send('ALL_ENDED');
    };

    ttsPlayer.onerror = function() {
        if (signal.aborted) return;
        revokeBlobUrl();
        showError(btn, 'Audio playback failed');
        ttsService.send('ERROR');
    };

    ttsPlayer.play().catch(function() {
        if (signal.aborted) return;
        revokeBlobUrl();
        showError(btn, 'Could not play audio');
        ttsService.send('ERROR');
    });
}

function doFetch(btn, text, voice, speed, signal, ttsService, showError) {
    // Unlock the audio element for iOS Safari and strict autoplay policies.
    // play() must be called within the synchronous user-gesture call stack.
    // Calling play() + pause() here "activates" the element so that the
    // later async play() (after fetch completes) is allowed by the browser.
    if (ttsPlayer) {
        ttsPlayer.play().catch(function() {});
        ttsPlayer.pause();
    }

    var textChunks = chunkTextForTTS(text);
    var allBlobs = [];

    // Fetch audio for all chunks sequentially, then concatenate and play
    function fetchChunk(index) {
        if (signal.aborted) return;
        if (index >= textChunks.length) {
            // All chunks fetched — combine and play
            var combinedBlob = new Blob(allBlobs, { type: allBlobs[0].type });
            playAudioFromBlob(combinedBlob, speed, signal, ttsService, btn, showError);
            return;
        }

        fetch('/api/speak', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ text: textChunks[index], voice: voice }),
            signal: signal,
        }).then(function(response) {
            if (signal.aborted) return;
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.blob();
        }).then(function(audioBlob) {
            if (signal.aborted || !audioBlob) return;
            allBlobs.push(audioBlob);
            fetchChunk(index + 1);
        }).catch(function(err) {
            if (signal.aborted) return;
            if (err.name === 'AbortError') return;
            var msg = (err && err.message && err.message.indexOf('503') !== -1)
                ? 'Speech service not configured'
                : 'Could not play audio';
            showError(btn, msg);
            ttsService.send('ERROR');
        });
    }

    fetchChunk(0);
}

/**
 * Clean up Web Audio streaming resources.
 * Stops all scheduled AudioBufferSourceNodes and closes the AudioContext.
 */
function cleanupStreamAudio() {
    if (streamSources) {
        for (var i = 0; i < streamSources.length; i++) {
            try { streamSources[i].onended = null; streamSources[i].stop(); } catch (_) {}
        }
        streamSources = [];
    }
    streamLastSource = null;
    streamNextStartTime = 0;
    if (streamAudioCtx && streamAudioCtx.state !== 'closed') {
        streamAudioCtx.close().catch(function() {});
    }
    streamAudioCtx = null;
}

/**
 * Release iOS audio session stream if active.
 * Stops all tracks to free the microphone resource.
 */
function releaseIosSessionStream() {
    if (iosSessionStream) {
        iosSessionStream.getTracks().forEach(function(t) { t.stop(); });
        iosSessionStream = null;
    }
}

/**
 * Revoke current blob URL if set.
 */
function revokeBlobUrl() {
    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = null;
    }
}

/**
 * Clean up all TTS resources.
 * Called from voice.js onTtsChange when transitioning to idle.
 *
 * @param {AbortController | null} ttsAbort - current session's AbortController
 */
export function cleanupTtsResources(ttsAbort) {
    if (ttsAbort) {
        ttsAbort.abort();
    }

    // Stop the hidden audio element
    if (ttsPlayer) {
        ttsPlayer.pause();
        ttsPlayer.onended = null;
        ttsPlayer.onerror = null;
        ttsPlayer.currentTime = 0;
    }

    revokeBlobUrl();

    // Stop streaming audio (Web Audio API path)
    cleanupStreamAudio();

    // Release iOS audio session stream — safe to stop tracks now that
    // TTS playback has ended (or been cancelled).
    releaseIosSessionStream();
}
