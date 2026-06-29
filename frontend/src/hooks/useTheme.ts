/**
 * Theme management hook — dark/light mode toggle with persistence.
 *
 * Priority: window.__INITIAL_THEME__ → localStorage → prefers-color-scheme → 'light' fallback.
 * Applies `data-theme` attribute on <html> element.
 *
 * Ref: T23 — Dark/Light Theme System
 * Ref: #165 — Fix theme persistence (Python injection beats empty localStorage)
 */

import { useState, useEffect, useCallback } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

function getInitialTheme(): Theme {
  // 1. Check Python-injected config (source of truth in production).
  //    pywebview creates a fresh browser context every launch, so
  //    localStorage is always empty on startup.  The injected global
  //    carries the persisted Python config value to prevent system-
  //    preference fallback from overwriting the user's saved theme.
  //    Ref: #165
  const injected = (window as any).__INITIAL_THEME__;
  if (injected === "light" || injected === "dark") {
    // Sync to localStorage so subsequent in-session priority chain works
    localStorage.setItem(STORAGE_KEY, injected);
    return injected;
  }
  // 2. Check localStorage (dev mode / in-session changes)
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  // 3. Check system preference
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  // 4. Default to light
  return "light";
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  // Apply theme to <html> element
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
    if (window.pywebview?.api?.set_config) {
      window.pywebview.api.set_config("theme", theme).catch((err) => {
        console.error("Failed to sync theme to python config:", err);
      });
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  const isDark = theme === "dark";

  return { theme, toggleTheme, isDark } as const;
}
