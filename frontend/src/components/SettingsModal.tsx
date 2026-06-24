/**
 * Settings modal component.
 *
 * Overlay with blur, 480px modal, scale animation enter/exit.
 * Sections: Language, About.
 * Per design spec §3.10.
 *
 * Ref: T19 — Settings Modal
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { X } from "lucide-react";
import type { UseApiReturn } from "../hooks/useApi";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  api: UseApiReturn;
}

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "zh-TW", label: "繁體中文" },
  { code: "zh-CN", label: "简体中文" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
];

export function SettingsModal({ open, onClose, api }: SettingsModalProps) {
  const [language, setLanguage] = useState("zh-TW");
  const [closing, setClosing] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Load current language from config
  useEffect(() => {
    if (!open || !api.ready) return;
    let cancelled = false;

    async function loadLanguage() {
      try {
        const config = await api.getConfig("language");
        if (!cancelled && config.value && typeof config.value === "string") {
          setLanguage(config.value);
        }
      } catch {
        // Use default
      }
    }

    loadLanguage();
    return () => { cancelled = true; };
  }, [open, api]);

  // ESC key handler
  useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        handleClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  });

  // Focus trap
  useEffect(() => {
    if (open && modalRef.current) {
      modalRef.current.focus();
    }
  }, [open]);

  const handleClose = useCallback(() => {
    setClosing(true);
    setTimeout(() => {
      setClosing(false);
      onClose();
    }, 150); // --duration-fast
  }, [onClose]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) {
        handleClose();
      }
    },
    [handleClose]
  );

  const handleLanguageChange = useCallback(
    async (newLanguage: string) => {
      setLanguage(newLanguage);
      if (api.ready) {
        try {
          await api.setConfig("language", newLanguage);
        } catch {
          // Silent fail for config write
        }
      }
    },
    [api]
  );

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 flex items-center justify-center"
      style={{
        background: "var(--color-overlay, rgba(0, 0, 0, 0.4))",
        backdropFilter: "blur(4px)",
        zIndex: "var(--z-modal)",
        opacity: closing ? 0 : 1,
        transition: `opacity var(--duration-fast) var(--ease-in)`,
      }}
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        style={{
          width: 480,
          maxWidth: "90vw",
          maxHeight: "80vh",
          overflowY: "auto",
          background: "var(--color-surface)",
          borderRadius: "var(--radius-xl)",
          boxShadow: "var(--shadow-elevated)",
          padding: "var(--space-6)",
          transform: closing ? "scale(0.95)" : "scale(1)",
          opacity: closing ? 0 : 1,
          transition: closing
            ? `transform var(--duration-fast) var(--ease-in), opacity var(--duration-fast) var(--ease-in)`
            : `transform var(--duration-normal) var(--ease-spring), opacity var(--duration-normal) var(--ease-out)`,
          animation: closing
            ? undefined
            : "settings-modal-enter var(--duration-normal) var(--ease-spring)",
          outline: "none",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between"
          style={{
            paddingBottom: "var(--space-4)",
            borderBottom: "1px solid var(--border)",
            marginBottom: "var(--space-5)",
          }}
        >
          <h2
            style={{
              fontSize: 20,
              fontWeight: 600,
              lineHeight: 1.3,
              letterSpacing: "-0.3px",
              color: "var(--color-text-primary)",
              margin: 0,
            }}
          >
            Settings
          </h2>
          <button
            onClick={handleClose}
            className="flex items-center justify-center rounded-md"
            style={{
              width: 32,
              height: 32,
              color: "var(--color-text-secondary)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              transition: `color var(--duration-fast) var(--ease-default),
                           background var(--duration-fast) var(--ease-default)`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--color-text-primary)";
              e.currentTarget.style.background = "var(--color-surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--color-text-secondary)";
              e.currentTarget.style.background = "transparent";
            }}
            aria-label="Close settings"
          >
            <X size={18} />
          </button>
        </div>

        {/* Language section */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <h3
            style={{
              fontSize: 16,
              fontWeight: 600,
              lineHeight: 1.4,
              letterSpacing: "-0.1px",
              color: "var(--color-text-primary)",
              margin: "0 0 var(--space-3) 0",
            }}
          >
            Language
          </h3>
          <select
            id="settings-language-select"
            value={language}
            onChange={(e) => handleLanguageChange(e.target.value)}
            style={{
              width: "100%",
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
            {LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
        </div>

        {/* About section */}
        <div>
          <h3
            style={{
              fontSize: 16,
              fontWeight: 600,
              lineHeight: 1.4,
              letterSpacing: "-0.1px",
              color: "var(--color-text-primary)",
              margin: "0 0 var(--space-3) 0",
            }}
          >
            About
          </h3>
          <div
            style={{
              padding: "var(--space-4)",
              background: "var(--color-surface-hover)",
              borderRadius: "var(--radius-lg)",
            }}
          >
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: "var(--color-text-primary)",
                marginBottom: "var(--space-1)",
              }}
            >
              Simple Edge TTS
            </div>
            <div
              style={{
                fontSize: 13,
                color: "var(--color-text-secondary)",
              }}
            >
              Cross-platform text-to-speech desktop app powered by Edge TTS
            </div>
          </div>
        </div>
      </div>

      {/* Enter animation keyframes */}
      <style>{`
        @keyframes settings-modal-enter {
          from {
            transform: scale(0.95);
            opacity: 0;
          }
          to {
            transform: scale(1);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
