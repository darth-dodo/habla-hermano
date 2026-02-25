/**
 * Habla Hermano - HTMX Event Handlers (ES Module)
 * Handles HTMX lifecycle events for chat interactions and UI behaviors.
 *
 * Dead code removed: onBeforeRequest and onAfterRequest were no-ops after
 * Phase 15 switched chat to SSE streaming via fetch().
 */

import { getChatMessages, getMessageInput, scrollToBottom, hideLoading, escapeHtml } from './dom.js';

// ============================================
// HTMX Event Handlers
// ============================================

/**
 * After HTMX swaps content into DOM
 */
function onAfterSwap(event) {
    // Remove any user message we added optimistically (server response includes it)
    // Actually, we need to handle this differently - server only returns AI response now

    // Scroll to bottom after new message is added
    scrollToBottom();

    // Add animation class to new messages
    const newMessages = event.detail.target.querySelectorAll('.message-enter:not(.animated)');
    newMessages.forEach(msg => {
        msg.classList.add('animated');
    });
}

/**
 * Handle HTMX errors
 * Note: Error colors (red-*) are intentionally hardcoded as semantic error indicators
 * that remain consistent across all themes for accessibility and clarity.
 */
function onResponseError(event) {
    console.error('HTMX request failed:', event.detail);
    hideLoading();

    // Show error message to user
    const chatMessages = getChatMessages();
    if (chatMessages) {
        const errorHtml = `
            <div class="message-enter flex justify-start mb-6">
                <div class="bg-red-900/50 border border-red-700 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%]">
                    <p class="text-red-200">
                        Sorry, there was an error processing your message. Please try again.
                    </p>
                </div>
            </div>
        `;
        chatMessages.insertAdjacentHTML('beforeend', errorHtml);
        scrollToBottom();
    }
}

// ============================================
// New Conversation Handler
// ============================================

/**
 * Handle new conversation button response
 * Server returns HX-Redirect header, HTMX handles the redirect automatically
 */
function handleNewConversation() {
    // Clear existing messages (for visual feedback while redirect happens)
    const chatMessages = getChatMessages();
    const messageInput = getMessageInput();

    // Optional: Show brief loading state
    if (chatMessages) {
        // Keep welcome message, clear the rest
        const allMessages = chatMessages.querySelectorAll('.message-enter, [data-user-message]');

        // If redirect doesn't happen immediately, give visual feedback
        allMessages.forEach((msg, index) => {
            if (index > 0) { // Skip first message (welcome)
                msg.style.opacity = '0.5';
                msg.style.transition = 'opacity 0.2s';
            }
        });
    }

    // Clear input
    if (messageInput) {
        messageInput.value = '';
    }
}

/**
 * HTMX beforeRequest handler for new conversation
 */
function onNewConversationRequest(event) {
    // Check if this is a request to /new endpoint
    const path = event.detail.pathInfo?.requestPath || event.detail.path;
    if (path === '/new') {
        handleNewConversation();
    }
}

// ============================================
// Initialization
// ============================================

export function initHTMXHandlers() {
    document.body.addEventListener('htmx:afterSwap', onAfterSwap);
    document.body.addEventListener('htmx:responseError', onResponseError);
    document.body.addEventListener('htmx:beforeRequest', onNewConversationRequest);
}
