/**
 * Header bar component.
 *
 * Height 48px, app name left, settings gear right.
 * Per design spec §3.1.
 *
 * Ref: T18 Plan §5 — Header Component
 */

import { Settings } from "lucide-react";

interface HeaderProps {
  onSettingsClick?: () => void;
  t: (key: string) => string;
}

export function Header({ onSettingsClick, t }: HeaderProps) {
  return (
    <header
      className="flex items-center justify-between shrink-0"
      style={{
        height: 48,
        padding: "0 var(--space-4)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <h1
        style={{
          fontSize: 20,
          fontWeight: 700,
          lineHeight: 1.3,
          letterSpacing: "-0.3px",
          color: "var(--color-text-primary)",
          margin: 0,
        }}
      >
        Simple Edge TTS
      </h1>

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
    </header>
  );
}
