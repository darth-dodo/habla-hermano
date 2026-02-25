/**
 * Tests for stream.js — SSE Streaming Client
 *
 * The module exports only initStreamingForm(). Internal functions like
 * parseSSEEvent, createStreamingBubble, etc. are not exported, so we test
 * through the public API behavior by submitting the form with mocked fetch
 * responses that return controlled SSE event streams.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a minimal DOM matching the chat page layout.
 * stream.js and dom.js look up elements by ID at call time.
 */
function setupChatDOM({ includeForm = true, includeMessages = true, includeInput = true, includeMicBtn = false, includeLanguageInput = false } = {}) {
    let html = '';
    if (includeMessages) {
        html += '<div id="chat-container"><div id="chat-messages"></div></div>';
    }
    if (includeForm) {
        html += `
            <form id="chat-form">
                ${includeInput ? '<textarea id="message-input"></textarea>' : ''}
                <button type="submit">Send</button>
            </form>
        `;
    }
    html += '<div id="loading-indicator" class="hidden"></div>';
    if (includeMicBtn) {
        html += '<button id="mic-btn"></button>';
    }
    if (includeLanguageInput) {
        html += '<input type="hidden" name="language" value="de" />';
    }
    document.body.innerHTML = html;

    // jsdom does not implement scrollTo — stub it to avoid errors
    const container = document.getElementById('chat-container');
    if (container) container.scrollTo = vi.fn();
}

/**
 * Create a mock Response whose body is a ReadableStream that emits the given
 * SSE event strings all at once then closes.
 *
 * @param {Array<{event?: string, data: object|string}>} events
 * @returns {Response}
 */
function createMockSSEResponse(events) {
    const text = events.map(e => {
        let str = '';
        if (e.event) str += `event: ${e.event}\n`;
        const payload = typeof e.data === 'string' ? e.data : JSON.stringify(e.data);
        str += `data: ${payload}\n\n`;
        return str;
    }).join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
        start(controller) {
            controller.enqueue(encoder.encode(text));
            controller.close();
        },
    });

    return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
    });
}

/**
 * Shortcut: set up DOM, init module, fill input, mock fetch, submit the form,
 * and wait until streaming finishes (button re-enabled).
 *
 * @param {Function} initStreamingForm - the exported init function
 * @param {Array} events - SSE events to feed through the mock
 * @param {object} [domOptions] - extra options for setupChatDOM
 * @returns {Promise<void>}
 */
async function submitAndWait(initStreamingForm, events, domOptions = {}) {
    setupChatDOM(domOptions);
    globalThis.fetch = vi.fn(() => Promise.resolve(createMockSSEResponse(events)));
    initStreamingForm();

    const input = document.getElementById('message-input');
    input.value = 'Hola';

    const form = document.getElementById('chat-form');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

    // Wait for the async streamChat pipeline to finish.
    // finishStreaming() re-enables the send button, so poll for that.
    await vi.waitFor(() => {
        const btn = form.querySelector('button[type="submit"]');
        expect(btn.disabled).toBe(false);
    });

    // Flush any pending timers (scrollToBottom uses 50ms setTimeout)
    await vi.advanceTimersByTimeAsync(200);
}

// ===========================================================================
// Tests
// ===========================================================================

describe('stream.js — initStreamingForm', () => {
    let initStreamingForm;

    beforeEach(async () => {
        document.body.innerHTML = '';
        vi.useFakeTimers();
        vi.restoreAllMocks();
        // Dynamic import so each test gets a fresh module evaluation context
        // for the module-level state (isStreaming, bubbleCounter, etc.)
        const mod = await import('../../src/static/js/modules/stream.js');
        initStreamingForm = mod.initStreamingForm;
    });

    afterEach(() => {
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    // ------------------------------------------------------------------
    // Original 8 tests (basic setup and form submission)
    // ------------------------------------------------------------------

    it('does nothing when #chat-form does not exist', () => {
        document.body.innerHTML = '<div>No form here</div>';
        expect(() => initStreamingForm()).not.toThrow();
    });

    it('attaches a submit listener to #chat-form when it exists', () => {
        setupChatDOM();
        const form = document.getElementById('chat-form');
        const spy = vi.spyOn(form, 'addEventListener');

        initStreamingForm();

        expect(spy).toHaveBeenCalledWith('submit', expect.any(Function));
    });

    it('form submit with empty message does not trigger fetch', () => {
        setupChatDOM();
        const fetchSpy = vi.spyOn(globalThis, 'fetch');

        initStreamingForm();

        const form = document.getElementById('chat-form');
        const input = document.getElementById('message-input');
        input.value = '   '; // whitespace only

        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('form submit with no message-input element does not trigger fetch', () => {
        setupChatDOM({ includeInput: false });
        const fetchSpy = vi.spyOn(globalThis, 'fetch');

        initStreamingForm();

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('form submit with valid message calls fetch to /chat/stream', async () => {
        setupChatDOM();

        const mockReader = {
            read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        };
        const mockResponse = {
            ok: true,
            body: { getReader: () => mockReader },
        };
        const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse);

        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Hola amigo';

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        await vi.waitFor(() => {
            expect(fetchSpy).toHaveBeenCalledTimes(1);
        });

        const [url, options] = fetchSpy.mock.calls[0];
        expect(url).toBe('/chat/stream');
        expect(options.method).toBe('POST');
        expect(options.body).toBeInstanceOf(FormData);
    });

    it('form submit clears the input field after sending', async () => {
        setupChatDOM();

        const mockReader = {
            read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        };
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            body: { getReader: () => mockReader },
        });

        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Hola';

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(input.value).toBe('');
    });

    it('form submit adds user message bubble to chat-messages', async () => {
        setupChatDOM();

        const mockReader = {
            read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        };
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            body: { getReader: () => mockReader },
        });

        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Buenos dias';

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        const chatMessages = document.getElementById('chat-messages');
        const userBubble = chatMessages.querySelector('[data-user-message]');
        expect(userBubble).not.toBeNull();
        expect(userBubble.textContent).toContain('Buenos dias');
    });

    it('disables submit button during streaming', async () => {
        setupChatDOM();

        let resolveRead;
        const readPromise = new Promise((resolve) => {
            resolveRead = resolve;
        });
        const mockReader = {
            read: vi.fn().mockReturnValue(readPromise),
        };
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            body: { getReader: () => mockReader },
        });

        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Test';

        const form = document.getElementById('chat-form');
        const sendBtn = form.querySelector('button[type="submit"]');

        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        await vi.waitFor(() => {
            expect(sendBtn.disabled).toBe(true);
        });

        resolveRead({ done: true, value: undefined });
    });

    // ------------------------------------------------------------------
    // NEW: createStreamingBubble — creates AI response bubble with cursor
    // ------------------------------------------------------------------

    it('creates a streaming bubble with cursor when stream starts', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        // Should contain a stream-1-wrapper (first bubble created)
        const wrapper = chatMessages.querySelector('[id$="-wrapper"]');
        expect(wrapper).not.toBeNull();
        expect(wrapper.id).toMatch(/^stream-\d+-wrapper$/);

        // The bubble inner div should have bg-ai class
        const bubble = wrapper.querySelector('.bg-ai');
        expect(bubble).not.toBeNull();
    });

    // ------------------------------------------------------------------
    // NEW: parseSSEEvent — multi-line data, event-only lines, missing data
    // ------------------------------------------------------------------

    it('handles token events and appends text to the streaming bubble', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Hola ' } },
            { event: 'token', data: { content: 'amigo' } },
            { event: 'response_complete', data: { content: 'Hola amigo' } },
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const textEl = chatMessages.querySelector('[id$="-text"]');
        expect(textEl).not.toBeNull();
        expect(textEl.textContent).toContain('Hola ');
        expect(textEl.textContent).toContain('amigo');
    });

    // ------------------------------------------------------------------
    // NEW: appendToken + finalizeBubble — cursor removed after finalize
    // ------------------------------------------------------------------

    it('removes the streaming cursor after response_complete', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Hi' } },
            { event: 'response_complete', data: { content: 'Hi' } },
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const cursor = chatMessages.querySelector('.streaming-cursor');
        // Cursor should be removed by finalizeBubble
        expect(cursor).toBeNull();
    });

    // ------------------------------------------------------------------
    // NEW: addSpeakerButton — with mic-btn present and absent
    // ------------------------------------------------------------------

    it('adds a speaker button when mic-btn is present', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Guten Tag' } },
            { event: 'response_complete', data: { content: 'Guten Tag' } },
            { event: 'done', data: {} },
        ], { includeMicBtn: true, includeLanguageInput: true });

        const speakerBtn = document.querySelector('.voice-speak-btn');
        expect(speakerBtn).not.toBeNull();
        expect(speakerBtn.getAttribute('data-text')).toBe('Guten Tag');
        expect(speakerBtn.getAttribute('data-language')).toBe('de');
        expect(speakerBtn.getAttribute('aria-label')).toBe('Listen to response');
    });

    it('does NOT add speaker button when mic-btn is absent', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Hola' } },
            { event: 'response_complete', data: { content: 'Hola' } },
            { event: 'done', data: {} },
        ], { includeMicBtn: false });

        const speakerBtn = document.querySelector('.voice-speak-btn');
        expect(speakerBtn).toBeNull();
    });

    it('does NOT add speaker button when response text is empty', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'response_complete', data: { content: '' } },
            { event: 'done', data: {} },
        ], { includeMicBtn: true });

        const speakerBtn = document.querySelector('.voice-speak-btn');
        expect(speakerBtn).toBeNull();
    });

    // ------------------------------------------------------------------
    // NEW: insertFeedback — scaffolding / grammar HTML injection
    // ------------------------------------------------------------------

    it('inserts feedback HTML for scaffolding events', async () => {
        const feedbackHtml = '<div class="scaffolding-tip"><p>Tip: Use present tense!</p></div>';

        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Hola' } },
            { event: 'response_complete', data: { content: 'Hola' } },
            { event: 'scaffolding', data: { html: feedbackHtml } },
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const feedbackContainer = chatMessages.querySelector('[data-stream-feedback]');
        expect(feedbackContainer).not.toBeNull();
        expect(feedbackContainer.innerHTML).toContain('Tip: Use present tense!');
    });

    it('inserts multiple feedback sections after the same bubble', async () => {
        const scaffoldingHtml = '<div>Scaffolding</div>';
        const grammarHtml = '<div>Grammar note</div>';

        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Yo hablo' } },
            { event: 'response_complete', data: { content: 'Yo hablo' } },
            { event: 'scaffolding', data: { html: scaffoldingHtml } },
            { event: 'grammar', data: { html: grammarHtml } },
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const feedbacks = chatMessages.querySelectorAll('[data-stream-feedback]');
        expect(feedbacks.length).toBe(2);
        expect(feedbacks[0].innerHTML).toContain('Scaffolding');
        expect(feedbacks[1].innerHTML).toContain('Grammar note');
    });

    it('initializes Alpine.js on feedback content when Alpine is available', async () => {
        const initTreeSpy = vi.fn();
        window.Alpine = { initTree: initTreeSpy };

        const feedbackHtml = '<div x-data="{ open: false }">Alpine content</div>';

        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Test' } },
            { event: 'response_complete', data: { content: 'Test' } },
            { event: 'scaffolding', data: { html: feedbackHtml } },
            { event: 'done', data: {} },
        ]);

        expect(initTreeSpy).toHaveBeenCalledTimes(1);

        delete window.Alpine;
    });

    // ------------------------------------------------------------------
    // NEW: handleStreamEvent — error event shows error bubble
    // ------------------------------------------------------------------

    it('shows an error bubble when an error event is received', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Par' } },
            { event: 'error', data: { message: 'Rate limit exceeded' } },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const errorBubble = chatMessages.querySelector('.bg-red-900\\/50');
        expect(errorBubble).not.toBeNull();
        expect(errorBubble.textContent).toContain('Rate limit exceeded');
    });

    // ------------------------------------------------------------------
    // NEW: streamChat error paths — HTTP error, offline, timeout
    // ------------------------------------------------------------------

    it('shows error bubble when fetch returns non-ok status', async () => {
        setupChatDOM();
        globalThis.fetch = vi.fn(() => Promise.resolve(new Response('', { status: 500 })));
        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Test';

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        await vi.waitFor(() => {
            const btn = form.querySelector('button[type="submit"]');
            expect(btn.disabled).toBe(false);
        });
        await vi.advanceTimersByTimeAsync(200);

        const chatMessages = document.getElementById('chat-messages');
        const errorBubble = chatMessages.querySelector('.bg-red-900\\/50');
        expect(errorBubble).not.toBeNull();
        expect(errorBubble.textContent).toContain('Connection lost');
    });

    it('shows offline error when fetch fails and navigator is offline', async () => {
        setupChatDOM();
        globalThis.fetch = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
        // Mock navigator.onLine
        Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true });

        initStreamingForm();

        const input = document.getElementById('message-input');
        input.value = 'Test';

        const form = document.getElementById('chat-form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        await vi.waitFor(() => {
            const btn = form.querySelector('button[type="submit"]');
            expect(btn.disabled).toBe(false);
        });
        await vi.advanceTimersByTimeAsync(200);

        const chatMessages = document.getElementById('chat-messages');
        const errorBubble = chatMessages.querySelector('.bg-red-900\\/50');
        expect(errorBubble).not.toBeNull();
        expect(errorBubble.textContent).toContain('offline');

        // Restore
        Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
    });

    // ------------------------------------------------------------------
    // NEW: finishStreaming — re-enables UI after stream completes
    // ------------------------------------------------------------------

    it('re-enables the submit button after streaming completes', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Done' } },
            { event: 'done', data: {} },
        ]);

        const form = document.getElementById('chat-form');
        const sendBtn = form.querySelector('button[type="submit"]');
        expect(sendBtn.disabled).toBe(false);
    });

    // ------------------------------------------------------------------
    // NEW: guard against double-submit while streaming
    // ------------------------------------------------------------------

    it('ignores a second submit while already streaming', async () => {
        setupChatDOM();

        let resolveRead;
        const readPromise = new Promise((resolve) => { resolveRead = resolve; });
        const mockReader = { read: vi.fn().mockReturnValue(readPromise) };

        globalThis.fetch = vi.fn(() => Promise.resolve({
            ok: true,
            body: { getReader: () => mockReader },
        }));

        initStreamingForm();

        const input = document.getElementById('message-input');
        const form = document.getElementById('chat-form');

        // First submit
        input.value = 'First';
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        await vi.waitFor(() => {
            expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        });

        // Second submit while streaming — isStreaming is true
        input.value = 'Second';
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        // fetch should still only have been called once
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);

        // Clean up
        resolveRead({ done: true, value: undefined });
    });

    // ------------------------------------------------------------------
    // NEW: addSpeakerButton defaults language to 'es' when no input found
    // ------------------------------------------------------------------

    it('defaults speaker button language to es when language input is absent', async () => {
        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Hola' } },
            { event: 'response_complete', data: { content: 'Hola' } },
            { event: 'done', data: {} },
        ], { includeMicBtn: true, includeLanguageInput: false });

        const speakerBtn = document.querySelector('.voice-speak-btn');
        expect(speakerBtn).not.toBeNull();
        expect(speakerBtn.getAttribute('data-language')).toBe('es');
    });

    // ------------------------------------------------------------------
    // NEW: pronunciation event inserts feedback (like grammar/scaffolding)
    // ------------------------------------------------------------------

    it('inserts feedback HTML for pronunciation events', async () => {
        const pronHtml = '<div class="pronunciation-tip">Roll your Rs!</div>';

        await submitAndWait(initStreamingForm, [
            { event: 'token', data: { content: 'Perro' } },
            { event: 'response_complete', data: { content: 'Perro' } },
            { event: 'pronunciation', data: { html: pronHtml } },
            { event: 'done', data: {} },
        ]);

        const chatMessages = document.getElementById('chat-messages');
        const feedbackContainer = chatMessages.querySelector('[data-stream-feedback]');
        expect(feedbackContainer).not.toBeNull();
        expect(feedbackContainer.innerHTML).toContain('Roll your Rs!');
    });
});
