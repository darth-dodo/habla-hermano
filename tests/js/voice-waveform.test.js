/**
 * Tests for voice-waveform.js — Wavesurfer.js wrapper for AI message TTS waveforms.
 *
 * Exports: createWaveformPlayer, destroyWaveformPlayer, SPEED_OPTIONS
 *
 * Wavesurfer.js is fully mocked since jsdom does not provide Web Audio APIs.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================
// Wavesurfer.js Mock
// ============================================

var mockEventHandlers = {};

function createMockWaveSurfer() {
    mockEventHandlers = {};
    return {
        on: vi.fn(function(event, handler) {
            if (!mockEventHandlers[event]) mockEventHandlers[event] = [];
            mockEventHandlers[event].push(handler);
        }),
        loadBlob: vi.fn(),
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        isPlaying: vi.fn(function() { return false; }),
        setPlaybackRate: vi.fn(),
        getPlaybackRate: vi.fn(function() { return 1; }),
        getCurrentTime: vi.fn(function() { return 0; }),
        getDuration: vi.fn(function() { return 10; }),
        destroy: vi.fn(),
        setOptions: vi.fn(),
    };
}

var mockWs;

vi.mock('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js', function() {
    return {
        default: {
            create: vi.fn(function() {
                mockWs = createMockWaveSurfer();
                return mockWs;
            }),
        },
    };
});

// ============================================
// Import module under test (after mock setup)
// ============================================

var mod = await import('../../src/static/js/modules/voice-waveform.js');
var createWaveformPlayer = mod.createWaveformPlayer;
var destroyWaveformPlayer = mod.destroyWaveformPlayer;
var SPEED_OPTIONS = mod.SPEED_OPTIONS;

// ============================================
// Helper
// ============================================

function fireWsEvent(event) {
    var handlers = mockEventHandlers[event] || [];
    for (var i = 0; i < handlers.length; i++) {
        handlers[i]();
    }
}

// ============================================
// Tests
// ============================================

describe('voice-waveform', function() {
    var container;

    beforeEach(function() {
        container = document.createElement('div');
        container.className = 'voice-waveform-container';
        document.body.appendChild(container);
        mockWs = null;
        mockEventHandlers = {};
    });

    describe('SPEED_OPTIONS', function() {
        it('exports expected speed values', function() {
            expect(SPEED_OPTIONS).toEqual([0.75, 1, 1.25, 1.5]);
        });
    });

    describe('createWaveformPlayer', function() {
        it('returns a handle with expected properties', function() {
            var handle = createWaveformPlayer(container, { language: 'es', text: 'Hola' });
            expect(handle).toHaveProperty('ws');
            expect(handle).toHaveProperty('container');
            expect(handle).toHaveProperty('opts');
            expect(handle).toHaveProperty('playBtn');
            expect(handle).toHaveProperty('speedChip');
            expect(typeof handle.play).toBe('function');
            expect(typeof handle.pause).toBe('function');
            expect(typeof handle.loadBlob).toBe('function');
            expect(typeof handle.destroy).toBe('function');
        });

        it('stores opts on the handle', function() {
            var opts = { language: 'de', text: 'Hallo' };
            var handle = createWaveformPlayer(container, opts);
            expect(handle.opts).toBe(opts);
        });

        describe('DOM structure', function() {
            it('appends a wrapper element to the container', function() {
                createWaveformPlayer(container, {});
                var wrapper = container.querySelector('.voice-wf-player');
                expect(wrapper).not.toBeNull();
            });

            it('creates a play button with play icon and aria-label', function() {
                createWaveformPlayer(container, {});
                var btn = container.querySelector('.voice-wf-play');
                expect(btn).not.toBeNull();
                expect(btn.tagName).toBe('BUTTON');
                expect(btn.getAttribute('aria-label')).toBe('Play audio');
                expect(btn.innerHTML).toContain('polygon');
            });

            it('creates a waveform div for wavesurfer', function() {
                createWaveformPlayer(container, {});
                var waveDiv = container.querySelector('.voice-wf-wave');
                expect(waveDiv).not.toBeNull();
            });

            it('creates a speed chip defaulting to 1x', function() {
                createWaveformPlayer(container, {});
                var chip = container.querySelector('.voice-wf-speed');
                expect(chip).not.toBeNull();
                expect(chip.tagName).toBe('BUTTON');
                expect(chip.textContent).toBe('1\u00d7');
                expect(chip.getAttribute('aria-label')).toBe('Playback speed');
            });

            it('creates a time display defaulting to 0:00', function() {
                createWaveformPlayer(container, {});
                var timeEl = container.querySelector('.voice-wf-time');
                expect(timeEl).not.toBeNull();
                expect(timeEl.textContent).toBe('0:00');
            });

            it('creates a top row containing play button, wave div, and speed chip', function() {
                createWaveformPlayer(container, {});
                var topRow = container.querySelector('.voice-wf-top');
                expect(topRow).not.toBeNull();
                expect(topRow.children.length).toBe(3);
                expect(topRow.children[0].className).toBe('voice-wf-play');
                expect(topRow.children[1].className).toBe('voice-wf-wave');
                expect(topRow.children[2].className).toBe('voice-wf-speed');
            });
        });

        describe('WaveSurfer.create', function() {
            it('calls WaveSurfer.create with correct options', async function() {
                var WaveSurfer = (await import('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js')).default;
                createWaveformPlayer(container, {});
                expect(WaveSurfer.create).toHaveBeenCalled();
                var callOpts = WaveSurfer.create.mock.calls[WaveSurfer.create.mock.calls.length - 1][0];
                expect(callOpts.barWidth).toBe(2);
                expect(callOpts.barGap).toBe(1);
                expect(callOpts.barRadius).toBe(2);
                expect(callOpts.height).toBe(32);
                expect(callOpts.normalize).toBe(true);
                expect(callOpts.interact).toBe(true);
                expect(callOpts.cursorWidth).toBe(0);
            });

            it('registers ready, audioprocess, and finish event handlers', function() {
                createWaveformPlayer(container, {});
                var onCalls = mockWs.on.mock.calls.map(function(c) { return c[0]; });
                expect(onCalls).toContain('ready');
                expect(onCalls).toContain('audioprocess');
                expect(onCalls).toContain('finish');
            });
        });
    });

    describe('play/pause button', function() {
        it('calls ws.play() and shows pause icon when clicked while not playing', function() {
            var handle = createWaveformPlayer(container, {});
            mockWs.isPlaying.mockReturnValue(false);
            handle.playBtn.click();
            expect(mockWs.play).toHaveBeenCalled();
            expect(handle.playBtn.innerHTML).toContain('rect');
            expect(handle.playBtn.getAttribute('aria-label')).toBe('Pause audio');
        });

        it('calls ws.pause() and shows play icon when clicked while playing', function() {
            var handle = createWaveformPlayer(container, {});
            // First click: start playing
            mockWs.isPlaying.mockReturnValue(false);
            handle.playBtn.click();
            // Second click: now playing
            mockWs.isPlaying.mockReturnValue(true);
            handle.playBtn.click();
            expect(mockWs.pause).toHaveBeenCalled();
            expect(handle.playBtn.innerHTML).toContain('polygon');
            expect(handle.playBtn.getAttribute('aria-label')).toBe('Play audio');
        });
    });

    describe('handle.play() and handle.pause()', function() {
        it('play() calls ws.play and sets pause icon', function() {
            var handle = createWaveformPlayer(container, {});
            handle.play();
            expect(mockWs.play).toHaveBeenCalled();
            expect(handle.playBtn.innerHTML).toContain('rect');
        });

        it('pause() calls ws.pause and sets play icon', function() {
            var handle = createWaveformPlayer(container, {});
            handle.pause();
            expect(mockWs.pause).toHaveBeenCalled();
            expect(handle.playBtn.innerHTML).toContain('polygon');
        });
    });

    describe('speed chip cycling', function() {
        it('cycles through all speed options on repeated clicks', function() {
            var handle = createWaveformPlayer(container, {});
            // Default is index 1 (1x). Clicks cycle: 1.25x -> 1.5x -> 0.75x -> 1x
            var expected = ['1.25\u00d7', '1.5\u00d7', '0.75\u00d7', '1\u00d7'];
            var expectedSpeeds = [1.25, 1.5, 0.75, 1];

            for (var i = 0; i < expected.length; i++) {
                handle.speedChip.click();
                expect(handle.speedChip.textContent).toBe(expected[i]);
                expect(mockWs.setPlaybackRate).toHaveBeenCalledWith(expectedSpeeds[i]);
            }
        });

        it('wraps around after reaching the last speed option', function() {
            var handle = createWaveformPlayer(container, {});
            // Click 4 times to cycle back to 1x, then once more for 1.25x
            for (var i = 0; i < 4; i++) handle.speedChip.click();
            expect(handle.speedChip.textContent).toBe('1\u00d7');
            handle.speedChip.click();
            expect(handle.speedChip.textContent).toBe('1.25\u00d7');
        });
    });

    describe('wavesurfer event handlers', function() {
        it('ready event updates time display with duration', function() {
            createWaveformPlayer(container, {});
            mockWs.getDuration.mockReturnValue(65);
            fireWsEvent('ready');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('1:05');
        });

        it('audioprocess event updates time with current/duration', function() {
            createWaveformPlayer(container, {});
            mockWs.getCurrentTime.mockReturnValue(33);
            mockWs.getDuration.mockReturnValue(120);
            fireWsEvent('audioprocess');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('0:33 / 2:00');
        });

        it('finish event resets play button and shows duration', function() {
            var handle = createWaveformPlayer(container, {});
            // Simulate playing state
            handle.play();
            expect(handle.playBtn.innerHTML).toContain('rect');

            mockWs.getDuration.mockReturnValue(10);
            fireWsEvent('finish');
            expect(handle.playBtn.innerHTML).toContain('polygon');
            expect(handle.playBtn.getAttribute('aria-label')).toBe('Play audio');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('0:10');
        });
    });

    describe('time formatting', function() {
        it('formats 0 seconds as 0:00', function() {
            createWaveformPlayer(container, {});
            mockWs.getDuration.mockReturnValue(0);
            fireWsEvent('ready');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('0:00');
        });

        it('formats 9 seconds with leading zero', function() {
            createWaveformPlayer(container, {});
            mockWs.getDuration.mockReturnValue(9);
            fireWsEvent('ready');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('0:09');
        });

        it('formats 90 seconds as 1:30', function() {
            createWaveformPlayer(container, {});
            mockWs.getDuration.mockReturnValue(90);
            fireWsEvent('ready');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('1:30');
        });

        it('formats 605 seconds as 10:05', function() {
            createWaveformPlayer(container, {});
            mockWs.getDuration.mockReturnValue(605);
            fireWsEvent('ready');
            var timeEl = container.querySelector('.voice-wf-time');
            expect(timeEl.textContent).toBe('10:05');
        });
    });

    describe('loadBlob', function() {
        it('delegates to ws.loadBlob', function() {
            var handle = createWaveformPlayer(container, {});
            var blob = new Blob(['test'], { type: 'audio/wav' });
            handle.loadBlob(blob);
            expect(mockWs.loadBlob).toHaveBeenCalledWith(blob);
        });
    });

    describe('handle.destroy()', function() {
        it('calls ws.destroy()', function() {
            var handle = createWaveformPlayer(container, {});
            handle.destroy();
            expect(mockWs.destroy).toHaveBeenCalled();
        });
    });

    describe('destroyWaveformPlayer', function() {
        it('calls ws.destroy() on a valid handle', function() {
            var handle = createWaveformPlayer(container, {});
            destroyWaveformPlayer(handle);
            expect(mockWs.destroy).toHaveBeenCalled();
        });

        it('handles null handle gracefully', function() {
            expect(function() {
                destroyWaveformPlayer(null);
            }).not.toThrow();
        });

        it('handles handle without ws gracefully', function() {
            expect(function() {
                destroyWaveformPlayer({ container: container });
            }).not.toThrow();
        });
    });
});
