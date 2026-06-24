---
title: "T18: React UI Components — Design Spec Implementation"
complexity: complex+
required_reads:
  - docs/spec/ui-design-spec.md  # Full design spec (tokens, components, interactions)
  - src/api.py  # IPC bridge (T16) — all 7 API methods consumed by frontend
  - src/main.py  # PyWebView window setup (dev/prod URL detection)
  - frontend/src/index.css  # Current Tailwind/shadcn theme (to be replaced)
  - frontend/src/App.tsx  # Current scaffold (to be rewritten)
  - frontend/src/main.tsx  # React entry point
  - frontend/src/components/ui/button.tsx  # Existing shadcn button (may need re-theme)
  - frontend/vite.config.ts  # Vite config
  - frontend/package.json  # Current dependencies
---

# T18: React UI Components — Design Spec Implementation

> **Decision**: d-11 (Light Cream + Coral + Wide), d-12 (wave plan)
> **Base SHA**: `83411e2` (origin/main, post-T16 merge)
> **Branch**: `feat/t18-react-ui`
> **PR target**: `main`

## Overview

Build the complete React UI for Simple Edge TTS, implementing all components from
the design spec (§3) with the design token system (§1). The UI replaces the current
scaffold `App.tsx` with a fully functional 2-column wide layout connected to the
PyWebView IPC bridge (`window.pywebview.api.*`).

## Scope

### Files to Create
- `frontend/src/components/Header.tsx` — App header bar (§3.1)
- `frontend/src/components/VoiceSelector.tsx` — Language + voice dropdowns (§3.6, §3.7)
- `frontend/src/components/TextEditor.tsx` — Textarea with char count (§3.8)
- `frontend/src/components/ActionBar.tsx` — Speed slider + format select + action buttons (§3.9)
- `frontend/src/components/Toast.tsx` — Toast notification system (§3.11)
- `frontend/src/hooks/useApi.ts` — PyWebView IPC hook (wraps `window.pywebview.api`)
- `frontend/src/hooks/useToast.ts` — Toast state management
- `frontend/src/types.ts` — TypeScript interfaces for API responses

### Files to Modify
- `frontend/src/App.tsx` — Rewrite with 2-column layout, wire all components
- `frontend/src/index.css` — Replace theme with design spec tokens (§1, §6, §7)

### Files Unchanged
- `frontend/src/main.tsx` — Keep as-is
- `frontend/src/lib/utils.ts` — Keep as-is (cn utility)
- `frontend/src/components/ui/button.tsx` — shadcn component, theme picks up from CSS vars

## Implementation Plan

### Section 1: Design Token System (~80 lines)

**File**: `frontend/src/index.css`

Replace the current shadcn default theme (oklch values) with the design spec's token
system. Define all CSS custom properties from §1 in `:root`, then map to shadcn
variable convention per §7.2.

Key changes:
- **Add** Google Fonts import for Inter (400-700)
- **Replace** `:root` oklch values with design spec hex values
- **Add** all `--color-*`, `--space-*`, `--radius-*`, `--shadow-*`, `--duration-*`, `--ease-*`, `--z-*` tokens from §1
- **Map** shadcn variables (`--background`, `--foreground`, `--primary`, etc.) to our tokens per §7.2
- **Add** `--popover` and `--popover-foreground` mappings
- **Keep** `@import "tailwindcss"` and shadcn imports
- **Note**: Using Tailwind v4 `@theme inline` block in CSS (no separate `tailwind.config.ts` needed). The `@theme` block in `index.css` already defines color/radius/shadow tokens that Tailwind consumes.

### Section 2: TypeScript Types (~40 lines)

**File**: `frontend/src/types.ts`

Define interfaces for all API response shapes:
- `Voice` — `{ ShortName: string; Locale: string; Gender: string; FriendlyName: string }`
- `TTSResult` — `{ path?: string; error?: string }`
- `ConfigValue` — `{ value: unknown }`
- `TranslationData` — `{ language: string; strings: Record<string, string> }`
- `ApiResponse<T>` — generic wrapper for success/error responses

### Section 3: IPC Hook (~60 lines)

**File**: `frontend/src/hooks/useApi.ts`

Custom React hook wrapping `window.pywebview.api.*` calls:
- **Ensure** `window.pywebview` exists before calling (PyWebView injects it)
- **Add** `pywebviewReady` event listener for when API becomes available
- Methods: `getVoices()`, `generateTTS(text, voice, rate, pitch)`, `getConfig(key)`, `setConfig(key, value)`, `getTranslations()`, `playAudio(path)`, `stopAudio()`
- Each method: call API → parse JSON response → return typed result
- **Add** loading/error states

### Section 4: Toast System (~50 lines)

**Files**: `frontend/src/hooks/useToast.ts`, `frontend/src/components/Toast.tsx`

- `useToast` hook: manages toast queue (add, remove, auto-dismiss after 4s)
- `Toast` component: renders positioned at bottom-center per §3.11
  - Background: `--color-text-primary`, text white
  - Success/error variants with left border
  - Slide-up + fade-in enter animation
  - Fade-out exit animation

### Section 5: Header Component (~30 lines)

**File**: `frontend/src/components/Header.tsx`

Per §3.1:
- Height 48px, transparent bg
- App name "Simple Edge TTS" with `--text-heading` weight 700
- Settings icon (gear from lucide-react), 20×20px
- Settings icon hover → accent color
- Settings icon onClick → no-op for T18 (wired to Settings Modal in T19)
- Bottom border 1px `--color-border`

### Section 6: Voice Selector Component (~80 lines)

**File**: `frontend/src/components/VoiceSelector.tsx`

Per §3.6 (Select/Dropdown), §4.1 (Voice Selection Flow):
- On mount: call `api.getVoices()` to get voice list
- **Language dropdown** (§3.6): Select component with grouped languages extracted from voice locales
- **Voice dropdown** (§3.6): Filtered by selected language, shows voice name + gender badge
- Voice preview tag showing selected voice
- Loading skeleton while voices fetch
- Expose `selectedVoice` state to parent

### Section 7: Text Editor Component (~50 lines)

**File**: `frontend/src/components/TextEditor.tsx`

Per §3.7 (Textarea):
- Textarea with `--text-body`, min height 200px, grows with content
- Character count badge (bottom-right corner)
- Placeholder text from i18n or default "Enter text to speak..."
- Focus ring `--shadow-focus`
- Expose `text` state to parent

### Section 8: Action Bar Component (~80 lines)

**File**: `frontend/src/components/ActionBar.tsx`

Per §3.9, §3.8 (Slider), §4.2:
- Height 60px, bottom of right panel
- **Speed slider** (w: 200px): displays `0.5×–2.0×` per §3.8, step 0.1×
  - Internal conversion: multiplier → API percentage (e.g. `1.0× → 0`, `0.5× → -50`, `2.0× → +100`)
  - Formula: `percentage = (multiplier - 1.0) × 100`
  - Default: `1.0×` (= 0%)
- **Format select** (w: 120px): mp3 / webm options
  - NOTE: `api.py generate_tts()` currently has no `format` parameter — impl should either extend the API to accept format, or remove this control if format is auto-determined. Discovery item.
- **[Speak] button**: Primary accent, calls `api.generateTTS()` → `api.playAudio()`
  - Loading state with spinner during generation
  - Success/error toast feedback
- **[Save As...] button**: Secondary outline, calls `api.generateTTS()` only
  - Success toast with file path

### Section 9: App Layout (~60 lines)

**File**: `frontend/src/App.tsx`

Per §2.1 layout:
- 2-column layout: left panel (40%) + right panel (60%)
- Left panel: VoiceSelector
- Right panel: TextEditor + ActionBar
- Header spans full width
- Toast system mounted at root
- State management: lift `selectedVoice`, `text`, `rate`, `format` to App level
- Wire IPC calls through `useApi` hook

## Verification Steps

1. `cd frontend && npm run build` — TypeScript compiles without errors
2. `cd frontend && npm run lint` — No lint errors
3. Visual verification (manual):
   - 2-column layout renders correctly at default 1200×750
   - Responsive: resize to <1000px → single column (voice above text, per §2.2)
   - Design tokens (coral accent `#cc4a35`, cream bg `#fafafa`) applied
   - Voice selector populates from API
   - Speak/Save buttons trigger TTS via IPC
   - Toast notifications appear on success/error
   - Focus ring (`--shadow-focus`) visible when tabbing through controls
   - Keyboard tab order follows visual layout (header → voice → text → action bar)
4. `uv run pytest tests/` — Existing Python tests still pass (no Python changes in T18)

## Affected Tests

- No Python test changes (T18 is frontend-only)
- Frontend lint via `npm run lint` (oxlint)
- TypeScript type checking via `npm run build` (tsc)

## General's Directive

> T18 完成時截一張實際畫面圖（main view，含 coral accent 按鈕/slider）→ 回報 General → 轉 operator 眼驗 coral 深淺實際效果

After implementation, capture a screenshot of the rendered UI for General/operator review.

## Out of Scope

- Settings Modal (T19)
- System Tray (T20)
- CI/CD updates (T21)
- Dark mode (future)
