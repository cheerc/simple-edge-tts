/**
 * Audio Player Bridge — JS-side module for HTML5 <audio> playback.
 *
 * Communicates with Python AudioPlayer via pywebview's JS↔Python bridge.
 * The Python side calls playAudio()/stopAudio() via evaluate_js();
 * this module calls back to Python via pywebview.api.notify_playback_finished().
 *
 * Integration with React (T18):
 *   Import this module and use the exported functions, or wrap in a React hook:
 *     const { playAudio, stopAudio, isPlaying } = useAudioPlayer();
 *
 * Standalone usage (pre-React, plain HTML):
 *   <script src="audio_player_bridge.js"></script>
 *   Then Python calls: window.audioPlayerBridge.playAudio("/path/to/file.mp3")
 */

(function () {
  "use strict";

  /** @type {HTMLAudioElement|null} */
  let audioElement = null;

  /** @type {string|null} */
  let currentSrc = null;

  /**
   * Convert an absolute file path to a URL servable by pywebview's HTTP server.
   *
   * PyWebView's built-in HTTP server can serve local files. The exact URL
   * mapping depends on the server configuration:
   *
   * Option 1: If pywebview serves from a root that includes the file path,
   *           use a relative path from the served directory.
   * Option 2: Use a Python-side API endpoint that streams the file bytes.
   * Option 3: Use pywebview's window.expose() to read file as base64.
   *
   * For now, we use a simple approach: Python sends the absolute path,
   * and we use it with pywebview's API to get the file content.
   *
   * @param {string} filePath - Absolute path to the audio file
   * @returns {Promise<string>} URL suitable for HTMLAudioElement.src
   */
  async function filePathToUrl(filePath) {
    // When pywebview runs with http_server=True and serves from a known root,
    // we can construct a relative URL. For cross-platform compatibility,
    // we expose a Python API endpoint that serves the audio file.
    // The Python backend should expose: pywebview.api.get_audio_url(path)
    // which returns an http://localhost:PORT/... URL.
    //
    // Fallback: use file:// protocol (may not work in all WebView engines)
    if (
      typeof window.pywebview !== "undefined" &&
      typeof window.pywebview.api !== "undefined" &&
      typeof window.pywebview.api.get_audio_url === "function"
    ) {
      // pywebview API calls return Promises — must await
      return await window.pywebview.api.get_audio_url(filePath);
    }
    // Fallback for development/testing: try file:// protocol
    return "file:///" + filePath.replace(/\\/g, "/").replace(/^\//, "");
  }

  /**
   * Create or reuse the HTMLAudioElement.
   * @returns {HTMLAudioElement}
   */
  function getAudioElement() {
    if (!audioElement) {
      audioElement = new Audio();
    }
    return audioElement;
  }

  /**
   * Notify the Python backend that playback has finished.
   */
  function notifyPythonFinished() {
    if (
      typeof window.pywebview !== "undefined" &&
      typeof window.pywebview.api !== "undefined" &&
      typeof window.pywebview.api.notify_playback_finished === "function"
    ) {
      window.pywebview.api.notify_playback_finished();
    }
  }

  /**
   * Play an audio file.
   * @param {string} filePath - Absolute path to the audio file
   */
  async function playAudio(filePath) {
    var audio = getAudioElement();

    // Stop current playback if any
    if (!audio.paused) {
      audio.pause();
      audio.currentTime = 0;
    }

    var url = await filePathToUrl(filePath);
    currentSrc = filePath;
    audio.src = url;

    // Return a Promise that resolves when playback ends.
    // This lets Python's evaluate_js() (and thus the React frontend)
    // wait until audio finishes before setting speaking=false.
    // Ref: #63, #74 — proper playback lifecycle.
    return new Promise(function (resolve, reject) {
      audio.onended = function () {
        currentSrc = null;
        notifyPythonFinished();
        resolve();
      };
      audio.onerror = function (e) {
        console.error("Audio playback error:", e);
        currentSrc = null;
        notifyPythonFinished();
        reject(e);
      };
      audio.play().catch(function (err) {
        currentSrc = null;
        notifyPythonFinished();
        reject(err);
      });
    });
  }

  /**
   * Stop current audio playback.
   */
  function stopAudio() {
    if (audioElement && !audioElement.paused) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }
    currentSrc = null;
  }

  /**
   * Get current playback state.
   * @returns {{ playing: boolean, src: string|null }}
   */
  function getState() {
    return {
      playing: audioElement ? !audioElement.paused : false,
      src: currentSrc,
    };
  }

  /**
   * Set volume (0.0 to 1.0).
   * @param {number} level
   */
  function setVolume(level) {
    var audio = getAudioElement();
    audio.volume = Math.max(0, Math.min(1, level));
  }

  // Expose as global bridge object for Python evaluate_js() calls
  window.audioPlayerBridge = {
    playAudio: playAudio,
    stopAudio: stopAudio,
    getState: getState,
    setVolume: setVolume,
  };
})();
