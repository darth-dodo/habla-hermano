/**
 * Habla Hermano - Voice Module
 * Phase 21: FSM + AbortController refactor.
 * Mic button for speech-to-text, speaker icon for text-to-speech.
 *
 * TTS uses WebSocket streaming for low-latency playback (~300ms to first audio).
 * Falls back to REST API for browsers without AudioContext support.
 *
 * Two finite state machines (STT and TTS) replace boolean flags.
 * One AbortController per session replaces generation counters.
 */

import { createMachine, interpret } from './fsm.js';

// ============================================
// Constants
// ============================================

// Masculine voices -- matches Hermano "big brother" persona
var VOICES = {
    es: 'aura-2-nestor-es',
    de: 'aura-2-julius-de',
    fr: 'aura-2-hector-fr',
};

var STT_SAMPLE_RATE = 16000; // Deepgram expects 16kHz linear16
var TTS_SAMPLE_RATE = 24000; // Deepgram TTS output sample rate
var DEFAULT_TTS_SPEED = 1.0; // 0.5 = half speed, 1.0 = normal, 2.0 = double

var MIC_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />'
    + '<line x1="12" y1="19" x2="12" y2="23" />'
    + '<line x1="8" y1="23" x2="16" y2="23" />'
    + '</svg>';

var STOP_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
    + '</svg>';

var LEVEL_BARS_HTML = '<div class="voice-level-bars" aria-hidden="true">'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '</div>';

var SPINNER_HTML = '<div class="voice-spinner" aria-hidden="true"></div>';

var SPEAKER_ICON = '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<path d="M15.54 8.46a5 5 0 0 1 0 7.07" />'
    + '<path d="M19.07 4.93a10 10 0 0 1 0 14.14" />'
    + '</svg>';

var SPEAKER_PLAYING_ICON = '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<line x1="23" y1="9" x2="17" y2="15" />'
    + '<line x1="17" y1="9" x2="23" y2="15" />'
    + '</svg>';

// ============================================
// Audio Utility Functions
// ============================================

/**
 * Convert Float32 audio samples to Int16 (linear16) for Deepgram.
 */
function floatTo16BitPCM(float32Array) {
    var buffer = new ArrayBuffer(float32Array.length * 2);
    var view = new DataView(buffer);
    for (var i = 0; i < float32Array.length; i++) {
        var s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
}

/**
 * Downsample audio from source sample rate to target sample rate.
 */
function downsample(buffer, sourceSampleRate, targetSampleRate) {
    if (sourceSampleRate === targetSampleRate) return buffer;
    var ratio = sourceSampleRate / targetSampleRate;
    var newLength = Math.round(buffer.length / ratio);
    var result = new Float32Array(newLength);
    for (var i = 0; i < newLength; i++) {
        var index = Math.round(i * ratio);
        result[i] = buffer[index];
    }
    return result;
}

// ============================================
// Module State
// ============================================

// FSM services (created in initVoice)
var sttService = null;
var ttsService = null;

// AbortControllers for current sessions (null when idle)
var sttAbort = null;
var ttsAbort = null;

// DOM references (set in initVoice)
var micButton = null;
var chatInput = null;
var sendButton = null;
var micWrapper = null;

// Shared TTS AudioContext (Safari limits to 4 instances)
var sharedTtsCtx = null;

// STT audio capture resources (managed by STT session)
var sttWs = null;
var sttStream = null;
var sttScriptProcessor = null;
var sttWorkletNode = null;
var sttAudioCtx = null;
var sttAnalyser = null;
var sttSource = null;
var sttFinalTranscript = '';

// STT UI state
var levelAnimFrame = null;
var timerInterval = null;
var timerStartTime = 0;
var timerElement = null;
var processingTimeout = null;
var processingIndicator = null;

// TTS resources (managed by TTS session)
var ttsWs = null;
var ttsAudioCtx = null;
var ttsSources = [];
var ttsEndFallback = null;
var ttsActiveBtn = null;

// REST fallback TTS
var currentAudio = null;
var currentBlobUrl = null;

// Stop bar
var stopBar = null;

// Error tooltip timeouts
var errorTimeouts = {};

// ============================================
// STT State Machine
// ============================================

var sttMachine = createMachine({
    initial: 'idle',
    states: {
        idle: {
            on: { START: 'connecting' },
        },
        connecting: {
            on: {
                CONNECTED: 'recording',
                ERROR: 'idle',
                CANCEL: 'idle',
            },
        },
        recording: {
            on: {
                STOP: 'processing',
                ERROR: 'idle',
                CANCEL: 'idle',
            },
        },
        processing: {
            on: {
                PROCESSED: 'idle',
                ERROR: 'idle',
            },
        },
    },
});

/**
 * STT state change handler. All side effects for STT transitions live here.
 */
function onSttChange(state, prev) {
    // --- entering connecting ---
    if (state === 'connecting' && prev === 'idle') {
        sttAbort = new AbortController();
        sttFinalTranscript = '';
        startRecordingSession(sttAbort.signal);
    }

    // --- entering recording (from connecting) ---
    if (state === 'recording' && prev === 'connecting') {
        setSendEnabled(false);
        showMicRecording();
        startTimer();
        startLevelAnimation();
    }

    // --- entering processing (from recording) ---
    if (state === 'processing' && prev === 'recording') {
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        showProcessing();
    }

    // --- entering idle (from connecting on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'connecting') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        restoreMicIcon();
        setSendEnabled(true);
    }

    // --- entering idle (from recording on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'recording') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        stopTimer();
        stopLevelAnimation();
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        restoreMicIcon();
        setSendEnabled(true);
    }

    // --- entering idle (from processing) ---
    if (state === 'idle' && prev === 'processing') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        hideProcessing();
    }
}

// ============================================
// TTS State Machine
// ============================================

var ttsMachine = createMachine({
    initial: 'idle',
    states: {
        idle: {
            on: { PLAY: 'loading' },
        },
        loading: {
            on: {
                STREAMING: 'playing',
                ALL_ENDED: 'idle',
                ERROR: 'idle',
                CANCEL: 'idle',
            },
        },
        playing: {
            on: {
                ALL_ENDED: 'idle',
                ERROR: 'idle',
                CANCEL: 'idle',
            },
        },
    },
});

/**
 * TTS state change handler. All side effects for TTS transitions live here.
 */
function onTtsChange(state, prev) {
    // --- entering loading (from idle) ---
    if (state === 'loading' && prev === 'idle') {
        ttsAbort = new AbortController();
    }

    // --- entering playing (from loading) ---
    if (state === 'playing' && prev === 'loading') {
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading');
            ttsActiveBtn.classList.add('voice-playing');
            ttsActiveBtn.innerHTML = SPEAKER_PLAYING_ICON;
        }
        showStopBar();
    }

    // --- entering idle (from loading on ERROR/CANCEL/ALL_ENDED) ---
    if (state === 'idle' && prev === 'loading') {
        cleanupTtsResources();
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading', 'voice-playing');
            ttsActiveBtn.innerHTML = SPEAKER_ICON;
        }
        hideStopBar();
        ttsActiveBtn = null;
    }

    // --- entering idle (from playing on ALL_ENDED/ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'playing') {
        cleanupTtsResources();
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading', 'voice-playing');
            ttsActiveBtn.innerHTML = SPEAKER_ICON;
        }
        hideStopBar();
        ttsActiveBtn = null;
    }
}

// ============================================
// STT Functions
// ============================================

/**
 * Start a recording session: getUserMedia, AudioContext, WebSocket.
 * All async callbacks check signal.aborted before acting.
 */
function startRecordingSession(signal) {
    var language = 'multi'; // code-switching (learners mix English + target language)

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showMicError('Voice input is not supported in this browser');
        sttService.send('ERROR');
        return;
    }

    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
        showMicError('Voice input is not supported in this browser');
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
                    showMicError('Recording interrupted -- tap mic to restart');
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
                    // Dismiss processing state early on final transcript
                    if (processingTimeout) hideProcessing();
                } else {
                    var prefix = sttFinalTranscript ? sttFinalTranscript + ' ' : '';
                    chatInput.value = prefix + data.transcript;
                    chatInput.classList.add('voice-interim');
                }
                if (window.autoResizeInput) window.autoResizeInput();
            }
        };

        sttWs.onerror = function() {
            if (signal.aborted) return;
            showMicError('Voice input temporarily unavailable');
            sttService.send('ERROR');
        };

        sttWs.onclose = function(event) {
            if (signal.aborted) return;
            // If we're still in connecting or recording, this is unexpected
            if (sttService.matches('connecting') || sttService.matches('recording')) {
                if (event.code === 1011) {
                    showMicError('Voice service error -- please try again');
                } else if (event.code === 1008) {
                    showMicError(event.reason || 'Invalid request');
                } else if (event.code !== 1000 && event.code !== 1001) {
                    showMicError('Voice connection lost');
                }
                sttService.send('ERROR');
            }
        };
    }).catch(function(err) {
        if (signal.aborted) return;
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            showMicError('Microphone access needed for voice input');
        } else if (err.name === 'NotReadableError') {
            showMicError('Microphone is in use by another app');
        } else {
            showMicError('Could not access microphone');
        }
        sttService.send('ERROR');
    });
}

/**
 * Disconnect audio processing nodes and stop media tracks.
 */
function teardownSttAudio() {
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

    // 2. Stop level animation data (cancel rAF, null analyser)
    if (levelAnimFrame) {
        cancelAnimationFrame(levelAnimFrame);
        levelAnimFrame = null;
    }
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
function closeSttWs() {
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

// ============================================
// TTS Functions
// ============================================

/**
 * WebSocket streaming TTS -- sends text to /ws/speak, receives PCM audio
 * chunks, and plays them via AudioContext for near-instant playback.
 */
function streamTTS(btn, text, voice, speed, audioCtx, signal) {
    ttsAudioCtx = audioCtx;
    ttsSources = [];

    var nextStartTime = 0;
    var started = false;
    var totalScheduled = 0;
    var wsDone = false;

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
        ws.send(JSON.stringify({ text: text }));
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
                    // All audio for this text has been sent
                }
            } catch (_) {}
        }
    };

    ws.onerror = function() {
        if (signal.aborted) return;
        showTooltipError(btn, 'Could not play audio');
        ttsService.send('ERROR');
    };

    ws.onclose = function(event) {
        if (signal.aborted) return;
        // If no audio was ever received, show an error
        if (!started && event.code !== 1000) {
            if (event.code === 1011) {
                showTooltipError(btn, 'Speech service error -- try again');
            } else if (event.code === 1008) {
                showTooltipError(btn, event.reason || 'Invalid voice request');
            } else {
                showTooltipError(btn, 'Could not play audio');
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
 * REST fallback TTS -- buffers entire response then plays.
 * Used when AudioContext is not available.
 */
function restTTS(btn, text, voice, speed, signal) {
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
            showTooltipError(btn, 'Audio playback failed');
            ttsService.send('ERROR');
        };

        audio.play().catch(function() {
            if (signal.aborted) return;
            URL.revokeObjectURL(audioUrl);
            currentBlobUrl = null;
            currentAudio = null;
            showTooltipError(btn, 'Could not play audio');
            ttsService.send('ERROR');
        });
    }).catch(function(err) {
        if (signal.aborted) return;
        if (err.name === 'AbortError') return;
        var msg = (err && err.message && err.message.indexOf('503') !== -1)
            ? 'Speech service not configured'
            : 'Could not play audio';
        showTooltipError(btn, msg);
        ttsService.send('ERROR');
    });
}

/**
 * Clean up all TTS resources (WebSocket, sources, fallback timer, REST audio).
 */
function cleanupTtsResources() {
    if (ttsAbort) {
        ttsAbort.abort();
        ttsAbort = null;
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

    // Don't close shared AudioContext -- it's reused across TTS sessions
    ttsAudioCtx = null;
}

// ============================================
// UI Helpers: Mic
// ============================================

/**
 * Show mic button in recording state (level bars).
 */
function showMicRecording() {
    if (!micButton) return;
    micButton.classList.add('voice-recording');
    micButton.setAttribute('aria-label', 'Stop recording');
    micButton.innerHTML = LEVEL_BARS_HTML;
}

/**
 * Restore mic button to default idle state.
 */
function restoreMicIcon() {
    if (!micButton) return;
    micButton.classList.remove('voice-recording');
    micButton.setAttribute('aria-label', 'Record voice message');
    micButton.innerHTML = MIC_ICON;
}

/**
 * Enable or disable the send button and textarea during recording/processing.
 */
function setSendEnabled(enabled) {
    if (sendButton) sendButton.disabled = !enabled;
    if (chatInput) chatInput.readOnly = !enabled;
}

/**
 * Show an error tooltip near the mic button.
 */
function showMicError(message) {
    var anchor = micWrapper || micButton;
    showTooltipError(anchor, message);
}

// ============================================
// UI Helpers: Tooltips
// ============================================

/**
 * Show an error tooltip near any element. Reusable for mic and speaker errors.
 */
function showTooltipError(anchor, message) {
    if (!anchor) return;

    var timeoutKey = anchor.id || 'anon';
    if (errorTimeouts[timeoutKey]) clearTimeout(errorTimeouts[timeoutKey]);

    var parent = anchor.closest('.flex') || anchor.parentElement;
    var existing = parent.querySelector('.voice-error-tooltip');
    if (existing) existing.remove();

    var tooltip = document.createElement('div');
    tooltip.className = 'voice-error-tooltip';
    tooltip.textContent = message;
    tooltip.setAttribute('role', 'alert');

    parent.style.position = 'relative';
    parent.appendChild(tooltip);

    errorTimeouts[timeoutKey] = setTimeout(function() {
        if (tooltip.parentElement) tooltip.remove();
        delete errorTimeouts[timeoutKey];
    }, 4000);
}

// ============================================
// UI Helpers: Timer
// ============================================

/**
 * Start the recording timer display.
 */
function startTimer() {
    if (!micWrapper) return;
    timerStartTime = Date.now();

    var timer = document.createElement('div');
    timer.className = 'voice-timer';
    timer.textContent = '0:00';
    timer.setAttribute('aria-hidden', 'true');
    timerElement = timer;
    micWrapper.appendChild(timer);

    timerInterval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - timerStartTime) / 1000);
        var min = Math.floor(elapsed / 60);
        var sec = elapsed % 60;
        timer.textContent = min + ':' + (sec < 10 ? '0' : '') + sec;
    }, 1000);
}

/**
 * Stop and remove the recording timer.
 */
function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    if (timerElement && timerElement.parentElement) {
        timerElement.remove();
    }
    timerElement = null;
    timerStartTime = 0;
}

// ============================================
// UI Helpers: Level Bars
// ============================================

/**
 * Start the audio level bar animation.
 */
function startLevelAnimation() {
    if (!sttAnalyser) return;
    var dataArray = new Uint8Array(sttAnalyser.frequencyBinCount);

    // Respect prefers-reduced-motion: skip animation loop (CSS gives static height)
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    function animate() {
        if (!sttService || !sttService.matches('recording')) return;
        sttAnalyser.getByteFrequencyData(dataArray);

        var bars = micButton ? micButton.querySelectorAll('.voice-bar') : [];
        var bins = [1, 3, 6, 10]; // Voice-frequency bins
        for (var i = 0; i < bars.length; i++) {
            var val = dataArray[bins[i]] || 0;
            var height = Math.max(3, (val / 255) * 18);
            bars[i].style.height = height + 'px';
        }
        levelAnimFrame = requestAnimationFrame(animate);
    }
    levelAnimFrame = requestAnimationFrame(animate);
}

/**
 * Stop the audio level bar animation.
 */
function stopLevelAnimation() {
    if (levelAnimFrame) {
        cancelAnimationFrame(levelAnimFrame);
        levelAnimFrame = null;
    }
    sttAnalyser = null;
}

// ============================================
// UI Helpers: Processing Indicator
// ============================================

/**
 * Show the processing spinner and pill after recording stops.
 */
function showProcessing() {
    if (!micButton) return;

    micButton.classList.remove('voice-recording');
    micButton.innerHTML = SPINNER_HTML;
    micButton.setAttribute('aria-label', 'Processing speech\u2026');

    if (micWrapper) {
        var indicator = document.createElement('div');
        indicator.className = 'voice-processing-indicator';
        indicator.textContent = 'Processing\u2026';
        processingIndicator = indicator;
        micWrapper.appendChild(indicator);
    }

    // Auto-dismiss after 2 seconds
    processingTimeout = setTimeout(function() {
        sttService.send('PROCESSED');
    }, 2000);
}

/**
 * Hide the processing indicator and restore mic button.
 */
function hideProcessing() {
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    if (processingIndicator && processingIndicator.parentElement) {
        processingIndicator.remove();
    }
    processingIndicator = null;

    // Safety: ensure timer is fully stopped
    stopTimer();

    restoreMicIcon();
    setSendEnabled(true);
}

// ============================================
// UI Helpers: Stop Bar
// ============================================

/**
 * Show a floating stop bar above the input area during TTS playback.
 */
function showStopBar() {
    if (stopBar) return; // Already visible

    var bar = document.createElement('div');
    bar.className = 'voice-stop-bar';
    bar.innerHTML = '<button type="button" class="voice-stop-btn" aria-label="Stop audio playback">'
        + '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
        + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
        + '</svg>'
        + '<span>Stop</span>'
        + '</button>';

    bar.querySelector('.voice-stop-btn').addEventListener('click', function() {
        stopAllTTS();
    });

    var footer = document.querySelector('footer');
    if (footer && footer.parentNode) {
        footer.parentNode.insertBefore(bar, footer);
    } else {
        document.body.appendChild(bar);
    }
    stopBar = bar;
}

/**
 * Hide the floating stop bar.
 */
function hideStopBar() {
    if (stopBar) {
        stopBar.remove();
        stopBar = null;
    }
}

// ============================================
// Public API
// ============================================

/**
 * Initialize voice module. Called once on DOMContentLoaded.
 */
export function initVoice() {
    micButton = document.getElementById('mic-btn');
    chatInput = document.getElementById('message-input');
    sendButton = document.getElementById('send-btn');

    if (!micButton) return; // Voice not enabled

    // Wrap mic button for floating indicators (timer, processing pill)
    if (micButton.parentNode) {
        var wrapper = document.createElement('div');
        wrapper.className = 'flex-shrink-0 relative';
        micButton.parentNode.insertBefore(wrapper, micButton);
        wrapper.appendChild(micButton);
        micWrapper = wrapper;
    }

    // Create FSM services
    sttService = interpret(sttMachine, onSttChange);
    ttsService = interpret(ttsMachine, onTtsChange);

    // Mic button click
    micButton.addEventListener('click', function() {
        toggleRecording();
    });

    // Delegate speaker icon clicks
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.voice-speak-btn');
        if (btn) handleSpeakClick(btn);
    });

    // Handle page visibility changes (background/foreground)
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            // iOS kills MediaStream tracks when backgrounded -- stop cleanly
            if (sttService.matches('recording') || sttService.matches('connecting')) {
                sttService.send('CANCEL');
            }
        }
    });
}

/**
 * Tear down voice module. Called on beforeunload.
 */
export function destroyVoice() {
    // 1. Stop any active recording
    if (sttService && !sttService.matches('idle')) {
        sttService.send('CANCEL');
    }

    // 2. Stop any active TTS
    if (ttsService && !ttsService.matches('idle')) {
        ttsService.send('CANCEL');
    }

    // 3. Stop FSM services
    if (sttService) { sttService.stop(); sttService = null; }
    if (ttsService) { ttsService.stop(); ttsService = null; }

    // 4. Close/suspend shared TTS AudioContext
    if (sharedTtsCtx && sharedTtsCtx.state !== 'closed') {
        sharedTtsCtx.close().catch(function() {});
        sharedTtsCtx = null;
    }

    // 5. Defensive: stop mic stream tracks
    if (sttStream) {
        sttStream.getTracks().forEach(function(t) { t.stop(); });
        sttStream = null;
    }

    // 6. Clear pending timeouts
    if (ttsEndFallback) {
        clearTimeout(ttsEndFallback);
        ttsEndFallback = null;
    }
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    Object.keys(errorTimeouts).forEach(function(key) {
        clearTimeout(errorTimeouts[key]);
    });
    errorTimeouts = {};

    // 7. Stop timer and level animation
    stopTimer();
    stopLevelAnimation();

    // 8. Hide stop bar and processing indicator
    hideStopBar();
    if (processingIndicator && processingIndicator.parentElement) {
        processingIndicator.remove();
    }
    processingIndicator = null;

    // 9. Null out DOM refs
    micButton = null;
    chatInput = null;
    sendButton = null;
    micWrapper = null;
}

/**
 * Toggle microphone recording on/off.
 */
export function toggleRecording() {
    if (!sttService) return;
    if (sttService.matches('idle')) {
        sttService.send('START');
    } else if (sttService.matches('recording')) {
        sttService.send('STOP');
    }
    // In connecting or processing state, ignore clicks (brief transient states)
}

/**
 * Handle a speaker button click for TTS playback.
 */
export function handleSpeakClick(btn) {
    var text = btn.dataset.text;
    var language = btn.dataset.language || 'es';
    // Read live speed from picker; fall back to button's data-speed, then default
    var picker = document.getElementById('tts-speed-picker');
    var speed = parseFloat((picker && picker.dataset.ttsSpeed) || btn.dataset.speed) || DEFAULT_TTS_SPEED;

    // Clamp speed to safe range (0.25x to 2.0x)
    speed = Math.max(0.25, Math.min(2.0, speed));

    if (!text) return;

    // If this button is already playing or loading, stop it (toggle off)
    if (btn.classList.contains('voice-playing') || btn.classList.contains('voice-loading')) {
        if (ttsService && !ttsService.matches('idle')) {
            ttsService.send('CANCEL');
        }
        return;
    }

    // Stop any currently active TTS before starting a new one
    // Race condition fix: abort current session first, then start new
    if (ttsService && !ttsService.matches('idle')) {
        ttsService.send('CANCEL');
    }

    var voice = VOICES[language] || VOICES.es;
    ttsActiveBtn = btn;
    btn.classList.add('voice-loading');

    // Transition to loading state
    ttsService.send('PLAY');

    // Use WebSocket streaming TTS with AudioContext fallback check
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
        // Reuse shared TTS AudioContext (Safari limits to 4 instances per page)
        if (!sharedTtsCtx || sharedTtsCtx.state === 'closed') {
            sharedTtsCtx = new Ctx({ sampleRate: TTS_SAMPLE_RATE });
        }
        // ALWAYS call resume() in the click handler -- iOS Safari can report
        // state='running' but silently refuse to produce audio after the first
        // TTS session ends. resume() on an already-running context is a no-op
        // on desktop but re-activates the audio pipeline on iOS.
        var ctx = sharedTtsCtx;
        ctx.resume();
        streamTTS(btn, text, voice, speed, ctx, ttsAbort.signal);
    } else {
        restTTS(btn, text, voice, speed, ttsAbort.signal);
    }
}

/**
 * Stop all TTS playback. External stop (e.g. new message arriving).
 */
export function stopAllTTS() {
    if (!ttsService) return;
    // Also clean up any buttons that have stale classes
    var activeBtns = document.querySelectorAll('.voice-speak-btn.voice-playing, .voice-speak-btn.voice-loading');
    activeBtns.forEach(function(b) {
        b.classList.remove('voice-playing', 'voice-loading');
        b.innerHTML = SPEAKER_ICON;
    });

    if (!ttsService.matches('idle')) {
        ttsService.send('CANCEL');
    }
}

// ============================================
// Self-Initialization
// ============================================

var _beforeUnloadRegistered = false;

function init() {
    // Prevent double-init if script is re-executed (e.g. HTMX swap)
    if (window.voiceManager) return;

    initVoice();

    // Backward compatibility: expose public API on window
    window.voiceManager = {
        init: initVoice,
        destroy: destroyVoice,
        toggleRecording: toggleRecording,
        handleSpeakClick: handleSpeakClick,
        stopAllTTS: stopAllTTS,
    };

    // Register beforeunload handler exactly once
    if (!_beforeUnloadRegistered) {
        _beforeUnloadRegistered = true;
        window.addEventListener('beforeunload', function() {
            destroyVoice();
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
