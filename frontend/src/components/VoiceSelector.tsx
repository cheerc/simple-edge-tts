/**
 * Voice controls card — language/voice dropdowns + speed/pitch sliders.
 *
 * Horizontal layout: left = language + voice selects, right = speed + pitch sliders.
 * Per mockup v2 — single row voice controls card.
 *
 * Ref: T25 — UI Layout Rework
 */

import { useState, useEffect, useMemo } from "react";
import type { Voice } from "../types";
import type { UseApiReturn } from "../hooks/useApi";

interface VoiceSelectorProps {
  api: UseApiReturn;
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
  pitch: number;
  onPitchChange: (pitch: number) => void;
  t: (key: string) => string;
}

export function VoiceSelector({
  api, selectedVoice, onVoiceChange,
  speed, onSpeedChange, pitch, onPitchChange, t,
}: VoiceSelectorProps) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState("zh-TW");

  useEffect(() => {
    if (!api.ready) return;
    let cancelled = false;

    async function fetchVoices() {
      try {
        const voiceList = await api.getVoices();
        if (!cancelled) {
          setVoices(voiceList);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }

    fetchVoices();
    return () => { cancelled = true; };
  }, [api]);

  const languages = useMemo(() => {
    const locales = [...new Set(voices.map((v) => v.Locale))].sort();
    const priority = ["zh-TW", "en-US"];
    const sorted = priority.filter((l) => locales.includes(l));
    const rest = locales.filter((l) => !priority.includes(l));
    return [...sorted, ...rest];
  }, [voices]);

  const filteredVoices = useMemo(
    () => voices.filter((v) => v.Locale === selectedLanguage),
    [voices, selectedLanguage]
  );

  // Auto-select first voice when language changes
  useEffect(() => {
    if (filteredVoices.length > 0 && !filteredVoices.find((v) => v.ShortName === selectedVoice)) {
      onVoiceChange(filteredVoices[0].ShortName);
    }
  }, [filteredVoices, selectedVoice, onVoiceChange]);

  const selectStyle: React.CSSProperties = {
    height: 40,
    background: "var(--color-surface)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "0 12px",
    fontSize: 14,
    color: "var(--color-text-primary)",
    cursor: "pointer",
    outline: "none",
    width: "100%",
    transition: "border-color 0.15s",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 600,
    color: "var(--color-text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  };

  if (loading) {
    return (
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          padding: "20px 24px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        <div className="flex gap-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg flex-1"
              style={{ height: 40, background: "var(--color-surface-hover)" }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: "20px 24px",
        display: "flex",
        gap: 32,
        alignItems: "flex-end",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Left: Language + Voice dropdowns */}
      <div style={{ display: "flex", gap: 16, flex: 1 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
          <label htmlFor="language-select" style={labelStyle}>
            {t("language")}
          </label>
          <select
            id="language-select"
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            style={selectStyle}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-border-focus)";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(204,74,53,0.1)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {languages.map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
          <label htmlFor="voice-select" style={labelStyle}>
            {t("voice_selection")}
          </label>
          <select
            id="voice-select"
            value={selectedVoice}
            onChange={(e) => onVoiceChange(e.target.value)}
            style={selectStyle}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-border-focus)";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(204,74,53,0.1)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {filteredVoices.map((v) => (
              <option key={v.ShortName} value={v.ShortName}>
                {v.FriendlyName || v.ShortName} ({v.Gender})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Right: Speed + Pitch sliders */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 220 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", width: 42, textAlign: "right" }}>
            {t("speed")}
          </span>
          <input
            id="speed-slider"
            type="range"
            min={0.5}
            max={2.0}
            step={0.1}
            value={speed}
            onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
            style={{ flex: 1 }}
          />
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", width: 38, textAlign: "left" }}>
            {speed.toFixed(1)}×
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", width: 42, textAlign: "right" }}>
            {t("pitch")}
          </span>
          <input
            id="pitch-slider"
            type="range"
            min={-50}
            max={50}
            step={1}
            value={pitch}
            onChange={(e) => onPitchChange(parseInt(e.target.value, 10))}
            style={{ flex: 1 }}
          />
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", width: 38, textAlign: "left" }}>
            {pitch > 0 ? "+" : ""}{pitch}Hz
          </span>
        </div>
      </div>
    </div>
  );
}
