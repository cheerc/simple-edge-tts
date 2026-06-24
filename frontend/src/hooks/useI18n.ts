/**
 * Internationalization hook — loads translations from PyWebView API.
 *
 * Provides t(key) lookup and setLanguage() for live switching.
 * On mount, loads translations via api.getTranslations().
 * On language change, calls api.setConfig('language', lang) then refreshes.
 *
 * Ref: Hotfix — Frontend i18n live switching
 */

import { useState, useEffect, useCallback } from "react";
import type { UseApiReturn } from "./useApi";

export interface UseI18nReturn {
  t: (key: string) => string;
  language: string;
  setLanguage: (lang: string) => Promise<void>;
}

export function useI18n(api: UseApiReturn): UseI18nReturn {
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [language, setLanguageState] = useState("zh-TW");

  // Load translations on mount and when API becomes ready
  useEffect(() => {
    if (!api.ready) return;
    let cancelled = false;

    async function load() {
      try {
        const data = await api.getTranslations();
        if (!cancelled) {
          setTranslations(data.strings);
          setLanguageState(data.language);
        }
      } catch {
        // Use fallback keys
      }
    }

    load();
    return () => { cancelled = true; };
  }, [api, api.ready]);

  const t = useCallback(
    (key: string): string => {
      return translations[key] || key;
    },
    [translations]
  );

  const setLanguage = useCallback(
    async (lang: string) => {
      if (!api.ready) return;
      try {
        // Save language preference via IPC
        await api.setConfig("language", lang);
        // Refresh translations from backend (which now has updated i18n)
        const data = await api.getTranslations();
        setTranslations(data.strings);
        setLanguageState(data.language);
      } catch {
        // Silent fail
      }
    },
    [api]
  );

  return { t, language, setLanguage };
}
