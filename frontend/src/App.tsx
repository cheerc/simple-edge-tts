/**
 * Main application layout — 2-column wide layout.
 *
 * Left panel (40%): VoiceSelector
 * Right panel (60%): TextEditor + ActionBar
 * Header spans full width, Toast system at root.
 *
 * Per design spec §2.1 layout.
 * Ref: T18 Plan §9 — App Layout
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

  // Check for updates on mount (non-blocking, fail-silent)
  useEffect(() => {
    if (!api.ready) return;
    let cancelled = false;

    async function checkForUpdate() {
      try {
        const update = await api.checkUpdate();
        if (!cancelled && update) {
          addToast(
            `${t("update_available").replace("{version}", update.latest)} → ${update.url}`,
            "info"
          );
        }
      } catch {
        // Fail silently — no error toast if offline
      }
    }

    checkForUpdate();
    return () => { cancelled = true; };
  }, [api, api.ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Convert speed multiplier to API percentage: (multiplier - 1.0) × 100
  const speedToRate = useCallback((multiplier: number): number => {
    return Math.round((multiplier - 1.0) * 100);
  }, []);

  const handleSpeak = useCallback(async () => {
    if (!text.trim() || !api.ready) return;

    setSpeaking(true);
    try {
      const rate = speedToRate(speed);
      const result = await api.generateTTS(text, selectedVoice, rate, pitch);

      if (result.error) {
        addToast(result.error, "error");
      } else if (result.path) {
        await api.playAudio(result.path);
        addToast(t("status_playing"), "success");
      }
    } catch (err) {
      addToast(err instanceof Error ? err.message : "TTS generation failed", "error");
    } finally {
      setSpeaking(false);
    }
  }, [text, selectedVoice, speed, pitch, api, addToast, speedToRate, t]);

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

  return (
    <div
      className="flex flex-col min-h-screen"
      style={{
        background: "var(--background)",
        padding: "var(--space-8)",
      }}
    >
      {/* Header — full width */}
      <Header onSettingsClick={() => setSettingsOpen(true)} onThemeToggle={toggleTheme} isDark={isDark} t={t} />

      {/* Main content — 2-column layout */}
      <div
        className="flex flex-1 gap-5 mt-5"
        style={{ minHeight: 0 }}
      >
        {/* Left panel (40%) — Voice Selection */}
        <div
          className="flex flex-col"
          style={{
            width: "40%",
            minWidth: 280,
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-xl)",
            boxShadow: "var(--shadow-card)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "var(--space-4) var(--space-5)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600,
                lineHeight: 1.4,
                letterSpacing: "-0.1px",
                color: "var(--color-text-primary)",
                margin: 0,
              }}
            >
              {t("voice_selection")}
            </h2>
          </div>
          <VoiceSelector
            api={api}
            selectedVoice={selectedVoice}
            onVoiceChange={setSelectedVoice}
            t={t}
          />
        </div>

        {/* Right panel (60%) — Text Editor + Action Bar */}
        <div
          className="flex flex-col flex-1"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-xl)",
            boxShadow: "var(--shadow-card)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "var(--space-4) var(--space-5)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600,
                lineHeight: 1.4,
                letterSpacing: "-0.1px",
                color: "var(--color-text-primary)",
                margin: 0,
              }}
            >
              {t("text_input")}
            </h2>
          </div>

          <div
            className="flex flex-col flex-1"
            style={{ padding: "var(--space-5)" }}
          >
            <TextEditor text={text} onTextChange={setText} t={t} />
          </div>

          <ActionBar
            speed={speed}
            onSpeedChange={setSpeed}
            pitch={pitch}
            onPitchChange={setPitch}
            onSpeak={handleSpeak}
            onSave={handleSave}
            speaking={speaking}
            saving={saving}
            disabled={!text.trim() || !api.ready}
            t={t}
          />
        </div>
      </div>

      {/* Responsive: stack on narrow screens */}
      <style>{`
        @media (max-width: 999px) {
          .flex.flex-1.gap-5.mt-5 {
            flex-direction: column;
          }
          .flex.flex-1.gap-5.mt-5 > div:first-child {
            width: 100% !important;
            min-width: unset !important;
          }
        }
      `}</style>

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
