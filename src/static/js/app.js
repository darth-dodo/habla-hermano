/**
 * HablaAI - Main JavaScript
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

    // ============================================
    // HTMX Event Handlers
    // ============================================

    /**
     * Before HTMX request is sent
     */
    function onBeforeRequest(event) {
        // Only handle chat form requests
        if (event.detail.elt.id !== 'chat-form') return;

        showLoading();
    }

    /**
     * After HTMX request completes (success or error)
     */
    function onAfterRequest(event) {
        // Only handle chat form requests
        if (event.detail.elt.id !== 'chat-form') return;

        hideLoading();
        clearInput();
        focusInput();
    }

    /**
     * After HTMX swaps content into DOM
     */
    function onAfterSwap(event) {
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
     */
    function onResponseError(event) {
        console.error('HTMX request failed:', event.detail);
        hideLoading();

        // Show error message to user
        const { chatMessages } = getElements();
        if (chatMessages) {
            const errorHtml = `
                <div class="message-enter flex items-start gap-3">
                    <div class="flex-shrink-0 w-8 h-8 rounded-full bg-red-600 flex items-center justify-center">
                        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <div class="bg-red-900/50 border border-red-700 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%]">
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

        // Keyboard shortcuts
        document.addEventListener('keydown', handleKeyboardShortcuts);

        // Initial scroll to bottom (in case of pre-loaded messages)
        scrollToBottom(false);

        // Focus input on load
        focusInput();

        console.log('HablaAI initialized');
    }

    // ============================================
    // Global Exports (for inline HTMX handlers)
    // ============================================
    window.showLoading = showLoading;
    window.hideLoading = hideLoading;
    window.clearInput = clearInput;
    window.scrollToBottom = scrollToBottom;
    window.focusInput = focusInput;

    // ============================================
    // Start
    // ============================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
