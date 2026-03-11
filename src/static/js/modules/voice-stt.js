/**
 * Habla Hermano - STT (Speech-to-Text) Module
 * Phase 21: Extracted from voice.js for modularity.
 *
 * Manages STT WebSocket, audio capture pipeline, and transcript accumulation.
 * Owns all STT-specific resources in module scope.
 */

import { createMachine } from './fsm.js';
import { STT_SAMPLE_RATE, floatTo16BitPCM, downsample } from './voice-constants.js';

// ============================================
// STT State Machine Definition
// ============================================

export var sttMachine = createMachine({
    initial: 'idle',
    states: {
        idle: { on: { START: 'connecting' } },
        connecting: { on: { CONNECTED: 'recording', ERROR: 'idle', CANCEL: 'idle' } },
        recording: { on: { STOP: 'processing', ERROR: 'idle', CANCEL: 'idle' } },
        processing: { on: { PROCESSED: 'idle', ERROR: 'idle' } },
    },
});

// ============================================
// Module-scoped STT Resources
// ============================================

var sttWs = null;
var sttStream = null;
var sttScriptProcessor = null;
var sttWorkletNode = null;
var sttAudioCtx = null;
var sttAnalyser = null;
var sttSource = null;
var sttFinalTranscript = '';

/**
 * Get the current AnalyserNode (for level animation in voice.js).
 */
export function getAnalyser() {
    return sttAnalyser;
}

/**
 * Get the current media stream (for cleanup in destroyVoice).
 */
export function getStream() {
    return sttStream;
}

/**
 * Reset the final transcript accumulator.
 */
export function resetTranscript() {
    sttFinalTranscript = '';
}

/**
 * Start a recording session: getUserMedia, AudioContext, WebSocket.
 * All async callbacks check signal.aborted before acting.
 *
 * @param {AbortSignal} signal
 * @param {object} sttService - FSM service to send events
 * @param {HTMLTextAreaElement} chatInput - textarea for transcript display
 * @param {function(string): void} showError - error display callback
 * @param {function(): void} [onFinalTranscript] - called when a final transcript arrives
 */
export function startRecordingSession(signal, sttService, chatInput, showError, onFinalTranscript) {
    var language = 'multi'; // code-switching (learners mix English + target language)

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showError('Voice input is not supported in this browser');
        sttService.send('ERROR');
        return;
    }

    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
        showError('Voice input is not supported in this browser');
        sttService.send('ERROR');
        return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        // Race condition fix: if user cancelled while getUserMedia was pending
        if (signal.aborted) {
            stream.getTracks().forEach(function(t) { t.stop(); });
            return;
        }

        sttStream = stream;

        // Monitor track state for phone calls, screen lock, permission revocation
        var audioTrack = stream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.addEventListener('ended', function() {
                if (signal.aborted) return;
                if (sttService.matches('recording')) {
                    sttService.send('ERROR');
                    showError('Recording interrupted -- tap mic to restart');
                }
            });
        }

        // Create AudioContext for both PCM capture and level bars
        sttAudioCtx = new Ctx();
        var source = sttAudioCtx.createMediaStreamSource(stream);
        sttSource = source;

        // Analyser for level bars (doesn't affect audio pipeline)
        sttAnalyser = sttAudioCtx.createAnalyser();
        sttAnalyser.fftSize = 256;
        sttAnalyser.smoothingTimeConstant = 0.7;
        source.connect(sttAnalyser);

        // Audio capture: prefer AudioWorklet (mobile-safe), fall back to ScriptProcessor
        function sendPCM(float32) {
            if (signal.aborted) return;
            if (!sttService.matches('recording')) return;
            if (!sttWs || sttWs.readyState !== WebSocket.OPEN) return;
            var downsampled = downsample(float32, sttAudioCtx.sampleRate, STT_SAMPLE_RATE);
            sttWs.send(floatTo16BitPCM(downsampled));
        }

        function setupScriptProcessor() {
            var processor = sttAudioCtx.createScriptProcessor(4096, 1, 1);
            sttScriptProcessor = processor;
            processor.onaudioprocess = function(e) {
                sendPCM(e.inputBuffer.getChannelData(0));
            };
            source.connect(processor);
            processor.connect(sttAudioCtx.destination);
        }

        if (sttAudioCtx.audioWorklet) {
            sttAudioCtx.audioWorklet.addModule('/static/js/pcm-processor.js').then(function() {
                if (signal.aborted) return;
                var workletNode = new AudioWorkletNode(sttAudioCtx, 'pcm-processor');
                sttWorkletNode = workletNode;
                workletNode.port.onmessage = function(e) { sendPCM(e.data); };
                source.connect(workletNode);
            }).catch(function() {
                if (signal.aborted) return;
                setupScriptProcessor(); // Fallback for module load failure
            });
        } else {
            setupScriptProcessor(); // Fallback for browsers without AudioWorklet
        }

        // Open WebSocket for STT
        var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        sttWs = new WebSocket(
            wsProtocol + '//' + location.host + '/ws/transcribe?language=' + encodeURIComponent(language)
        );

        sttWs.onopen = function() {
            if (signal.aborted) {
                sttWs.close(1000, 'Cancelled');
                return;
            }
            sttService.send('CONNECTED');
        };

        sttWs.onmessage = function(event) {
            if (signal.aborted) return;
            var data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            if (chatInput && data.transcript) {
                if (data.is_final) {
                    sttFinalTranscript += (sttFinalTranscript ? ' ' : '') + data.transcript;
                    chatInput.value = sttFinalTranscript;
                    chatInput.classList.remove('voice-interim');
                    // Notify voice.js to dismiss processing state early
                    if (onFinalTranscript) onFinalTranscript();
                } else {
                    var prefix = sttFinalTranscript ? sttFinalTranscript + ' ' : '';
                    chatInput.value = prefix + data.transcript;
                    chatInput.classList.add('voice-interim');
                }
                // Trigger auto-resize (input event listener in main.js)
                chatInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        sttWs.onerror = function() {
            if (signal.aborted) return;
            showError('Voice input temporarily unavailable');
            sttService.send('ERROR');
        };

        sttWs.onclose = function(event) {
            if (signal.aborted) return;
            // If we're still in connecting or recording, this is unexpected
            if (sttService.matches('connecting') || sttService.matches('recording')) {
                if (event.code === 1011) {
                    showError('Voice service error -- please try again');
                } else if (event.code === 1008) {
                    showError(event.reason || 'Invalid request');
                } else if (event.code !== 1000 && event.code !== 1001) {
                    showError('Voice connection lost');
                }
                sttService.send('ERROR');
            }
        };
    }).catch(function(err) {
        if (signal.aborted) return;
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            showError('Microphone access needed for voice input');
        } else if (err.name === 'NotReadableError') {
            showError('Microphone is in use by another app');
        } else {
            showError('Could not access microphone');
        }
        sttService.send('ERROR');
    });
}

/**
 * Disconnect audio processing nodes and stop media tracks.
 */
export function teardownSttAudio() {
    // 1. Disconnect audio processing nodes (stops data flow)
    if (sttScriptProcessor) {
        sttScriptProcessor.onaudioprocess = null;
        try { sttScriptProcessor.disconnect(); } catch (_) {}
        sttScriptProcessor = null;
    }
    if (sttWorkletNode) {
        sttWorkletNode.port.postMessage('stop');
        try { sttWorkletNode.disconnect(); } catch (_) {}
        sttWorkletNode = null;
    }

    // 2. Null analyser (level animation uses getAnalyser())
    sttAnalyser = null;

    // 3. Disconnect MediaStreamAudioSourceNode
    if (sttSource) {
        try { sttSource.disconnect(); } catch (_) {}
        sttSource = null;
    }

    // 4. Stop all MediaStream tracks (releases microphone hardware)
    if (sttStream) {
        sttStream.getTracks().forEach(function(t) { t.stop(); });
        sttStream = null;
    }

    // 5. Close AudioContext AFTER tracks are stopped
    if (sttAudioCtx && sttAudioCtx.state !== 'closed') {
        sttAudioCtx.close().catch(function() {});
    }
    sttAudioCtx = null;
}

/**
 * Close STT WebSocket and detach handlers.
 */
export function closeSttWs() {
    if (sttWs) {
        if (sttWs.readyState === WebSocket.OPEN || sttWs.readyState === WebSocket.CONNECTING) {
            sttWs.close(1000, 'Recording stopped');
        }
        sttWs.onmessage = null;
        sttWs.onerror = null;
        sttWs.onclose = null;
        sttWs = null;
    }
}
