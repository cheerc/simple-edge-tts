/**
 * PyWebView IPC hook — wraps window.pywebview.api.* calls with typed responses.
 *
 * Handles the pywebviewready event to ensure API availability before calling.
 * All PyWebView API methods return JSON-encoded strings; this hook parses and
 * validates them against Zod schemas so IPC contract deviations surface as
 * descriptive errors rather than silent type mismatches.
 *
 * Ref: T18 Plan §3 — IPC Hook
 * Ref: #141 — Runtime schema validation
 */

import { z } from "zod";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { Voice, TTSResult, ConfigValue, ConfigSetResult, TranslationData, AudioResult, UpdateInfo, OutputDirResult, DownloadProgress } from "../types";

// ── Zod schemas matching Python API return shapes ──────────────────────

const VoiceSchema = z.object({
  ShortName: z.string(),
  Locale: z.string(),
  Gender: z.string(),
  FriendlyName: z.string(),
});

const VoiceArraySchema = z.array(VoiceSchema);

const TTSResultSchema = z.object({
  path: z.string().optional(),
  error: z.string().optional(),
});

const ConfigValueSchema = z.object({
  value: z.unknown(),
}).required();

const ConfigSetResultSchema = z.object({
  success: z.boolean(),
  error: z.string().optional(),
});

const TranslationDataSchema = z.object({
  language: z.string(),
  strings: z.record(z.string(), z.string()),
});

const AudioResultSchema = z.object({
  success: z.boolean(),
  error: z.string().optional(),
});

const UpdateInfoSchema = z.object({
  latest: z.string(),
  url: z.string(),
});

const OutputDirResultSchema = z.object({
  output_dir: z.string().optional(),
  error: z.string().optional(),
});

const DownloadProgressSchema = z.object({
  state: z.string(),
  progress: z.number(),
  error: z.string().nullable(),
});

// ── Validation helper ──────────────────────────────────────────────────

/**
 * Parse a JSON string and validate against a Zod schema.
 *
 * Throws a descriptive error on JSON parse failure OR schema mismatch so
 * IPC contract deviations never propagate silently into the React tree.
 */
function validate<T>(raw: string, schema: z.ZodSchema<T>, label: string): T {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`[${label}] Invalid JSON response from API: ${raw.slice(0, 200)}`);
  }
  const result = schema.safeParse(parsed);
  if (!result.success) {
    throw new Error(
      `[${label}] API response shape mismatch: ${result.error.message} — raw: ${raw.slice(0, 200)}`
    );
  }
  return result.data as T;
}

// ── Hook return type ───────────────────────────────────────────────────

export interface UseApiReturn {
  ready: boolean;
  getVoices: () => Promise<Voice[]>;
  generateTTS: (text: string, voice: string, rate: number, pitch: number) => Promise<TTSResult>;
  previewTTS: (text: string, voice: string, rate: number, pitch: number) => Promise<TTSResult>;
  getConfig: (key: string) => Promise<ConfigValue>;
  setConfig: (key: string, value: unknown) => Promise<ConfigSetResult>;
  getTranslations: () => Promise<TranslationData>;
  playAudio: (path: string) => Promise<AudioResult>;
  stopAudio: () => Promise<AudioResult>;
  checkUpdate: (manual?: boolean) => Promise<UpdateInfo | null>;
  getOutputDir: () => Promise<OutputDirResult>;
  selectOutputDir: () => Promise<OutputDirResult>;
  /** Start background download of the latest release. Returns initial state. */
  downloadUpdate: () => Promise<{ state: string }>;
  /** Poll download progress. Returns { state, progress, error }. */
  getDownloadProgress: () => Promise<DownloadProgress>;
  /** Cancel an in-progress download. */
  cancelDownload: () => Promise<void>;
  /** Install the downloaded update and restart the app. */
  installUpdate: () => Promise<{ success: boolean; error?: string }>;
}

// ── Hook implementation ────────────────────────────────────────────────

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
    const parsed = validate<Voice[]>(result, VoiceArraySchema, "getVoices");
    // Additionally check for inline error payload (Python may return {"error": ...})
    const obj = JSON.parse(result);
    if (obj && typeof obj === "object" && "error" in obj) {
      throw new Error(String((obj as { error: unknown }).error));
    }
    return parsed;
  }, [getApi]);

  const generateTTS = useCallback(
    async (text: string, voice: string, rate: number, pitch: number): Promise<TTSResult> => {
      const result = await getApi().generate_tts(text, voice, rate, pitch);
      return validate<TTSResult>(result, TTSResultSchema, "generateTTS");
    },
    [getApi]
  );

  const previewTTS = useCallback(
    async (text: string, voice: string, rate: number, pitch: number): Promise<TTSResult> => {
      const result = await getApi().preview_tts(text, voice, rate, pitch);
      return validate<TTSResult>(result, TTSResultSchema, "previewTTS");
    },
    [getApi]
  );

  const getConfig = useCallback(
    async (key: string): Promise<ConfigValue> => {
      const result = await getApi().get_config(key);
      return validate<ConfigValue>(result, ConfigValueSchema, "getConfig");
    },
    [getApi]
  );

  const setConfig = useCallback(
    async (key: string, value: unknown): Promise<ConfigSetResult> => {
      const result = await getApi().set_config(key, value);
      return validate<ConfigSetResult>(result, ConfigSetResultSchema, "setConfig");
    },
    [getApi]
  );

  const getTranslations = useCallback(async (): Promise<TranslationData> => {
    const result = await getApi().get_translations();
    return validate<TranslationData>(result, TranslationDataSchema, "getTranslations");
  }, [getApi]);

  const playAudio = useCallback(
    async (path: string): Promise<AudioResult> => {
      const result = await getApi().play_audio(path);
      return validate<AudioResult>(result, AudioResultSchema, "playAudio");
    },
    [getApi]
  );

  const stopAudio = useCallback(async (): Promise<AudioResult> => {
    const result = await getApi().stop_audio();
    return validate<AudioResult>(result, AudioResultSchema, "stopAudio");
  }, [getApi]);

  const checkUpdate = useCallback(async (manual = false): Promise<UpdateInfo | null> => {
    const result = await getApi().check_update(manual);
    const parsed = JSON.parse(result);
    if (parsed === null) return null;
    if (parsed.error) {
      throw new Error(parsed.error);
    }
    return validate<UpdateInfo>(result, UpdateInfoSchema, "checkUpdate");
  }, [getApi]);

  const getOutputDir = useCallback(async (): Promise<OutputDirResult> => {
    const result = await getApi().get_output_dir();
    return validate<OutputDirResult>(result, OutputDirResultSchema, "getOutputDir");
  }, [getApi]);

  const selectOutputDir = useCallback(async (): Promise<OutputDirResult> => {
    const result = await getApi().select_output_dir();
    return validate<OutputDirResult>(result, OutputDirResultSchema, "selectOutputDir");
  }, [getApi]);

  // Ref: #179 — Auto-update download & install IPC

  const downloadUpdate = useCallback(async (): Promise<{ state: string }> => {
    const result = await getApi().download_update();
    const parsed = JSON.parse(result);
    return parsed as { state: string };
  }, [getApi]);

  const getDownloadProgress = useCallback(async (): Promise<DownloadProgress> => {
    const result = await getApi().get_download_progress();
    return validate<DownloadProgress>(result, DownloadProgressSchema, "getDownloadProgress");
  }, [getApi]);

  const cancelDownload = useCallback(async (): Promise<void> => {
    await getApi().cancel_download();
  }, [getApi]);

  const installUpdate = useCallback(async (): Promise<{ success: boolean; error?: string }> => {
    const result = await getApi().install_update();
    return JSON.parse(result) as { success: boolean; error?: string };
  }, [getApi]);

  return useMemo(
    () => ({
      ready,
      getVoices,
      generateTTS,
      previewTTS,
      getConfig,
      setConfig,
      getTranslations,
      playAudio,
      stopAudio,
      checkUpdate,
      getOutputDir,
      selectOutputDir,
      downloadUpdate,
      getDownloadProgress,
      cancelDownload,
      installUpdate,
    }),
    [
      ready,
      getVoices,
      generateTTS,
      previewTTS,
      getConfig,
      setConfig,
      getTranslations,
      playAudio,
      stopAudio,
      checkUpdate,
      getOutputDir,
      selectOutputDir,
      downloadUpdate,
      getDownloadProgress,
      cancelDownload,
      installUpdate,
    ]
  );
}
