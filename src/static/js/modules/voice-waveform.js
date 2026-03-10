/**
 * Habla Hermano — Voice Waveform Player
 * Phase 22: Wavesurfer.js wrapper for AI message TTS waveforms.
 *
 * Creates/destroys waveform player instances per AI message.
 * Each player: play/pause button + wavesurfer waveform + speed chip + time display.
 */
import WaveSurfer from 'https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js';

export var SPEED_OPTIONS = [0.75, 1, 1.25, 1.5];

var PLAY_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
var PAUSE_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

/**
 * Create a waveform player inside the given container.
 * @param {HTMLElement} container - the .voice-waveform-container element
 * @param {Object} opts - { language, text }
 * @returns {Object} player handle with { ws, play, pause, destroy, loadBlob, container }
 */
export function createWaveformPlayer(container, opts) {
    var wrapper = document.createElement('div');
    wrapper.className = 'voice-wf-player';

    // Play/pause button
    var playBtn = document.createElement('button');
    playBtn.type = 'button';
    playBtn.className = 'voice-wf-play';
    playBtn.innerHTML = PLAY_ICON;
    playBtn.setAttribute('aria-label', 'Play audio');

    // Waveform div (wavesurfer mounts here)
    var waveDiv = document.createElement('div');
    waveDiv.className = 'voice-wf-wave';

    // Speed chip
    var speedIdx = 1; // default 1x (index into SPEED_OPTIONS)
    var speedChip = document.createElement('button');
    speedChip.type = 'button';
    speedChip.className = 'voice-wf-speed';
    speedChip.textContent = '1\u00d7';
    speedChip.setAttribute('aria-label', 'Playback speed');

    // Time display
    var timeEl = document.createElement('div');
    timeEl.className = 'voice-wf-time';
    timeEl.textContent = '0:00';

    var topRow = document.createElement('div');
    topRow.className = 'voice-wf-top';
    topRow.appendChild(playBtn);
    topRow.appendChild(waveDiv);
    topRow.appendChild(speedChip);

    wrapper.appendChild(topRow);
    wrapper.appendChild(timeEl);
    container.appendChild(wrapper);

    // CSS variables for theme
    var accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#60a5fa';
    var subtle = getComputedStyle(document.documentElement).getPropertyValue('--text-subtle').trim() || '#9ca3af';

    // Create wavesurfer instance
    var ws = WaveSurfer.create({
        container: waveDiv,
        waveColor: subtle + '66',
        progressColor: accent,
        cursorWidth: 0,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 32,
        normalize: true,
        interact: true,
    });

    function formatTime(sec) {
        var m = Math.floor(sec / 60);
        var s = Math.floor(sec % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    ws.on('ready', function() {
        timeEl.textContent = formatTime(ws.getDuration());
    });
    ws.on('audioprocess', function() {
        timeEl.textContent = formatTime(ws.getCurrentTime()) + ' / ' + formatTime(ws.getDuration());
    });
    ws.on('finish', function() {
        playBtn.innerHTML = PLAY_ICON;
        playBtn.setAttribute('aria-label', 'Play audio');
        timeEl.textContent = formatTime(ws.getDuration());
    });

    playBtn.addEventListener('click', function() {
        if (ws.isPlaying()) {
            ws.pause();
            playBtn.innerHTML = PLAY_ICON;
            playBtn.setAttribute('aria-label', 'Play audio');
        } else {
            ws.play();
            playBtn.innerHTML = PAUSE_ICON;
            playBtn.setAttribute('aria-label', 'Pause audio');
        }
    });

    speedChip.addEventListener('click', function() {
        speedIdx = (speedIdx + 1) % SPEED_OPTIONS.length;
        var speed = SPEED_OPTIONS[speedIdx];
        speedChip.textContent = speed + '\u00d7';
        ws.setPlaybackRate(speed);
    });

    var handle = {
        ws: ws,
        container: container,
        opts: opts,
        playBtn: playBtn,
        speedChip: speedChip,
        play: function() { ws.play(); playBtn.innerHTML = PAUSE_ICON; },
        pause: function() { ws.pause(); playBtn.innerHTML = PLAY_ICON; },
        loadBlob: function(blob) { ws.loadBlob(blob); },
        destroy: function() { ws.destroy(); },
    };

    return handle;
}

/**
 * Destroy a waveform player and clean up.
 */
export function destroyWaveformPlayer(handle) {
    if (!handle) return;
    if (handle.ws) handle.ws.destroy();
}
