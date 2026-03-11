/**
 * Habla Hermano - Main Entry Point
 * Phase 16: ES module entry point. Imports all modules and initializes the app.
 */

import { scrollToBottom, focusInput, getMessageInput, autoResizeTextarea } from './modules/dom.js';
import { initStreamingForm } from './modules/stream.js';
import { initKeyboardShortcuts } from './modules/shortcuts.js';
import { initScaffoldDelegation } from './modules/scaffold.js';
import { initHTMXHandlers } from './modules/htmx-handlers.js';

// ============================================
// Initialization
// ============================================
function init() {
    initHTMXHandlers();
    initStreamingForm();
    initKeyboardShortcuts();
    initScaffoldDelegation();

    // Auto-resize textarea on input
    const messageInput = getMessageInput();
    if (messageInput) {
        messageInput.addEventListener('input', () => autoResizeTextarea(messageInput));
    }

    // Initial state
    scrollToBottom(false);
    focusInput();
}

// ES module scripts are deferred by default — DOM is ready.
// Keep the check as a safety net for dynamic injection.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// ============================================
// Virtual Keyboard Handling (mobile)
// ============================================
if ('visualViewport' in window) {
    let vkPending = false;
    window.visualViewport.addEventListener('resize', () => {
        if (vkPending) return;
        vkPending = true;
        requestAnimationFrame(() => {
            vkPending = false;
            const chatContainer = document.getElementById('chat-container');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        });
    });
}
