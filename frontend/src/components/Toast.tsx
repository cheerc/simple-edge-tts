/**
 * Toast notification component.
 *
 * Renders at bottom-center, supports success/error/info variants.
 * Per design spec §3.11.
 *
 * Ref: T18 Plan §4 — Toast System
 */

import type { ToastItem } from "../types";

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
          <div style={{ marginBottom: toast.actions && toast.actions.length > 0 ? "var(--space-2)" : 0 }}>
            {toast.message}
          </div>
          {toast.actions && toast.actions.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
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
