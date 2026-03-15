/**
 * AudioWorklet processor for real-time PCM audio capture.
 * Runs on the audio rendering thread — immune to main-thread GC pauses.
 * Used for STT: captures mic input and posts Float32 samples to the main thread
 * for downsampling and WebSocket transmission to Deepgram.
 *
 * Buffers audio to ~80ms chunks (Deepgram's recommended chunk size for Nova-3)
 * before posting, reducing WebSocket message overhead vs. sending every 128-sample
 * render quantum (~2.7ms at 48kHz).
 *
 * Fallback: ScriptProcessorNode (deprecated but still works on older browsers).
 */
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._active = true;
        // Buffer ~80ms of audio before posting (Deepgram recommendation).
        // sampleRate is a global in AudioWorkletGlobalScope.
        this._bufferSize = Math.round(sampleRate * 0.08);
        this._buffer = new Float32Array(this._bufferSize);
        this._writeIndex = 0;
        this.port.onmessage = function(e) {
            if (e.data === 'stop') {
                // Flush any remaining buffered samples before stopping
                if (this._writeIndex > 0) {
                    this.port.postMessage(
                        new Float32Array(this._buffer.subarray(0, this._writeIndex))
                    );
                    this._writeIndex = 0;
                }
                this._active = false;
            }
        }.bind(this);
    }

    process(inputs) {
        if (!this._active) return false;
        var input = inputs[0];
        if (!input || input.length === 0 || input[0].length === 0) return true;

        var samples = input[0];
        var i = 0;

        while (i < samples.length) {
            var remaining = this._bufferSize - this._writeIndex;
            var toCopy = Math.min(remaining, samples.length - i);
            this._buffer.set(samples.subarray(i, i + toCopy), this._writeIndex);
            this._writeIndex += toCopy;
            i += toCopy;

            if (this._writeIndex >= this._bufferSize) {
                // Post a copy — the buffer is reused
                this.port.postMessage(new Float32Array(this._buffer));
                this._writeIndex = 0;
            }
        }

        return true; // keep processor alive
    }
}

registerProcessor('pcm-processor', PCMProcessor);
