/**
 * Action bar — 3 equal-width buttons: 試聽 / 停止 / 另存新檔.
 * Below buttons: output folder selector row (📁 path, clickable).
 *
 * Sliders moved to VoiceSelector (T25 layout rework).
 * Per mockup v2 — btn-primary, btn-outline, btn-secondary.
 *
 * Ref: T25 — UI Layout Rework
 * Ref: #50 — Output folder selector
 */

import { Loader2, FolderOpen } from "lucide-react";

interface ActionBarProps {
  onSpeak: () => void;
  onStop: () => void;
  onSave: () => void;
  speaking: boolean;
  saving: boolean;
  disabled: boolean;
  t: (key: string) => string;
  outputDir: string;
  onSelectOutputDir: () => void;
}

export function ActionBar({
  onSpeak,
  onStop,
  onSave,
  speaking,
  saving,
  disabled,
  t,
  outputDir,
  onSelectOutputDir,
}: ActionBarProps) {
  const baseBtnStyle: React.CSSProperties = {
    flex: 1,
    height: 44,
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.15s",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    letterSpacing: "0.2px",
  };

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: "16px 24px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Button row */}
      <div style={{ display: "flex", gap: 12 }}>
        {/* 試聽 — primary (coral filled) */}
        <button
          onClick={onSpeak}
          disabled={disabled || speaking || saving}
          style={{
            ...baseBtnStyle,
            background: "var(--color-accent-main)",
            color: "var(--color-text-on-accent)",
            border: "none",
            boxShadow: "0 2px 8px rgba(204,74,53,0.25)",
            opacity: disabled ? 0.5 : 1,
            cursor: disabled || speaking || saving ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (!disabled && !speaking && !saving) {
              e.currentTarget.style.background = "var(--color-accent-hover)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--color-accent-main)";
          }}
          aria-busy={speaking}
        >
          {speaking && <Loader2 size={16} className="animate-spin" />}
          {speaking ? t("status_generating") : `▶ ${t("preview")}`}
        </button>

        {/* 停止 — outline (coral border) */}
        <button
          onClick={onStop}
          disabled={!speaking}
          style={{
            ...baseBtnStyle,
            background: "transparent",
            color: "var(--color-accent-main)",
            border: "1.5px solid var(--color-accent-main)",
            opacity: !speaking ? 0.5 : 1,
            cursor: !speaking ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (speaking) {
              e.currentTarget.style.background = "rgba(204,74,53,0.06)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          ■ {t("stop")}
        </button>

        {/* 另存新檔 — secondary (coral filled) */}
        <button
          onClick={onSave}
          disabled={disabled || speaking || saving}
          style={{
            ...baseBtnStyle,
            background: "var(--color-accent-main)",
            color: "var(--color-text-on-accent)",
            border: "none",
            boxShadow: "0 2px 8px rgba(204,74,53,0.25)",
            opacity: disabled ? 0.5 : 1,
            cursor: disabled || saving || speaking ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (!disabled && !saving && !speaking) {
              e.currentTarget.style.background = "var(--color-accent-hover)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--color-accent-main)";
          }}
          aria-busy={saving}
        >
          {saving && <Loader2 size={16} className="animate-spin" />}
          {saving ? t("status_saving") : `↓ ${t("export_mp3")}`}
        </button>
      </div>

      {/* Output folder selector row */}
      <div
        onClick={onSelectOutputDir}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderRadius: 8,
          cursor: "pointer",
          transition: "background 0.15s",
          color: "var(--color-text-secondary)",
          fontSize: 13,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "var(--color-surface-hover, rgba(0,0,0,0.04))";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
        title={t("select_output_folder") || "Select output folder"}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectOutputDir();
          }
        }}
      >
        <FolderOpen size={16} style={{ flexShrink: 0, opacity: 0.7 }} />
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            direction: "rtl",
            textAlign: "left",
          }}
        >
          {outputDir}
        </span>
      </div>
    </div>
  );
}
