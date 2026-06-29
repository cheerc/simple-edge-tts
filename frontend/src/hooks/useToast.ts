/**
 * Toast state management hook.
 *
 * Manages a queue of toast notifications with auto-dismiss (4s).
 * Ref: T18 Plan §4 — Toast System
 */

import { useState, useCallback, useRef } from "react";
import type { ToastItem, ToastVariant, ToastAction, ToastMessage } from "../types";

let toastCounter = 0;

export interface UseToastReturn {
  toasts: ToastItem[];
  addToast: (message: ToastMessage, variant?: ToastVariant, actions?: ToastAction[], durationMs?: number) => string;
  removeToast: (id: string) => void;
  /** Update an existing toast's message, actions, progress, variant, or duration. */
  updateToast: (id: string, updates: Partial<Pick<ToastItem, 'message' | 'actions' | 'progress' | 'durationMs' | 'variant'>>) => void;
}

export function useToast(): UseToastReturn {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: ToastMessage, variant: ToastVariant = "info", actions?: ToastAction[], durationMs?: number): string => {
      const id = `toast-${++toastCounter}`;
      const effectiveDuration = durationMs ?? (actions && actions.length > 0 ? 15000 : 4000);
      const item: ToastItem = { id, message, variant, actions, durationMs: effectiveDuration };
      setToasts((prev) => [...prev, item]);

      if (effectiveDuration > 0) {
        const timer = setTimeout(() => {
          removeToast(id);
        }, effectiveDuration);
        timers.current.set(id, timer);
      }
      return id;
    },
    [removeToast]
  );

  const updateToast = useCallback(
    (id: string, updates: Partial<Pick<ToastItem, 'message' | 'actions' | 'progress' | 'durationMs' | 'variant'>>) => {
      setToasts((prev) =>
        prev.map((t) => {
          if (t.id !== id) return t;
          const updated = { ...t, ...updates };
          // If duration changed, reset the auto-dismiss timer
          if (updates.durationMs !== undefined) {
            const oldTimer = timers.current.get(id);
            if (oldTimer) clearTimeout(oldTimer);
            if (updated.durationMs && updated.durationMs > 0) {
              const newTimer = setTimeout(() => {
                removeToast(id);
              }, updated.durationMs);
              timers.current.set(id, newTimer);
            } else {
              timers.current.delete(id);
            }
          }
          return updated;
        })
      );
    },
    [removeToast]
  );

  return { toasts, addToast, removeToast, updateToast };
}
