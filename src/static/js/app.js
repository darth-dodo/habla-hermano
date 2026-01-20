/**
 * Habla Hermano - Main JavaScript
 * Handles chat interactions, HTMX events, and UI behaviors
 */

(function() {
    'use strict';

    // ============================================
    // Configuration
    // ============================================
    const CONFIG = {
        scrollBehavior: 'smooth',
        inputFocusDelay: 100,
        scrollDelay: 50,
    };

    // ============================================
    // DOM Elements
    // ============================================
    const getElements = () => ({
        chatContainer: document.getElementById('chat-container'),
        chatMessages: document.getElementById('chat-messages'),
        chatForm: document.getElementById('chat-form'),
        messageInput: document.getElementById('message-input'),
        loadingIndicator: document.getElementById('loading-indicator'),
    });

    // ============================================
    // Utility Functions
    // ============================================

    /**
     * Scroll chat container to bottom
     * @param {boolean} smooth - Use smooth scrolling
     */
    function scrollToBottom(smooth = true) {
        const { chatContainer } = getElements();
        if (!chatContainer) return;

        setTimeout(() => {
            chatContainer.scrollTo({
                top: chatContainer.scrollHeight,
                behavior: smooth ? CONFIG.scrollBehavior : 'auto'
            });
        }, CONFIG.scrollDelay);
    }

    /**
     * Focus the message input field
     */
    function focusInput() {
        const { messageInput } = getElements();
        if (!messageInput) return;

        setTimeout(() => {
            messageInput.focus();
        }, CONFIG.inputFocusDelay);
    }

    /**
     * Clear the message input field
     */
    function clearInput() {
        const { messageInput } = getElements();
        if (!messageInput) return;

        messageInput.value = '';
    }

    /**
     * Show loading indicator
     */
    function showLoading() {
        const { loadingIndicator } = getElements();
        if (!loadingIndicator) return;

        loadingIndicator.classList.remove('hidden');
        scrollToBottom();
    }

    /**
     * Hide loading indicator
     */
    function hideLoading() {
        const { loadingIndicator } = getElements();
        if (!loadingIndicator) return;

        loadingIndicator.classList.add('hidden');
    }

    /**
     * Add user message bubble immediately (optimistic UI)
     * @param {string} message - The user's message
     */
    function addUserMessage(message) {
        const { chatMessages } = getElements();
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
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ============================================
    // HTMX Event Handlers
    // ============================================

    /**
     * Before HTMX request is sent
     */
    function onBeforeRequest(event) {
        // Only handle chat form requests
        if (event.detail.elt.id !== 'chat-form') return;

        // Get the message before it's cleared
        const { messageInput } = getElements();
        const message = messageInput ? messageInput.value : '';

        // Show user message immediately (optimistic UI)
        addUserMessage(message);

        // Clear input right away for better UX
        clearInput();

        // Show loading indicator
        showLoading();
    }

    /**
     * After HTMX request completes (success or error)
     */
    function onAfterRequest(event) {
        // Only handle chat form requests
        if (event.detail.elt.id !== 'chat-form') return;

        hideLoading();
        focusInput();
    }

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
        const { chatMessages } = getElements();
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
    // Keyboard Shortcuts
    // ============================================

    function handleKeyboardShortcuts(event) {
        // Cmd/Ctrl + Enter to send (alternative to Enter)
        if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            const { chatForm } = getElements();
            if (chatForm && document.activeElement.id === 'message-input') {
                event.preventDefault();
                htmx.trigger(chatForm, 'submit');
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
            const { messageInput } = getElements();
            if (messageInput && document.activeElement === messageInput) {
                messageInput.blur();
            }
        }

        // '/' to focus input (when not already focused)
        if (event.key === '/' && document.activeElement.tagName !== 'INPUT') {
            event.preventDefault();
            focusInput();
        }
    }

    // ============================================
    // Initialization
    // ============================================

    function init() {
        // HTMX event listeners
        document.body.addEventListener('htmx:beforeRequest', onBeforeRequest);
        document.body.addEventListener('htmx:afterRequest', onAfterRequest);
        document.body.addEventListener('htmx:afterSwap', onAfterSwap);
        document.body.addEventListener('htmx:responseError', onResponseError);
        document.body.addEventListener('htmx:beforeRequest', onNewConversationRequest);

        // Keyboard shortcuts
        document.addEventListener('keydown', handleKeyboardShortcuts);

        // Initial scroll to bottom (in case of pre-loaded messages)
        scrollToBottom(false);

        // Focus input on load
        focusInput();

        console.log('Habla Hermano initialized');
    }

    // ============================================
    // Scaffolding Functions (Word Bank & Sentence Starter)
    // ============================================

    /**
     * Insert word from word bank into message input
     * @param {string} word - The word to insert (may include translation in parentheses)
     */
    function insertWord(word) {
        const { messageInput } = getElements();
        if (!messageInput) return;

        // Extract just the word (remove translation in parentheses if present)
        const cleanWord = word.replace(/\s*\([^)]*\)\s*$/, '').trim();

        // Get cursor position
        const start = messageInput.selectionStart;
        const end = messageInput.selectionEnd;
        const text = messageInput.value;

        // Add space before if needed (not at start and previous char isn't space)
        const needsSpaceBefore = start > 0 && text[start - 1] !== ' ';
        // Add space after for easier continuation
        const insertText = (needsSpaceBefore ? ' ' : '') + cleanWord + ' ';

        // Insert at cursor position
        messageInput.value = text.slice(0, start) + insertText + text.slice(end);

        // Focus and set cursor position after inserted word
        messageInput.focus();
        const newPos = start + insertText.length;
        messageInput.selectionStart = messageInput.selectionEnd = newPos;
    }

    /**
     * Insert sentence starter (replaces input content)
     * @param {string} starter - The sentence starter to insert
     */
    function insertStarter(starter) {
        const { messageInput } = getElements();
        if (!messageInput) return;

        // Replace entire input with sentence starter
        messageInput.value = starter + ' ';

        // Focus and place cursor at end
        messageInput.focus();
        messageInput.selectionStart = messageInput.selectionEnd = messageInput.value.length;
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
        const { chatMessages, messageInput } = getElements();

        // Optional: Show brief loading state
        if (chatMessages) {
            // Keep welcome message, clear the rest
            const welcomeMessage = chatMessages.querySelector('.message-enter');
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
    // Global Exports (for inline HTMX handlers)
    // ============================================
    window.showLoading = showLoading;
    window.hideLoading = hideLoading;
    window.clearInput = clearInput;
    window.scrollToBottom = scrollToBottom;
    window.focusInput = focusInput;
    window.insertWord = insertWord;
    window.insertStarter = insertStarter;
    window.handleNewConversation = handleNewConversation;

    // ============================================
    // Start
    // ============================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
