/**
 * Toast state management hook.
 *
 * Manages a queue of toast notifications with auto-dismiss (4s).
 * Ref: T18 Plan §4 — Toast System
 */

import { useState, useCallback, useRef } from "react";
import type { ToastItem, ToastVariant } from "../types";

let toastCounter = 0;

export interface UseToastReturn {
  toasts: ToastItem[];
  addToast: (message: string, variant?: ToastVariant) => void;
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
    (message: string, variant: ToastVariant = "info") => {
      const id = `toast-${++toastCounter}`;
      const item: ToastItem = { id, message, variant };
      setToasts((prev) => [...prev, item]);

      const timer = setTimeout(() => {
        removeToast(id);
      }, 4000);
      timers.current.set(id, timer);
    },
    [removeToast]
  );

  return { toasts, addToast, removeToast };
}
