/**
 * Habla Hermano - TTS (Text-to-Speech) Module
 * Phase 21: Extracted from voice.js for modularity.
 *
 * Manages TTS WebSocket streaming, REST fallback, and audio playback.
 * Owns all TTS-specific resources in module scope.
 */

import { createMachine } from './fsm.js';
import { TTS_SAMPLE_RATE } from './voice-constants.js';

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
 * Assemble Float32 PCM chunks into a WAV Blob for wavesurfer.
 *
 * @param {Float32Array[]} chunks - array of Float32Array PCM chunks
 * @param {number} sampleRate - audio sample rate
 * @returns {Blob} WAV audio blob
 */
export function assembleWavBlob(chunks, sampleRate) {
    var totalLength = chunks.reduce(function(sum, c) { return sum + c.length; }, 0);
    var merged = new Float32Array(totalLength);
    var offset = 0;
    for (var i = 0; i < chunks.length; i++) {
        merged.set(chunks[i], offset);
        offset += chunks[i].length;
    }
    var buffer = new ArrayBuffer(44 + merged.length * 2);
    var view = new DataView(buffer);
    function writeString(o, s) { for (var j = 0; j < s.length; j++) view.setUint8(o + j, s.charCodeAt(j)); }
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + merged.length * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, merged.length * 2, true);
    for (var k = 0; k < merged.length; k++) {
        var s = Math.max(-1, Math.min(1, merged[k]));
        view.setInt16(44 + k * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
}

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
 * @param {function(Blob): void} [onAudioReady] - callback with assembled WAV blob after playback
 */
export function streamTTS(btn, text, voice, speed, audioCtx, signal, ttsService, showError, onAudioReady) {
    ttsSources = [];

    var nextStartTime = 0;
    var started = false;
    var totalScheduled = 0;
    var wsDone = false;
    var pcmChunks = [];

    var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(
        wsProtocol + '//' + location.host + '/ws/speak?voice=' + encodeURIComponent(voice)
    );
    ws.binaryType = 'arraybuffer';
    ttsWs = ws;

    function deliverBlob() {
        if (onAudioReady && pcmChunks.length > 0) {
            var wavBlob = assembleWavBlob(pcmChunks, TTS_SAMPLE_RATE);
            onAudioReady(wavBlob);
        }
    }

    ws.onopen = function() {
        if (signal.aborted) {
            ws.close(1000, 'Cancelled');
            return;
        }
        ws.send(JSON.stringify({ text: text }));
        // NOTE: Do NOT send close here. The server cancels the audio forwarding
        // task when _handle_browser_tts_messages returns, so sending close
        // before audio arrives would kill the stream. Instead, we detect
        // completion via Flushed/metadata messages from Deepgram.
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

            // Collect chunk for WAV blob assembly
            pcmChunks.push(floatData);

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
                    deliverBlob();
                    ttsService.send('ALL_ENDED');
                }
            };
        } else {
            // JSON metadata or control message
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === 'Flushed' || msg.type === 'metadata') {
                    // All audio for this text has been sent by Deepgram.
                    // Defense-in-depth: mark done even before ws.onclose fires.
                    wsDone = true;
                    if (totalScheduled <= 0) {
                        deliverBlob();
                        ttsService.send('ALL_ENDED');
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
            deliverBlob();
            ttsService.send('ALL_ENDED');
        } else {
            // Fallback: ensure cleanup runs after remaining audio finishes.
            // source.onended may not fire reliably for all scheduled buffers.
            var remaining = Math.max(0, nextStartTime - audioCtx.currentTime);
            ttsEndFallback = setTimeout(function() {
                if (signal.aborted) return;
                if (ttsService.matches('playing') || ttsService.matches('loading')) {
                    deliverBlob();
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
 * @param {function(Blob): void} [onAudioReady] - callback with audio blob when available
 */
export function restTTS(btn, text, voice, speed, signal, ttsService, showError, onAudioReady) {
    fetch('/api/speak', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ text: text, voice: voice }),
        signal: signal,
    }).then(function(response) {
        if (signal.aborted) return;
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.blob();
    }).then(function(audioBlob) {
        if (signal.aborted || !audioBlob) return;

        // Deliver blob to waveform before playing
        if (onAudioReady) onAudioReady(audioBlob);

        var audioUrl = URL.createObjectURL(audioBlob);
        var audio = new Audio(audioUrl);

        audio.playbackRate = speed;
        currentAudio = audio;
        currentBlobUrl = audioUrl;

        // Transition to playing (REST buffers full response, so go straight to playing)
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
