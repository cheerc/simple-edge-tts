/**
 * Theme management hook — dark/light mode toggle with persistence.
 *
 * Priority: URL query param → window.__INITIAL_THEME__ → localStorage →
 *            prefers-color-scheme → 'light' fallback.
 * Applies `data-theme` attribute on <html> element.
 *
 * Ref: T23 — Dark/Light Theme System
 * Ref: #165 — Fix theme flash: URL param arrives before React renders,
 *       unlike __INITIAL_THEME__ which is injected after 'loaded' event.
 */

import { useState, useEffect, useCallback } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

function getInitialTheme(): Theme {
  // 1. Check URL query parameter (set by Python before page load).
  //    Ref: #165 — This arrives synchronously with the initial HTML,
  //    before React's first render, eliminating the theme flash that
  //    occurred when __INITIAL_THEME__ was injected via evaluate_js
  //    (which fires after the loaded event).
  const params = new URLSearchParams(window.location.search);
  const urlTheme = params.get("theme");
  if (urlTheme === "light" || urlTheme === "dark") {
    localStorage.setItem(STORAGE_KEY, urlTheme);
    return urlTheme;
  }
  // 2. Check Python-injected global (fallback for backward compat).
  //    pywebview creates a fresh browser context every launch, so
  //    localStorage is always empty on startup.  The injected global
  //    carries the persisted Python config value to prevent system-
  //    preference fallback from overwriting the user's saved theme.
  const injected = (window as any).__INITIAL_THEME__;
  if (injected === "light" || injected === "dark") {
    // Sync to localStorage so subsequent in-session priority chain works
    localStorage.setItem(STORAGE_KEY, injected);
    return injected;
  }
  // 3. Check localStorage (dev mode / in-session changes)
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  // 4. Check system preference
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  // 5. Default to light
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
