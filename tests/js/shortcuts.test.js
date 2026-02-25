/**
 * Tests for src/static/js/modules/shortcuts.js
 *
 * @environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { initKeyboardShortcuts } from '../../src/static/js/modules/shortcuts.js';

// ---------------------------------------------------------------------------
// Shared DOM scaffold
// ---------------------------------------------------------------------------

function setupDOM() {
    document.body.innerHTML = `
        <form id="chat-form">
            <textarea id="message-input"></textarea>
            <button type="submit" id="send-button">Send</button>
        </form>
        <button hx-post="/new" id="new-chat-btn">New Conversation</button>
        <div id="chat-container"><div id="chat-messages"></div></div>
    `;
    // jsdom does not implement scrollTo
    const container = document.getElementById('chat-container');
    container.scrollTo = vi.fn();
}

// ---------------------------------------------------------------------------
// Helper: dispatch a keyboard event on document
// ---------------------------------------------------------------------------

function pressKey(key, options = {}) {
    const event = new KeyboardEvent('keydown', {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
    });
    document.dispatchEvent(event);
    return event;
}

// ---------------------------------------------------------------------------
// initKeyboardShortcuts
// ---------------------------------------------------------------------------

describe('initKeyboardShortcuts', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('registers a keydown listener on document', () => {
        const spy = vi.spyOn(document, 'addEventListener');
        initKeyboardShortcuts();

        const registeredEvents = spy.mock.calls.map(call => call[0]);
        expect(registeredEvents).toContain('keydown');

        spy.mockRestore();
    });
});

// ---------------------------------------------------------------------------
// Cmd/Ctrl + Enter  (submit form)
// ---------------------------------------------------------------------------

describe('Cmd/Ctrl + Enter shortcut', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        initKeyboardShortcuts();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('submits the form when message-input is focused (metaKey)', () => {
        const form = document.getElementById('chat-form');
        form.requestSubmit = vi.fn();

        const input = document.getElementById('message-input');
        input.focus();

        pressKey('Enter', { metaKey: true });

        expect(form.requestSubmit).toHaveBeenCalledOnce();
    });

    it('submits the form when message-input is focused (ctrlKey)', () => {
        const form = document.getElementById('chat-form');
        form.requestSubmit = vi.fn();

        const input = document.getElementById('message-input');
        input.focus();

        pressKey('Enter', { ctrlKey: true });

        expect(form.requestSubmit).toHaveBeenCalledOnce();
    });

    it('does nothing when message-input is not focused', () => {
        const form = document.getElementById('chat-form');
        form.requestSubmit = vi.fn();

        // Focus something other than message-input
        document.getElementById('send-button').focus();

        pressKey('Enter', { metaKey: true });

        expect(form.requestSubmit).not.toHaveBeenCalled();
    });

    it('does nothing when chat-form is missing', () => {
        document.getElementById('chat-form').removeAttribute('id');
        const input = document.getElementById('message-input');
        // Re-create input outside any form
        document.body.innerHTML = '<textarea id="message-input"></textarea>';
        const newInput = document.getElementById('message-input');
        newInput.focus();

        // Should not throw even though getChatForm() returns null
        expect(() => {
            pressKey('Enter', { metaKey: true });
        }).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// Cmd/Ctrl + Shift + N  (new conversation)
// ---------------------------------------------------------------------------

describe('Cmd/Ctrl + Shift + N shortcut', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        // Mock the global htmx object
        window.htmx = { trigger: vi.fn() };
        initKeyboardShortcuts();
    });
    afterEach(() => {
        vi.useRealTimers();
        delete window.htmx;
    });

    it('triggers click on the new conversation button', () => {
        const newChatBtn = document.querySelector('[hx-post="/new"]');

        pressKey('N', { metaKey: true, shiftKey: true });

        expect(window.htmx.trigger).toHaveBeenCalledWith(newChatBtn, 'click');
    });

    it('does nothing when the new conversation button is missing', () => {
        document.getElementById('new-chat-btn').remove();

        expect(() => {
            pressKey('N', { metaKey: true, shiftKey: true });
        }).not.toThrow();

        expect(window.htmx.trigger).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// Escape  (blur input)
// ---------------------------------------------------------------------------

describe('Escape shortcut', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        initKeyboardShortcuts();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('blurs message-input when it is focused', () => {
        const input = document.getElementById('message-input');
        input.focus();
        expect(document.activeElement).toBe(input);

        pressKey('Escape');

        expect(document.activeElement).not.toBe(input);
    });

    it('does nothing when message-input is not focused', () => {
        const input = document.getElementById('message-input');
        const blurSpy = vi.spyOn(input, 'blur');

        // Focus something else
        document.getElementById('send-button').focus();

        pressKey('Escape');

        expect(blurSpy).not.toHaveBeenCalled();

        blurSpy.mockRestore();
    });
});

// ---------------------------------------------------------------------------
// '/' shortcut  (focus input)
// ---------------------------------------------------------------------------

describe('/ shortcut (focus input)', () => {
    beforeEach(() => {
        setupDOM();
        vi.useFakeTimers();
        initKeyboardShortcuts();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('calls focusInputExplicit when activeElement is not INPUT or TEXTAREA', () => {
        // Focus on a non-input element (the button)
        document.getElementById('send-button').focus();

        const input = document.getElementById('message-input');
        input.focus = vi.fn();

        pressKey('/');

        // focusInputExplicit sets _explicit flag then calls focusInput which
        // uses setTimeout(100ms). jsdom has ontouchstart so focusInput normally
        // skips, but _explicit bypasses that guard.
        vi.advanceTimersByTime(100);

        expect(input.focus).toHaveBeenCalledOnce();
    });

    it('does not trigger when activeElement is an INPUT', () => {
        // Create an input element and focus it
        const textInput = document.createElement('input');
        textInput.type = 'text';
        document.body.appendChild(textInput);
        textInput.focus();

        const msgInput = document.getElementById('message-input');
        msgInput.focus = vi.fn();

        pressKey('/');

        vi.advanceTimersByTime(100);

        expect(msgInput.focus).not.toHaveBeenCalled();
    });

    it('does not trigger when activeElement is a TEXTAREA', () => {
        // The message-input is a textarea; focus it first
        const textarea = document.getElementById('message-input');
        textarea.focus();

        const focusSpy = vi.fn();
        // Replace focus to track calls after the initial focus()
        textarea.focus = focusSpy;

        pressKey('/');

        vi.advanceTimersByTime(100);

        expect(focusSpy).not.toHaveBeenCalled();
    });
});
