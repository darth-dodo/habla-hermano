/**
 * Thread switching for the sidebar (thread_sidebar.html calls it via window.hablaThreads).
 */

const XHR = { 'X-Requested-With': 'XMLHttpRequest' };

/**
 * Select a thread (sets the active_thread cookie), then load its messages.
 * Rejects when either request fails, so the caller never shows another
 * thread's content under the wrong selection.
 * @param {string} threadId
 * @returns {Promise<{html: string, lang: string, level: string}>}
 */
export async function fetchThreadContent(threadId) {
    const selected = await fetch('/threads/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', ...XHR },
        body: 'thread_id=' + encodeURIComponent(threadId),
    });
    if (!selected.ok) throw new Error(`select failed: HTTP ${selected.status}`);

    const content = await fetch('/chat/thread-content', { headers: XHR });
    if (!content.ok) throw new Error(`thread content failed: HTTP ${content.status}`);
    return {
        html: await content.text(),
        lang: content.headers.get('X-Thread-Language') || 'es',
        level: content.headers.get('X-Thread-Level') || 'A1',
    };
}
