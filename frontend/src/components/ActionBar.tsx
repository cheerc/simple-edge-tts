/**
 * Action bar — 2 buttons: Preview/Stop toggle + Export MP3.
 * Below buttons: output folder selector row (📁 path, clickable).
 *
 * Ref: T25 — UI Layout Rework
 * Ref: #50 — Output folder selector
 * Ref: #51 — Merge Preview + Stop into toggle button
 */

import { Loader2, FolderOpen, Settings, Sun, Moon } from "lucide-react";

interface ActionBarProps {
  onTogglePreview: () => void;
  onSave: () => void;
  speaking: boolean;
  saving: boolean;
  disabled: boolean;
  t: (key: string) => string;
  outputDir: string;
  onSelectOutputDir: () => void;
  onSettingsClick?: () => void;
  onThemeToggle?: () => void;
  isDark?: boolean;
}

export function ActionBar({
  onTogglePreview,
  onSave,
  speaking,
  saving,
  disabled,
  t,
  outputDir,
  onSelectOutputDir,
  onSettingsClick,
  onThemeToggle,
  isDark,
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
        {/* Preview/Stop toggle — Ref: #51 */}
        <button
          onClick={onTogglePreview}
          disabled={(!speaking && disabled) || saving}
          style={{
            ...baseBtnStyle,
            background: speaking ? "transparent" : "var(--color-accent-main)",
            color: speaking ? "var(--color-text-accent)" : "var(--color-text-on-accent)",
            border: speaking ? "1.5px solid var(--color-accent-main)" : "none",
            boxShadow: speaking ? "none" : "0 2px 8px rgba(204,74,53,0.25)",
            opacity: !speaking && disabled ? 0.5 : 1,
            cursor: (!speaking && disabled) || saving ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (speaking) {
              e.currentTarget.style.background = "rgba(204,74,53,0.06)";
            } else if (!disabled && !saving) {
              e.currentTarget.style.background = "var(--color-accent-hover)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = speaking ? "transparent" : "var(--color-accent-main)";
          }}
          aria-busy={speaking}
        >
          {speaking ? (
            <>■ {t("stop")}</>
          ) : (
            <>
              {saving ? <Loader2 size={16} className="animate-spin" /> : null}
              ▶ {t("preview")}
            </>
          )}
        </button>

        {/* Export MP3 — unchanged */}
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

      {/* Output folder selector row — Ref: #50, Ref: #193 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        {/* Folder path — clickable */}
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
            flex: 1,
            minWidth: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--color-surface-hover, rgba(0,0,0,0.04))";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
          title={t("select_output_folder")}
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

        {/* Theme toggle + Settings — right-aligned (Ref: #193) */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-1)", flexShrink: 0 }}>
          <button
            onClick={onThemeToggle}
            className="flex items-center justify-center rounded-md"
            style={{
              width: 36,
              height: 36,
              color: "var(--color-text-secondary)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              transition: `color var(--duration-fast) var(--ease-default),
                           background var(--duration-fast) var(--ease-default)`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--color-accent-main)";
              e.currentTarget.style.background = "var(--color-surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--color-text-secondary)";
              e.currentTarget.style.background = "transparent";
            }}
            aria-label={t("theme_toggle")}
          >
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          <button
            onClick={onSettingsClick}
            className="flex items-center justify-center rounded-md"
            style={{
              width: 36,
              height: 36,
              color: "var(--color-text-secondary)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              transition: `color var(--duration-fast) var(--ease-default),
                           background var(--duration-fast) var(--ease-default)`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--color-accent-main)";
              e.currentTarget.style.background = "var(--color-surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--color-text-secondary)";
              e.currentTarget.style.background = "transparent";
            }}
            aria-label={t("settings")}
          >
            <Settings size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
