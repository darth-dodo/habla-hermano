/**
 * Habla Hermano - TTS (Text-to-Speech) Module
 * Phase 21: Extracted from voice.js for modularity.
 *
 * Manages TTS WebSocket streaming, REST fallback, and audio playback.
 * Owns all TTS-specific resources in module scope.
 */

import { createMachine } from './fsm.js';
import { TTS_SAMPLE_RATE, chunkTextForTTS } from './voice-constants.js';

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

var ttsWs = null;
var ttsSources = [];
var ttsEndFallback = null;

// REST fallback TTS
var currentAudio = null;
var currentBlobUrl = null;

/**
 * WebSocket streaming TTS — sends text to /ws/speak, receives PCM audio
 * chunks, and plays them via AudioContext for near-instant playback.
 *
 * @param {HTMLElement} btn - speaker button for error tooltips
 * @param {string} text - text to synthesize
 * @param {string} voice - Deepgram voice ID
 * @param {number} speed - playback rate (0.25–2.0)
 * @param {AudioContext} audioCtx - shared AudioContext
 * @param {AbortSignal} signal - cancellation signal
 * @param {object} ttsService - FSM service to send events
 * @param {function(HTMLElement, string): void} showError - error display callback
 */
export function streamTTS(btn, text, voice, speed, audioCtx, signal, ttsService, showError) {
    ttsSources = [];

    var nextStartTime = 0;
    var started = false;
    var totalScheduled = 0;
    var wsDone = false;

    // Chunk text for the server's MAX_TTS_TEXT_LENGTH limit
    var textChunks = chunkTextForTTS(text);
    var totalChunks = textChunks.length;
    var flushedCount = 0;

    var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(
        wsProtocol + '//' + location.host + '/ws/speak?voice=' + encodeURIComponent(voice)
    );
    ws.binaryType = 'arraybuffer';
    ttsWs = ws;

    ws.onopen = function() {
        if (signal.aborted) {
            ws.close(1000, 'Cancelled');
            return;
        }
        // Send all chunks; server forwards each as Speak+Flush to Deepgram
        for (var i = 0; i < textChunks.length; i++) {
            ws.send(JSON.stringify({ text: textChunks[i] }));
        }
    };

    ws.onmessage = function(event) {
        if (signal.aborted) return;

        // Safari may deliver ArrayBuffer as Blob despite binaryType='arraybuffer'
        if (event.data instanceof Blob) {
            event.data.arrayBuffer().then(function(ab) {
                if (signal.aborted) return;
                ws.onmessage({ data: ab });
            });
            return;
        }

        if (event.data instanceof ArrayBuffer) {
            var pcmData = new Int16Array(event.data);
            var floatData = new Float32Array(pcmData.length);
            for (var i = 0; i < pcmData.length; i++) {
                floatData[i] = pcmData[i] / 32768.0;
            }

            var audioBuffer = audioCtx.createBuffer(1, floatData.length, TTS_SAMPLE_RATE);
            audioBuffer.getChannelData(0).set(floatData);

            var source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.playbackRate.value = speed;
            source.connect(audioCtx.destination);
            ttsSources.push(source);

            var startAt = Math.max(audioCtx.currentTime, nextStartTime);
            source.start(startAt);
            nextStartTime = startAt + (audioBuffer.duration / speed);
            totalScheduled++;

            // Transition to playing on first chunk
            if (!started) {
                started = true;
                ttsService.send('STREAMING');
            }

            // Detect end of playback on last scheduled buffer
            source.onended = function() {
                if (signal.aborted) return;
                totalScheduled--;
                if (totalScheduled <= 0 && wsDone) {
                    ttsService.send('ALL_ENDED');
                }
            };
        } else {
            // JSON metadata or control message
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === 'Flushed' || msg.type === 'metadata') {
                    flushedCount++;
                    // Only mark done when all chunks have been flushed
                    if (flushedCount >= totalChunks) {
                        wsDone = true;
                        if (totalScheduled <= 0) {
                            ttsService.send('ALL_ENDED');
                        }
                    }
                }
            } catch (_) {}
        }
    };

    ws.onerror = function() {
        if (signal.aborted) return;
        showError(btn, 'Could not play audio');
        ttsService.send('ERROR');
    };

    ws.onclose = function(event) {
        if (signal.aborted) return;
        // If no audio was ever received, show an error
        if (!started && event.code !== 1000) {
            if (event.code === 1011) {
                showError(btn, 'Speech service error -- try again');
            } else if (event.code === 1008) {
                showError(btn, event.reason || 'Invalid voice request');
            } else {
                showError(btn, 'Could not play audio');
            }
            ttsService.send('ERROR');
            return;
        }
        wsDone = true;
        if (totalScheduled <= 0) {
            ttsService.send('ALL_ENDED');
        } else {
            // Fallback: ensure cleanup runs after remaining audio finishes.
            // source.onended may not fire reliably for all scheduled buffers.
            var remaining = Math.max(0, nextStartTime - audioCtx.currentTime);
            ttsEndFallback = setTimeout(function() {
                if (signal.aborted) return;
                if (ttsService.matches('playing') || ttsService.matches('loading')) {
                    ttsService.send('ALL_ENDED');
                }
            }, (remaining * 1000) + 500);
        }
    };
}

/**
 * REST fallback TTS — buffers entire response then plays.
 * Used when AudioContext is not available.
 *
 * @param {HTMLElement} btn - speaker button for error tooltips
 * @param {string} text - text to synthesize
 * @param {string} voice - Deepgram voice ID
 * @param {number} speed - playback rate
 * @param {AbortSignal} signal - cancellation signal
 * @param {object} ttsService - FSM service to send events
 * @param {function(HTMLElement, string): void} showError - error display callback
 */
export function restTTS(btn, text, voice, speed, signal, ttsService, showError, prewarmedAudio) {
    var textChunks = chunkTextForTTS(text);
    var allBlobs = [];

    // Fetch audio for all chunks sequentially, then concatenate and play
    function fetchChunk(index) {
        if (signal.aborted) return;
        if (index >= textChunks.length) {
            // All chunks fetched — combine and play
            var combinedBlob = new Blob(allBlobs, { type: allBlobs[0].type });
            playRestAudio(combinedBlob);
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

    function playRestAudio(audioBlob) {
        if (signal.aborted) return;

        var audioUrl = URL.createObjectURL(audioBlob);
        // Reuse pre-warmed Audio element if provided (iOS gesture unlock),
        // otherwise create a new one.
        var audio = prewarmedAudio || new Audio();
        audio.src = audioUrl;
        audio.playbackRate = speed;
        audio.muted = false;
        audio.volume = 1;
        currentAudio = audio;
        currentBlobUrl = audioUrl;

        ttsService.send('STREAMING');

        audio.onended = function() {
            if (signal.aborted) return;
            URL.revokeObjectURL(audioUrl);
            currentBlobUrl = null;
            currentAudio = null;
            ttsService.send('ALL_ENDED');
        };

        audio.onerror = function() {
            if (signal.aborted) return;
            URL.revokeObjectURL(audioUrl);
            currentBlobUrl = null;
            currentAudio = null;
            showError(btn, 'Audio playback failed');
            ttsService.send('ERROR');
        };

        audio.play().catch(function() {
            if (signal.aborted) return;
            URL.revokeObjectURL(audioUrl);
            currentBlobUrl = null;
            currentAudio = null;
            showError(btn, 'Could not play audio');
            ttsService.send('ERROR');
        });
    }

    fetchChunk(0);
}

/**
 * Clean up all TTS resources (WebSocket, sources, fallback timer, REST audio).
 * Called from voice.js onTtsChange when transitioning to idle.
 *
 * @param {AbortController | null} ttsAbort - current session's AbortController
 */
export function cleanupTtsResources(ttsAbort) {
    if (ttsAbort) {
        ttsAbort.abort();
    }

    if (ttsEndFallback) {
        clearTimeout(ttsEndFallback);
        ttsEndFallback = null;
    }

    if (ttsWs) {
        if (ttsWs.readyState === WebSocket.OPEN) {
            try { ttsWs.send(JSON.stringify({ type: 'close' })); } catch (_) {}
        }
        if (ttsWs.readyState === WebSocket.OPEN || ttsWs.readyState === WebSocket.CONNECTING) {
            ttsWs.close();
        }
        ttsWs = null;
    }

    // Stop all scheduled AudioBufferSourceNodes
    if (ttsSources && ttsSources.length > 0) {
        ttsSources.forEach(function(source) {
            try { source.stop(); } catch (_) {}
        });
        ttsSources = [];
    }

    // Stop REST fallback audio
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.onended = null;
        currentAudio.onerror = null;
        currentAudio = null;
    }
    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = null;
    }
}

