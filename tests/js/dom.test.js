/**
 * Tests for src/static/js/modules/dom.js
 *
 * @environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
    getChatContainer,
    getChatMessages,
    getMessageInput,
    getChatForm,
    getLoadingIndicator,
    scrollToBottom,
    focusInput,
    focusInputExplicit,
    clearInput,
    showLoading,
    hideLoading,
    addUserMessage,
    escapeHtml,
} from '../../src/static/js/modules/dom.js';

// ---------------------------------------------------------------------------
// Shared DOM scaffold
// ---------------------------------------------------------------------------

function setupDOM() {
    document.body.innerHTML = `
        <div id="chat-container"><div id="chat-messages"></div></div>
        <textarea id="message-input"></textarea>
        <form id="chat-form"></form>
        <div id="loading-indicator" class="hidden"></div>
    `;
}

// ---------------------------------------------------------------------------
// Element Accessors
// ---------------------------------------------------------------------------

describe('Element accessors', () => {
    beforeEach(setupDOM);

    it('getChatContainer returns the chat-container element', () => {
        const el = getChatContainer();
        expect(el).not.toBeNull();
        expect(el.id).toBe('chat-container');
    });

    it('getChatMessages returns the chat-messages element', () => {
        const el = getChatMessages();
        expect(el).not.toBeNull();
        expect(el.id).toBe('chat-messages');
    });

    it('getMessageInput returns the message-input textarea', () => {
        const el = getMessageInput();
        expect(el).not.toBeNull();
        expect(el.id).toBe('message-input');
        expect(el.tagName.toLowerCase()).toBe('textarea');
    });

    it('getChatForm returns the chat-form element', () => {
        const el = getChatForm();
        expect(el).not.toBeNull();
        expect(el.id).toBe('chat-form');
    });

    it('getLoadingIndicator returns the loading-indicator element', () => {
        const el = getLoadingIndicator();
        expect(el).not.toBeNull();
        expect(el.id).toBe('loading-indicator');
    });

    it('accessors return null when elements are missing', () => {
        document.body.innerHTML = '';
        expect(getChatContainer()).toBeNull();
        expect(getChatMessages()).toBeNull();
        expect(getMessageInput()).toBeNull();
        expect(getChatForm()).toBeNull();
        expect(getLoadingIndicator()).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------

describe('escapeHtml', () => {
    it('escapes angle brackets to prevent script injection', () => {
        const result = escapeHtml('<script>alert(1)</script>');
        expect(result).not.toContain('<script>');
        expect(result).toContain('&lt;script&gt;');
    });

    it('escapes double quotes for safe attribute usage', () => {
        const result = escapeHtml('"quotes"');
        expect(result).toBe('&quot;quotes&quot;');
    });

    it('escapes single quotes for safe attribute usage', () => {
        const result = escapeHtml("it's");
        expect(result).toBe("it&#39;s");
    });

    it('escapes ampersands', () => {
        const result = escapeHtml('&amp;');
        expect(result).toBe('&amp;amp;');
    });

    it('escapes bare ampersands', () => {
        const result = escapeHtml('A & B');
        expect(result).toBe('A &amp; B');
    });

    it('preserves plain text unchanged', () => {
        expect(escapeHtml('hello world')).toBe('hello world');
    });

    it('escapes a mixed malicious payload', () => {
        const result = escapeHtml('<img src=x onerror="alert(1)">');
        expect(result).not.toContain('<img');
        expect(result).toContain('&lt;img');
    });

    it('handles an empty string', () => {
        expect(escapeHtml('')).toBe('');
    });
});

// ---------------------------------------------------------------------------
// clearInput
// ---------------------------------------------------------------------------

describe('clearInput', () => {
    beforeEach(setupDOM);

    it('clears the message input value', () => {
        const input = getMessageInput();
        input.value = 'some text';
        clearInput();
        expect(input.value).toBe('');
    });

    it('does nothing when message-input is missing', () => {
        document.body.innerHTML = '';
        expect(() => clearInput()).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// showLoading / hideLoading
// ---------------------------------------------------------------------------

describe('showLoading', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('removes the hidden class from loading indicator', () => {
        const indicator = getLoadingIndicator();
        expect(indicator.classList.contains('hidden')).toBe(true);
        showLoading();
        expect(indicator.classList.contains('hidden')).toBe(false);
    });

    it('does nothing when loading indicator is missing', () => {
        document.body.innerHTML = '';
        expect(() => showLoading()).not.toThrow();
    });
});

describe('hideLoading', () => {
    beforeEach(setupDOM);

    it('adds the hidden class to loading indicator', () => {
        const indicator = getLoadingIndicator();
        indicator.classList.remove('hidden');
        hideLoading();
        expect(indicator.classList.contains('hidden')).toBe(true);
    });

    it('is idempotent when already hidden', () => {
        const indicator = getLoadingIndicator();
        expect(indicator.classList.contains('hidden')).toBe(true);
        hideLoading();
        expect(indicator.classList.contains('hidden')).toBe(true);
    });

    it('does nothing when loading indicator is missing', () => {
        document.body.innerHTML = '';
        expect(() => hideLoading()).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// scrollToBottom
// ---------------------------------------------------------------------------

describe('scrollToBottom', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('calls scrollTo on chat-container after the configured delay', () => {
        const container = getChatContainer();
        container.scrollTo = vi.fn();

        scrollToBottom();
        // scrollTo should not fire synchronously
        expect(container.scrollTo).not.toHaveBeenCalled();

        vi.advanceTimersByTime(50);
        expect(container.scrollTo).toHaveBeenCalledOnce();
        expect(container.scrollTo).toHaveBeenCalledWith(
            expect.objectContaining({ behavior: 'smooth' }),
        );
    });

    it('uses auto behavior when smooth=false', () => {
        const container = getChatContainer();
        container.scrollTo = vi.fn();

        scrollToBottom(false);
        vi.advanceTimersByTime(50);

        expect(container.scrollTo).toHaveBeenCalledWith(
            expect.objectContaining({ behavior: 'auto' }),
        );
    });

    it('passes scrollHeight as the top value', () => {
        const container = getChatContainer();
        container.scrollTo = vi.fn();
        // jsdom scrollHeight defaults to 0; verify it is forwarded
        scrollToBottom();
        vi.advanceTimersByTime(50);

        expect(container.scrollTo).toHaveBeenCalledWith(
            expect.objectContaining({ top: container.scrollHeight }),
        );
    });

    it('does nothing when chat-container is missing', () => {
        document.body.innerHTML = '';
        expect(() => {
            scrollToBottom();
            vi.advanceTimersByTime(50);
        }).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// focusInput
// ---------------------------------------------------------------------------

describe('focusInput', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('skips focus on touch devices to avoid popping virtual keyboard', () => {
        // jsdom defines ontouchstart, so focusInput should be a no-op
        const input = getMessageInput();
        input.focus = vi.fn();

        focusInput();
        vi.advanceTimersByTime(200);
        expect(input.focus).not.toHaveBeenCalled();
    });

    it('focusInputExplicit focuses even on touch devices', () => {
        const input = getMessageInput();
        input.focus = vi.fn();

        focusInputExplicit();
        expect(input.focus).not.toHaveBeenCalled();

        vi.advanceTimersByTime(100);
        expect(input.focus).toHaveBeenCalledOnce();
    });

    it('does not focus before the delay elapses', () => {
        const input = getMessageInput();
        input.focus = vi.fn();

        focusInputExplicit();
        vi.advanceTimersByTime(50);
        expect(input.focus).not.toHaveBeenCalled();
    });

    it('does nothing when message-input is missing', () => {
        document.body.innerHTML = '';
        expect(() => {
            focusInput();
            vi.advanceTimersByTime(100);
        }).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// addUserMessage
// ---------------------------------------------------------------------------

describe('addUserMessage', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('appends a user message bubble to chat-messages', () => {
        addUserMessage('Hola mundo');
        const messages = getChatMessages();
        const bubble = messages.querySelector('[data-user-message]');
        expect(bubble).not.toBeNull();
        expect(bubble.textContent).toContain('Hola mundo');
    });

    it('escapes HTML in the message content', () => {
        addUserMessage('<script>alert("xss")</script>');
        const messages = getChatMessages();
        const paragraph = messages.querySelector('p');
        expect(paragraph.innerHTML).not.toContain('<script>');
        expect(paragraph.textContent).toContain('<script>');
    });

    it('creates the correct CSS class structure', () => {
        addUserMessage('test');
        const bubble = getChatMessages().querySelector('[data-user-message]');
        expect(bubble.classList.contains('flex')).toBe(true);
        expect(bubble.classList.contains('justify-end')).toBe(true);
        const inner = bubble.querySelector('.bg-user');
        expect(inner).not.toBeNull();
    });

    it('wraps message text in a paragraph with text-user-text class', () => {
        addUserMessage('styled text');
        const paragraph = getChatMessages().querySelector('p.text-user-text');
        expect(paragraph).not.toBeNull();
        expect(paragraph.textContent).toContain('styled text');
    });

    it('calls scrollToBottom after inserting the message', () => {
        const container = getChatContainer();
        container.scrollTo = vi.fn();

        addUserMessage('triggers scroll');

        // Advance past the scroll delay (50ms)
        vi.advanceTimersByTime(50);
        expect(container.scrollTo).toHaveBeenCalled();
    });

    it('does nothing when message is an empty string', () => {
        addUserMessage('');
        const messages = getChatMessages();
        expect(messages.querySelector('[data-user-message]')).toBeNull();
    });

    it('does nothing when message is only whitespace', () => {
        addUserMessage('   \t\n  ');
        const messages = getChatMessages();
        expect(messages.querySelector('[data-user-message]')).toBeNull();
    });

    it('does nothing when chat-messages element is missing', () => {
        document.body.innerHTML = '';
        expect(() => addUserMessage('hello')).not.toThrow();
    });
});
