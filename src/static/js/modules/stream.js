/**
 * Habla Hermano - SSE Streaming Client (ES Module)
 * Phase 15: Real-time token streaming for chat responses.
 *
 * Intercepts the chat form submit, sends via fetch() POST to /chat/stream,
 * and parses SSE events from the ReadableStream response.
 * Tokens are appended to a streaming bubble, feedback sections are injected
 * as server-rendered HTML after the response completes.
 */

import { getChatMessages, scrollToBottom, focusInput, clearInput, addUserMessage, escapeHtml } from './dom.js';

// ============================================
// State
// ============================================
let isStreaming = false;
let currentController = null;
let bubbleCounter = 0;
let tokenCounter = 0;

// ============================================
// Lesson Mode Detection
// ============================================

/**
 * Detect if the page is in lesson mode.
 * @returns {boolean}
 */
function isLessonMode() {
    const chatRoot = document.querySelector('[data-lesson-mode]');
    return chatRoot !== null;
}

/**
 * Get the stream URL based on mode.
 * @returns {string}
 */
function getStreamUrl() {
    return isLessonMode() ? '/chat/lesson/stream' : '/chat/stream';
}

// ============================================
// SSE Event Parsing
// ============================================

/**
 * Parse a raw SSE event string into {event, data}.
 * Handles multi-line data fields per SSE spec.
 * @param {string} eventStr - Raw SSE text block (between double newlines)
 * @returns {{event: string, data: string}|null}
 */
function parseSSEEvent(eventStr) {
    let event = 'message';
    let dataLines = [];

    const lines = eventStr.split('\n');
    for (const line of lines) {
        if (line.startsWith('event:')) {
            event = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim());
        }
    }

    if (dataLines.length === 0) return null;

    return { event, data: dataLines.join('\n') };
}

// ============================================
// Streaming Bubble Management
// ============================================

/**
 * Create an empty AI response bubble with a "Thinking..." indicator.
 * The indicator is replaced by a streaming cursor once the first token arrives.
 * @returns {string} The bubble ID for later reference
 */
function createStreamingBubble() {
    const chatMessages = getChatMessages();
    if (!chatMessages) return '';

    const id = 'stream-' + (++bubbleCounter);
    const bubbleHtml = `
        <div class="message-enter flex justify-start mb-6" id="${id}-wrapper">
            <div class="bg-ai rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] shadow-sm border border-border">
                <div class="text-ai-text leading-relaxed" id="${id}-text"><span class="thinking-indicator" id="${id}-thinking">Thinking\u2026</span><span class="streaming-cursor hidden" id="${id}-cursor"></span></div>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', bubbleHtml);
    scrollToBottom();
    return id;
}

/**
 * Append token text to the streaming bubble.
 * On the first token, removes the "Thinking..." indicator and shows the cursor.
 * @param {string} bubbleId
 * @param {string} content - Token text to append
 */
function appendToken(bubbleId, content) {
    const textEl = document.getElementById(bubbleId + '-text');
    if (!textEl) return;

    // Remove thinking indicator on first token
    const thinking = document.getElementById(bubbleId + '-thinking');
    if (thinking) thinking.remove();

    const cursor = document.getElementById(bubbleId + '-cursor');
    if (cursor) {
        cursor.classList.remove('hidden');
        // Insert text before cursor
        cursor.insertAdjacentText('beforebegin', content);
    } else {
        textEl.insertAdjacentText('beforeend', content);
    }
}

/**
 * Finalize the streaming bubble: remove cursor and thinking indicator.
 * @param {string} bubbleId
 */
function finalizeBubble(bubbleId) {
    const thinking = document.getElementById(bubbleId + '-thinking');
    if (thinking) thinking.remove();
    const cursor = document.getElementById(bubbleId + '-cursor');
    if (cursor) cursor.remove();
}

/**
 * Add a TTS speaker button inside the streaming bubble (Phase 17).
 * Only adds the button if voice is enabled (mic-btn exists on page).
 * @param {string} bubbleId
 * @param {string} text - Full AI response text for TTS
 */
function addSpeakerButton(bubbleId, text) {
    // Only add if voice is enabled (mic button present)
    if (!document.getElementById('mic-btn')) return;
    if (!text) return;

    const wrapper = document.getElementById(bubbleId + '-wrapper');
    if (!wrapper) return;

    // Find the bubble's inner container (the bg-ai div)
    const bubble = wrapper.querySelector('.bg-ai');
    if (!bubble) return;

    // Get the current language from the hidden form input
    const languageInput = document.querySelector('input[name="language"]');
    const language = languageInput ? languageInput.value : 'es';

    const row = document.createElement('div');
    row.className = 'voice-tts-row mt-2';
    row.setAttribute('data-text', text);
    row.setAttribute('data-language', language);
    row.innerHTML = '<button type="button" class="voice-tts-play" aria-label="Play audio">'
        + '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>'
        + '</button>'
        + '<button type="button" class="voice-tts-speed" aria-label="Playback speed">1×</button>';

    bubble.appendChild(row);
}

/**
 * Insert feedback HTML after the bubble wrapper.
 * @param {string} bubbleId
 * @param {string} html - Server-rendered HTML to insert
 */
function insertFeedback(bubbleId, html) {
    const wrapper = document.getElementById(bubbleId + '-wrapper');
    if (!wrapper) return;

    // Find the last sibling that was inserted as feedback, or use wrapper itself
    let insertAfter = wrapper;
    let next = wrapper.nextElementSibling;
    while (next && next.hasAttribute('data-stream-feedback')) {
        insertAfter = next;
        next = next.nextElementSibling;
    }

    // Wrap in a container with marker attribute
    const container = document.createElement('div');
    container.setAttribute('data-stream-feedback', 'true');
    container.innerHTML = html;

    insertAfter.insertAdjacentElement('afterend', container);

    // Initialize Alpine.js directives in the new content
    if (window.Alpine && container.querySelectorAll('[x-data]').length > 0) {
        window.Alpine.initTree(container);
    }

    scrollToBottom();
}

// ============================================
// Stream Handler
// ============================================

/**
 * Handle a single SSE event.
 * @param {string} event - Event type
 * @param {string} dataStr - JSON data string
 * @param {string} bubbleId - Current streaming bubble ID
 */
function handleStreamEvent(event, dataStr, bubbleId) {
    let data;
    try {
        data = JSON.parse(dataStr);
    } catch {
        return;
    }

    switch (event) {
        case 'token':
            appendToken(bubbleId, data.content || '');
            // Throttled scroll — scroll every ~3 tokens to reduce layout thrash
            if (++tokenCounter % 3 === 0) scrollToBottom();
            break;

        case 'response_complete':
            finalizeBubble(bubbleId);
            // Replace plain-text streamed content with server-rendered markdown HTML
            if (data.rendered_html) {
                const textEl = document.getElementById(bubbleId + '-text');
                if (textEl) {
                    textEl.innerHTML = data.rendered_html;
                }
            }
            addSpeakerButton(bubbleId, data.content || '');
            scrollToBottom();
            break;

        case 'scaffolding':
        case 'grammar':
        case 'pronunciation':
            if (data.html) {
                insertFeedback(bubbleId, data.html);
            }
            break;

        case 'lesson_progress':
            updateLessonProgress(data);
            break;

        case 'exercise_result':
            showExerciseResult(data);
            break;

        case 'lesson_complete':
            showLessonComplete(data);
            break;

        case 'done':
            finishStreaming();
            break;

        case 'error':
            finalizeBubble(bubbleId);
            showStreamError(data.message || 'Something went wrong.');
            finishStreaming();
            break;
    }
}

// ============================================
// Core Streaming Function
// ============================================

/**
 * Send message via streaming fetch and process SSE response.
 * @param {FormData} formData
 */
async function streamChat(formData) {
    if (isStreaming) return;
    isStreaming = true;
    tokenCounter = 0;

    const sendBtn = document.querySelector('#chat-form button[type="submit"]');
    if (sendBtn) sendBtn.disabled = true;

    // Hide the loading indicator (we show cursor in bubble instead)
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) loadingIndicator.classList.add('hidden');

    // Create the streaming bubble
    const bubbleId = createStreamingBubble();

    // Set up abort controller with timeout
    currentController = new AbortController();
    const timeout = setTimeout(() => {
        if (currentController) currentController.abort();
    }, 60000);

    try {
        const response = await fetch(getStreamUrl(), {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData,
            signal: currentController.signal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Normalize \r\n to \n (servers may send either)
            buffer = buffer.replace(/\r\n/g, '\n');

            // Split on double newlines (SSE event boundary)
            const parts = buffer.split('\n\n');
            buffer = parts.pop(); // Keep incomplete event in buffer

            for (const part of parts) {
                const trimmed = part.trim();
                if (!trimmed) continue;

                const parsed = parseSSEEvent(trimmed);
                if (parsed) {
                    handleStreamEvent(parsed.event, parsed.data, bubbleId);
                }
            }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
            const parsed = parseSSEEvent(buffer.trim());
            if (parsed) {
                handleStreamEvent(parsed.event, parsed.data, bubbleId);
            }
        }

    } catch (err) {
        finalizeBubble(bubbleId);
        if (err.name === 'AbortError') {
            showStreamError('Response timed out. Please try again.');
        } else if (!navigator.onLine) {
            showStreamError('You appear to be offline. Check your connection.');
        } else {
            showStreamError('Connection lost. Please try again.');
        }
    } finally {
        clearTimeout(timeout);
        currentController = null;
        finishStreaming();
    }
}

/**
 * Re-enable input after streaming completes.
 */
function finishStreaming() {
    isStreaming = false;
    const sendBtn = document.querySelector('#chat-form button[type="submit"]');
    if (sendBtn) sendBtn.disabled = false;
    focusInput();
    scrollToBottom();
}

/**
 * Show an error message in the chat.
 * @param {string} message
 */
function showStreamError(message) {
    const chatMessages = getChatMessages();
    if (!chatMessages) return;

    const errorHtml = `
        <div class="message-enter flex justify-start mb-6">
            <div class="bg-red-900/50 border border-red-700 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%]">
                <p class="text-red-200">${escapeHtml(message)}</p>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', errorHtml);
    scrollToBottom();
}

// ============================================
// Lesson Mode Handlers
// ============================================

const PHASE_LABELS = {
    intro: 'Introduction',
    teaching: 'Teaching',
    exercise_ask: 'Exercise',
    exercise_eval: 'Checking...',
    complete: 'Complete!',
};

/**
 * Update lesson progress bar and phase badge.
 * @param {Object} data - lesson_progress SSE data
 */
function updateLessonProgress(data) {
    const progressBar = document.getElementById('lesson-progress-bar');
    const phaseBadge = document.getElementById('lesson-phase-badge');

    if (progressBar && data.progress !== undefined) {
        progressBar.style.width = data.progress + '%';
    }

    if (phaseBadge && data.phase) {
        phaseBadge.textContent = PHASE_LABELS[data.phase] || data.phase;
    }
}

/**
 * Show exercise result feedback inline.
 * @param {Object} data - exercise_result SSE data
 */
function showExerciseResult(data) {
    const chatMessages = getChatMessages();
    if (!chatMessages) return;

    const isCorrect = data.is_correct;
    const icon = isCorrect ? '✅' : '❌';
    const colorClass = isCorrect
        ? 'bg-success-muted border-success/30 text-success'
        : 'bg-red-900/20 border-red-700/30 text-red-300';

    const html = `
        <div class="message-enter flex justify-start mb-4" data-exercise-result="true">
            <div class="${colorClass} rounded-xl px-4 py-2 text-sm border font-medium">
                ${icon} ${isCorrect ? 'Correct!' : 'Not quite'}
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

/**
 * Show lesson completion banner.
 * @param {Object} data - lesson_complete SSE data
 */
function showLessonComplete(data) {
    const chatMessages = getChatMessages();
    if (!chatMessages) return;

    // Update progress bar to 100%
    const progressBar = document.getElementById('lesson-progress-bar');
    if (progressBar) progressBar.style.width = '100%';

    const phaseBadge = document.getElementById('lesson-phase-badge');
    if (phaseBadge) phaseBadge.textContent = 'Complete!';

    const score = data.score || 0;
    const vocabCount = data.vocab_count || 0;
    const lessonId = data.lesson_id || '';

    let statsHtml = `<span class="text-2xl font-bold text-accent">${score}%</span> score`;
    if (vocabCount > 0) {
        statsHtml += ` · <span class="font-semibold text-green-400">${vocabCount}</span> words`;
    }

    const html = `
        <div class="message-enter my-6 p-6 bg-surface-elevated rounded-2xl border border-accent/30 text-center" data-lesson-complete="true">
            <div class="text-4xl mb-3">🎉</div>
            <h3 class="text-lg font-bold text-text mb-2">Lesson Complete!</h3>
            <p class="text-text-muted mb-4">${statsHtml}</p>
            <div class="flex flex-col sm:flex-row gap-2 justify-center">
                <a href="/lessons/" class="px-4 py-2 border border-border text-text hover:bg-surface-overlay rounded-lg text-sm font-medium transition-colors">
                    More Lessons
                </a>
                <a href="/chat" class="px-4 py-2 bg-accent hover:bg-accent-hover text-accent-text rounded-lg text-sm font-medium transition-colors">
                    Free Chat
                </a>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

// ============================================
// Lesson Auto-Start
// ============================================

/**
 * In lesson mode, auto-send a "start" message to kick off the lesson.
 */
function autoStartLesson() {
    if (!isLessonMode()) return;

    const form = document.getElementById('chat-form');
    if (!form) return;

    // Build FormData with a start message
    const formData = new FormData(form);
    formData.set('message', 'Start the lesson');

    // Start streaming (no user bubble shown for auto-start)
    streamChat(formData);
}

// ============================================
// Form Intercept
// ============================================

export function initStreamingForm() {
    const form = document.getElementById('chat-form');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const messageInput = document.getElementById('message-input');
        if (!messageInput) return;

        const message = messageInput.value.trim();
        if (!message) return;
        if (isStreaming) return;

        // Show user message immediately (optimistic UI)
        addUserMessage(message);

        // Clear input
        clearInput();

        // Build FormData from form
        const formData = new FormData(form);
        // Ensure message is set (input was already cleared)
        formData.set('message', message);

        // Start streaming
        streamChat(formData);
    });

    // Auto-start lesson after a short delay to let the page render
    if (isLessonMode()) {
        setTimeout(autoStartLesson, 300);
    }
}
