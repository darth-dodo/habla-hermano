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
 * Detect if the page is in lesson mode via URL params.
 * @returns {boolean}
 */
export function isLessonMode() {
    return new URLSearchParams(window.location.search).has('lesson');
}

/**
 * Get the stream URL. Always /chat/stream (lesson_id goes in form data).
 * @returns {string}
 */
export function getStreamUrl() {
    return '/chat/stream';
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

    // Remove lesson welcome card if present (lesson auto-start replaces it)
    const welcome = document.getElementById('lesson-welcome');
    if (welcome) welcome.remove();

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

    scrollToBottom(true, { force: false });
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

        case 'thread_title': {
            // Update the sidebar thread title if it exists (use data-thread-id, not href)
            const titleSpan = document.querySelector(`[data-thread-id="${data.thread_id}"] span.thread-title`);
            if (titleSpan) {
                titleSpan.textContent = data.title;
            }
            break;
        }

        case 'thread_created': {
            // Server auto-created a thread; update hidden input so subsequent
            // messages go to the same thread.
            if (data.thread_id) {
                let threadInput = document.querySelector('input[name="thread_id"]');
                if (threadInput) {
                    threadInput.value = data.thread_id;
                } else {
                    const form = document.getElementById('chat-form');
                    if (form) {
                        threadInput = document.createElement('input');
                        threadInput.type = 'hidden';
                        threadInput.name = 'thread_id';
                        threadInput.value = data.thread_id;
                        form.prepend(threadInput);
                    }
                }

                // Persist selection via cookie (keeps thread_id out of URL)
                fetch('/threads/select', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
                    body: 'thread_id=' + encodeURIComponent(data.thread_id),
                }).catch(() => {}); // fire-and-forget

                // Keep URL clean — no thread_id in query string
                window.history.replaceState({}, '', '/');

                // Add the new thread to the sidebar (matches thread_sidebar.html structure)
                const flagMap = { es: '\u{1F1EA}\u{1F1F8}', de: '\u{1F1E9}\u{1F1EA}', fr: '\u{1F1EB}\u{1F1F7}' };
                const flag = flagMap[data.language] || '\u{1F1EA}\u{1F1F8}';
                const threadList = document.querySelector('.overflow-y-auto.p-2.space-y-0\\.5');
                if (threadList) {
                    // Remove "No conversations yet" placeholder if present
                    const placeholder = threadList.querySelector('.text-center');
                    if (placeholder) placeholder.remove();

                    // Remove active styling from any previously active thread
                    threadList.querySelectorAll(':scope > div').forEach(div => {
                        div.classList.remove('bg-accent/10');
                        div.classList.add('hover:bg-surface-overlay');
                        const link = div.querySelector('a');
                        if (link) {
                            link.classList.remove('text-accent', 'font-medium');
                            link.classList.add('text-text');
                        }
                    });

                    // Insert new thread — href="/" so clicking re-selects via cookie
                    const wrapper = document.createElement('div');
                    wrapper.className = 'group relative flex items-center rounded-xl transition-all duration-200 bg-accent/10';
                    wrapper.innerHTML = `<a href="/" data-thread-id="${escapeHtml(data.thread_id)}" class="flex-1 flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm cursor-pointer min-w-0 text-accent font-medium"><span class="flex-shrink-0 text-base leading-none" aria-hidden="true">${flag}</span><span class="flex-1 truncate">New conversation</span></a>`;
                    threadList.prepend(wrapper);
                }
            }
            break;
        }

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

    // Include lesson_id from URL params as safety net
    if (isLessonMode()) {
        const lessonId = new URLSearchParams(window.location.search).get('lesson');
        if (lessonId) formData.append('lesson_id', lessonId);
    }

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
            <div class="rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%]" style="background: var(--error-muted); border: 1px solid var(--error); color: var(--text-primary)">
                <p>${escapeHtml(message)}</p>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', errorHtml);
    scrollToBottom();
}

// ============================================
// Lesson Mode Handlers
// ============================================

/**
 * Update lesson progress bar width.
 * @param {Object} data - lesson_progress SSE data
 */
function updateLessonProgress(data) {
    const progressBar = document.getElementById('lesson-progress-bar');
    if (!progressBar) return;

    // Phase-to-index mapping matching chat.html template segments
    const phaseIndex = { intro: 1, teaching: 2, exercise: 3, complete: 4 };
    const currentIndex = data.phase ? (phaseIndex[data.phase] || 1) : null;

    if (currentIndex !== null) {
        // Update each segment bar and label based on current phase
        const segments = progressBar.querySelectorAll(':scope > div');
        segments.forEach((segment, i) => {
            const idx = i + 1;
            const bar = segment.querySelector('div');
            const label = segment.querySelector('span');
            if (bar) {
                bar.classList.toggle('bg-accent', idx <= currentIndex);
                bar.classList.toggle('bg-border', idx > currentIndex);
            }
            if (label) {
                label.classList.toggle('text-accent', idx <= currentIndex);
                label.classList.toggle('text-text-subtle', idx > currentIndex);
            }
        });
    }

    // Update ARIA attributes for accessibility
    if (data.progress !== undefined) {
        progressBar.setAttribute('aria-valuenow', Math.round(data.progress / 25));
    } else if (currentIndex !== null) {
        progressBar.setAttribute('aria-valuenow', currentIndex);
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
 * Show compact lesson completion card.
 * @param {Object} data - lesson_complete SSE data
 */
function showLessonComplete(data) {
    // Update progress bar to complete (all segments filled)
    updateLessonProgress({ phase: 'complete' });

    const chatMessages = getChatMessages();
    if (!chatMessages) return;

    const vocabCount = data.vocab_count || 0;
    const correctCount = data.correct_count || 0;
    const totalExercises = data.total_exercises || 0;

    const card = document.createElement('div');
    card.className = 'mx-auto max-w-md my-4 p-4 bg-surface-elevated rounded-xl border border-border text-center';
    card.setAttribute('data-lesson-complete', 'true');
    card.innerHTML = `
        <p class="text-lg font-semibold text-text mb-2">${correctCount}/${totalExercises} correct · ${vocabCount} words learned</p>
        <div class="flex gap-3 justify-center mt-3">
            <a href="/lessons" class="px-4 py-2 text-sm border border-border rounded-lg hover:bg-surface-overlay transition-colors">More Lessons</a>
            <a href="/" class="px-4 py-2 text-sm bg-accent rounded-lg hover:bg-accent/80 transition-colors" style="color: var(--accent-text, white)">Free Chat</a>
        </div>
    `;
    chatMessages.appendChild(card);
    scrollToBottom();
}

// ============================================
// Lesson Auto-Start
// ============================================

/**
 * In lesson mode, auto-send a "start" message to kick off the lesson.
 * The auto-sent user bubble is hidden from the chat display.
 * Each page load uses a fresh lesson_session UUID, so lessons always
 * start from scratch with a clean checkpoint.
 */
function autoStartLesson() {
    if (!isLessonMode()) return;

    const form = document.getElementById('chat-form');
    if (!form) return;

    // Set flag so addUserMessage skips rendering for auto-start
    window.__lessonAutoStarting = true;

    // Build FormData with a start message
    const formData = new FormData(form);
    formData.set('message', 'Start the lesson');

    // Start streaming (no user bubble shown for auto-start)
    streamChat(formData);

    // Clear flag after stream is initiated
    window.__lessonAutoStarting = false;
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
