/**
 * Habla Hermano - Finite State Machine Module
 * Phase 21: Generic, reusable FSM with guarded transitions.
 *
 * Design choices:
 * - Immutable machine definition (Object.freeze)
 * - Invalid transitions are no-ops with console.warn (safe for stale callbacks)
 * - Single onChange callback, no event emitter complexity
 * - Pure state logic — side effects happen in onChange handler
 */

/**
 * Create a frozen machine definition.
 * @param {{ initial: string, states: Object<string, Object<string, string>> }} config
 * @returns {Readonly<{ initial: string, states: Object }>}
 */
export function createMachine(config) {
    var machine = { initial: config.initial, states: config.states };
    return Object.freeze(machine);
}

/**
 * Create an interpreter (service) for a machine definition.
 * @param {Readonly<{ initial: string, states: Object }>} machine
 * @param {function(string, string, string): void} [onChange] - Called on valid transitions
 * @returns {{ state: string, send: function(string): void, matches: function(string): boolean, stop: function(): void }}
 */
export function interpret(machine, onChange) {
    var current = machine.initial;
    var stopped = false;
    var callback = onChange || null;

    return {
        get state() {
            return current;
        },

        send: function send(event) {
            if (stopped) return;

            var stateConfig = machine.states[current];
            if (!stateConfig) {
                console.warn(
                    'FSM: no transition for event "' + event + '" in state "' + current + '"'
                );
                return;
            }

            // Support both flat { EVENT: 'target' } and nested { on: { EVENT: 'target' } }
            var transitions = stateConfig.on || stateConfig;
            if (!(event in transitions)) {
                console.warn(
                    'FSM: no transition for event "' + event + '" in state "' + current + '"'
                );
                return;
            }

            var prev = current;
            current = transitions[event];

            if (callback) {
                callback(current, prev, event);
            }
        },

        matches: function matches(state) {
            return current === state;
        },

        stop: function stop() {
            stopped = true;
            callback = null;
        },
    };
}
