/**
 * Habla Hermano - Voice Module (Orchestrator)
 * Phase 21: FSM + AbortController refactor.
 *
 * This file wires together the sub-modules:
 *   voice-constants.js — constants and audio utilities
 *   voice-ui.js        — DOM manipulation helpers
 *   voice-stt.js       — STT state machine and recording session
 *   voice-tts.js       — TTS state machine and playback
 *
 * All mutable state lives here. Sub-modules are stateless or own
 * only their internal resources (WebSocket, AudioContext, etc.).
 */

import { interpret } from './fsm.js';
import {
    VOICES, DEFAULT_TTS_SPEED, TTS_SAMPLE_RATE,
    SPEAKER_ICON,
    MIC_ICON, STOP_SQUARE_ICON, SPINNER_HTML,
} from './voice-constants.js';
import {
    showMicRecording, restoreMicIcon, setSendEnabled,
    showTooltipError, startTimer, stopTimer,
    startLevelAnimation, showProcessing, hideProcessing,
    createStopBar, removeStopBar, setupButtonSwap,
    createRecordingBar, removeRecordingBar, animateRecordingWaveform,
} from './voice-ui.js';
import {
    sttMachine, startRecordingSession,
    teardownSttAudio, closeSttWs,
    getAnalyser, resetTranscript, getStream,
} from './voice-stt.js';
import {
    ttsMachine, streamTTS, restTTS, cleanupTtsResources,
} from './voice-tts.js';
import {
    createWaveformPlayer, destroyWaveformPlayer,
} from './voice-waveform.js';

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

// TTS active button reference (now the .voice-waveform-container element)
var ttsActiveBtn = null;

// Active waveform player handle (from voice-waveform.js)
var activeWfPlayer = null;

// UI state handles (returned by voice-ui.js functions)
var timerHandle = null;
var levelHandle = null;
var processingHandle = null;
var processingTimeout = null;
var stopBar = null;

// Recording bar handles (Task 3)
var recordingBarHandle = null;
var waveformAnimHandle = null;

// Error tooltip timeouts (shared mutable map)
var errorTimeouts = {};

// ============================================
// STT State Change Handler
// ============================================

/**
 * STT state change handler. All side effects for STT transitions live here.
 */
function onSttChange(state, prev) {
    // --- entering connecting ---
    if (state === 'connecting' && prev === 'idle') {
        sttAbort = new AbortController();
        resetTranscript();
        startRecordingSession(
            sttAbort.signal,
            sttService,
            chatInput,
            function showError(msg) {
                showTooltipError(micWrapper || micButton, msg, errorTimeouts);
            },
            function onFinalTranscript() {
                // Dismiss processing state early on final transcript
                if (processingTimeout) doHideProcessing();
            }
        );
    }

    // --- entering recording (from connecting) ---
    if (state === 'recording' && prev === 'connecting') {
        setSendEnabled(sendButton, chatInput, false);

        // Create recording bar inside the form / input container
        var inputContainer = chatInput ? chatInput.closest('form') || chatInput.parentElement.parentElement : null;
        recordingBarHandle = createRecordingBar(inputContainer, function() {
            sttService.send('CANCEL');
        });

        // Morph mic button to stop square
        if (micButton) {
            micButton.classList.add('voice-stop-square');
            micButton.innerHTML = STOP_SQUARE_ICON;
            micButton.setAttribute('aria-label', 'Stop recording');
        }

        // Start waveform animation
        waveformAnimHandle = animateRecordingWaveform(
            getAnalyser(),
            recordingBarHandle ? recordingBarHandle.waveformEl : null,
            function() { return sttService && sttService.matches('recording'); }
        );
    }

    // --- entering processing (from recording) ---
    if (state === 'processing' && prev === 'recording') {
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');

        // Stop waveform animation
        if (waveformAnimHandle) { waveformAnimHandle.stop(); waveformAnimHandle = null; }

        // Show spinner inside the recording bar (replace waveform)
        if (recordingBarHandle && recordingBarHandle.waveformEl) {
            recordingBarHandle.waveformEl.innerHTML = SPINNER_HTML;
        }

        // Auto-dismiss after 2 seconds
        processingTimeout = setTimeout(function() {
            sttService.send('PROCESSED');
        }, 2000);
    }

    // --- entering idle (from connecting on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'connecting') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');

        // Remove recording bar if it exists (edge case: rapid cancel)
        if (recordingBarHandle) {
            var container = chatInput ? chatInput.closest('form') || chatInput.parentElement.parentElement : null;
            removeRecordingBar(recordingBarHandle, container);
            recordingBarHandle = null;
        }

        doRestoreMicButton();
        setSendEnabled(sendButton, chatInput, true);
    }

    // --- entering idle (from recording on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'recording') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        if (waveformAnimHandle) { waveformAnimHandle.stop(); waveformAnimHandle = null; }
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');

        // Remove recording bar with slideOutLeft animation
        var containerRec = chatInput ? chatInput.closest('form') || chatInput.parentElement.parentElement : null;
        removeRecordingBar(recordingBarHandle, containerRec, 'slideOutLeft');
        recordingBarHandle = null;

        doRestoreMicButton();
        setSendEnabled(sendButton, chatInput, true);
    }

    // --- entering idle (from processing) ---
    if (state === 'idle' && prev === 'processing') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }

        if (processingTimeout) {
            clearTimeout(processingTimeout);
            processingTimeout = null;
        }

        // Remove recording bar with fadeOut animation
        var containerProc = chatInput ? chatInput.closest('form') || chatInput.parentElement.parentElement : null;
        removeRecordingBar(recordingBarHandle, containerProc, 'fadeOut');
        recordingBarHandle = null;

        doRestoreMicButton();
        setSendEnabled(sendButton, chatInput, true);
    }
}

/**
 * Restore the mic button to its default idle icon and classes.
 */
function doRestoreMicButton() {
    if (!micButton) return;
    micButton.classList.remove('voice-stop-square');
    micButton.innerHTML = MIC_ICON;
    micButton.setAttribute('aria-label', 'Record voice message');
}

/**
 * Show the processing state with auto-dismiss timeout.
 */
function doShowProcessing() {
    processingHandle = showProcessing(micButton, micWrapper);

    // Auto-dismiss after 2 seconds
    processingTimeout = setTimeout(function() {
        sttService.send('PROCESSED');
    }, 2000);
}

/**
 * Hide processing state and restore mic button.
 */
function doHideProcessing() {
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    hideProcessing(processingHandle);
    processingHandle = null;

    // Safety: ensure timer is fully stopped
    stopTimer(timerHandle); timerHandle = null;

    restoreMicIcon(micButton);
    setSendEnabled(sendButton, chatInput, true);
}

// ============================================
// TTS State Change Handler
// ============================================

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
        }
        stopBar = createStopBar(function() { stopAllTTS(); });
    }

    // --- entering idle (from loading on ERROR/CANCEL/ALL_ENDED) ---
    if (state === 'idle' && prev === 'loading') {
        cleanupTtsResources(ttsAbort);
        ttsAbort = null;
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading', 'voice-playing');
        }
        removeStopBar(stopBar); stopBar = null;
        activeWfPlayer = null;
        ttsActiveBtn = null;
    }

    // --- entering idle (from playing on ALL_ENDED/ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'playing') {
        cleanupTtsResources(ttsAbort);
        ttsAbort = null;
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading', 'voice-playing');
        }
        removeStopBar(stopBar); stopBar = null;
        activeWfPlayer = null;
        ttsActiveBtn = null;
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

    // Use mic button's parent as wrapper for floating indicators (timer, processing pill).
    // The template already provides a positioned container around mic + send.
    micWrapper = micButton.parentNode;

    // Mic/send button swap: show mic when input is empty, send when has text
    if (sendButton && chatInput) {
        setupButtonSwap(micButton, sendButton, chatInput);
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
    // 0. Capture recording bar element before CANCEL nullifies the handle
    //    (CANCEL triggers onSttChange which calls removeRecordingBar with animation,
    //     but jsdom/real browsers may not fire animationend synchronously)
    var pendingBarEl = recordingBarHandle ? recordingBarHandle.element : null;

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
    var stream = getStream();
    if (stream) {
        stream.getTracks().forEach(function(t) { t.stop(); });
    }

    // 6. Clear pending timeouts
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    Object.keys(errorTimeouts).forEach(function(key) {
        clearTimeout(errorTimeouts[key]);
    });
    errorTimeouts = {};

    // 7. Stop timer and level animation
    stopTimer(timerHandle); timerHandle = null;
    if (levelHandle) { levelHandle.stop(); levelHandle = null; }

    // 8. Hide stop bar and processing indicator
    removeStopBar(stopBar); stopBar = null;
    hideProcessing(processingHandle); processingHandle = null;

    // 9. Clean up recording bar
    if (waveformAnimHandle) { waveformAnimHandle.stop(); waveformAnimHandle = null; }
    if (recordingBarHandle) {
        recordingBarHandle.cancel();
        if (recordingBarHandle.element && recordingBarHandle.element.parentElement) {
            recordingBarHandle.element.remove();
        }
        recordingBarHandle = null;
    }
    // Force-remove bar element if CANCEL left it in the DOM (animation pending)
    if (pendingBarEl && pendingBarEl.parentElement) {
        var parentContainer = pendingBarEl.parentElement;
        pendingBarEl.remove();
        // Restore any children hidden by the recording bar
        var hidden = parentContainer.querySelectorAll('[data-voice-hidden]');
        for (var i = 0; i < hidden.length; i++) {
            hidden[i].style.display = '';
            hidden[i].removeAttribute('data-voice-hidden');
        }
    }

    // 10. Null out DOM refs
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

    // Error display helper bound to this button
    function showError(anchor, msg) {
        showTooltipError(anchor, msg, errorTimeouts);
    }

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
        streamTTS(btn, text, voice, speed, ctx, ttsAbort.signal, ttsService, showError);
    } else {
        restTTS(btn, text, voice, speed, ttsAbort.signal, ttsService, showError);
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
