/**
 * Toast notification component.
 *
 * Renders at bottom-center, supports success/error/info variants.
 * Per design spec §3.11.
 *
 * Ref: T18 Plan §4 — Toast System
 */

import type { ToastItem, ToastMessage } from "../types";

/** Resolve a ToastMessage to a rendered string. */
function resolveMessage(msg: ToastMessage, t: (key: string) => string): string {
  if (typeof msg === "string") return msg;
  let text = t(msg.key);
  if (msg.params) {
    for (const [k, v] of Object.entries(msg.params)) {
      text = text.replace(`{${k}}`, v);
    }
  }
  return text;
}

interface ToastProps {
  toasts: ToastItem[];
  onRemove: (id: string) => void;
  /** i18n translate function for reactive action label resolution. */
  t: (key: string) => string;
}

const variantBorderColor: Record<string, string> = {
  success: "var(--color-success)",
  error: "var(--destructive)",
  info: "transparent",
};

export function Toast({ toasts, onRemove, t }: ToastProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 flex flex-col gap-2"
      style={{ zIndex: "var(--z-toast)" }}
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="animate-toast-in cursor-pointer"
          style={{
            background: "var(--color-toast-bg)",
            color: "white",
            fontSize: "13px",
            fontWeight: 500,
            lineHeight: "1.5",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3) var(--space-4)",
            boxShadow: "var(--shadow-elevated)",
            borderLeft:
              toast.variant !== "info"
                ? `3px solid ${variantBorderColor[toast.variant]}`
                : undefined,
            minWidth: 240,
            maxWidth: 400,
          }}
          onClick={() => onRemove(toast.id)}
          role="status"
        >
          <div style={{ marginBottom: (toast.progress !== undefined || (toast.actions && toast.actions.length > 0)) ? "var(--space-2)" : 0, textAlign: "center" }}>
            {resolveMessage(toast.message, t)}
          </div>
          {toast.progress !== undefined && (
            <div
              style={{
                height: 4,
                marginBottom: "var(--space-2)",
                borderRadius: 2,
                background: "var(--color-text-secondary)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.min(toast.progress, 100)}%`,
                  background: "var(--primary)",
                  borderRadius: 2,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          )}
          {toast.actions && toast.actions.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "center" }}>
              {toast.actions.map((action, idx) => (
                <button
                  key={idx}
                  onClick={(e) => {
                    e.stopPropagation();
                    action.onClick();
                    onRemove(toast.id);
                  }}
                  style={{
                    height: 36,
                    padding: "0 var(--space-3)",
                    fontSize: 13,
                    fontWeight: 500,
                    border: idx === 0 ? "none" : "1px solid var(--color-text-secondary)",
                    borderRadius: "var(--radius-md)",
                    background: idx === 0 ? "var(--primary)" : "transparent",
                    color: idx === 0 ? "var(--primary-foreground)" : "var(--color-text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  {typeof action.label === "string" ? action.label : t(action.label.key)}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
