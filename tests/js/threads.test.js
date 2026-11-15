/**
 * Tests for threads.js: a thread switch never loads content after a failed select.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchThreadContent } from '../../src/static/js/modules/threads.js';

afterEach(() => vi.restoreAllMocks());

describe('threads.js: fetchThreadContent', () => {
    it('selects, then returns the content with its language and level', async () => {
        globalThis.fetch = vi.fn()
            .mockResolvedValueOnce(new Response('', { status: 200 }))
            .mockResolvedValueOnce(new Response('<p>hola</p>', {
                status: 200,
                headers: { 'X-Thread-Language': 'hi', 'X-Thread-Level': 'A2' },
            }));
        await expect(fetchThreadContent('user:u:t1')).resolves.toEqual({ html: '<p>hola</p>', lang: 'hi', level: 'A2' });
        expect(fetch.mock.calls[0][0]).toBe('/threads/select');
        expect(fetch.mock.calls[0][1].body).toBe('thread_id=user%3Au%3At1');
    });

    it('rejects and never loads content when the select fails', async () => {
        globalThis.fetch = vi.fn().mockResolvedValueOnce(new Response('', { status: 404 }));
        await expect(fetchThreadContent('user:u:gone')).rejects.toThrow('HTTP 404');
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it('rejects when the content request fails', async () => {
        globalThis.fetch = vi.fn()
            .mockResolvedValueOnce(new Response('', { status: 200 }))
            .mockResolvedValueOnce(new Response('oops', { status: 500 }));
        await expect(fetchThreadContent('user:u:t1')).rejects.toThrow('HTTP 500');
    });
});
