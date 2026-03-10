/**
 * Tests for fsm.js — Generic Finite State Machine Module (Phase 21)
 *
 * Pure unit tests for transition tables, no-op on invalid events,
 * onChange callback, stop(), and frozen machine definitions.
 */
import { describe, it, expect, vi } from 'vitest';
import { createMachine, interpret } from '../../src/static/js/modules/fsm.js';

// ============================================
// Shared test machine — models a simple connection lifecycle
// ============================================

var testMachine = createMachine({
    initial: 'idle',
    states: {
        idle:       { START: 'connecting' },
        connecting: { CONNECTED: 'active', ERROR: 'idle', CANCEL: 'idle' },
        active:     { STOP: 'idle' },
    },
});

// ============================================
// createMachine
// ============================================

describe('createMachine', () => {
    it('returns a frozen machine definition', () => {
        expect(Object.isFrozen(testMachine)).toBe(true);
    });

    it('preserves initial state', () => {
        expect(testMachine.initial).toBe('idle');
    });

    it('preserves state definitions', () => {
        expect(testMachine.states.idle).toEqual({ START: 'connecting' });
        expect(testMachine.states.connecting).toEqual({
            CONNECTED: 'active',
            ERROR: 'idle',
            CANCEL: 'idle',
        });
        expect(testMachine.states.active).toEqual({ STOP: 'idle' });
    });
});

// ============================================
// interpret — basic transitions
// ============================================

describe('interpret — basic transitions', () => {
    it('starts in the initial state', () => {
        var service = interpret(testMachine);
        expect(service.state).toBe('idle');
    });

    it('transitions idle -> connecting -> active -> idle', () => {
        var service = interpret(testMachine);

        service.send('START');
        expect(service.state).toBe('connecting');

        service.send('CONNECTED');
        expect(service.state).toBe('active');

        service.send('STOP');
        expect(service.state).toBe('idle');
    });

    it('transitions connecting -> idle on ERROR', () => {
        var service = interpret(testMachine);
        service.send('START');
        service.send('ERROR');
        expect(service.state).toBe('idle');
    });

    it('transitions connecting -> idle on CANCEL', () => {
        var service = interpret(testMachine);
        service.send('START');
        service.send('CANCEL');
        expect(service.state).toBe('idle');
    });
});

// ============================================
// interpret — invalid transitions
// ============================================

describe('interpret — invalid transitions', () => {
    it('is a no-op when event is not valid for current state', () => {
        var warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        var service = interpret(testMachine);

        service.send('BOGUS');
        expect(service.state).toBe('idle');

        warnSpy.mockRestore();
    });

    it('logs console.warn on invalid transition', () => {
        var warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        var service = interpret(testMachine);

        service.send('CONNECTED');
        expect(warnSpy).toHaveBeenCalledOnce();
        expect(warnSpy.mock.calls[0][0]).toContain('CONNECTED');
        expect(warnSpy.mock.calls[0][0]).toContain('idle');

        warnSpy.mockRestore();
    });

    it('does not change state on invalid event', () => {
        var warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        var service = interpret(testMachine);

        service.send('STOP');
        expect(service.state).toBe('idle');

        service.send('START');
        service.send('STOP');
        expect(service.state).toBe('connecting');

        warnSpy.mockRestore();
    });
});

// ============================================
// interpret — onChange callback
// ============================================

describe('interpret — onChange callback', () => {
    it('fires with (newState, prevState, event) on valid transitions', () => {
        var callback = vi.fn();
        var service = interpret(testMachine, callback);

        service.send('START');
        expect(callback).toHaveBeenCalledWith('connecting', 'idle', 'START');

        service.send('CONNECTED');
        expect(callback).toHaveBeenCalledWith('active', 'connecting', 'CONNECTED');

        expect(callback).toHaveBeenCalledTimes(2);
    });

    it('does NOT fire on invalid transitions', () => {
        var warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        var callback = vi.fn();
        var service = interpret(testMachine, callback);

        service.send('BOGUS');
        service.send('CONNECTED');
        service.send('STOP');

        expect(callback).not.toHaveBeenCalled();
        warnSpy.mockRestore();
    });

    it('works without onChange callback', () => {
        var service = interpret(testMachine);
        service.send('START');
        expect(service.state).toBe('connecting');
    });
});

// ============================================
// interpret — matches()
// ============================================

describe('interpret — matches()', () => {
    it('returns true for current state', () => {
        var service = interpret(testMachine);
        expect(service.matches('idle')).toBe(true);
    });

    it('returns false for non-current state', () => {
        var service = interpret(testMachine);
        expect(service.matches('connecting')).toBe(false);
        expect(service.matches('active')).toBe(false);
    });

    it('updates after transitions', () => {
        var service = interpret(testMachine);
        service.send('START');

        expect(service.matches('idle')).toBe(false);
        expect(service.matches('connecting')).toBe(true);
    });
});

// ============================================
// interpret — stop()
// ============================================

describe('interpret — stop()', () => {
    it('makes send() a no-op after stop', () => {
        var service = interpret(testMachine);
        service.send('START');
        expect(service.state).toBe('connecting');

        service.stop();

        service.send('CONNECTED');
        expect(service.state).toBe('connecting');
    });

    it('does not log console.warn after stop', () => {
        var warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        var service = interpret(testMachine);
        service.stop();

        service.send('BOGUS');
        service.send('START');

        expect(warnSpy).not.toHaveBeenCalled();
        warnSpy.mockRestore();
    });

    it('does not fire onChange after stop', () => {
        var callback = vi.fn();
        var service = interpret(testMachine, callback);

        service.send('START');
        expect(callback).toHaveBeenCalledTimes(1);

        service.stop();
        service.send('CONNECTED');
        expect(callback).toHaveBeenCalledTimes(1);
    });
});

// ============================================
// interpret — multiple independent instances
// ============================================

describe('interpret — multiple instances', () => {
    it('two services from same machine are independent', () => {
        var service1 = interpret(testMachine);
        var service2 = interpret(testMachine);

        service1.send('START');
        expect(service1.state).toBe('connecting');
        expect(service2.state).toBe('idle');

        service2.send('START');
        service2.send('CONNECTED');
        expect(service2.state).toBe('active');
        expect(service1.state).toBe('connecting');
    });

    it('stopping one service does not affect another', () => {
        var service1 = interpret(testMachine);
        var service2 = interpret(testMachine);

        service1.stop();

        service2.send('START');
        expect(service2.state).toBe('connecting');

        service1.send('START');
        expect(service1.state).toBe('idle');
    });
});
