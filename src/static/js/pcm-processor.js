/**
 * AudioWorklet processor for real-time PCM audio capture.
 * Runs on the audio rendering thread — immune to main-thread GC pauses.
 * Used for STT: captures mic input and posts Float32 samples to the main thread
 * for downsampling and WebSocket transmission to Deepgram.
 *
 * Fallback: ScriptProcessorNode (deprecated but still works on older browsers).
 */
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._active = true;
        this.port.onmessage = function(e) {
            if (e.data === 'stop') this._active = false;
        }.bind(this);
    }

    process(inputs) {
        if (!this._active) return false;
        var input = inputs[0];
        if (input && input.length > 0 && input[0].length > 0) {
            // Copy the Float32 channel data and post to main thread
            // (input buffers are recycled by the audio thread)
            this.port.postMessage(new Float32Array(input[0]));
        }
        return true; // keep processor alive
    }
}

registerProcessor('pcm-processor', PCMProcessor);
