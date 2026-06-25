/**
 * TypeScript interfaces for PyWebView API responses.
 *
 * Matches the JSON structures returned by src/api.py methods.
 * Ref: T18 Plan §2 — TypeScript Types
 */

/** Voice object from edge-tts voice list. */
export interface Voice {
  ShortName: string;
  Locale: string;
  Gender: string;
  FriendlyName: string;
}

/** Result from generate_tts() API call. */
export interface TTSResult {
  path?: string;
  error?: string;
}

/** Result from get_config() API call. */
export interface ConfigValue {
  value: unknown;
}

/** Result from set_config() API call. */
export interface ConfigSetResult {
  success: boolean;
  error?: string;
}

/** Result from get_translations() API call. */
export interface TranslationData {
  language: string;
  strings: Record<string, string>;
}

/** Result from play_audio() / stop_audio() API calls. */
export interface AudioResult {
  success: boolean;
  error?: string;
}

/** Result from check_update() API call. null if no update available. */
export interface UpdateInfo {
  latest: string;
  url: string;
}

/** Result from get_output_dir() / select_output_dir() API calls. */
export interface OutputDirResult {
  output_dir?: string;
  error?: string;
}

/** Toast notification variant. */
export type ToastVariant = "success" | "error" | "info";

/** Toast notification item. */
export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

/**
 * PyWebView API interface — matches window.pywebview.api methods.
 *
 * PyWebView returns all values as strings (JSON-encoded),
 * so the hook layer parses them into typed objects.
 */
export interface PyWebViewApi {
  get_voices(): Promise<string>;
  generate_tts(text: string, voice: string, rate: number, pitch: number): Promise<string>;
  preview_tts(text: string, voice: string, rate: number, pitch: number): Promise<string>;
  get_config(key: string): Promise<string>;
  set_config(key: string, value: unknown): Promise<string>;
  get_translations(): Promise<string>;
  play_audio(file_path: string): Promise<string>;
  stop_audio(): Promise<string>;
  check_update(): Promise<string>;
  get_output_dir(): Promise<string>;
  select_output_dir(): Promise<string>;
}

/** Augment the global Window interface for PyWebView. */
declare global {
  interface Window {
    pywebview?: {
      api: PyWebViewApi;
    };
  }
}
