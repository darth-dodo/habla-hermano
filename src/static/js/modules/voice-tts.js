/**
 * Habla Hermano - TTS (Text-to-Speech) Module
 * Phase 21: Extracted from voice.js for modularity.
 *
 * Uses a hidden <audio> element (Deepgram's recommended pattern) for
 * cross-device playback including iOS Safari after getUserMedia.
 * Audio data is fetched via POST, converted to a blob URL, then played
 * through the pre-initialized <audio id="tts-player"> element.
 */

import { createMachine } from './fsm.js';
import { chunkTextForTTS } from './voice-constants.js';

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

    var textChunks = chunkTextForTTS(text);
    var allBlobs = [];

    // Fetch audio for all chunks sequentially, then concatenate and play
    function fetchChunk(index) {
        if (signal.aborted) return;
        if (index >= textChunks.length) {
            // All chunks fetched — combine and play
            var combinedBlob = new Blob(allBlobs, { type: allBlobs[0].type });
            playAudio(combinedBlob);
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

    function playAudio(audioBlob) {
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

    fetchChunk(0);
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
}
