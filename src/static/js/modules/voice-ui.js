/**
 * Habla Hermano - Voice UI Helpers
 * Phase 21: Extracted from voice.js for modularity.
 *
 * All functions take DOM elements as parameters — no module-scoped state.
 */

import {
    MIC_ICON, LEVEL_BARS_HTML, SPINNER_HTML,
} from './voice-constants.js';

/**
 * Show mic button in recording state (level bars).
 */
export function showMicRecording(micButton) {
    if (!micButton) return;
    micButton.classList.add('voice-recording');
    micButton.setAttribute('aria-label', 'Stop recording');
    micButton.innerHTML = LEVEL_BARS_HTML;
}

/**
 * Restore mic button to default idle state.
 */
export function restoreMicIcon(micButton) {
    if (!micButton) return;
    micButton.classList.remove('voice-recording');
    micButton.setAttribute('aria-label', 'Record voice message');
    micButton.innerHTML = MIC_ICON;
}

/**
 * Enable or disable the send button and textarea.
 */
export function setSendEnabled(sendButton, chatInput, enabled) {
    if (sendButton) sendButton.disabled = !enabled;
    if (chatInput) chatInput.readOnly = !enabled;
}

/**
 * Show an error tooltip near any element.
 * @param {HTMLElement} anchor
 * @param {string} message
 * @param {Object<string, number>} errorTimeouts - mutable map of active timeout IDs
 */
export function showTooltipError(anchor, message, errorTimeouts) {
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

/**
 * Create and start a recording timer. Returns handle for stopTimer().
 * @param {HTMLElement} micWrapper
 * @returns {{ element: HTMLElement, interval: number } | null}
 */
export function startTimer(micWrapper) {
    if (!micWrapper) return null;
    var startTime = Date.now();

    var timer = document.createElement('div');
    timer.className = 'voice-timer';
    timer.textContent = '0:00';
    timer.setAttribute('aria-hidden', 'true');
    micWrapper.appendChild(timer);

    var interval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - startTime) / 1000);
        var min = Math.floor(elapsed / 60);
        var sec = elapsed % 60;
        timer.textContent = min + ':' + (sec < 10 ? '0' : '') + sec;
    }, 1000);

    return { element: timer, interval: interval };
}

/**
 * Stop and remove a recording timer.
 * @param {{ element: HTMLElement, interval: number } | null} handle
 */
export function stopTimer(handle) {
    if (!handle) return;
    if (handle.interval) clearInterval(handle.interval);
    if (handle.element && handle.element.parentElement) handle.element.remove();
}

/**
 * Start audio level bar animation. Returns handle with stop() method.
 * @param {AnalyserNode} analyser
 * @param {HTMLElement} micButton
 * @param {function(): boolean} isRecording - check if still recording
 * @returns {{ stop: function(): void } | null}
 */
export function startLevelAnimation(analyser, micButton, isRecording) {
    if (!analyser) return null;
    var dataArray = new Uint8Array(analyser.frequencyBinCount);

    // Respect prefers-reduced-motion: skip animation loop (CSS gives static height)
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return null;
    }

    var animFrame = null;
    function animate() {
        if (!isRecording()) return;
        analyser.getByteFrequencyData(dataArray);

        var bars = micButton ? micButton.querySelectorAll('.voice-bar') : [];
        var bins = [1, 3, 6, 10]; // Voice-frequency bins
        for (var i = 0; i < bars.length; i++) {
            var val = dataArray[bins[i]] || 0;
            var height = Math.max(3, (val / 255) * 18);
            bars[i].style.height = height + 'px';
        }
        animFrame = requestAnimationFrame(animate);
    }
    animFrame = requestAnimationFrame(animate);

    return {
        stop: function() {
            if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
        },
    };
}

/**
 * Show processing spinner and pill. Returns handle for hideProcessing().
 * @param {HTMLElement} micButton
 * @param {HTMLElement} micWrapper
 * @returns {{ indicator: HTMLElement | null } | null}
 */
export function showProcessing(micButton, micWrapper) {
    if (!micButton) return null;

    micButton.classList.remove('voice-recording');
    micButton.innerHTML = SPINNER_HTML;
    micButton.setAttribute('aria-label', 'Processing speech\u2026');

    var indicator = null;
    if (micWrapper) {
        indicator = document.createElement('div');
        indicator.className = 'voice-processing-indicator';
        indicator.textContent = 'Processing\u2026';
        micWrapper.appendChild(indicator);
    }

    return { indicator: indicator };
}

/**
 * Hide processing indicator.
 * @param {{ indicator: HTMLElement | null } | null} handle
 */
export function hideProcessing(handle) {
    if (!handle) return;
    if (handle.indicator && handle.indicator.parentElement) {
        handle.indicator.remove();
    }
}

/**
 * Set up mic/send button swap based on textarea content.
 * When the textarea is empty, show mic and hide send.
 * When the textarea has text, show send and hide mic.
 * @param {HTMLElement} micButton
 * @param {HTMLElement} sendButton
 * @param {HTMLTextAreaElement} chatInput
 * @returns {function(): void} update function (for testing)
 */
export function setupButtonSwap(micButton, sendButton, chatInput) {
    function update() {
        var hasText = chatInput.value.trim().length > 0;
        if (hasText) {
            micButton.classList.add('hidden');
            sendButton.classList.remove('hidden');
        } else {
            micButton.classList.remove('hidden');
            sendButton.classList.add('hidden');
        }
    }
    chatInput.addEventListener('input', update);
    update(); // initial state
    return update;
}
