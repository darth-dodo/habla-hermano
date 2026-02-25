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
    // Cmd/Ctrl + Enter to send (alternative to Enter)
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        const chatForm = getChatForm();
        if (chatForm && document.activeElement.id === 'message-input') {
            event.preventDefault();
            chatForm.requestSubmit();
        }
    }

    // Cmd/Ctrl + Shift + N to start new conversation
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key === 'N') {
        event.preventDefault();
        // Find and click the new conversation button
        const newChatBtn = document.querySelector('[hx-post="/new"]');
        if (newChatBtn) {
            htmx.trigger(newChatBtn, 'click');
        }
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
