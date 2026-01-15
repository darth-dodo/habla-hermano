/**
 * HablaAI - Minimal JavaScript for HTMX enhancements
 * Most interactivity is handled by HTMX
 */

// Dark mode toggle
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');

    // Check for saved theme preference or system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
        document.documentElement.classList.add('dark');
    }

    // Toggle theme on button click
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        });
    }
});

// HTMX configuration
document.body.addEventListener('htmx:configRequest', function(event) {
    // Add CSRF token if present
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        event.detail.headers['X-CSRF-Token'] = csrfToken.content;
    }
});

// Handle HTMX errors gracefully
document.body.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX request failed:', event.detail.xhr.status);
    // Could show a toast notification here
});

// Scroll to bottom of chat after new message
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'chat-messages') {
        event.detail.target.scrollTop = event.detail.target.scrollHeight;
    }
});

// Show/hide scaffold area based on content
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'scaffold-area') {
        const scaffoldArea = document.getElementById('scaffold-area');
        if (scaffoldArea && scaffoldArea.innerHTML.trim()) {
            scaffoldArea.classList.remove('hidden');
        } else if (scaffoldArea) {
            scaffoldArea.classList.add('hidden');
        }
    }
});
