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
import { X, RefreshCw } from "lucide-react";
import type { UseApiReturn } from "../hooks/useApi";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  api: UseApiReturn;
  t: (key: string) => string;
  language: string;
  onLanguageChange: (lang: string) => Promise<void>;
}

const LANGUAGES = [
  { code: "en-US", label: "English" },
  { code: "zh-TW", label: "繁體中文" },
];

export function SettingsModal({ open, onClose, api, t, language, onLanguageChange }: SettingsModalProps) {
  const [closing, setClosing] = useState(false);
  const [enableLogging, setEnableLogging] = useState(false);
  const [showRestartDialog, setShowRestartDialog] = useState(false);
  // Ref: #170 — Auto-update UI state
  const [autoCheck, setAutoCheck] = useState(true);
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<{ latest?: string; upToDate?: boolean } | null>(null);
  const [skippedVersion, setSkippedVersion] = useState<string | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Load logging config when modal opens
  useEffect(() => {
    if (open && api.ready) {
      api.getConfig("enable_file_logging").then((res) => {
        if (res && res.value !== undefined) {
          setEnableLogging(!!res.value);
        }
      });
    }
  }, [open, api, api.ready]);

  // Load auto-update config when modal opens
  useEffect(() => {
    if (open && api.ready) {
      api.getConfig("auto_check_update").then((res) => {
        if (res && res.value !== undefined && res.value !== null) {
          setAutoCheck(!!res.value);
        }
      });
      api.getConfig("skip_version").then((res) => {
        if (res && res.value) {
          setSkippedVersion(String(res.value));
        }
      });
    }
  }, [open, api, api.ready]);

  const handleLoggingToggle = useCallback(
    async (checked: boolean) => {
      setEnableLogging(checked);
      if (api.ready) {
        try {
          await api.setConfig("enable_file_logging", checked);
          setShowRestartDialog(true);
        } catch (e) {
          console.error("Failed to save config", e);
        }
      }
    },
    [api]
  );

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

  const handleAutoCheckToggle = useCallback(
    async (checked: boolean) => {
      setAutoCheck(checked);
      if (api.ready) {
        try {
          await api.setConfig("auto_check_update", checked);
        } catch (e) {
          console.error("Failed to save auto_check_update config", e);
        }
      }
    },
    [api]
  );

  const handleCheckUpdate = useCallback(async () => {
    if (!api.ready) return;
    setChecking(true);
    setCheckResult(null);
    try {
      const update = await api.checkUpdate();
      if (update) {
        setCheckResult({ latest: update.latest });
      } else {
        setCheckResult({ upToDate: true });
      }
    } catch {
      setCheckResult(null);
    } finally {
      setChecking(false);
    }
  }, [api]);

  const handleClearSkip = useCallback(async () => {
    if (api.ready) {
      try {
        await api.setConfig("skip_version", null);
        setSkippedVersion(null);
      } catch (e) {
        console.error("Failed to clear skip_version", e);
      }
    }
  }, [api]);

  const handleLanguageChange = useCallback(
    async (newLanguage: string) => {
      await onLanguageChange(newLanguage);
    },
    [onLanguageChange]
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
          position: "relative",
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
            {t("settings_title")}
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
            aria-label={t("cancel")}
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
            {t("language")}
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

        {/* File Logging section */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <div className="flex items-center justify-between" style={{ minHeight: 44 }}>
            <div>
              <h3
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  lineHeight: 1.4,
                  letterSpacing: "-0.1px",
                  color: "var(--color-text-primary)",
                  margin: 0,
                }}
              >
                {t("enable_logging")}
              </h3>
              <p
                style={{
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                  margin: "var(--space-1) 0 0 0",
                  maxWidth: "340px",
                  lineHeight: 1.4,
                }}
              >
                {t("enable_logging_desc")}
              </p>
            </div>
            
            <button
              role="switch"
              aria-checked={enableLogging}
              onClick={() => handleLoggingToggle(!enableLogging)}
              style={{
                position: "relative",
                width: 44,
                height: 24,
                backgroundColor: enableLogging ? "var(--primary)" : "var(--border)",
                borderRadius: "var(--radius-full)",
                border: "none",
                cursor: "pointer",
                padding: 0,
                transition: "background-color var(--duration-fast) var(--ease-default)",
                outline: "none",
              }}
              onFocus={(e) => {
                e.currentTarget.style.boxShadow = "var(--shadow-focus)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <span
                style={{
                  display: "block",
                  width: 18,
                  height: 18,
                  backgroundColor: "#ffffff",
                  borderRadius: "50%",
                  boxShadow: "var(--shadow-sm)",
                  transform: enableLogging ? "translateX(22px)" : "translateX(4px)",
                  transition: "transform var(--duration-fast) var(--ease-spring)",
                }}
              />
            </button>
          </div>
        </div>

        {/* Ref: #170 — Updates section */}
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
            {t("update_section_title")}
          </h3>

          {/* Auto-check toggle */}
          <div className="flex items-center justify-between" style={{ minHeight: 44 }}>
            <div>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: "var(--color-text-primary)",
                }}
              >
                {t("update_auto_check")}
              </span>
              <p
                style={{
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                  margin: "var(--space-1) 0 0 0",
                  maxWidth: "340px",
                  lineHeight: 1.4,
                }}
              >
                {t("update_auto_check_desc")}
              </p>
            </div>

            <button
              role="switch"
              aria-checked={autoCheck}
              onClick={() => handleAutoCheckToggle(!autoCheck)}
              style={{
                position: "relative",
                width: 44,
                height: 24,
                backgroundColor: autoCheck ? "var(--primary)" : "var(--border)",
                borderRadius: "var(--radius-full)",
                border: "none",
                cursor: "pointer",
                padding: 0,
                transition: "background-color var(--duration-fast) var(--ease-default)",
                outline: "none",
              }}
              onFocus={(e) => {
                e.currentTarget.style.boxShadow = "var(--shadow-focus)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <span
                style={{
                  display: "block",
                  width: 18,
                  height: 18,
                  backgroundColor: "#ffffff",
                  borderRadius: "50%",
                  boxShadow: "var(--shadow-sm)",
                  transform: autoCheck ? "translateX(22px)" : "translateX(4px)",
                  transition: "transform var(--duration-fast) var(--ease-spring)",
                }}
              />
            </button>
          </div>

          {/* Manual check button */}
          <div style={{ marginTop: "var(--space-3)" }}>
            <button
              onClick={handleCheckUpdate}
              disabled={checking}
              className="flex items-center justify-center gap-2 rounded-md"
              style={{
                width: "100%",
                height: 36,
                background: checking ? "var(--border)" : "var(--color-surface-hover)",
                color: "var(--color-text-primary)",
                border: "1px solid var(--border)",
                fontWeight: 500,
                fontSize: 13,
                cursor: checking ? "not-allowed" : "pointer",
                transition: "background-color var(--duration-fast) var(--ease-default)",
                opacity: checking ? 0.7 : 1,
              }}
              onMouseEnter={(e) => {
                if (!checking) e.currentTarget.style.background = "var(--border)";
              }}
              onMouseLeave={(e) => {
                if (!checking) e.currentTarget.style.background = "var(--color-surface-hover)";
              }}
            >
              <RefreshCw
                size={14}
                style={{
                  animation: checking ? "spin 1s linear infinite" : undefined,
                }}
              />
              {checking ? t("update_checking") : t("update_check_now")}
            </button>

            {/* Inline check result */}
            {checkResult && (
              <p
                style={{
                  fontSize: 12,
                  color: checkResult.upToDate ? "var(--color-success)" : "var(--primary)",
                  margin: "var(--space-2) 0 0 0",
                  lineHeight: 1.4,
                }}
              >
                {checkResult.upToDate
                  ? t("update_up_to_date")
                  : t("update_available").replace("{version}", checkResult.latest ?? "")}
              </p>
            )}
          </div>

          {/* Skipped version row */}
          {skippedVersion && (
            <div
              className="flex items-center justify-between"
              style={{
                marginTop: "var(--space-3)",
                padding: "var(--space-2) var(--space-3)",
                background: "var(--color-surface-hover)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                }}
              >
                {t("update_skipped_version").replace("{version}", skippedVersion)}
              </span>
              <button
                onClick={handleClearSkip}
                className="flex items-center justify-center rounded-md"
                style={{
                  height: 28,
                  padding: "0 var(--space-2)",
                  fontSize: 12,
                  fontWeight: 500,
                  color: "var(--color-text-secondary)",
                  background: "transparent",
                  border: "1px solid var(--border)",
                  cursor: "pointer",
                  transition: "color var(--duration-fast) var(--ease-default)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--color-text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--color-text-secondary)";
                }}
                aria-label={t("update_clear_skip")}
              >
                <X size={12} style={{ marginRight: 4 }} />
                {t("update_clear_skip")}
              </button>
            </div>
          )}
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
            {t("about")}
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
              {t("about_description")}
            </div>
          </div>
        </div>

        {/* Restart Required Dialog overlay */}
        {showRestartDialog && (
          <div
            className="absolute inset-0 flex items-center justify-center animate-toast-in"
            style={{
              background: "var(--color-overlay, rgba(0, 0, 0, 0.4))",
              backdropFilter: "blur(2px)",
              borderRadius: "var(--radius-xl)",
              zIndex: 50,
              padding: "var(--space-6)",
            }}
          >
            <div
              style={{
                width: 320,
                background: "var(--color-surface)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-elevated)",
                padding: "var(--space-5)",
                textAlign: "center",
              }}
            >
              <h4
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  margin: "0 0 var(--space-2) 0",
                }}
              >
                {t("restart_required_title")}
              </h4>
              <p
                style={{
                  fontSize: 13,
                  color: "var(--color-text-secondary)",
                  margin: "0 0 var(--space-4) 0",
                  lineHeight: 1.4,
                }}
              >
                {t("restart_required_desc")}
              </p>
              <button
                onClick={() => setShowRestartDialog(false)}
                className="w-full flex items-center justify-center rounded-md"
                style={{
                  height: 36,
                  background: "var(--primary)",
                  color: "var(--primary-foreground)",
                  border: "none",
                  fontWeight: 500,
                  fontSize: 14,
                  cursor: "pointer",
                  transition: "background-color var(--duration-fast) var(--ease-default)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--color-accent-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--primary)";
                }}
              >
                {t("ok")}
              </button>
            </div>
          </div>
        )}
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
