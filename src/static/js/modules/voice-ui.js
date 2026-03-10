/**
 * Habla Hermano - Voice UI Helpers
 * Phase 21: Extracted from voice.js for modularity.
 *
 * All functions take DOM elements as parameters — no module-scoped state.
 */

import {
    SPINNER_HTML, CANCEL_X_ICON,
} from './voice-constants.js';

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
 * Create a floating stop bar above the input area. Returns the bar element.
 * @param {function(): void} onStop - callback when stop is clicked
 * @returns {HTMLElement}
 */
export function createStopBar(onStop) {
    var bar = document.createElement('div');
    bar.className = 'voice-stop-bar animate__animated animate__fadeInUp animate__faster';
    bar.innerHTML = '<button type="button" class="voice-stop-btn" aria-label="Stop audio playback">'
        + '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
        + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
        + '</svg>'
        + '<span>Stop</span>'
        + '</button>';

    bar.querySelector('.voice-stop-btn').addEventListener('click', onStop);

    var footer = document.querySelector('footer');
    if (footer && footer.parentNode) {
        footer.parentNode.insertBefore(bar, footer);
    } else {
        document.body.appendChild(bar);
    }
    return bar;
}

/**
 * Remove a stop bar from the DOM.
 * @param {HTMLElement | null} bar
 */
export function removeStopBar(bar) {
    if (!bar || !bar.parentNode) return;
    bar.classList.remove('animate__fadeInUp');
    bar.classList.add('animate__fadeOutDown');
    bar.addEventListener('animationend', function() {
        if (bar.parentNode) bar.parentNode.removeChild(bar);
    }, { once: true });
    // Fallback: remove after 600ms if animationend doesn't fire (jsdom)
    setTimeout(function() {
        if (bar.parentNode) bar.parentNode.removeChild(bar);
    }, 600);
}

/**
 * Create the inline recording bar that replaces the input area during recording.
 * @param {HTMLElement} inputContainer - The parent element holding textarea + buttons
 * @param {function(): void} onCancel - Callback when cancel button is clicked
 * @returns {{ element: HTMLElement, timerEl: HTMLElement, waveformEl: HTMLElement, cancel: function(): void }}
 */
export function createRecordingBar(inputContainer, onCancel) {
    if (!inputContainer) return null;

    // Hide all existing children
    var children = inputContainer.children;
    for (var i = 0; i < children.length; i++) {
        children[i].style.display = 'none';
        children[i].setAttribute('data-voice-hidden', '');
    }

    // Build the recording bar
    var bar = document.createElement('div');
    bar.className = 'voice-recording-bar animate__animated animate__fadeIn animate__faster';

    // Cancel button
    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'voice-cancel-btn';
    cancelBtn.setAttribute('aria-label', 'Cancel recording');
    cancelBtn.innerHTML = CANCEL_X_ICON;
    cancelBtn.addEventListener('click', function() {
        if (onCancel) onCancel();
    });
    bar.appendChild(cancelBtn);

    // Red dot
    var dot = document.createElement('span');
    dot.className = 'voice-rec-dot';
    dot.setAttribute('aria-hidden', 'true');
    bar.appendChild(dot);

    // Timer
    var timerEl = document.createElement('span');
    timerEl.className = 'voice-rec-timer';
    timerEl.textContent = '0:00';
    timerEl.setAttribute('aria-hidden', 'true');
    bar.appendChild(timerEl);

    // Waveform container with 30 bars
    var waveformEl = document.createElement('div');
    waveformEl.className = 'voice-rec-waveform';
    waveformEl.setAttribute('aria-hidden', 'true');
    for (var j = 0; j < 30; j++) {
        var b = document.createElement('span');
        b.className = 'voice-rec-bar';
        waveformEl.appendChild(b);
    }
    bar.appendChild(waveformEl);

    inputContainer.appendChild(bar);

    // Timer interval
    var startTime = Date.now();
    var interval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - startTime) / 1000);
        var min = Math.floor(elapsed / 60);
        var sec = elapsed % 60;
        timerEl.textContent = min + ':' + (sec < 10 ? '0' : '') + sec;
    }, 1000);

    return {
        element: bar,
        timerEl: timerEl,
        waveformEl: waveformEl,
        cancel: function() {
            clearInterval(interval);
        },
    };
}

/**
 * Remove the recording bar and restore hidden input children.
 * @param {{ element: HTMLElement, cancel: function(): void } | null} handle
 * @param {HTMLElement} inputContainer
 * @param {string} [animationOut] - Optional animate.css class (e.g. 'slideOutLeft', 'fadeOut')
 */
export function removeRecordingBar(handle, inputContainer, animationOut) {
    if (!handle) return;
    handle.cancel();

    function restoreAndRemove() {
        if (handle.element && handle.element.parentElement) {
            handle.element.remove();
        }
        // Restore hidden children
        if (inputContainer) {
            var hidden = inputContainer.querySelectorAll('[data-voice-hidden]');
            for (var i = 0; i < hidden.length; i++) {
                hidden[i].style.display = '';
                hidden[i].removeAttribute('data-voice-hidden');
            }
        }
    }

    if (animationOut && handle.element) {
        // Remove fadeIn classes, add the exit animation
        handle.element.classList.remove('animate__fadeIn', 'animate__faster');
        handle.element.classList.add('animate__' + animationOut);
        handle.element.addEventListener('animationend', restoreAndRemove, { once: true });
    } else {
        restoreAndRemove();
    }
}

/**
 * Animate the recording waveform bars from an AnalyserNode.
 * @param {AnalyserNode} analyser
 * @param {HTMLElement} waveformEl
 * @param {function(): boolean} isRecordingFn
 * @returns {{ stop: function(): void } | null}
 */
export function animateRecordingWaveform(analyser, waveformEl, isRecordingFn) {
    if (!analyser || !waveformEl) return null;
    var dataArray = new Uint8Array(analyser.frequencyBinCount);
    var bars = waveformEl.querySelectorAll('.voice-rec-bar');
    var barCount = bars.length;

    // Respect prefers-reduced-motion
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return null;
    }

    var animFrame = null;
    function animate() {
        if (!isRecordingFn()) return;
        analyser.getByteFrequencyData(dataArray);

        var binCount = analyser.frequencyBinCount;
        for (var i = 0; i < barCount; i++) {
            var binIndex = Math.floor((i / barCount) * binCount);
            var val = dataArray[binIndex] || 0;
            var height = Math.max(4, (val / 255) * 28);
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
