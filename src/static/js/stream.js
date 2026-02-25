/**
 * Habla Hermano - SSE Streaming Client
 * Phase 15: Real-time token streaming for chat responses.
 *
 * Intercepts the chat form submit, sends via fetch() POST to /chat/stream,
 * and parses SSE events from the ReadableStream response.
 * Tokens are appended to a streaming bubble, feedback sections are injected
 * as server-rendered HTML after the response completes.
 */

(function() {
    'use strict';

    // ============================================
    // State
    // ============================================
    let isStreaming = false;
    let currentController = null;
    let bubbleCounter = 0;

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
     * Create an empty AI response bubble with a streaming cursor.
     * @returns {string} The bubble ID for later reference
     */
    function createStreamingBubble() {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return '';

        const id = 'stream-' + (++bubbleCounter);
        const bubbleHtml = `
            <div class="message-enter flex justify-start mb-6" id="${id}-wrapper">
                <div class="bg-ai rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] shadow-sm border border-border">
                    <div class="text-ai-text leading-relaxed" id="${id}-text"><span class="streaming-cursor" id="${id}-cursor"></span></div>
                </div>
            </div>
        `;
        chatMessages.insertAdjacentHTML('beforeend', bubbleHtml);
        window.scrollToBottom();
        return id;
    }

    /**
     * Append token text to the streaming bubble.
     * @param {string} bubbleId
     * @param {string} content - Token text to append
     */
    function appendToken(bubbleId, content) {
        const textEl = document.getElementById(bubbleId + '-text');
        if (!textEl) return;

        const cursor = document.getElementById(bubbleId + '-cursor');
        if (cursor) {
            // Insert text before cursor
            cursor.insertAdjacentText('beforebegin', content);
        } else {
            textEl.insertAdjacentText('beforeend', content);
        }
    }

    /**
     * Finalize the streaming bubble: remove cursor.
     * @param {string} bubbleId
     */
    function finalizeBubble(bubbleId) {
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

        // Get the current language from the hidden form inputs
        const languageInput = document.querySelector('input[name="language"]');
        const language = languageInput ? languageInput.value : 'es';

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'voice-speak-btn mt-2 p-1.5 text-text-subtle hover:text-accent transition-colors duration-150 rounded-lg hover:bg-surface-overlay';
        btn.setAttribute('data-text', text);
        btn.setAttribute('data-language', language);
        btn.setAttribute('aria-label', 'Listen to response');
        btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
            + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
            + '<path d="M15.54 8.46a5 5 0 0 1 0 7.07" />'
            + '<path d="M19.07 4.93a10 10 0 0 1 0 14.14" />'
            + '</svg>';

        bubble.appendChild(btn);
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

        window.scrollToBottom();
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
                // Throttled scroll — only scroll every few tokens
                if (Math.random() < 0.3) window.scrollToBottom();
                break;

            case 'response_complete': {
                finalizeBubble(bubbleId);
                // Prefer server-sent content; fall back to what was streamed into the bubble
                const ttsText = data.content || (function() {
                    const el = document.getElementById(bubbleId + '-text');
                    return el ? el.textContent.trim() : '';
                }());
                addSpeakerButton(bubbleId, ttsText);
                window.scrollToBottom();
                break;
            }

            case 'scaffolding':
            case 'grammar':
            case 'pronunciation':
                if (data.html) {
                    insertFeedback(bubbleId, data.html);
                }
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
            const response = await fetch('/chat/stream', {
                method: 'POST',
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
        window.focusInput();
        window.scrollToBottom();
    }

    /**
     * Show an error message in the chat.
     * @param {string} message
     */
    function showStreamError(message) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;

        const errorHtml = `
            <div class="message-enter flex justify-start mb-6">
                <div class="bg-red-900/50 border border-red-700 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%]">
                    <p class="text-red-200">${window.escapeHtml(message)}</p>
                </div>
            </div>
        `;
        chatMessages.insertAdjacentHTML('beforeend', errorHtml);
        window.scrollToBottom();
    }

    // ============================================
    // Form Intercept
    // ============================================

    function initStreamingForm() {
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
            window.addUserMessage(message);

            // Clear input
            window.clearInput();

            // Build FormData from form
            const formData = new FormData(form);
            // Ensure message is set (input was already cleared)
            formData.set('message', message);

            // Start streaming
            streamChat(formData);
        });
    }

    // ============================================
    // Initialization
    // ============================================

    function init() {
        initStreamingForm();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
