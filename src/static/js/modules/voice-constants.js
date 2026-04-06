/**
 * Habla Hermano - Voice Constants & Audio Utilities
 * Phase 21: Extracted from voice.js for modularity.
 */

// Masculine voices -- matches Hermano "big brother" persona
export var VOICES = {
    es: 'aura-2-nestor-es',
    de: 'aura-2-julius-de',
    fr: 'aura-2-hector-fr',
};

export var STT_SAMPLE_RATE = 16000; // Deepgram expects 16kHz linear16
export var TTS_SAMPLE_RATE = 24000; // Deepgram TTS output sample rate
export var TTS_WS_SAMPLE_RATE = 24000; // Deepgram WS TTS linear16 sample rate
export var DEFAULT_TTS_SPEED = 1.0; // 0.5 = half speed, 1.0 = normal, 2.0 = double
export var MAX_TTS_CHUNK_LENGTH = 2000; // Must match server MAX_TTS_TEXT_LENGTH
export var WS_SPEAK_PATH = '/ws/speak'; // WebSocket TTS endpoint

export var MIC_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />'
    + '<line x1="12" y1="19" x2="12" y2="23" />'
    + '<line x1="8" y1="23" x2="16" y2="23" />'
    + '</svg>';

export var STOP_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
    + '</svg>';

export var LEVEL_BARS_HTML = '<div class="voice-level-bars" aria-hidden="true">'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '</div>';

export var SPINNER_HTML = '<div class="voice-spinner" aria-hidden="true"></div>';

export var SEND_ICON = '<svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<line x1="22" y1="2" x2="11" y2="13"></line>'
    + '<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>'
    + '</svg>';

export var STOP_SQUARE_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="none">'
    + '<rect x="6" y="6" width="12" height="12" rx="2"></rect>'
    + '</svg>';

export var CANCEL_X_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<line x1="18" y1="6" x2="6" y2="18"></line>'
    + '<line x1="6" y1="6" x2="18" y2="18"></line>'
    + '</svg>';

export var WF_PLAY_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
export var WF_STOP_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>';

export var WF_SPEED_OPTIONS = [0.75, 1, 1.25, 1.5];

// ============================================
// Audio Utility Functions
// ============================================

/**
 * Convert Float32 audio samples to Int16 (linear16) for Deepgram.
 */
export function floatTo16BitPCM(float32Array) {
    var buffer = new ArrayBuffer(float32Array.length * 2);
    var view = new DataView(buffer);
    for (var i = 0; i < float32Array.length; i++) {
        var s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
}

/**
 * Downsample audio from source sample rate to target sample rate.
 */
export function downsample(buffer, sourceSampleRate, targetSampleRate) {
    if (sourceSampleRate === targetSampleRate) return buffer;
    var ratio = sourceSampleRate / targetSampleRate;
    var newLength = Math.round(buffer.length / ratio);
    var result = new Float32Array(newLength);
    for (var i = 0; i < newLength; i++) {
        var index = Math.round(i * ratio);
        result[i] = buffer[index];
    }
    return result;
}

/**
 * Split text into chunks that fit within the TTS character limit.
 * Splits at sentence boundaries (.!?) first, then at word boundaries
 * as a fallback for very long sentences.
 *
 * @param {string} text - Text to chunk
 * @param {number} [maxLen] - Maximum characters per chunk (default: MAX_TTS_CHUNK_LENGTH)
 * @returns {string[]} Array of text chunks, each <= maxLen characters
 */
export function chunkTextForTTS(text, maxLen) {
    if (!maxLen) maxLen = MAX_TTS_CHUNK_LENGTH;
    if (!text || text.length <= maxLen) return [text];

    // Split into sentences (keep the delimiter attached to the sentence)
    var sentences = text.match(/[^.!?]+[.!?]+[\s]*/g);
    // If no sentence delimiters found, treat the whole text as one "sentence"
    if (!sentences) sentences = [text];

    // Handle any trailing text without sentence-ending punctuation
    var joined = sentences.join('');
    if (joined.length < text.length) {
        sentences.push(text.slice(joined.length));
    }

    var chunks = [];
    var current = '';

    for (var i = 0; i < sentences.length; i++) {
        var sentence = sentences[i];

        // If a single sentence exceeds maxLen, split it at word boundaries
        if (sentence.length > maxLen) {
            // Flush current buffer first
            if (current) {
                chunks.push(current.trim());
                current = '';
            }
            var words = sentence.split(/(\s+)/);
            var wordBuf = '';
            for (var j = 0; j < words.length; j++) {
                if ((wordBuf + words[j]).length > maxLen && wordBuf) {
                    chunks.push(wordBuf.trim());
                    wordBuf = '';
                }
                wordBuf += words[j];
            }
            if (wordBuf.trim()) current = wordBuf;
            continue;
        }

        if ((current + sentence).length > maxLen) {
            if (current) chunks.push(current.trim());
            current = sentence;
        } else {
            current += sentence;
        }
    }

    if (current.trim()) chunks.push(current.trim());

    return chunks;
}

/**
 * Wrap raw linear16 PCM data in a WAV container for browser playback.
 * Creates a minimal 44-byte WAV header + raw PCM payload.
 *
 * @param {ArrayBuffer[]} pcmBuffers - Array of raw PCM ArrayBuffers (16-bit LE mono)
 * @param {number} sampleRate - Sample rate in Hz (e.g. 24000)
 * @returns {Blob} WAV audio blob playable by <audio> element
 */
export function createWavBlob(pcmBuffers, sampleRate) {
    var dataLength = 0;
    for (var i = 0; i < pcmBuffers.length; i++) {
        dataLength += pcmBuffers[i].byteLength;
    }

    var numChannels = 1;
    var bitsPerSample = 16;
    var byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    var blockAlign = numChannels * (bitsPerSample / 8);

    // 44-byte WAV header
    var header = new ArrayBuffer(44);
    var view = new DataView(header);

    // RIFF chunk descriptor
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    writeString(view, 8, 'WAVE');

    // fmt sub-chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);

    // data sub-chunk
    writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    var parts = [header];
    for (var j = 0; j < pcmBuffers.length; j++) {
        parts.push(pcmBuffers[j]);
    }
    return new Blob(parts, { type: 'audio/wav' });
}

function writeString(view, offset, str) {
    for (var i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}
