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
export var DEFAULT_TTS_SPEED = 1.0; // 0.5 = half speed, 1.0 = normal, 2.0 = double

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

export var SPEAKER_ICON = '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<path d="M15.54 8.46a5 5 0 0 1 0 7.07" />'
    + '<path d="M19.07 4.93a10 10 0 0 1 0 14.14" />'
    + '</svg>';

export var SPEAKER_PLAYING_ICON = '<svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<line x1="23" y1="9" x2="17" y2="15" />'
    + '<line x1="17" y1="9" x2="23" y2="15" />'
    + '</svg>';

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
