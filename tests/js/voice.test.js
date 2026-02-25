/**
 * Tests for voice.js — Voice STT/TTS Module (Phase 17)
 *
 * The module self-initializes on import and sets window.voiceManager.
 * VoiceManager is a constructor function (not exported), so we test
 * through the window.voiceManager instance after importing the module.
 *
 * Browser APIs (MediaDevices, WebSocket, AudioContext) are mocked since
 * jsdom does not provide them.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ============================================
// Browser API Mocks
// ============================================

function createMockMediaStream() {
    return {
        getTracks: () => [{ stop: vi.fn() }],
    };
}

function createMockAudioContext() {
    return {
        sampleRate: 44100,
        state: 'running',
        currentTime: 0,
        destination: {},
        createMediaStreamSource: vi.fn(() => ({
            connect: vi.fn(),
        })),
        createAnalyser: vi.fn(() => ({
            fftSize: 0,
            smoothingTimeConstant: 0,
            frequencyBinCount: 128,
            getByteFrequencyData: vi.fn(),
            connect: vi.fn(),
        })),
        createScriptProcessor: vi.fn(() => ({
            onaudioprocess: null,
            connect: vi.fn(),
            disconnect: vi.fn(),
        })),
        createBuffer: vi.fn(() => ({
            duration: 0.1,
            getChannelData: () => new Float32Array(100),
        })),
        createBufferSource: vi.fn(() => ({
            buffer: null,
            playbackRate: { value: 1 },
            connect: vi.fn(),
            start: vi.fn(),
            onended: null,
        })),
        close: vi.fn(() => Promise.resolve()),
    };
}

class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor(url) {
        this.url = url;
        this.readyState = MockWebSocket.CONNECTING;
        this.binaryType = 'blob';
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        // Auto-open after microtask to simulate real WS behavior
        MockWebSocket._lastInstance = this;
    }

    send(data) {}
    close() {
        this.readyState = MockWebSocket.CLOSED;
    }
}

// ============================================
// DOM Setup
// ============================================

function setupVoiceDOM() {
    document.body.innerHTML = `
        <div class="flex items-end gap-2">
            <button id="mic-btn" type="button" aria-label="Record voice message">
                <svg class="w-5 h-5"></svg>
            </button>
            <textarea id="message-input"></textarea>
            <button id="send-btn" type="submit">Send</button>
            <input type="hidden" name="language" value="es" />
        </div>
    `;
}

function setupVoiceDOMWithoutMic() {
    document.body.innerHTML = `
        <textarea id="message-input"></textarea>
        <button id="send-btn" type="submit">Send</button>
    `;
}

// ============================================
// Test Suites
// ============================================

describe('voice.js — VoiceManager', () => {
    let vm;

    beforeEach(() => {
        vi.useFakeTimers();
        vi.restoreAllMocks();
        document.body.innerHTML = '';

        // Set up browser API mocks on globalThis
        globalThis.WebSocket = MockWebSocket;
        globalThis.AudioContext = vi.fn(createMockAudioContext);
        globalThis.requestAnimationFrame = vi.fn((cb) => setTimeout(cb, 16));
        globalThis.cancelAnimationFrame = vi.fn((id) => clearTimeout(id));
        globalThis.URL = {
            createObjectURL: vi.fn(() => 'blob:mock-url'),
            revokeObjectURL: vi.fn(),
        };

        if (!navigator.mediaDevices) {
            Object.defineProperty(navigator, 'mediaDevices', {
                value: { getUserMedia: vi.fn() },
                configurable: true,
                writable: true,
            });
        } else {
            navigator.mediaDevices.getUserMedia = vi.fn();
        }
        navigator.mediaDevices.getUserMedia.mockResolvedValue(createMockMediaStream());

        // matchMedia stub for reduced-motion check
        globalThis.matchMedia = vi.fn(() => ({ matches: false }));
    });

    afterEach(() => {
        vi.useRealTimers();
        document.body.innerHTML = '';
        delete globalThis.WebSocket;
        delete window.voiceManager;
    });

    // Helper: create and init a VoiceManager without importing the module
    // (which would auto-init with whatever DOM exists at import time).
    // We re-create the constructor manually from the module's pattern.
    function createVoiceManager() {
        // Import the module. It will run init() which sets window.voiceManager.
        // Because we set up DOM *before* this runs, it finds the elements.
        // But we already have the DOM set up in beforeEach, so we just
        // construct a fresh VoiceManager using the prototype from the module.
        //
        // Actually, since voice.js uses plain `function VoiceManager()` and
        // self-initializes, the cleanest approach is to simply create a new
        // VoiceManager-like object that mirrors the constructor + init pattern.
        // But since we want to test the real code, we set up DOM first,
        // then use dynamic import.
    }

    async function importVoice() {
        // Force fresh module evaluation by busting the cache
        const timestamp = Date.now() + Math.random();
        // Vitest caches modules; use vi.resetModules() + dynamic import
        vi.resetModules();
        await import('../../src/static/js/modules/voice.js');
        return window.voiceManager;
    }

    describe('init()', () => {
        it('finds mic button, chat input, and send button', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            expect(vm.micButton).toBe(document.getElementById('mic-btn'));
            expect(vm.chatInput).toBe(document.getElementById('message-input'));
            expect(vm.sendButton).toBe(document.getElementById('send-btn'));
        });

        it('wraps mic button in a relative-positioned div', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const micBtn = document.getElementById('mic-btn');
            const wrapper = micBtn.parentElement;
            expect(wrapper.tagName).toBe('DIV');
            expect(wrapper.className).toContain('relative');
            expect(vm._micWrapper).toBe(wrapper);
        });

        it('does nothing when mic-btn is absent', async () => {
            setupVoiceDOMWithoutMic();
            vm = await importVoice();

            expect(vm.micButton).toBeNull();
            expect(vm._micWrapper).toBeNull();
        });
    });

    describe('toggleRecording()', () => {
        it('calls startRecording when not currently recording', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'startRecording');

            vm.isRecording = false;
            vm.toggleRecording();

            expect(spy).toHaveBeenCalledOnce();
        });

        it('calls stopRecording when already recording', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'stopRecording');

            vm.isRecording = true;
            vm.toggleRecording();

            expect(spy).toHaveBeenCalledOnce();
        });
    });

    describe('updateMicUI()', () => {
        it('shows recording class and stop-like UI when recording', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.isRecording = true;
            vm.updateMicUI();

            expect(vm.micButton.classList.contains('voice-recording')).toBe(true);
            expect(vm.micButton.getAttribute('aria-label')).toBe('Stop recording');
            // Should contain level bars HTML (voice-level-bars)
            expect(vm.micButton.innerHTML).toContain('voice-level-bars');
        });

        it('shows mic icon when not recording', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.isRecording = false;
            vm._processingTimeout = null;
            vm.updateMicUI();

            expect(vm.micButton.classList.contains('voice-recording')).toBe(false);
            expect(vm.micButton.getAttribute('aria-label')).toBe('Record voice message');
            // Should contain SVG mic icon path
            expect(vm.micButton.innerHTML).toContain('svg');
        });
    });

    describe('showMicError()', () => {
        it('creates tooltip element with the error message', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.showMicError('Microphone access needed');

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip).not.toBeNull();
            expect(tooltip.textContent).toBe('Microphone access needed');
            expect(tooltip.getAttribute('role')).toBe('alert');
        });

        it('auto-removes tooltip after 4 seconds', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.showMicError('Test error');

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip).not.toBeNull();

            // Advance timers by 4 seconds
            vi.advanceTimersByTime(4000);

            const removed = document.querySelector('.voice-error-tooltip');
            expect(removed).toBeNull();
        });

        it('replaces existing tooltip for the same anchor', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.showMicError('Error 1');
            vm.showMicError('Error 2');

            const tooltips = document.querySelectorAll('.voice-error-tooltip');
            expect(tooltips.length).toBe(1);
            expect(tooltips[0].textContent).toBe('Error 2');
        });
    });

    describe('_setSendEnabled()', () => {
        it('disables send button and makes input readonly when false', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._setSendEnabled(false);

            expect(vm.sendButton.disabled).toBe(true);
            expect(vm.chatInput.readOnly).toBe(true);
        });

        it('enables send button and makes input editable when true', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._setSendEnabled(false);
            vm._setSendEnabled(true);

            expect(vm.sendButton.disabled).toBe(false);
            expect(vm.chatInput.readOnly).toBe(false);
        });
    });

    describe('_showProcessing()', () => {
        it('swaps mic button to spinner and shows processing pill', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();

            expect(vm.micButton.innerHTML).toContain('voice-spinner');
            expect(vm.micButton.getAttribute('aria-label')).toContain('Processing');
            expect(vm.micButton.classList.contains('voice-recording')).toBe(false);

            // Processing indicator should be appended to the wrapper
            const pill = document.querySelector('.voice-processing-indicator');
            expect(pill).not.toBeNull();
            expect(pill.textContent).toContain('Processing');
        });

        it('auto-hides after 2 seconds', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();
            expect(document.querySelector('.voice-processing-indicator')).not.toBeNull();

            vi.advanceTimersByTime(2000);

            expect(document.querySelector('.voice-processing-indicator')).toBeNull();
            // Mic icon should be restored
            expect(vm.micButton.innerHTML).toContain('svg');
        });
    });

    describe('_hideProcessing()', () => {
        it('restores mic icon and re-enables send', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();
            vm._hideProcessing();

            expect(vm.micButton.innerHTML).toContain('svg');
            expect(vm.micButton.getAttribute('aria-label')).toBe('Record voice message');
            expect(vm.sendButton.disabled).toBe(false);
            expect(vm.chatInput.readOnly).toBe(false);
        });

        it('removes processing indicator pill', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();
            vm._hideProcessing();

            expect(document.querySelector('.voice-processing-indicator')).toBeNull();
        });
    });

    describe('handleSpeakClick()', () => {
        it('does nothing when button has no data-text', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            // No data-text attribute

            // Should not throw
            expect(() => vm.handleSpeakClick(btn)).not.toThrow();
            // No classes should be added
            expect(btn.classList.contains('voice-loading')).toBe(false);
        });
    });

    describe('_stopTTS()', () => {
        it('removes playing and loading classes and restores speaker icon', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-playing voice-loading';
            btn.innerHTML = '<span>playing</span>';

            vm._stopTTS(btn);

            expect(btn.classList.contains('voice-playing')).toBe(false);
            expect(btn.classList.contains('voice-loading')).toBe(false);
            // Should restore the speaker SVG icon
            expect(btn.innerHTML).toContain('svg');
            expect(btn.innerHTML).toContain('polygon');
        });
    });

    describe('VOICES constant (tested via handleSpeakClick behavior)', () => {
        it('maps es to nestor, de to julius, fr to hector via WebSocket URL', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const testCases = [
                { lang: 'es', expectedVoice: 'aura-2-nestor-es' },
                { lang: 'de', expectedVoice: 'aura-2-julius-de' },
                { lang: 'fr', expectedVoice: 'aura-2-hector-fr' },
            ];

            for (const { lang, expectedVoice } of testCases) {
                const btn = document.createElement('button');
                btn.className = 'voice-speak-btn';
                btn.dataset.text = 'Hola';
                btn.dataset.language = lang;

                vm.handleSpeakClick(btn);

                // The WebSocket constructor is called with the voice in the URL
                const ws = MockWebSocket._lastInstance;
                expect(ws.url).toContain('voice=' + encodeURIComponent(expectedVoice));

                // Clean up for next iteration
                vm._stopTTS(btn);
            }
        });
    });

    describe('click delegation on mic button', () => {
        it('clicking mic-btn calls toggleRecording', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'toggleRecording');

            vm.micButton.click();

            expect(spy).toHaveBeenCalledOnce();
        });
    });
});
