/**
 * Voice selector component — language + voice dropdowns.
 *
 * Fetches voice list from PyWebView API on mount, groups by locale,
 * and provides language/voice selection with preview details.
 * Per design spec §3.6, §3.7, §4.1.
 *
 * Ref: T18 Plan §6 — Voice Selector
 */

import { useState, useEffect, useMemo } from "react";
import type { Voice } from "../types";
import type { UseApiReturn } from "../hooks/useApi";

interface VoiceSelectorProps {
  api: UseApiReturn;
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
}

export function VoiceSelector({ api, selectedVoice, onVoiceChange }: VoiceSelectorProps) {
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
    // Prioritize zh-TW and en-US
    const priority = ["zh-TW", "en-US"];
    const sorted = priority.filter((l) => locales.includes(l));
    const rest = locales.filter((l) => !priority.includes(l));
    return [...sorted, ...rest];
  }, [voices]);

  const filteredVoices = useMemo(
    () => voices.filter((v) => v.Locale === selectedLanguage),
    [voices, selectedLanguage]
  );

  const currentVoice = useMemo(
    () => voices.find((v) => v.ShortName === selectedVoice),
    [voices, selectedVoice]
  );

  // Auto-select first voice when language changes
  useEffect(() => {
    if (filteredVoices.length > 0 && !filteredVoices.find((v) => v.ShortName === selectedVoice)) {
      onVoiceChange(filteredVoices[0].ShortName);
    }
  }, [filteredVoices, selectedVoice, onVoiceChange]);

  if (loading) {
    return (
      <div className="flex flex-col gap-3" style={{ padding: "var(--space-5)" }}>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="animate-pulse rounded-lg"
            style={{
              height: 40,
              background: "var(--color-surface-hover)",
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" style={{ padding: "var(--space-5)" }}>
      {/* Language dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="language-select"
          style={{
            fontSize: 12,
            fontWeight: 500,
            lineHeight: 1.4,
            letterSpacing: "0.2px",
            color: "var(--color-text-secondary)",
          }}
        >
          Language
        </label>
        <select
          id="language-select"
          value={selectedLanguage}
          onChange={(e) => setSelectedLanguage(e.target.value)}
          style={{
            height: 40,
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-2) var(--space-3)",
            fontSize: 14,
            lineHeight: 1.5,
            color: "var(--color-text-primary)",
            cursor: "pointer",
            outline: "none",
            width: "100%",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-border-focus)";
            e.currentTarget.style.boxShadow = "var(--shadow-focus)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          {languages.map((lang) => (
            <option key={lang} value={lang}>
              {lang}
            </option>
          ))}
        </select>
      </div>

      {/* Voice dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="voice-select"
          style={{
            fontSize: 12,
            fontWeight: 500,
            lineHeight: 1.4,
            letterSpacing: "0.2px",
            color: "var(--color-text-secondary)",
          }}
        >
          Voice
        </label>
        <select
          id="voice-select"
          value={selectedVoice}
          onChange={(e) => onVoiceChange(e.target.value)}
          style={{
            height: 40,
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-2) var(--space-3)",
            fontSize: 14,
            lineHeight: 1.5,
            color: "var(--color-text-primary)",
            cursor: "pointer",
            outline: "none",
            width: "100%",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-border-focus)";
            e.currentTarget.style.boxShadow = "var(--shadow-focus)";
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

      {/* Voice details card */}
      {currentVoice && (
        <div
          className="flex flex-col gap-2"
          style={{
            padding: "var(--space-4)",
            background: "var(--color-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            transition: `opacity var(--duration-fast) var(--ease-default)`,
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "var(--color-text-primary)",
            }}
          >
            {currentVoice.FriendlyName || currentVoice.ShortName}
          </div>
          <div className="flex gap-2">
            <span
              style={{
                fontSize: 11,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: "var(--radius-sm)",
                background: "var(--color-accent-subtle)",
                color: "var(--color-accent-main)",
              }}
            >
              {currentVoice.Gender}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: "var(--radius-sm)",
                background: "var(--color-surface-hover)",
                color: "var(--color-text-secondary)",
              }}
            >
              {currentVoice.Locale}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
