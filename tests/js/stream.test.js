/**
 * Tests for stream.js — SSE Streaming Client
 *
 * The module exports only initStreamingForm(). Internal functions like
 * parseSSEEvent, createStreamingBubble, etc. are not exported, so we test
 * through the public API behavior.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Provide minimal DOM elements that dom.js accessors rely on.
function setupChatDOM({ includeForm = true, includeMessages = true, includeInput = true } = {}) {
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
    document.body.innerHTML = html;
}

describe('stream.js — initStreamingForm', () => {
    let initStreamingForm;

    beforeEach(async () => {
        document.body.innerHTML = '';
        vi.restoreAllMocks();
        // Dynamic import so each test gets a fresh module evaluation context
        // for the module-level state (isStreaming, bubbleCounter, etc.)
        const mod = await import('../../src/static/js/modules/stream.js');
        initStreamingForm = mod.initStreamingForm;
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('does nothing when #chat-form does not exist', () => {
        document.body.innerHTML = '<div>No form here</div>';
        // Should not throw
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

        // Mock fetch to return a readable stream that completes immediately
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

        // fetch is called asynchronously inside streamChat
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

        // Input is cleared synchronously in the submit handler
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

        // Create a reader that pauses so we can check mid-stream state
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

        // Wait for fetch to be called, which happens before read()
        await vi.waitFor(() => {
            expect(sendBtn.disabled).toBe(true);
        });

        // Complete the stream
        resolveRead({ done: true, value: undefined });
    });
});
