/**
 * PyWebView IPC hook — wraps window.pywebview.api.* calls with typed responses.
 *
 * Handles the pywebviewready event to ensure API availability before calling.
 * All PyWebView API methods return JSON-encoded strings; this hook parses them.
 *
 * Ref: T18 Plan §3 — IPC Hook
 */

import { useState, useEffect, useCallback } from "react";
import type { Voice, TTSResult, ConfigValue, ConfigSetResult, TranslationData, AudioResult, UpdateInfo } from "../types";

/** Hook return type. */
export interface UseApiReturn {
  ready: boolean;
  getVoices: () => Promise<Voice[]>;
  generateTTS: (text: string, voice: string, rate: number, pitch: number) => Promise<TTSResult>;
  getConfig: (key: string) => Promise<ConfigValue>;
  setConfig: (key: string, value: unknown) => Promise<ConfigSetResult>;
  getTranslations: () => Promise<TranslationData>;
  playAudio: (path: string) => Promise<AudioResult>;
  stopAudio: () => Promise<AudioResult>;
  checkUpdate: () => Promise<UpdateInfo | null>;
}

export function useApi(): UseApiReturn {
  const [ready, setReady] = useState(!!window.pywebview);

  useEffect(() => {
    if (window.pywebview) {
      setReady(true);
      return;
    }

    const handler = () => setReady(true);
    window.addEventListener("pywebviewready", handler);
    return () => window.removeEventListener("pywebviewready", handler);
  }, []);

  const getApi = useCallback(() => {
    if (!window.pywebview?.api) {
      throw new Error("PyWebView API not available");
    }
    return window.pywebview.api;
  }, []);

  const getVoices = useCallback(async (): Promise<Voice[]> => {
    const result = await getApi().get_voices();
    const parsed = JSON.parse(result);
    if (parsed.error) throw new Error(parsed.error);
    return parsed as Voice[];
  }, [getApi]);

  const generateTTS = useCallback(
    async (text: string, voice: string, rate: number, pitch: number): Promise<TTSResult> => {
      const result = await getApi().generate_tts(text, voice, rate, pitch);
      return JSON.parse(result) as TTSResult;
    },
    [getApi]
  );

  const getConfig = useCallback(
    async (key: string): Promise<ConfigValue> => {
      const result = await getApi().get_config(key);
      return JSON.parse(result) as ConfigValue;
    },
    [getApi]
  );

  const setConfig = useCallback(
    async (key: string, value: unknown): Promise<ConfigSetResult> => {
      const result = await getApi().set_config(key, value);
      return JSON.parse(result) as ConfigSetResult;
    },
    [getApi]
  );

  const getTranslations = useCallback(async (): Promise<TranslationData> => {
    const result = await getApi().get_translations();
    return JSON.parse(result) as TranslationData;
  }, [getApi]);

  const playAudio = useCallback(
    async (path: string): Promise<AudioResult> => {
      const result = await getApi().play_audio(path);
      return JSON.parse(result) as AudioResult;
    },
    [getApi]
  );

  const stopAudio = useCallback(async (): Promise<AudioResult> => {
    const result = await getApi().stop_audio();
    return JSON.parse(result) as AudioResult;
  }, [getApi]);

  const checkUpdate = useCallback(async (): Promise<UpdateInfo | null> => {
    const result = await getApi().check_update();
    return JSON.parse(result) as UpdateInfo | null;
  }, [getApi]);

  return { ready, getVoices, generateTTS, getConfig, setConfig, getTranslations, playAudio, stopAudio, checkUpdate };
}
