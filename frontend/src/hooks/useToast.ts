/**
 * Toast state management hook.
 *
 * Manages a queue of toast notifications with auto-dismiss (4s).
 * Ref: T18 Plan §4 — Toast System
 */

import { useState, useCallback, useRef } from "react";
import type { ToastItem, ToastVariant, ToastAction } from "../types";

let toastCounter = 0;

export interface UseToastReturn {
  toasts: ToastItem[];
  addToast: (message: string, variant?: ToastVariant, actions?: ToastAction[], durationMs?: number) => void;
  removeToast: (id: string) => void;
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
    (message: string, variant: ToastVariant = "info", actions?: ToastAction[], durationMs?: number) => {
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
    },
    [removeToast]
  );

  return { toasts, addToast, removeToast };
}
