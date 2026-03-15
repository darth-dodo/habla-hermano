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
    VOICES, DEFAULT_TTS_SPEED,
    WF_PLAY_ICON, WF_STOP_ICON, WF_SPEED_OPTIONS,
} from './voice-constants.js';
import {
    showMicRecording, restoreMicIcon, setSendEnabled,
    showTooltipError, startTimer, stopTimer,
    startLevelAnimation, showProcessing, hideProcessing,
    setupButtonSwap,
} from './voice-ui.js';
import {
    sttMachine, startRecordingSession,
    teardownSttAudio, closeSttWs,
    getAnalyser, resetTranscript, getStream,
} from './voice-stt.js';
import {
    ttsMachine, audioElementTTS, initTtsPlayer, cleanupTtsResources,
} from './voice-tts.js';


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

// TTS active button reference (the .voice-tts-row element)
var ttsActiveBtn = null;

// UI state handles (returned by voice-ui.js functions)
var timerHandle = null;
var levelHandle = null;
var processingHandle = null;
var processingTimeout = null;

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
        showMicRecording(micButton);
        timerHandle = startTimer(micWrapper);
        levelHandle = startLevelAnimation(
            getAnalyser(),
            micButton,
            function() { return sttService && sttService.matches('recording'); }
        );
    }

    // --- entering processing (from recording) ---
    if (state === 'processing' && prev === 'recording') {
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        doShowProcessing();
    }

    // --- entering idle (from connecting on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'connecting') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        restoreMicIcon(micButton);
        setSendEnabled(sendButton, chatInput, true);
    }

    // --- entering idle (from recording on ERROR/CANCEL) ---
    if (state === 'idle' && prev === 'recording') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        stopTimer(timerHandle); timerHandle = null;
        if (levelHandle) { levelHandle.stop(); levelHandle = null; }
        teardownSttAudio();
        closeSttWs();
        if (chatInput) chatInput.classList.remove('voice-interim');
        restoreMicIcon(micButton);
        setSendEnabled(sendButton, chatInput, true);
        // Trigger mic/send button swap (transcript was set programmatically)
        if (chatInput) chatInput.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // --- entering idle (from processing) ---
    if (state === 'idle' && prev === 'processing') {
        if (sttAbort) { sttAbort.abort(); sttAbort = null; }
        doHideProcessing();
        restoreMicIcon(micButton);
        setSendEnabled(sendButton, chatInput, true);
        // Trigger mic/send button swap (transcript was set programmatically)
        if (chatInput) chatInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
}

/**
 * Show processing UI (spinner + pill) with auto-dismiss timeout.
 */
function doShowProcessing() {
    stopTimer(timerHandle); timerHandle = null;
    if (levelHandle) { levelHandle.stop(); levelHandle = null; }
    processingHandle = showProcessing(micButton, micWrapper);
    processingTimeout = setTimeout(function() {
        sttService.send('PROCESSED');
    }, 2000);
}

/**
 * Hide processing UI and clear timeout.
 */
function doHideProcessing() {
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    hideProcessing(processingHandle);
    processingHandle = null;
    sttService.send('PROCESSED');
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
            var playEl = ttsActiveBtn.querySelector('.voice-tts-play');
            if (playEl) playEl.innerHTML = WF_STOP_ICON;
            var chip = ttsActiveBtn.querySelector('.voice-tts-speed');
            if (chip) chip.classList.add('voice-tts-speed-frozen');
        }
    }

    // --- entering idle (from loading or playing) ---
    if (state === 'idle' && (prev === 'loading' || prev === 'playing')) {
        cleanupTtsResources(ttsAbort);
        ttsAbort = null;
        if (ttsActiveBtn) {
            ttsActiveBtn.classList.remove('voice-loading', 'voice-playing');
            var playBtn = ttsActiveBtn.querySelector('.voice-tts-play');
            if (playBtn) playBtn.innerHTML = WF_PLAY_ICON;
            var speedChip = ttsActiveBtn.querySelector('.voice-tts-speed');
            if (speedChip) speedChip.classList.remove('voice-tts-speed-frozen');
        }
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

    // Initialize TTS hidden audio player (Deepgram pattern)
    initTtsPlayer();

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

    // Delegate TTS play/speed clicks
    document.addEventListener('click', function(e) {
        // Speed chip: cycle through speed options
        var speedChip = e.target.closest('.voice-tts-speed');
        if (speedChip) {
            // Speed is set server-side at stream start; block changes during playback
            if (speedChip.classList.contains('voice-tts-speed-frozen')) return;
            var cont = speedChip.closest('.voice-tts-row');
            if (cont) {
                var currentSpeed = parseFloat(cont.dataset.speed) || 1;
                var idx = WF_SPEED_OPTIONS.indexOf(currentSpeed);
                var nextIdx = (idx + 1) % WF_SPEED_OPTIONS.length;
                var newSpeed = WF_SPEED_OPTIONS[nextIdx];
                cont.dataset.speed = String(newSpeed);
                speedChip.textContent = newSpeed + '\u00d7';
            }
            return; // Don't trigger play
        }

        var playBtn = e.target.closest('.voice-tts-play');
        if (playBtn) {
            var row = playBtn.closest('.voice-tts-row');
            if (row) handleSpeakClick(row);
        }
    });

    // Handle page visibility changes — cancel active sessions when backgrounded.
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            if (ttsService && !ttsService.matches('idle')) {
                ttsService.send('CANCEL');
            }
            // iOS kills MediaStream tracks when backgrounded -- stop cleanly
            if (sttService && (sttService.matches('recording') || sttService.matches('connecting'))) {
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

    // 4. Defensive: stop mic stream tracks
    var stream = getStream();
    if (stream) {
        stream.getTracks().forEach(function(t) { t.stop(); });
    }

    // 5. Clear pending timeouts
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    Object.keys(errorTimeouts).forEach(function(key) {
        clearTimeout(errorTimeouts[key]);
    });
    errorTimeouts = {};

    // 6. Clean up STT UI handles
    stopTimer(timerHandle); timerHandle = null;
    if (levelHandle) { levelHandle.stop(); levelHandle = null; }
    hideProcessing(processingHandle); processingHandle = null;

    // 7. Null out DOM refs
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
        // Kill any active TTS before starting STT.
        // On iOS, getUserMedia() resumes a suspended AudioContext which would
        // replay any scheduled TTS BufferSource nodes ("zombie audio").
        if (ttsService && !ttsService.matches('idle')) {
            ttsService.send('CANCEL');
        }
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
    // Speed from button's data-speed attribute, or default
    var speed = parseFloat(btn.dataset.speed) || DEFAULT_TTS_SPEED;

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

    audioElementTTS(btn, text, voice, speed, ttsAbort.signal, ttsService, showError);
}

/**
 * Stop all TTS playback. External stop (e.g. new message arriving).
 */
export function stopAllTTS() {
    if (!ttsService) return;
    // Also clean up any rows that have stale classes
    var activeBtns = document.querySelectorAll('.voice-tts-row.voice-playing, .voice-tts-row.voice-loading');
    activeBtns.forEach(function(b) {
        b.classList.remove('voice-playing', 'voice-loading');
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
