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

function createMockTrack() {
    return {
        stop: vi.fn(),
        addEventListener: vi.fn(),
    };
}

function createMockMediaStream() {
    var track = createMockTrack();
    return {
        getTracks: () => [track],
        getAudioTracks: () => [track],
        _track: track,
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
            disconnect: vi.fn(),
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
        resume: vi.fn(() => Promise.resolve()),
        audioWorklet: {
            addModule: vi.fn(() => Promise.resolve()),
        },
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

// Mock Audio element for REST TTS
class MockAudio {
    constructor(url) {
        this.src = url || '';
        this.playbackRate = 1;
        this.onended = null;
        this.onerror = null;
        this.paused = true;
        MockAudio._lastInstance = this;
    }
    play() {
        this.paused = false;
        return Promise.resolve();
    }
    pause() {
        this.paused = true;
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
        globalThis.Audio = MockAudio;
        globalThis.AudioWorkletNode = vi.fn(function(ctx, name) {
            this.port = {
                onmessage: null,
                postMessage: vi.fn(),
            };
            this.connect = vi.fn();
            this.disconnect = vi.fn();
        });
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

        // fetch mock for REST TTS
        globalThis.fetch = vi.fn();
    });

    afterEach(() => {
        vi.useRealTimers();
        document.body.innerHTML = '';
        delete globalThis.WebSocket;
        delete globalThis.Audio;
        delete globalThis.AudioWorkletNode;
        delete window.voiceManager;
    });

    async function importVoice() {
        // Force fresh module evaluation by busting the cache
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

    describe('double-init guard', () => {
        it('does not create a second VoiceManager if window.voiceManager already exists', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const firstManager = window.voiceManager;

            // Import again — should be a no-op because of the guard
            vi.resetModules();
            // Manually set window.voiceManager to simulate existing instance
            window.voiceManager = firstManager;
            await import('../../src/static/js/modules/voice.js');

            expect(window.voiceManager).toBe(firstManager);
        });
    });

    describe('visibilitychange handler', () => {
        it('stops recording when page goes hidden', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm.isRecording = true;
            const spy = vi.spyOn(vm, 'stopRecording');

            Object.defineProperty(document, 'visibilityState', {
                value: 'hidden',
                configurable: true,
            });
            document.dispatchEvent(new Event('visibilitychange'));

            expect(spy).toHaveBeenCalledOnce();

            // Restore
            Object.defineProperty(document, 'visibilityState', {
                value: 'visible',
                configurable: true,
            });
        });

        it('does nothing when not recording and page goes hidden', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm.isRecording = false;
            const spy = vi.spyOn(vm, 'stopRecording');

            Object.defineProperty(document, 'visibilityState', {
                value: 'hidden',
                configurable: true,
            });
            document.dispatchEvent(new Event('visibilitychange'));

            expect(spy).not.toHaveBeenCalled();

            Object.defineProperty(document, 'visibilityState', {
                value: 'visible',
                configurable: true,
            });
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

    describe('startRecording()', () => {
        it('shows error when navigator.mediaDevices is not available', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'showMicError');

            const orig = navigator.mediaDevices;
            Object.defineProperty(navigator, 'mediaDevices', {
                value: undefined,
                configurable: true,
                writable: true,
            });

            vm.startRecording();
            expect(spy).toHaveBeenCalledWith('Voice input is not supported in this browser');

            Object.defineProperty(navigator, 'mediaDevices', {
                value: orig,
                configurable: true,
                writable: true,
            });
        });

        it('shows error when AudioContext is not available', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'showMicError');

            delete globalThis.AudioContext;
            delete globalThis.webkitAudioContext;

            vm.startRecording();
            expect(spy).toHaveBeenCalledWith('Voice input is not supported in this browser');
        });

        it('opens getUserMedia, creates AudioContext, and opens WebSocket', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0); // flush promise

            expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
            // WebSocket should be created with /ws/transcribe endpoint
            expect(MockWebSocket._lastInstance.url).toContain('/ws/transcribe');
            expect(MockWebSocket._lastInstance.url).toContain('language=multi');
        });

        it('sets isRecording=true and disables send on WS open', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            // Simulate WS open
            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            expect(vm.isRecording).toBe(true);
            expect(vm.sendButton.disabled).toBe(true);
            expect(vm.chatInput.readOnly).toBe(true);
        });

        it('uses ScriptProcessor fallback when AudioWorklet is not available', async () => {
            setupVoiceDOM();
            // Create context WITHOUT audioWorklet
            globalThis.AudioContext = vi.fn(() => {
                var ctx = createMockAudioContext();
                delete ctx.audioWorklet;
                return ctx;
            });
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            // ScriptProcessor should have been created
            expect(vm._sttAudioCtx.createScriptProcessor).toHaveBeenCalled();
        });

        it('falls back to ScriptProcessor when AudioWorklet addModule rejects', async () => {
            setupVoiceDOM();
            globalThis.AudioContext = vi.fn(() => {
                var ctx = createMockAudioContext();
                ctx.audioWorklet.addModule = vi.fn(() => Promise.reject(new Error('fail')));
                return ctx;
            });
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);
            // Flush the catch handler
            await vi.advanceTimersByTimeAsync(0);

            expect(vm._sttAudioCtx.createScriptProcessor).toHaveBeenCalled();
        });

        it('handles final transcript in onmessage', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            // Send a final transcript
            ws.onmessage({ data: JSON.stringify({ transcript: 'Hola', is_final: true }) });
            expect(vm.chatInput.value).toBe('Hola');
            expect(vm.chatInput.classList.contains('voice-interim')).toBe(false);

            // Send another final transcript — should accumulate
            ws.onmessage({ data: JSON.stringify({ transcript: 'amigo', is_final: true }) });
            expect(vm.chatInput.value).toBe('Hola amigo');
        });

        it('handles interim transcript in onmessage', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            // Send interim transcript
            ws.onmessage({ data: JSON.stringify({ transcript: 'hol', is_final: false }) });
            expect(vm.chatInput.value).toBe('hol');
            expect(vm.chatInput.classList.contains('voice-interim')).toBe(true);
        });

        it('shows interim with accumulated finals prefix', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            ws.onmessage({ data: JSON.stringify({ transcript: 'Hola', is_final: true }) });
            ws.onmessage({ data: JSON.stringify({ transcript: 'ami', is_final: false }) });
            expect(vm.chatInput.value).toBe('Hola ami');
        });

        it('ignores malformed JSON in onmessage', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            // Should not throw
            expect(() => ws.onmessage({ data: 'not json{{{' })).not.toThrow();
        });

        it('calls autoResizeInput when available', async () => {
            setupVoiceDOM();
            window.autoResizeInput = vi.fn();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            ws.onmessage({ data: JSON.stringify({ transcript: 'Hola', is_final: true }) });
            expect(window.autoResizeInput).toHaveBeenCalled();

            delete window.autoResizeInput;
        });

        it('stops recording and shows error on WS error', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const stopSpy = vi.spyOn(vm, 'stopRecording');
            const errSpy = vi.spyOn(vm, 'showMicError');

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.onerror();

            expect(stopSpy).toHaveBeenCalled();
            expect(errSpy).toHaveBeenCalledWith('Voice input temporarily unavailable');
        });

        it('shows service error on WS close with code 1011', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            ws.onclose({ code: 1011, reason: '' });
            expect(document.querySelector('.voice-error-tooltip').textContent).toBe('Voice service error \u2014 please try again');
        });

        it('shows reason on WS close with code 1008', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            ws.onclose({ code: 1008, reason: 'Bad language param' });
            expect(document.querySelector('.voice-error-tooltip').textContent).toBe('Bad language param');
        });

        it('shows connection lost on unexpected WS close codes', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            ws.onclose({ code: 1006, reason: '' });
            expect(document.querySelector('.voice-error-tooltip').textContent).toBe('Voice connection lost');
        });

        it('does not show error on normal close (1000)', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();
            // Manually stop to simulate normal close after stop
            vm.isRecording = true;
            ws.onclose({ code: 1000, reason: '' });
            // 1000 is normal, no error
            expect(document.querySelector('.voice-error-tooltip')).toBeNull();
        });

        it('shows error for NotAllowedError from getUserMedia', async () => {
            setupVoiceDOM();
            navigator.mediaDevices.getUserMedia = vi.fn(() => {
                var err = new Error('Permission denied');
                err.name = 'NotAllowedError';
                return Promise.reject(err);
            });
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'showMicError');

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            expect(spy).toHaveBeenCalledWith('Microphone access needed for voice input');
        });

        it('shows error for NotReadableError from getUserMedia', async () => {
            setupVoiceDOM();
            navigator.mediaDevices.getUserMedia = vi.fn(() => {
                var err = new Error('Device in use');
                err.name = 'NotReadableError';
                return Promise.reject(err);
            });
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'showMicError');

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            expect(spy).toHaveBeenCalledWith('Microphone is in use by another app');
        });

        it('shows generic error for other getUserMedia failures', async () => {
            setupVoiceDOM();
            navigator.mediaDevices.getUserMedia = vi.fn(() => Promise.reject(new Error('unknown')));
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'showMicError');

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            expect(spy).toHaveBeenCalledWith('Could not access microphone');
        });

        it('monitors audio track ended event and stops recording', async () => {
            setupVoiceDOM();
            const mockStream = createMockMediaStream();
            navigator.mediaDevices.getUserMedia = vi.fn(() => Promise.resolve(mockStream));
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            // Simulate WS open so isRecording is true
            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();
            expect(vm.isRecording).toBe(true);

            // The track should have had addEventListener('ended') called
            const track = mockStream._track;
            expect(track.addEventListener).toHaveBeenCalledWith('ended', expect.any(Function));

            // Simulate track ended
            const endedCb = track.addEventListener.mock.calls.find(c => c[0] === 'ended')[1];
            endedCb();

            // The stopRecording spy should show isRecording is now false
            expect(vm.isRecording).toBe(false);
        });
    });

    describe('stopRecording()', () => {
        it('cleans up ScriptProcessor, stream, and WebSocket', async () => {
            setupVoiceDOM();
            // Force ScriptProcessor path
            globalThis.AudioContext = vi.fn(() => {
                var ctx = createMockAudioContext();
                delete ctx.audioWorklet;
                return ctx;
            });
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            expect(vm.isRecording).toBe(true);
            expect(vm._scriptProcessor).not.toBeNull();

            vm.stopRecording();

            expect(vm.isRecording).toBe(false);
            expect(vm._scriptProcessor).toBeNull();
            expect(vm._source).toBeNull();
            expect(vm._stream).toBeNull();
            expect(vm.ws).toBeNull();
        });

        it('disconnects MediaStreamAudioSourceNode to release mic indicator', async () => {
            setupVoiceDOM();
            globalThis.AudioContext = vi.fn(() => {
                var ctx = createMockAudioContext();
                delete ctx.audioWorklet;
                return ctx;
            });
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            const source = vm._source;
            expect(source).not.toBeNull();

            vm.stopRecording();

            expect(source.disconnect).toHaveBeenCalled();
            expect(vm._source).toBeNull();
        });

        it('cleans up WorkletNode when present', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.startRecording();
            await vi.advanceTimersByTimeAsync(0);
            // Flush AudioWorklet addModule promise
            await vi.advanceTimersByTimeAsync(0);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen();

            // WorkletNode should have been created
            expect(vm._workletNode).not.toBeNull();
            const workletNode = vm._workletNode;

            vm.stopRecording();

            expect(workletNode.port.postMessage).toHaveBeenCalledWith('stop');
            expect(vm._workletNode).toBeNull();
        });

        it('removes voice-interim class from chat input', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.chatInput.classList.add('voice-interim');
            vm.isRecording = true;
            vm.stopRecording();

            expect(vm.chatInput.classList.contains('voice-interim')).toBe(false);
        });

        it('shows processing state after stopping', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm.isRecording = true;
            vm.stopRecording();

            expect(vm.micButton.innerHTML).toContain('voice-spinner');
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

        it('does not restore mic icon while processing timeout is active', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();
            vm.isRecording = false;
            // _processingTimeout is set
            vm.updateMicUI();

            // Should still show spinner, not mic icon
            expect(vm.micButton.innerHTML).toContain('voice-spinner');
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

    describe('_startLevelAnimation() / _stopLevelAnimation()', () => {
        it('starts animation loop using requestAnimationFrame', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            // Manually set up analyser
            const mockAnalyser = {
                fftSize: 0,
                smoothingTimeConstant: 0,
                frequencyBinCount: 128,
                getByteFrequencyData: vi.fn(),
            };
            vm._analyser = mockAnalyser;
            vm.isRecording = true;

            // Set up level bars in the mic button
            vm.micButton.innerHTML = '<div class="voice-level-bars">'
                + '<span class="voice-bar"></span><span class="voice-bar"></span>'
                + '<span class="voice-bar"></span><span class="voice-bar"></span>'
                + '</div>';

            vm._startLevelAnimation();

            expect(requestAnimationFrame).toHaveBeenCalled();

            // Advance one animation frame
            vi.advanceTimersByTime(16);

            expect(mockAnalyser.getByteFrequencyData).toHaveBeenCalled();
        });

        it('skips animation loop when prefers-reduced-motion is set', async () => {
            setupVoiceDOM();
            globalThis.matchMedia = vi.fn(() => ({ matches: true }));
            vm = await importVoice();

            vm._analyser = { frequencyBinCount: 128 };
            vm.isRecording = true;

            vm._startLevelAnimation();

            // requestAnimationFrame should NOT have been called
            expect(requestAnimationFrame).not.toHaveBeenCalled();
        });

        it('does nothing when analyser is null', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._analyser = null;
            vm._startLevelAnimation();

            expect(requestAnimationFrame).not.toHaveBeenCalled();
        });

        it('_stopLevelAnimation cancels animation frame and nulls analyser', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._levelAnimFrame = 42;
            vm._analyser = {};

            vm._stopLevelAnimation();

            expect(cancelAnimationFrame).toHaveBeenCalledWith(42);
            expect(vm._levelAnimFrame).toBeNull();
            expect(vm._analyser).toBeNull();
        });
    });

    describe('_startTimer() / _stopTimer()', () => {
        it('creates timer element and starts interval', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._startTimer();

            const timer = document.querySelector('.voice-timer');
            expect(timer).not.toBeNull();
            expect(timer.textContent).toBe('0:00');
            expect(timer.getAttribute('aria-hidden')).toBe('true');
            expect(vm._timerInterval).not.toBeNull();
        });

        it('updates timer display each second', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._startTimer();
            const timer = document.querySelector('.voice-timer');

            // Advance 1 second
            vi.advanceTimersByTime(1000);
            expect(timer.textContent).toBe('0:01');

            // Advance to 65 seconds
            vi.advanceTimersByTime(64000);
            expect(timer.textContent).toBe('1:05');
        });

        it('_stopTimer clears interval and removes element', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._startTimer();
            expect(document.querySelector('.voice-timer')).not.toBeNull();

            vm._stopTimer();

            expect(document.querySelector('.voice-timer')).toBeNull();
            expect(vm._timerInterval).toBeNull();
            expect(vm._timerElement).toBeNull();
            expect(vm._timerStartTime).toBe(0);
        });

        it('_startTimer does nothing when _micWrapper is null', async () => {
            setupVoiceDOMWithoutMic();
            vm = await importVoice();

            vm._startTimer();

            expect(document.querySelector('.voice-timer')).toBeNull();
            expect(vm._timerInterval).toBeNull();
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

        it('clears the processing timeout', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            vm._showProcessing();
            expect(vm._processingTimeout).not.toBeNull();

            vm._hideProcessing();
            expect(vm._processingTimeout).toBeNull();
        });

        it('dismisses processing early when called before timeout fires', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            // Show processing (sets 2s timeout)
            vm._showProcessing();
            expect(vm._processingTimeout).not.toBeNull();
            expect(document.querySelector('.voice-processing-indicator')).not.toBeNull();

            // Immediately hide (simulates early final transcript arriving)
            vm._hideProcessing();

            expect(vm._processingTimeout).toBeNull();
            expect(vm._processingIndicator).toBeNull();
            expect(document.querySelector('.voice-processing-indicator')).toBeNull();
            expect(vm.micButton.innerHTML).toContain('svg');
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

        it('stops TTS when button is already playing', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, '_stopTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-playing';
            btn.dataset.text = 'Hola';

            vm.handleSpeakClick(btn);

            expect(spy).toHaveBeenCalledWith(btn);
        });

        it('stops TTS when button is in loading state', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, '_stopTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            btn.dataset.text = 'Hola';

            vm.handleSpeakClick(btn);

            expect(spy).toHaveBeenCalledWith(btn);
        });

        it('stops all other TTS before starting new one', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, '_stopAllTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hola';
            btn.dataset.language = 'es';

            vm.handleSpeakClick(btn);

            expect(spy).toHaveBeenCalled();
            expect(btn.classList.contains('voice-loading')).toBe(true);
        });

        it('clamps speed to 0.25-2.0 range', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, '_streamTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hola';
            btn.dataset.speed = '5.0'; // above max
            btn.dataset.language = 'es';

            vm.handleSpeakClick(btn);
            await vi.advanceTimersByTimeAsync(0); // Flush resume() promise

            // Speed should be clamped to 2.0
            expect(spy).toHaveBeenCalledWith(btn, 'Hola', 'aura-2-nestor-es', 2.0, expect.anything());
        });

        it('uses speed from tts-speed-picker when available', async () => {
            setupVoiceDOM();
            // Add a speed picker element
            const picker = document.createElement('div');
            picker.id = 'tts-speed-picker';
            picker.dataset.ttsSpeed = '0.75';
            document.body.appendChild(picker);

            vm = await importVoice();
            const spy = vi.spyOn(vm, '_streamTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hola';
            btn.dataset.language = 'es';

            vm.handleSpeakClick(btn);
            await vi.advanceTimersByTimeAsync(0); // Flush resume() promise

            expect(spy).toHaveBeenCalledWith(btn, 'Hola', 'aura-2-nestor-es', 0.75, expect.anything());
        });

        it('resumes suspended AudioContext before calling _streamTTS', async () => {
            setupVoiceDOM();
            // Make AudioContext return suspended state
            const mockCtx = createMockAudioContext();
            mockCtx.state = 'suspended';
            let ctxCreated = false;
            globalThis.AudioContext = vi.fn(() => {
                if (!ctxCreated) {
                    ctxCreated = true;
                    return mockCtx;
                }
                return createMockAudioContext();
            });

            vm = await importVoice();
            const spy = vi.spyOn(vm, '_streamTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hola';
            btn.dataset.language = 'es';

            vm.handleSpeakClick(btn);

            expect(mockCtx.resume).toHaveBeenCalled();

            // Flush the resume promise
            await vi.advanceTimersByTimeAsync(0);

            expect(spy).toHaveBeenCalled();
        });

        it('falls back to _restTTS when AudioContext is not available', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            // Remove AudioContext after import so handleSpeakClick takes REST path
            delete globalThis.AudioContext;
            delete globalThis.webkitAudioContext;

            // Ensure fetch is available for the REST fallback
            globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, blob: () => Promise.resolve(new Blob()) }));
            const spy = vi.spyOn(vm, '_restTTS');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hola';
            btn.dataset.language = 'es';

            vm.handleSpeakClick(btn);

            expect(spy).toHaveBeenCalledWith(btn, 'Hola', 'aura-2-nestor-es', 1.0);
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

        it('closes active TTS WebSocket', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const mockWs = new MockWebSocket('ws://test');
            mockWs.readyState = MockWebSocket.OPEN;
            mockWs.send = vi.fn();
            mockWs.close = vi.fn();
            vm._ttsWs = mockWs;

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';

            vm._stopTTS(btn);

            expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'close' }));
            expect(mockWs.close).toHaveBeenCalled();
            expect(vm._ttsWs).toBeNull();
        });

        it('pauses current audio and revokes blob URL', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const mockAudio = { pause: vi.fn() };
            vm.currentAudio = mockAudio;
            vm.currentBlobUrl = 'blob:mock';

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';

            vm._stopTTS(btn);

            expect(mockAudio.pause).toHaveBeenCalled();
            expect(vm.currentAudio).toBeNull();
            expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
            expect(vm.currentBlobUrl).toBeNull();
        });

        it('stops all scheduled AudioBufferSourceNodes', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const source1 = { stop: vi.fn() };
            const source2 = { stop: vi.fn() };
            vm._ttsSources = [source1, source2];

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';

            vm._stopTTS(btn);

            expect(source1.stop).toHaveBeenCalled();
            expect(source2.stop).toHaveBeenCalled();
            expect(vm._ttsSources).toEqual([]);
        });
    });

    describe('_stopAllTTS()', () => {
        it('stops all buttons with voice-playing or voice-loading class', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            // Add some speak buttons in various states
            const btn1 = document.createElement('button');
            btn1.className = 'voice-speak-btn voice-playing';
            const btn2 = document.createElement('button');
            btn2.className = 'voice-speak-btn voice-loading';
            const btn3 = document.createElement('button');
            btn3.className = 'voice-speak-btn'; // idle — not affected
            document.body.appendChild(btn1);
            document.body.appendChild(btn2);
            document.body.appendChild(btn3);

            const spy = vi.spyOn(vm, '_stopTTS');

            vm._stopAllTTS();

            expect(spy).toHaveBeenCalledTimes(2);
            expect(spy).toHaveBeenCalledWith(btn1);
            expect(spy).toHaveBeenCalledWith(btn2);
        });
    });

    describe('_streamTTS()', () => {
        it('opens WebSocket with correct voice URL and sends text on open', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola mundo', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            expect(ws.url).toContain('/ws/speak');
            expect(ws.url).toContain('voice=' + encodeURIComponent('aura-2-nestor-es'));
            expect(ws.binaryType).toBe('arraybuffer');

            // Simulate open
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ text: 'Hola mundo' }));
        });

        it('decodes PCM audio and schedules playback via AudioBufferSource', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // Send binary PCM data (Int16)
            const pcm = new Int16Array([1000, -1000, 500, -500]);
            ws.onmessage({ data: pcm.buffer });

            expect(ctx.createBuffer).toHaveBeenCalledWith(1, pcm.length, 24000);
            expect(ctx.createBufferSource).toHaveBeenCalled();

            // Button should transition from loading to playing
            expect(btn.classList.contains('voice-loading')).toBe(false);
            expect(btn.classList.contains('voice-playing')).toBe(true);
        });

        it('handles Blob data from Safari by converting to ArrayBuffer', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // Simulate Safari sending Blob instead of ArrayBuffer.
            // Create a mock Blob-like object with arrayBuffer() method since
            // jsdom's Blob may not have it.
            const pcm = new Int16Array([500, -500]);
            const mockBlob = Object.create(Blob.prototype);
            mockBlob.arrayBuffer = vi.fn(() => Promise.resolve(pcm.buffer));

            ws.onmessage({ data: mockBlob });

            // Flush the blob.arrayBuffer() promise
            await vi.advanceTimersByTimeAsync(0);

            // After conversion, createBuffer should have been called
            expect(mockBlob.arrayBuffer).toHaveBeenCalled();
            expect(ctx.createBuffer).toHaveBeenCalled();
        });

        it('handles JSON control messages gracefully', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // JSON metadata message
            expect(() => ws.onmessage({ data: JSON.stringify({ type: 'Flushed' }) })).not.toThrow();
            expect(() => ws.onmessage({ data: 'not-json-not-arraybuffer' })).not.toThrow();
        });

        it('cleans up on WS error and shows tooltip', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.onerror();

            expect(btn.classList.contains('voice-loading')).toBe(false);
            expect(vm._ttsPlaying).toBe(false);
        });

        it('shows service error on WS close with code 1011 before audio started', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.onclose({ code: 1011, reason: '' });

            expect(btn.classList.contains('voice-loading')).toBe(false);
            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Speech service error \u2014 try again');
        });

        it('shows reason on WS close with code 1008', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.onclose({ code: 1008, reason: 'Bad voice param' });

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Bad voice param');
        });

        it('shows generic error on unexpected WS close before audio started', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.onclose({ code: 1006, reason: '' });

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Could not play audio');
        });

        it('cleans up after all buffers finish and WS is done', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            const sources = [];
            const ctx = createMockAudioContext();
            ctx.createBufferSource = vi.fn(() => {
                const src = {
                    buffer: null,
                    playbackRate: { value: 1 },
                    connect: vi.fn(),
                    start: vi.fn(),
                    onended: null,
                };
                sources.push(src);
                return src;
            });

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // Send two audio chunks
            const pcm1 = new Int16Array([100, 200]);
            const pcm2 = new Int16Array([300, 400]);
            ws.onmessage({ data: pcm1.buffer });
            ws.onmessage({ data: pcm2.buffer });

            // WS closes normally
            ws.onclose({ code: 1000, reason: '' });

            // Button should still be playing (buffers not finished yet)
            expect(btn.classList.contains('voice-playing')).toBe(true);

            // First buffer finishes
            sources[0].onended();
            expect(btn.classList.contains('voice-playing')).toBe(true);

            // Last buffer finishes — cleanup should happen
            sources[1].onended();
            expect(btn.classList.contains('voice-playing')).toBe(false);
            expect(vm._ttsPlaying).toBe(false);
        });

        it('ignores audio data after _ttsPlaying is set to false', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            const ctx = createMockAudioContext();

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // Manually stop TTS
            vm._ttsPlaying = false;

            // Send PCM data — should be ignored
            const pcm = new Int16Array([100, 200]);
            ws.onmessage({ data: pcm.buffer });

            expect(ctx.createBuffer).not.toHaveBeenCalled();
        });

        it('cleans up immediately on WS close when all buffers already done', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            const sources = [];
            const ctx = createMockAudioContext();
            ctx.createBufferSource = vi.fn(() => {
                const src = {
                    buffer: null,
                    playbackRate: { value: 1 },
                    connect: vi.fn(),
                    start: vi.fn(),
                    onended: null,
                };
                sources.push(src);
                return src;
            });

            vm._streamTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0, ctx);

            const ws = MockWebSocket._lastInstance;
            ws.readyState = MockWebSocket.OPEN;
            ws.send = vi.fn();
            ws.onopen();

            // Send one chunk
            const pcm = new Int16Array([100]);
            ws.onmessage({ data: pcm.buffer });

            // Buffer finishes before WS close
            sources[0].onended();

            // Now WS closes — should clean up immediately
            ws.onclose({ code: 1000, reason: '' });

            expect(btn.classList.contains('voice-playing')).toBe(false);
            expect(vm._ttsPlaying).toBe(false);
        });
    });

    describe('_restTTS()', () => {
        it('fetches audio from /api/speak and plays it', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const audioBlob = new Blob(['audio-data'], { type: 'audio/mpeg' });
            globalThis.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                blob: () => Promise.resolve(audioBlob),
            }));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0);

            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);

            expect(globalThis.fetch).toHaveBeenCalledWith('/api/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify({ text: 'Hola', voice: 'aura-2-nestor-es' }),
            });

            // Audio should be set up
            expect(btn.classList.contains('voice-playing')).toBe(true);
            expect(btn.classList.contains('voice-loading')).toBe(false);
        });

        it('cleans up on audio ended', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const audioBlob = new Blob(['data'], { type: 'audio/mpeg' });
            globalThis.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                blob: () => Promise.resolve(audioBlob),
            }));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0);

            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);

            // Trigger onended callback
            const audio = MockAudio._lastInstance;
            audio.onended();

            expect(URL.revokeObjectURL).toHaveBeenCalled();
            expect(btn.classList.contains('voice-playing')).toBe(false);
            expect(vm.currentAudio).toBeNull();
        });

        it('shows error tooltip on audio playback error', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const audioBlob = new Blob(['data'], { type: 'audio/mpeg' });
            globalThis.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                blob: () => Promise.resolve(audioBlob),
            }));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0);

            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);

            const audio = MockAudio._lastInstance;
            audio.onerror();

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Audio playback failed');
        });

        it('shows error on HTTP error response', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            globalThis.fetch = vi.fn(() => Promise.resolve({
                ok: false,
                status: 503,
            }));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0);

            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Speech service not configured');
            expect(btn.classList.contains('voice-loading')).toBe(false);
        });

        it('shows generic error on non-503 fetch failure', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            globalThis.fetch = vi.fn(() => Promise.reject(new Error('network error')));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 1.0);

            await vi.advanceTimersByTimeAsync(0);

            const tooltip = document.querySelector('.voice-error-tooltip');
            expect(tooltip.textContent).toBe('Could not play audio');
        });

        it('sets playbackRate from speed parameter', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const audioBlob = new Blob(['data'], { type: 'audio/mpeg' });
            globalThis.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                blob: () => Promise.resolve(audioBlob),
            }));

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn voice-loading';
            document.body.appendChild(btn);

            vm._restTTS(btn, 'Hola', 'aura-2-nestor-es', 0.75);

            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);

            const audio = MockAudio._lastInstance;
            expect(audio.playbackRate).toBe(0.75);
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
                await vi.advanceTimersByTimeAsync(0); // Flush resume() promise

                // The WebSocket constructor is called with the voice in the URL
                const ws = MockWebSocket._lastInstance;
                expect(ws.url).toContain('voice=' + encodeURIComponent(expectedVoice));

                // Clean up for next iteration
                vm._stopTTS(btn);
            }
        });

        it('defaults to es voice when language is unknown', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Hello';
            btn.dataset.language = 'xx'; // unknown language

            vm.handleSpeakClick(btn);
            await vi.advanceTimersByTimeAsync(0); // Flush resume() promise

            const ws = MockWebSocket._lastInstance;
            expect(ws.url).toContain('voice=' + encodeURIComponent('aura-2-nestor-es'));
            vm._stopTTS(btn);
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

    describe('speaker button click delegation', () => {
        it('delegates click on .voice-speak-btn to handleSpeakClick', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'handleSpeakClick');

            const btn = document.createElement('button');
            btn.className = 'voice-speak-btn';
            btn.dataset.text = 'Test';
            document.body.appendChild(btn);

            btn.click();

            expect(spy).toHaveBeenCalledWith(btn);
        });
    });

    describe('destroy()', () => {
        it('stops recording if active', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'stopRecording');
            vm.isRecording = true;

            vm.destroy();

            expect(spy).toHaveBeenCalledOnce();
        });

        it('calls _stopAllTTS', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, '_stopAllTTS');

            vm.destroy();

            expect(spy).toHaveBeenCalledOnce();
        });

        it('closes TTS WebSocket if open', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const mockWs = new MockWebSocket('ws://test');
            mockWs.readyState = MockWebSocket.OPEN;
            mockWs.close = vi.fn();
            vm._ttsWs = mockWs;

            vm.destroy();

            expect(mockWs.close).toHaveBeenCalled();
            expect(vm._ttsWs).toBeNull();
        });

        it('does not throw if TTS WebSocket is already closed', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const mockWs = new MockWebSocket('ws://test');
            mockWs.readyState = MockWebSocket.CLOSED;
            vm._ttsWs = mockWs;

            expect(() => vm.destroy()).not.toThrow();
            expect(vm._ttsWs).toBeNull();
        });

        it('stops microphone stream tracks', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const stream = createMockMediaStream();
            vm._stream = stream;

            vm.destroy();

            expect(stream._track.stop).toHaveBeenCalled();
            expect(vm._stream).toBeNull();
        });

        it('clears _ttsEndFallback timeout', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm._ttsEndFallback = setTimeout(() => {}, 10000);

            vm.destroy();

            expect(vm._ttsEndFallback).toBeNull();
        });

        it('clears _processingTimeout', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm._processingTimeout = setTimeout(() => {}, 10000);

            vm.destroy();

            expect(vm._processingTimeout).toBeNull();
        });

        it('clears _errorTimeout', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm._errorTimeout = setTimeout(() => {}, 10000);

            vm.destroy();

            expect(vm._errorTimeout).toBeNull();
        });

        it('clears dynamic _errTimeout_ keys', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm['_errTimeout_mic-btn'] = setTimeout(() => {}, 10000);
            vm['_errTimeout_anon'] = setTimeout(() => {}, 10000);

            vm.destroy();

            expect(vm['_errTimeout_mic-btn']).toBeNull();
            expect(vm['_errTimeout_anon']).toBeNull();
        });

        it('resets internal state', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            vm.isRecording = true;
            vm._ttsPlaying = true;
            vm._finalTranscript = 'hello';
            vm._ttsGeneration = 5;

            vm.destroy();

            expect(vm.isRecording).toBe(false);
            expect(vm._ttsPlaying).toBe(false);
            expect(vm._finalTranscript).toBe('');
            expect(vm._ttsGeneration).toBe(0);
            expect(vm.ws).toBeNull();
            expect(vm.currentAudio).toBeNull();
            expect(vm.currentBlobUrl).toBeNull();
            expect(vm._audioCtx).toBeNull();
            expect(vm._sttAudioCtx).toBeNull();
            expect(vm._source).toBeNull();
            expect(vm._scriptProcessor).toBeNull();
            expect(vm._workletNode).toBeNull();
            expect(vm._analyser).toBeNull();
        });

        it('is safe to call multiple times', async () => {
            setupVoiceDOM();
            vm = await importVoice();

            expect(() => {
                vm.destroy();
                vm.destroy();
                vm.destroy();
            }).not.toThrow();
        });

        it('does not throw when no state has been initialized', async () => {
            setupVoiceDOMWithoutMic();
            vm = await importVoice();

            expect(() => vm.destroy()).not.toThrow();
        });

        it('does not call stopRecording when not recording', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'stopRecording');
            vm.isRecording = false;

            vm.destroy();

            expect(spy).not.toHaveBeenCalled();
        });
    });

    describe('beforeunload handler', () => {
        it('calls destroy on the voiceManager during beforeunload', async () => {
            setupVoiceDOM();
            vm = await importVoice();
            const spy = vi.spyOn(vm, 'destroy');

            window.dispatchEvent(new Event('beforeunload'));

            // The handler may fire multiple times due to module re-imports across
            // tests (each import registers a new listener). The important thing is
            // that destroy was called at least once for the current manager.
            expect(spy).toHaveBeenCalled();
        });
    });
});
