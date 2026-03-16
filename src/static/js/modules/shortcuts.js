/**
 * Habla Hermano - Keyboard Shortcuts Module
 * Phase 16: Keyboard shortcut handling.
 */

import { getMessageInput, getChatForm, focusInputExplicit } from './dom.js';

// ============================================
// Keyboard Shortcuts
// ============================================

/**
 * Handle keyboard shortcut events
 * @param {KeyboardEvent} event
 */
function handleKeyboardShortcuts(event) {
    // Enter to send (Shift+Enter for newline)
    if (event.key === 'Enter' && !event.shiftKey && document.activeElement.id === 'message-input') {
        event.preventDefault();
        const chatForm = getChatForm();
        if (chatForm) {
            chatForm.requestSubmit();
        }
    }

    // Cmd/Ctrl + Shift + N: new conversation
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key === 'N') {
        event.preventDefault();
        window.location.href = '/';
    }

    // Escape to blur input
    if (event.key === 'Escape') {
        const messageInput = getMessageInput();
        if (messageInput && document.activeElement === messageInput) {
            messageInput.blur();
        }
    }

    // '/' to focus input (when not already in a text field)
    if (event.key === '/' && document.activeElement.tagName !== 'INPUT'
        && document.activeElement.tagName !== 'TEXTAREA') {
        event.preventDefault();
        focusInputExplicit();
    }
}

/**
 * Attach keyboard shortcut handler to document
 */
export function initKeyboardShortcuts() {
    document.addEventListener('keydown', handleKeyboardShortcuts);
}
