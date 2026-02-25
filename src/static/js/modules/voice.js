/**
 * Habla Hermano - Voice Module
 * Phase 17: Deepgram STT/TTS integration.
 * Mic button for speech-to-text, speaker icon for text-to-speech.
 *
 * TTS uses WebSocket streaming for low-latency playback (~300ms to first audio).
 * Falls back to REST API for browsers without AudioContext support.
 */

// ============================================
// Configuration
// ============================================
// Masculine voices — matches Hermano "big brother" persona
var VOICES = {
    es: 'aura-2-nestor-es',
    de: 'aura-2-julius-de',
    fr: 'aura-2-hector-fr',
};

var STT_SAMPLE_RATE = 16000; // Deepgram expects 16kHz linear16
var TTS_SAMPLE_RATE = 24000; // Deepgram TTS output sample rate
var DEFAULT_TTS_SPEED = 1.0; // 0.5 = half speed, 1.0 = normal, 2.0 = double

var MIC_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />'
    + '<path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />'
    + '<line x1="12" y1="19" x2="12" y2="23" />'
    + '<line x1="8" y1="23" x2="16" y2="23" />'
    + '</svg>';

var STOP_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
    + '</svg>';

var LEVEL_BARS_HTML = '<div class="voice-level-bars" aria-hidden="true">'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '<span class="voice-bar"></span><span class="voice-bar"></span>'
    + '</div>';

var SPINNER_HTML = '<div class="voice-spinner" aria-hidden="true"></div>';

var SPEAKER_ICON = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<path d="M15.54 8.46a5 5 0 0 1 0 7.07" />'
    + '<path d="M19.07 4.93a10 10 0 0 1 0 14.14" />'
    + '</svg>';

var SPEAKER_PLAYING_ICON = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
    + '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />'
    + '<line x1="23" y1="9" x2="17" y2="15" />'
    + '<line x1="17" y1="9" x2="23" y2="15" />'
    + '</svg>';

// ============================================
// Voice Manager
// ============================================

function VoiceManager() {
    this.ws = null;
    this.isRecording = false;
    this.currentAudio = null;
    this.currentBlobUrl = null;
    this.micButton = null;
    this.chatInput = null;
    this.sendButton = null;
    this._errorTimeout = null;
    this._ttsWs = null;
    this._audioCtx = null;
    this._ttsPlaying = false;
    // STT audio capture state
    this._stream = null;
    this._scriptProcessor = null;
    this._sttAudioCtx = null;
    this._finalTranscript = ''; // Accumulated final transcripts
    this._analyser = null;
    this._levelAnimFrame = null;
    this._timerInterval = null;
    this._timerStartTime = 0;
    this._timerElement = null;
    this._micWrapper = null;
    this._processingTimeout = null;
    this._processingIndicator = null;
}

VoiceManager.prototype.init = function() {
    this.micButton = document.getElementById('mic-btn');
    this.chatInput = document.getElementById('message-input');
    this.sendButton = document.getElementById('send-btn');

    if (!this.micButton) return; // Voice not enabled

    // Wrap mic button for floating indicators (timer, processing pill)
    if (this.micButton.parentNode) {
        var wrapper = document.createElement('div');
        wrapper.className = 'flex-shrink-0 relative';
        this.micButton.parentNode.insertBefore(wrapper, this.micButton);
        wrapper.appendChild(this.micButton);
        this._micWrapper = wrapper;
    }

    var self = this;
    this.micButton.addEventListener('click', function() {
        self.toggleRecording();
    });

    // Delegate speaker icon clicks
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.voice-speak-btn');
        if (btn) self.handleSpeakClick(btn);
    });
};

// ============================================
// STT — Microphone Recording
// ============================================

VoiceManager.prototype.toggleRecording = function() {
    if (this.isRecording) {
        this.stopRecording();
    } else {
        this.startRecording();
    }
};

/**
 * Convert Float32 audio samples to Int16 (linear16) for Deepgram.
 */
function floatTo16BitPCM(float32Array) {
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
function downsample(buffer, sourceSampleRate, targetSampleRate) {
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

VoiceManager.prototype.startRecording = function() {
    var self = this;

    // Always use 'multi' for code-switching (learners mix English + target language)
    var language = 'multi';

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        this.showMicError('Voice input is not supported in this browser');
        return;
    }

    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
        this.showMicError('Voice input is not supported in this browser');
        return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        self._stream = stream;

        // Create AudioContext for both PCM capture and level bars
        self._sttAudioCtx = new Ctx();
        var source = self._sttAudioCtx.createMediaStreamSource(stream);

        // Analyser for level bars (doesn't affect audio pipeline)
        self._analyser = self._sttAudioCtx.createAnalyser();
        self._analyser.fftSize = 256;
        self._analyser.smoothingTimeConstant = 0.7;
        source.connect(self._analyser);

        // ScriptProcessor captures raw PCM samples for Deepgram
        // 4096 buffer size balances latency (~93ms at 44.1kHz) vs efficiency
        var processor = self._sttAudioCtx.createScriptProcessor(4096, 1, 1);
        self._scriptProcessor = processor;

        // Set up PCM capture callback immediately (before WS connects).
        // ScriptProcessor may not fire onaudioprocess if set after processing starts.
        // Gate actual sending on WS readiness.
        processor.onaudioprocess = function(e) {
            if (!self.isRecording || !self.ws || self.ws.readyState !== WebSocket.OPEN) return;
            var inputData = e.inputBuffer.getChannelData(0);
            var downsampled = downsample(inputData, self._sttAudioCtx.sampleRate, STT_SAMPLE_RATE);
            var pcmBuffer = floatTo16BitPCM(downsampled);
            self.ws.send(pcmBuffer);
        };

        source.connect(processor);
        // Connect to destination to keep the processor alive (output is silent PCM)
        processor.connect(self._sttAudioCtx.destination);

        var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        self.ws = new WebSocket(
            wsProtocol + '//' + location.host + '/ws/transcribe?language=' + encodeURIComponent(language)
        );

        self.ws.onopen = function() {
            self.isRecording = true;
            self._setSendEnabled(false);
            self.updateMicUI();
            self._startTimer();
            self._startLevelAnimation();
        };

        self._finalTranscript = '';

        self.ws.onmessage = function(event) {
            var data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            if (self.chatInput && data.transcript) {
                if (data.is_final) {
                    // Accumulate finalized text
                    self._finalTranscript += (self._finalTranscript ? ' ' : '') + data.transcript;
                    self.chatInput.value = self._finalTranscript;
                    self.chatInput.classList.remove('voice-interim');
                    // Dismiss processing state early on final transcript
                    if (self._processingTimeout) self._hideProcessing();
                } else {
                    // Show accumulated finals + current interim
                    var prefix = self._finalTranscript ? self._finalTranscript + ' ' : '';
                    self.chatInput.value = prefix + data.transcript;
                    self.chatInput.classList.add('voice-interim');
                }
                // Resize textarea to fit transcript
                if (window.autoResizeInput) window.autoResizeInput();
            }
        };

        self.ws.onerror = function() {
            self.stopRecording();
            self.showMicError('Voice input temporarily unavailable');
        };

        self.ws.onclose = function(event) {
            if (self.isRecording) {
                self.stopRecording();
                // Show user-facing error for unexpected closes
                if (event.code === 1011) {
                    self.showMicError('Voice service error — please try again');
                } else if (event.code === 1008) {
                    self.showMicError(event.reason || 'Invalid request');
                } else if (event.code !== 1000 && event.code !== 1001) {
                    self.showMicError('Voice connection lost');
                }
            }
        };

    }).catch(function(err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            self.showMicError('Microphone access needed for voice input');
        } else {
            self.showMicError('Could not access microphone');
        }
    });
};

VoiceManager.prototype.stopRecording = function() {
    this.isRecording = false;
    this._stopLevelAnimation();
    this._stopTimer();

    // Disconnect ScriptProcessor to stop audio capture
    if (this._scriptProcessor) {
        this._scriptProcessor.onaudioprocess = null;
        try { this._scriptProcessor.disconnect(); } catch (_) {}
        this._scriptProcessor = null;
    }

    // Stop microphone stream tracks
    if (this._stream) {
        this._stream.getTracks().forEach(function(t) { t.stop(); });
        this._stream = null;
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
    }
    if (this.chatInput) this.chatInput.classList.remove('voice-interim');
    this._showProcessing();
};

/**
 * Enable or disable the send button and textarea during recording/processing.
 */
VoiceManager.prototype._setSendEnabled = function(enabled) {
    if (this.sendButton) this.sendButton.disabled = !enabled;
    if (this.chatInput) this.chatInput.readOnly = !enabled;
};

VoiceManager.prototype.updateMicUI = function() {
    if (!this.micButton) return;
    if (this.isRecording) {
        this.micButton.classList.add('voice-recording');
        this.micButton.setAttribute('aria-label', 'Stop recording');
        this.micButton.innerHTML = LEVEL_BARS_HTML;
    } else if (!this._processingTimeout) {
        // Only restore mic icon if not in processing state
        this.micButton.classList.remove('voice-recording');
        this.micButton.setAttribute('aria-label', 'Record voice message');
        this.micButton.innerHTML = MIC_ICON;
    }
};

VoiceManager.prototype.showMicError = function(message) {
    // Use the wrapper (has relative positioning) for mic error tooltips
    var anchor = this._micWrapper || this.micButton;
    this._showTooltipError(anchor, message);
};

/**
 * Show an error tooltip near any element. Reusable for mic and speaker errors.
 * @param {HTMLElement} anchor - Element to attach tooltip near
 * @param {string} message - Error message to display
 */
VoiceManager.prototype._showTooltipError = function(anchor, message) {
    if (!anchor) return;

    // Clear any existing timeout for this anchor
    var timeoutKey = '_errTimeout_' + (anchor.id || 'anon');
    if (this[timeoutKey]) clearTimeout(this[timeoutKey]);

    var parent = anchor.closest('.flex') || anchor.parentElement;
    var existing = parent.querySelector('.voice-error-tooltip');
    if (existing) existing.remove();

    var tooltip = document.createElement('div');
    tooltip.className = 'voice-error-tooltip';
    tooltip.textContent = message;
    tooltip.setAttribute('role', 'alert');

    parent.style.position = 'relative';
    parent.appendChild(tooltip);

    var self = this;
    this[timeoutKey] = setTimeout(function() {
        if (tooltip.parentElement) tooltip.remove();
        self[timeoutKey] = null;
    }, 4000);
};

// ============================================
// STT — Audio Level Animation
// ============================================

VoiceManager.prototype._startLevelAnimation = function() {
    if (!this._analyser) return;
    var self = this;
    var dataArray = new Uint8Array(this._analyser.frequencyBinCount);

    // Respect prefers-reduced-motion: skip animation loop (CSS gives static height)
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    function animate() {
        if (!self.isRecording) return;
        self._analyser.getByteFrequencyData(dataArray);

        var bars = self.micButton ? self.micButton.querySelectorAll('.voice-bar') : [];
        // Voice-frequency bins (~187Hz, ~562Hz, ~1125Hz, ~1875Hz)
        var bins = [1, 3, 6, 10];
        for (var i = 0; i < bars.length; i++) {
            var val = dataArray[bins[i]] || 0;
            var height = Math.max(3, (val / 255) * 18);
            bars[i].style.height = height + 'px';
        }
        self._levelAnimFrame = requestAnimationFrame(animate);
    }
    this._levelAnimFrame = requestAnimationFrame(animate);
};

VoiceManager.prototype._stopLevelAnimation = function() {
    if (this._levelAnimFrame) {
        cancelAnimationFrame(this._levelAnimFrame);
        this._levelAnimFrame = null;
    }
    if (this._sttAudioCtx && this._sttAudioCtx.state !== 'closed') {
        this._sttAudioCtx.close().catch(function() {});
    }
    this._sttAudioCtx = null;
    this._analyser = null;
};

// ============================================
// STT — Recording Timer
// ============================================

VoiceManager.prototype._startTimer = function() {
    if (!this._micWrapper) return;
    var self = this;
    this._timerStartTime = Date.now();

    var timer = document.createElement('div');
    timer.className = 'voice-timer';
    timer.textContent = '0:00';
    timer.setAttribute('aria-hidden', 'true');
    this._timerElement = timer;
    this._micWrapper.appendChild(timer);

    this._timerInterval = setInterval(function() {
        var elapsed = Math.floor((Date.now() - self._timerStartTime) / 1000);
        var min = Math.floor(elapsed / 60);
        var sec = elapsed % 60;
        timer.textContent = min + ':' + (sec < 10 ? '0' : '') + sec;
    }, 1000);
};

VoiceManager.prototype._stopTimer = function() {
    if (this._timerInterval) {
        clearInterval(this._timerInterval);
        this._timerInterval = null;
    }
    if (this._timerElement && this._timerElement.parentElement) {
        this._timerElement.remove();
    }
    this._timerElement = null;
    this._timerStartTime = 0;
};

// ============================================
// STT — Processing State
// ============================================

VoiceManager.prototype._showProcessing = function() {
    if (!this.micButton) return;
    var self = this;

    // Swap button to spinner icon
    this.micButton.classList.remove('voice-recording');
    this.micButton.innerHTML = SPINNER_HTML;
    this.micButton.setAttribute('aria-label', 'Processing speech\u2026');

    // Show floating "Processing..." pill
    if (this._micWrapper) {
        var indicator = document.createElement('div');
        indicator.className = 'voice-processing-indicator';
        indicator.textContent = 'Processing\u2026';
        this._processingIndicator = indicator;
        this._micWrapper.appendChild(indicator);
    }

    // Auto-dismiss after 2 seconds
    this._processingTimeout = setTimeout(function() {
        self._hideProcessing();
    }, 2000);
};

VoiceManager.prototype._hideProcessing = function() {
    if (this._processingTimeout) {
        clearTimeout(this._processingTimeout);
        this._processingTimeout = null;
    }
    if (this._processingIndicator && this._processingIndicator.parentElement) {
        this._processingIndicator.remove();
    }
    this._processingIndicator = null;

    // Safety: ensure timer is fully stopped (guards against race conditions
    // where onmessage triggers _hideProcessing before the 2s timeout)
    this._stopTimer();

    // Restore normal mic button state
    if (this.micButton) {
        this.micButton.classList.remove('voice-recording');
        this.micButton.innerHTML = MIC_ICON;
        this.micButton.setAttribute('aria-label', 'Record voice message');
    }
    this._setSendEnabled(true);
};

// ============================================
// TTS — Text-to-Speech Playback
// ============================================

VoiceManager.prototype.handleSpeakClick = function(btn) {
    var text = btn.dataset.text;
    var language = btn.dataset.language || 'es';
    // Read live speed from picker; fall back to button's data-speed, then default
    var picker = document.getElementById('tts-speed-picker');
    var speed = parseFloat((picker && picker.dataset.ttsSpeed) || btn.dataset.speed) || DEFAULT_TTS_SPEED;

    // Clamp speed to safe range (0.25x to 2.0x)
    speed = Math.max(0.25, Math.min(2.0, speed));

    if (!text) return;

    // If already playing or loading, stop
    if (btn.classList.contains('voice-playing') || btn.classList.contains('voice-loading')) {
        this._stopTTS(btn);
        return;
    }

    // Stop any other playing audio
    this._stopAllTTS();

    var voice = VOICES[language] || VOICES.es;
    btn.classList.add('voice-loading');

    // Use WebSocket streaming TTS (low latency) with AudioContext fallback check
    if (typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined') {
        this._streamTTS(btn, text, voice, speed);
    } else {
        this._restTTS(btn, text, voice, speed);
    }
};

/**
 * Stop current TTS playback and clean up resources.
 */
VoiceManager.prototype._stopTTS = function(btn) {
    this._ttsPlaying = false;

    if (this._ttsWs && this._ttsWs.readyState === WebSocket.OPEN) {
        try { this._ttsWs.send(JSON.stringify({ type: 'close' })); } catch (_) {}
        this._ttsWs.close();
    }
    this._ttsWs = null;

    if (this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
    }
    if (this.currentBlobUrl) {
        URL.revokeObjectURL(this.currentBlobUrl);
        this.currentBlobUrl = null;
    }
    if (this._audioCtx && this._audioCtx.state !== 'closed') {
        this._audioCtx.close().catch(function() {});
        this._audioCtx = null;
    }

    btn.classList.remove('voice-playing', 'voice-loading');
    btn.innerHTML = SPEAKER_ICON;
};

/**
 * Stop all currently playing TTS buttons.
 */
VoiceManager.prototype._stopAllTTS = function() {
    var self = this;
    // Stop buttons in loading or playing state
    var activeBtns = document.querySelectorAll('.voice-speak-btn.voice-playing, .voice-speak-btn.voice-loading');
    activeBtns.forEach(function(b) { self._stopTTS(b); });
};

/**
 * WebSocket streaming TTS — sends text to /ws/speak, receives PCM audio
 * chunks, and plays them via AudioContext for near-instant playback.
 * @param {number} speed - Playback rate (0.25 to 2.0, default 1.0)
 */
VoiceManager.prototype._streamTTS = function(btn, text, voice, speed) {
    var self = this;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    var audioCtx = new Ctx({ sampleRate: TTS_SAMPLE_RATE });
    this._audioCtx = audioCtx;
    this._ttsPlaying = true;

    // Queue of AudioBuffers scheduled for playback
    var nextStartTime = 0;
    var started = false;
    var totalScheduled = 0;
    var lastScheduledBuffer = null;
    var wsDone = false; // true once WS closes normally (all audio sent)

    var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(
        wsProtocol + '//' + location.host + '/ws/speak?voice=' + encodeURIComponent(voice)
    );
    ws.binaryType = 'arraybuffer';
    this._ttsWs = ws;

    function cleanup() {
        self._ttsPlaying = false;
        if (self._ttsWs === ws) self._ttsWs = null;
        btn.classList.remove('voice-playing', 'voice-loading');
        btn.innerHTML = SPEAKER_ICON;
        if (audioCtx.state !== 'closed') {
            audioCtx.close().catch(function() {});
        }
        // Only clear instance ref if it still points to this session's context
        if (self._audioCtx === audioCtx) self._audioCtx = null;
    }

    ws.onopen = function() {
        // Send text and flush for immediate audio generation
        ws.send(JSON.stringify({ text: text }));
    };

    ws.onmessage = function(event) {
        if (!self._ttsPlaying) return;

        if (event.data instanceof ArrayBuffer) {
            // Binary audio chunk — linear16 PCM, 24kHz, mono
            var pcmData = new Int16Array(event.data);
            var floatData = new Float32Array(pcmData.length);
            for (var i = 0; i < pcmData.length; i++) {
                floatData[i] = pcmData[i] / 32768.0;
            }

            var audioBuffer = audioCtx.createBuffer(1, floatData.length, TTS_SAMPLE_RATE);
            audioBuffer.getChannelData(0).set(floatData);

            var source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.playbackRate.value = speed;
            source.connect(audioCtx.destination);

            // Schedule seamlessly after previous chunk
            // Duration is adjusted by speed (faster = shorter playback)
            var startAt = Math.max(audioCtx.currentTime, nextStartTime);
            source.start(startAt);
            nextStartTime = startAt + (audioBuffer.duration / speed);
            totalScheduled++;
            lastScheduledBuffer = source;

            // Show playing state after first chunk
            if (!started) {
                started = true;
                btn.classList.remove('voice-loading');
                btn.classList.add('voice-playing');
                btn.innerHTML = SPEAKER_PLAYING_ICON;
            }

            // Detect end of playback on the last scheduled buffer
            source.onended = function() {
                totalScheduled--;
                if (totalScheduled <= 0 && wsDone) {
                    cleanup();
                }
            };
        } else {
            // JSON metadata or control message — audio generation complete
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === 'Flushed' || msg.type === 'metadata') {
                    // All audio for this text has been sent
                    // Playback continues until all buffers finish
                }
            } catch (_) {}
        }
    };

    ws.onerror = function() {
        cleanup();
        self._showTooltipError(btn, 'Could not play audio');
    };

    ws.onclose = function(event) {
        // If no audio was ever received, show an error
        if (!started && event.code !== 1000) {
            cleanup();
            if (event.code === 1011) {
                self._showTooltipError(btn, 'Speech service error — try again');
            } else if (event.code === 1008) {
                self._showTooltipError(btn, event.reason || 'Invalid voice request');
            } else {
                self._showTooltipError(btn, 'Could not play audio');
            }
            return;
        }
        // Mark WS as done; if all buffers already finished, clean up now
        wsDone = true;
        if (totalScheduled <= 0) {
            cleanup();
        }
        // Otherwise, the last source.onended will trigger cleanup
    };
};

/**
 * REST fallback TTS — buffers entire response then plays.
 * Used when AudioContext is not available.
 * @param {number} speed - Playback rate (0.25 to 2.0, default 1.0)
 */
VoiceManager.prototype._restTTS = function(btn, text, voice, speed) {
    var self = this;

    fetch('/api/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, voice: voice }),
    }).then(function(response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.blob();
    }).then(function(audioBlob) {
        var audioUrl = URL.createObjectURL(audioBlob);
        var audio = new Audio(audioUrl);

        audio.playbackRate = speed;
        self.currentAudio = audio;
        self.currentBlobUrl = audioUrl;
        btn.classList.remove('voice-loading');
        btn.classList.add('voice-playing');
        btn.innerHTML = SPEAKER_PLAYING_ICON;

        function done() {
            URL.revokeObjectURL(audioUrl);
            self.currentBlobUrl = null;
            btn.classList.remove('voice-playing');
            btn.innerHTML = SPEAKER_ICON;
            self.currentAudio = null;
        }

        audio.onended = done;
        audio.onerror = function() {
            done();
            self._showTooltipError(btn, 'Audio playback failed');
        };
        audio.play().catch(function() {
            btn.classList.remove('voice-loading');
            done();
            self._showTooltipError(btn, 'Could not play audio');
        });
    }).catch(function(err) {
        btn.classList.remove('voice-loading', 'voice-playing');
        btn.innerHTML = SPEAKER_ICON;
        var msg = (err && err.message && err.message.indexOf('503') !== -1)
            ? 'Speech service not configured'
            : 'Could not play audio';
        self._showTooltipError(btn, msg);
    });
};

// ============================================
// Initialization
// ============================================
function init() {
    var manager = new VoiceManager();
    manager.init();
    window.voiceManager = manager;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
