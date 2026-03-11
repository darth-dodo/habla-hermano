/**
 * Habla Hermano - DOM Utilities Module
 * Phase 16: Shared DOM accessors and UI helpers.
 */

const CONFIG = {
    scrollBehavior: 'smooth',
    inputFocusDelay: 100,
    scrollDelay: 50,
};

// ============================================
// Element Accessors
// Functions not cached refs — elements may not exist on all pages
// ============================================

export function getChatContainer() { return document.getElementById('chat-container'); }
export function getChatMessages() { return document.getElementById('chat-messages'); }
export function getMessageInput() { return document.getElementById('message-input'); }
export function getChatForm() { return document.getElementById('chat-form'); }
export function getLoadingIndicator() { return document.getElementById('loading-indicator'); }

// ============================================
// Utility Functions
// ============================================

/**
 * Scroll chat container to bottom
 * @param {boolean} smooth - Use smooth scrolling
 */
export function scrollToBottom(smooth = true) {
    const chatContainer = getChatContainer();
    if (!chatContainer) return;

    setTimeout(() => {
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: smooth ? CONFIG.scrollBehavior : 'auto'
        });
    }, CONFIG.scrollDelay);
}

/**
 * Focus the message input field.
 * On touch devices, skip auto-focus to avoid popping up the virtual keyboard
 * unexpectedly (e.g. after page load or message send).
 */
export function focusInput() {
    if ('ontouchstart' in window && !focusInput._explicit) return;
    focusInput._explicit = false;

    const messageInput = getMessageInput();
    if (!messageInput) return;

    setTimeout(() => {
        messageInput.focus();
    }, CONFIG.inputFocusDelay);
}

/**
 * Focus the message input field even on mobile.
 * Use this when the user has explicitly requested focus (e.g. pressing '/' shortcut).
 */
export function focusInputExplicit() {
    focusInput._explicit = true;
    focusInput();
}

/**
 * Clear the message input field and reset its height.
 */
export function clearInput() {
    const messageInput = getMessageInput();
    if (!messageInput) return;

    messageInput.value = '';
    messageInput.style.height = 'auto';
    // Dispatch input event so listeners (e.g. mic/send button swap, auto-resize) react
    messageInput.dispatchEvent(new Event('input', { bubbles: true }));
}

/**
 * Auto-resize textarea to fit its content, capped at ~6 rows.
 * Call on 'input' events to grow/shrink dynamically.
 * @param {HTMLTextAreaElement} textarea
 */
export function autoResizeTextarea(textarea) {
    if (!textarea) return;
    // Reset to auto to get the correct scrollHeight for shrinking
    textarea.style.height = 'auto';
    // Cap at roughly 6 lines (6 * line-height ~1.5 * 16px = 144px)
    const maxHeight = 144;
    textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
    // Show scrollbar only when at max height
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden';
}

/**
 * Show loading indicator
 */
export function showLoading() {
    const loadingIndicator = getLoadingIndicator();
    if (!loadingIndicator) return;

    loadingIndicator.classList.remove('hidden');
    scrollToBottom();
}

/**
 * Hide loading indicator
 */
export function hideLoading() {
    const loadingIndicator = getLoadingIndicator();
    if (!loadingIndicator) return;

    loadingIndicator.classList.add('hidden');
}

/**
 * Add user message bubble immediately (optimistic UI)
 * @param {string} message - The user's message
 */
export function addUserMessage(message) {
    const chatMessages = getChatMessages();
    if (!chatMessages || !message.trim()) return;

    const userBubbleHtml = `
        <div class="message-enter flex justify-end mb-6" data-user-message>
            <div class="bg-user rounded-2xl rounded-br-sm px-4 py-3 max-w-[80%] shadow-sm">
                <p class="text-user-text leading-relaxed">${escapeHtml(message)}</p>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', userBubbleHtml);
    scrollToBottom();
}

/**
 * Escape HTML to prevent XSS.
 * Escapes &, <, >, " and ' so the result is safe in both
 * element content and attribute values.
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
