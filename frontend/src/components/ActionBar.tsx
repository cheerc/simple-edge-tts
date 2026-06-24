/**
 * Action bar component — speed/pitch sliders + action buttons.
 *
 * Per design spec §3.9, §3.8 (Slider), §4.2.
 * Speed slider displays 0.5×–2.0×, converts to percentage for API.
 * Pitch slider displays -50Hz to +50Hz, passed directly to API.
 *
 * Ref: T18 Plan §8 — Action Bar
 */

import { Loader2 } from "lucide-react";

interface ActionBarProps {
  speed: number; // Multiplier value (0.5–2.0)
  onSpeedChange: (speed: number) => void;
  pitch: number; // Hz value (-50 to +50)
  onPitchChange: (pitch: number) => void;
  onSpeak: () => void;
  onSave: () => void;
  speaking: boolean;
  saving: boolean;
  disabled: boolean;
  t: (key: string) => string;
}

export function ActionBar({
  speed,
  onSpeedChange,
  pitch,
  onPitchChange,
  onSpeak,
  onSave,
  speaking,
  saving,
  disabled,
  t,
}: ActionBarProps) {
  return (
    <div
      className="flex items-center justify-between shrink-0"
      style={{
        height: 60,
        background: "var(--color-surface)",
        borderTop: "1px solid var(--border)",
        borderRadius: "0 0 var(--radius-xl) var(--radius-xl)",
        padding: "var(--space-3) var(--space-5)",
      }}
    >
      {/* Left: Speed slider */}
      <div className="flex items-center gap-3">
        <label
          htmlFor="speed-slider"
          style={{
            fontSize: 12,
            fontWeight: 500,
            lineHeight: 1.4,
            letterSpacing: "0.2px",
            color: "var(--color-text-secondary)",
            whiteSpace: "nowrap",
          }}
        >
          {t("speed")}
        </label>
        <input
          id="speed-slider"
          type="range"
          min={0.5}
          max={2.0}
          step={0.1}
          value={speed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
          style={{ width: 160 }}
        />
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-text-primary)",
            minWidth: 36,
            textAlign: "center",
          }}
        >
          {speed.toFixed(1)}×
        </span>

        {/* Pitch slider */}
        <label
          htmlFor="pitch-slider"
          style={{
            fontSize: 12,
            fontWeight: 500,
            lineHeight: 1.4,
            letterSpacing: "0.2px",
            color: "var(--color-text-secondary)",
            whiteSpace: "nowrap",
            marginLeft: "var(--space-3)",
          }}
        >
          {t("pitch")}
        </label>
        <input
          id="pitch-slider"
          type="range"
          min={-50}
          max={50}
          step={1}
          value={pitch}
          onChange={(e) => onPitchChange(parseInt(e.target.value, 10))}
          style={{ width: 160 }}
        />
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-text-primary)",
            minWidth: 48,
            textAlign: "center",
          }}
        >
          {pitch > 0 ? "+" : ""}{pitch}Hz
        </span>
      </div>

      {/* Right: Action buttons */}
      <div className="flex items-center gap-3">
        {/* Speak button — primary accent */}
        <button
          onClick={onSpeak}
          disabled={disabled || speaking || saving}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-2)",
            height: 40,
            minWidth: 100,
            padding: "0 24px",
            background: disabled || speaking || saving
              ? "var(--color-accent-main)"
              : "var(--color-accent-main)",
            color: "var(--color-text-on-accent)",
            fontSize: 14,
            fontWeight: 600,
            border: "none",
            borderRadius: "var(--radius-md)",
            cursor: disabled || speaking || saving ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            transition: `all var(--duration-fast) var(--ease-default)`,
          }}
          onMouseEnter={(e) => {
            if (!disabled && !speaking && !saving) {
              e.currentTarget.style.background = "var(--color-accent-hover)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--color-accent-main)";
          }}
          onMouseDown={(e) => {
            if (!disabled && !speaking && !saving) {
              e.currentTarget.style.background = "var(--color-accent-active)";
              e.currentTarget.style.transform = "scale(0.98)";
            }
          }}
          onMouseUp={(e) => {
            e.currentTarget.style.transform = "scale(1)";
          }}
          aria-busy={speaking}
        >
          {speaking && <Loader2 size={16} className="animate-spin" />}
          {speaking ? t("status_generating") : t("preview")}
        </button>

        {/* Save button — secondary outline */}
        <button
          onClick={onSave}
          disabled={disabled || speaking || saving}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-2)",
            height: 40,
            minWidth: 100,
            padding: "0 24px",
            background: "transparent",
            color: "var(--color-text-primary)",
            fontSize: 14,
            fontWeight: 500,
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            cursor: disabled || saving || speaking ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            transition: `all var(--duration-fast) var(--ease-default)`,
          }}
          onMouseEnter={(e) => {
            if (!disabled && !saving && !speaking) {
              e.currentTarget.style.background = "var(--color-surface-hover)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
          onMouseDown={(e) => {
            if (!disabled && !saving && !speaking) {
              e.currentTarget.style.background = "var(--color-surface-active)";
            }
          }}
          aria-busy={saving}
        >
          {saving && <Loader2 size={16} className="animate-spin" />}
          {saving ? t("status_saving") : t("export_mp3")}
        </button>
      </div>
    </div>
  );
}
