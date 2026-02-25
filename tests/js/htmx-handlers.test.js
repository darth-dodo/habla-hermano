/**
 * Tests for src/static/js/modules/htmx-handlers.js
 *
 * @environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { initHTMXHandlers } from '../../src/static/js/modules/htmx-handlers.js';

// ---------------------------------------------------------------------------
// Shared DOM scaffold
// ---------------------------------------------------------------------------

function setupDOM() {
    document.body.innerHTML = `
        <div id="chat-container">
            <div id="chat-messages">
                <div class="message-enter" data-user-message>Welcome message</div>
            </div>
        </div>
        <textarea id="message-input"></textarea>
        <div id="loading-indicator" class="hidden"></div>
    `;
    // jsdom does not implement scrollTo, so we mock it
    const container = document.getElementById('chat-container');
    container.scrollTo = vi.fn();
}

// ---------------------------------------------------------------------------
// Helper: dispatch a custom HTMX-style event on document.body
// ---------------------------------------------------------------------------

function dispatchHTMXEvent(eventName, detail = {}) {
    const event = new CustomEvent(eventName, {
        bubbles: true,
        detail,
    });
    document.body.dispatchEvent(event);
}

// ---------------------------------------------------------------------------
// initHTMXHandlers
// ---------------------------------------------------------------------------

describe('initHTMXHandlers', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('registers event listeners on document.body', () => {
        const spy = vi.spyOn(document.body, 'addEventListener');
        initHTMXHandlers();

        const registeredEvents = spy.mock.calls.map(call => call[0]);
        expect(registeredEvents).toContain('htmx:afterSwap');
        expect(registeredEvents).toContain('htmx:responseError');
        expect(registeredEvents).toContain('htmx:beforeRequest');

        spy.mockRestore();
    });
});

// ---------------------------------------------------------------------------
// htmx:afterSwap
// ---------------------------------------------------------------------------

describe('htmx:afterSwap handler', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        initHTMXHandlers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('scrolls to bottom and adds animated class to new messages', () => {
        const chatMessages = document.getElementById('chat-messages');
        const container = document.getElementById('chat-container');

        // Insert two un-animated messages into the swap target
        chatMessages.insertAdjacentHTML('beforeend', `
            <div class="message-enter">New msg 1</div>
            <div class="message-enter">New msg 2</div>
        `);

        // The target in afterSwap detail is the element HTMX swapped into
        dispatchHTMXEvent('htmx:afterSwap', {
            target: chatMessages,
        });

        // Advance past the 50ms scroll delay
        vi.advanceTimersByTime(50);

        expect(container.scrollTo).toHaveBeenCalled();

        // All .message-enter:not(.animated) should now have the animated class
        const msgs = chatMessages.querySelectorAll('.message-enter');
        msgs.forEach(msg => {
            expect(msg.classList.contains('animated')).toBe(true);
        });
    });

    it('does not re-add animated class to already-animated messages', () => {
        const chatMessages = document.getElementById('chat-messages');

        chatMessages.insertAdjacentHTML('beforeend', `
            <div class="message-enter animated">Already animated</div>
            <div class="message-enter">Brand new</div>
        `);

        dispatchHTMXEvent('htmx:afterSwap', {
            target: chatMessages,
        });

        const alreadyAnimated = chatMessages.querySelector('.message-enter.animated');
        expect(alreadyAnimated).not.toBeNull();

        // The new message should also be animated now
        const allAnimated = chatMessages.querySelectorAll('.message-enter.animated');
        expect(allAnimated.length).toBeGreaterThanOrEqual(2);
    });
});

// ---------------------------------------------------------------------------
// htmx:responseError
// ---------------------------------------------------------------------------

describe('htmx:responseError handler', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        vi.spyOn(console, 'error').mockImplementation(() => {});
        initHTMXHandlers();
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('hides loading indicator, inserts error message, and scrolls to bottom', () => {
        const chatMessages = document.getElementById('chat-messages');
        const container = document.getElementById('chat-container');
        const loadingIndicator = document.getElementById('loading-indicator');

        // Show loading first so we can verify it gets hidden
        loadingIndicator.classList.remove('hidden');

        dispatchHTMXEvent('htmx:responseError', {
            xhr: { status: 500 },
        });

        // Loading indicator should be hidden
        expect(loadingIndicator.classList.contains('hidden')).toBe(true);

        // Error message should be inserted
        const errorMsg = chatMessages.querySelector('.text-red-200');
        expect(errorMsg).not.toBeNull();
        expect(errorMsg.textContent).toContain('Sorry, there was an error');

        // scrollToBottom should have been called (advance past delay)
        vi.advanceTimersByTime(50);
        expect(container.scrollTo).toHaveBeenCalled();
    });

    it('logs error details to console', () => {
        const detail = { xhr: { status: 500 }, message: 'Server error' };
        dispatchHTMXEvent('htmx:responseError', detail);

        expect(console.error).toHaveBeenCalledWith('HTMX request failed:', detail);
    });

    it('does nothing extra when chat-messages is missing', () => {
        // Remove chat-messages but keep loading-indicator
        document.getElementById('chat-messages').remove();

        // Should not throw
        expect(() => {
            dispatchHTMXEvent('htmx:responseError', {
                xhr: { status: 500 },
            });
        }).not.toThrow();

        // Loading indicator should still be hidden (hideLoading runs before the chatMessages check)
        const loadingIndicator = document.getElementById('loading-indicator');
        expect(loadingIndicator.classList.contains('hidden')).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// htmx:beforeRequest (new conversation)
// ---------------------------------------------------------------------------

describe('htmx:beforeRequest handler (new conversation)', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        initHTMXHandlers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('clears input and fades messages (skipping first) when path is /new', () => {
        const chatMessages = document.getElementById('chat-messages');
        const messageInput = document.getElementById('message-input');

        // Add a second message so fading logic has something beyond the welcome
        chatMessages.insertAdjacentHTML('beforeend', `
            <div class="message-enter">Second message</div>
            <div class="message-enter">Third message</div>
        `);
        messageInput.value = 'some draft text';

        dispatchHTMXEvent('htmx:beforeRequest', {
            path: '/new',
        });

        // Input should be cleared
        expect(messageInput.value).toBe('');

        // First message should NOT be faded (index 0)
        const allMessages = chatMessages.querySelectorAll('.message-enter, [data-user-message]');
        expect(allMessages[0].style.opacity).not.toBe('0.5');

        // Subsequent messages should be faded
        for (let i = 1; i < allMessages.length; i++) {
            expect(allMessages[i].style.opacity).toBe('0.5');
            expect(allMessages[i].style.transition).toBe('opacity 0.2s');
        }
    });

    it('handles missing chat-messages and message-input gracefully', () => {
        document.body.innerHTML = '';

        expect(() => {
            dispatchHTMXEvent('htmx:beforeRequest', {
                path: '/new',
            });
        }).not.toThrow();
    });

    it('does nothing when path is not /new', () => {
        const messageInput = document.getElementById('message-input');
        messageInput.value = 'unchanged';

        dispatchHTMXEvent('htmx:beforeRequest', {
            path: '/chat',
        });

        expect(messageInput.value).toBe('unchanged');

        const chatMessages = document.getElementById('chat-messages');
        const msgs = chatMessages.querySelectorAll('.message-enter');
        msgs.forEach(msg => {
            expect(msg.style.opacity).not.toBe('0.5');
        });
    });

    it('uses pathInfo.requestPath when available', () => {
        const messageInput = document.getElementById('message-input');
        messageInput.value = 'should be cleared';

        dispatchHTMXEvent('htmx:beforeRequest', {
            pathInfo: { requestPath: '/new' },
            path: '/something-else',
        });

        // pathInfo.requestPath takes priority via optional chaining
        expect(messageInput.value).toBe('');
    });

    it('falls back to detail.path when pathInfo is undefined', () => {
        const messageInput = document.getElementById('message-input');
        messageInput.value = 'should be cleared';

        dispatchHTMXEvent('htmx:beforeRequest', {
            path: '/new',
        });

        expect(messageInput.value).toBe('');
    });
});
