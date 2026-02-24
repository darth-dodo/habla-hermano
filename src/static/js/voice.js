/**
 * Habla Hermano - Voice Module
 * Phase 17: Deepgram STT/TTS integration.
 * Mic button for speech-to-text, speaker icon for text-to-speech.
 */

(function() {
    'use strict';

    // ============================================
    // Configuration
    // ============================================
    var VOICES = {
        es: 'aura-2-celeste-es',
        de: 'aura-2-elara-de',
        fr: 'aura-2-agathe-fr',
    };

    var CHUNK_INTERVAL = 250; // ms between audio chunks

    var MIC_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
        + '<path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />'
        + '<path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />'
        + '<line x1="12" y1="19" x2="12" y2="23" />'
        + '<line x1="8" y1="23" x2="16" y2="23" />'
        + '</svg>';

    var STOP_ICON = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">'
        + '<rect x="6" y="6" width="12" height="12" rx="2" stroke-linecap="round" stroke-linejoin="round" />'
        + '</svg>';

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
        this.mediaRecorder = null;
        this.ws = null;
        this.isRecording = false;
        this.currentAudio = null;
        this.currentBlobUrl = null;
        this.micButton = null;
        this.chatInput = null;
        this._errorTimeout = null;
    }

    VoiceManager.prototype.init = function() {
        this.micButton = document.getElementById('mic-btn');
        this.chatInput = document.getElementById('message-input');

        if (!this.micButton) return; // Voice not enabled

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

    VoiceManager.prototype.toggleRecording = function() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    };

    VoiceManager.prototype.startRecording = function() {
        var self = this;

        // Get language from the hidden form input
        var languageInput = document.querySelector('input[name="language"]');
        var language = languageInput ? languageInput.value : 'es';

        // Check for MediaRecorder support
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showMicError('Voice input is not supported in this browser');
            return;
        }

        navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
            // Detect supported mime type
            var mimeType = 'audio/webm;codecs=opus';
            if (typeof MediaRecorder.isTypeSupported === 'function' && !MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/mp4';
                if (typeof MediaRecorder.isTypeSupported === 'function' && !MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = ''; // Let browser choose default
                }
            }

            var recorderOptions = mimeType ? { mimeType: mimeType } : {};
            self.mediaRecorder = new MediaRecorder(stream, recorderOptions);

            // Open WebSocket
            var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            self.ws = new WebSocket(
                wsProtocol + '//' + location.host + '/ws/transcribe?language=' + encodeURIComponent(language)
            );

            self.ws.onopen = function() {
                self.mediaRecorder.ondataavailable = function(event) {
                    if (event.data.size > 0 && self.ws && self.ws.readyState === WebSocket.OPEN) {
                        self.ws.send(event.data);
                    }
                };
                self.mediaRecorder.start(CHUNK_INTERVAL);
                self.isRecording = true;
                self.updateMicUI();
            };

            self.ws.onmessage = function(event) {
                var data;
                try {
                    data = JSON.parse(event.data);
                } catch (e) {
                    return;
                }
                if (self.chatInput && data.transcript) {
                    self.chatInput.value = data.transcript;
                    if (data.is_final) {
                        self.chatInput.classList.remove('voice-interim');
                    } else {
                        self.chatInput.classList.add('voice-interim');
                    }
                }
            };

            self.ws.onerror = function() {
                self.stopRecording();
                self.showMicError('Voice input temporarily unavailable');
            };

            self.ws.onclose = function() {
                if (self.isRecording) {
                    self.stopRecording();
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
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        // Stop all tracks to release mic
        if (this.mediaRecorder && this.mediaRecorder.stream) {
            this.mediaRecorder.stream.getTracks().forEach(function(t) { t.stop(); });
        }
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.close();
        }
        this.isRecording = false;
        if (this.chatInput) {
            this.chatInput.classList.remove('voice-interim');
        }
        this.updateMicUI();
    };

    VoiceManager.prototype.updateMicUI = function() {
        if (!this.micButton) return;
        if (this.isRecording) {
            this.micButton.classList.add('voice-recording');
            this.micButton.setAttribute('aria-label', 'Stop recording');
            this.micButton.innerHTML = STOP_ICON;
        } else {
            this.micButton.classList.remove('voice-recording');
            this.micButton.setAttribute('aria-label', 'Record voice message');
            this.micButton.innerHTML = MIC_ICON;
        }
    };

    VoiceManager.prototype.showMicError = function(message) {
        if (!this.micButton) return;

        // Clear any existing error tooltip
        if (this._errorTimeout) {
            clearTimeout(this._errorTimeout);
        }

        var existing = this.micButton.parentElement.querySelector('.voice-error-tooltip');
        if (existing) existing.remove();

        // Create tooltip
        var tooltip = document.createElement('div');
        tooltip.className = 'voice-error-tooltip';
        tooltip.textContent = message;
        tooltip.setAttribute('role', 'alert');

        // Position relative to mic button
        this.micButton.parentElement.style.position = 'relative';
        this.micButton.parentElement.appendChild(tooltip);

        var self = this;
        this._errorTimeout = setTimeout(function() {
            if (tooltip.parentElement) {
                tooltip.remove();
            }
            self._errorTimeout = null;
        }, 4000);
    };

    VoiceManager.prototype.handleSpeakClick = function(btn) {
        var text = btn.dataset.text;
        var language = btn.dataset.language || 'es';
        var self = this;

        if (!text) return;

        // If already playing this button's audio, pause/stop it
        if (btn.classList.contains('voice-playing')) {
            if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
            }
            if (this.currentBlobUrl) {
                URL.revokeObjectURL(this.currentBlobUrl);
                this.currentBlobUrl = null;
            }
            btn.classList.remove('voice-playing');
            btn.innerHTML = SPEAKER_ICON;
            return;
        }

        // Stop any other currently playing audio
        var playingBtns = document.querySelectorAll('.voice-speak-btn.voice-playing');
        playingBtns.forEach(function(b) {
            b.classList.remove('voice-playing');
            b.innerHTML = SPEAKER_ICON;
        });
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        if (this.currentBlobUrl) {
            URL.revokeObjectURL(this.currentBlobUrl);
            this.currentBlobUrl = null;
        }

        var voice = VOICES[language] || VOICES.es;

        btn.classList.add('voice-loading');

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

            self.currentAudio = audio;
            self.currentBlobUrl = audioUrl;
            btn.classList.remove('voice-loading');
            btn.classList.add('voice-playing');
            btn.innerHTML = SPEAKER_PLAYING_ICON;

            audio.onended = function() {
                URL.revokeObjectURL(audioUrl);
                self.currentBlobUrl = null;
                btn.classList.remove('voice-playing');
                btn.innerHTML = SPEAKER_ICON;
                self.currentAudio = null;
            };

            audio.onerror = function() {
                URL.revokeObjectURL(audioUrl);
                self.currentBlobUrl = null;
                btn.classList.remove('voice-playing');
                btn.innerHTML = SPEAKER_ICON;
                self.currentAudio = null;
            };

            audio.play().catch(function() {
                URL.revokeObjectURL(audioUrl);
                self.currentBlobUrl = null;
                btn.classList.remove('voice-playing', 'voice-loading');
                btn.innerHTML = SPEAKER_ICON;
                self.currentAudio = null;
            });
        }).catch(function() {
            btn.classList.remove('voice-loading', 'voice-playing');
            btn.innerHTML = SPEAKER_ICON;
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

})();
