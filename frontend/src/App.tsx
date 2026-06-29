/**
 * Main application layout — single column.
 *
 * Top to bottom: Header → Voice Controls Card → Text Area → Action Bar.
 * Per mockup v2 — T25 UI Layout Rework.
 */

import { useState, useCallback, useEffect } from "react";

import { Header } from "./components/Header";
import { VoiceSelector } from "./components/VoiceSelector";
import { TextEditor } from "./components/TextEditor";
import { ActionBar } from "./components/ActionBar";
import { Toast } from "./components/Toast";
import { SettingsModal } from "./components/SettingsModal";
import { useApi } from "./hooks/useApi";
import { useToast } from "./hooks/useToast";
import { useI18n } from "./hooks/useI18n";
import { useTheme } from "./hooks/useTheme";

function App() {
  const api = useApi();
  const { toasts, addToast, removeToast } = useToast();
  const { t, language, setLanguage } = useI18n(api);
  const { toggleTheme, isDark } = useTheme();

  // Lifted state
  const [selectedVoice, setSelectedVoice] = useState("zh-TW-HsiaoChenNeural");
  const [text, setText] = useState("");
  const [speed, setSpeed] = useState(1.0);
  const [pitch, setPitch] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [outputDir, setOutputDir] = useState("");

  // Check for updates on mount (non-blocking, fail-silent)
  // Ref: #170 — respect auto_check_update config
  useEffect(() => {
    if (!api.ready) return;
    let cancelled = false;

    async function checkForUpdate() {
      try {
        // Only check if auto_check_update is not explicitly false
        const config = await api.getConfig("auto_check_update");
        if (config && config.value === false) return;

        const update = await api.checkUpdate();
        if (!cancelled && update) {
          addToast(
            t("update_available").replace("{version}", update.latest),
            "info",
            [
              {
                label: t("update_download"),
                onClick: () => window.open(update.url, "_blank"),
              },
              {
                label: t("update_skip"),
                onClick: async () => {
                  await api.setConfig("skip_version", update.latest);
                },
              },
            ]
          );
        }
      } catch {
        // Fail silently — no error toast if offline
      }
    }

    checkForUpdate();
    return () => { cancelled = true; };
  }, [api, api.ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load output directory on mount
  useEffect(() => {
    if (!api.ready) return;

    async function loadOutputDir() {
      try {
        const result = await api.getOutputDir();
        if (result.output_dir) setOutputDir(result.output_dir);
      } catch {
        // Fail silently — default will be shown
      }
    }

    loadOutputDir();
  }, [api, api.ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Convert speed multiplier to API percentage: (multiplier - 1.0) × 100
  const speedToRate = useCallback((multiplier: number): number => {
    return Math.round((multiplier - 1.0) * 100);
  }, []);

  // Ref: #52 — Preview uses previewTTS() (temp file, not Desktop)
  // Ref: #74 — setSpeaking(false) is handled by 'audioPlaybackFinished'
  // event (fired by Python notify_playback_finished), not here.
  // evaluate_js() returns immediately, so we cannot rely on
  // api.playAudio() awaiting actual playback completion.
  const handleSpeak = useCallback(async () => {
    if (!text.trim() || !api.ready) return;

    setSpeaking(true);
    try {
      const rate = speedToRate(speed);
      const result = await api.previewTTS(text, selectedVoice, rate, pitch);

      if (result.error) {
        addToast(result.error, "error");
        setSpeaking(false);
      } else if (result.path) {
        // Fire-and-forget: speaking stays true until audioPlaybackFinished
        api.playAudio(result.path);
      } else {
        setSpeaking(false);
      }
    } catch (err) {
      addToast(err instanceof Error ? err.message : "TTS generation failed", "error");
      setSpeaking(false);
    }
  }, [text, selectedVoice, speed, pitch, api, addToast, speedToRate]);

  const handleStop = useCallback(async () => {
    try {
      await api.stopAudio();
    } catch {
      // Fail silently
    }
    setSpeaking(false);
  }, [api]);

  // Ref: #74 — Listen for Python-dispatched playback completion event.
  // When audio finishes naturally (onended), the JS bridge calls
  // notifyPythonFinished() → Python dispatches 'audioPlaybackFinished'
  // window event → React resets speaking state.
  useEffect(() => {
    const onFinished = () => setSpeaking(false);
    window.addEventListener("audioPlaybackFinished", onFinished);
    return () => window.removeEventListener("audioPlaybackFinished", onFinished);
  }, []);

  // Ref: #51 — Toggle preview/stop from a single button
  const handleTogglePreview = useCallback(() => {
    if (speaking) {
      handleStop();
    } else {
      handleSpeak();
    }
  }, [speaking, handleStop, handleSpeak]);

  const handleSave = useCallback(async () => {
    if (!text.trim() || !api.ready) return;

    setSaving(true);
    try {
      const rate = speedToRate(speed);
      const result = await api.generateTTS(text, selectedVoice, rate, pitch);

      if (result.error) {
        addToast(result.error, "error");
      } else if (result.path) {
        addToast(`Saved to ${result.path}`, "success");
      }
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Save failed", "error");
    } finally {
      setSaving(false);
    }
  }, [text, selectedVoice, speed, pitch, api, addToast, speedToRate]);

  const handleSelectOutputDir = useCallback(async () => {
    if (!api.ready) return;
    try {
      const result = await api.selectOutputDir();
      if (result.output_dir) {
        setOutputDir(result.output_dir);
      }
    } catch {
      // Fail silently
    }
  }, [api]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--background)",
      }}
    >
      {/* Header — full width */}
      <Header onSettingsClick={() => setSettingsOpen(true)} onThemeToggle={toggleTheme} isDark={isDark} t={t} />

      {/* Content area — single column */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 16,
          padding: "20px 28px",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Voice Controls Card */}
        <VoiceSelector
          api={api}
          selectedVoice={selectedVoice}
          onVoiceChange={setSelectedVoice}
          speed={speed}
          onSpeedChange={setSpeed}
          pitch={pitch}
          onPitchChange={setPitch}
          t={t}
        />

        {/* Text Area — fills remaining space */}
        <div
          style={{
            flex: 1,
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: 14,
            display: "flex",
            flexDirection: "column",
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            overflow: "hidden",
            minHeight: 0,
          }}
        >
          <TextEditor text={text} onTextChange={setText} t={t} />
        </div>

        {/* Action Bar — 2 buttons (Ref: #51) */}
        <ActionBar
          onTogglePreview={handleTogglePreview}
          onSave={handleSave}
          speaking={speaking}
          saving={saving}
          disabled={!text.trim() || !api.ready}
          t={t}
          outputDir={outputDir}
          onSelectOutputDir={handleSelectOutputDir}
        />
      </div>

      {/* Settings modal */}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        api={api}
        t={t}
        language={language}
        onLanguageChange={setLanguage}
      />

      {/* Toast system */}
      <Toast toasts={toasts} onRemove={removeToast} />
    </div>
  );
}

export default App;
