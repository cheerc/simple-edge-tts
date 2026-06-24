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
}

const variantBorderColor: Record<string, string> = {
  success: "var(--color-success)",
  error: "var(--destructive)",
  info: "transparent",
};

export function Toast({ toasts, onRemove }: ToastProps) {
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
            background: "var(--color-text-primary)",
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
          {toast.message}
        </div>
      ))}
    </div>
  );
}
