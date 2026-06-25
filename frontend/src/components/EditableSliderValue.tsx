/**
 * Inline click-to-edit numeric value for sliders.
 *
 * Default: renders a <span> with the formatted value.
 * Click: switches to <input>, auto-focuses + selects all.
 * Blur/Enter: validates, clamps to [min, max], calls onChange, returns to span.
 * Escape: cancels edit, restores original value.
 *
 * Ref: #65 — Slider editable input
 */

import { useState, useRef, useCallback } from "react";

interface EditableSliderValueProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  /** Format the numeric value for display, e.g. "1.0×" or "+5Hz" */
  format: (value: number) => string;
  /** Parse user input string to number. Defaults to parseFloat. */
  parse?: (input: string) => number;
  style?: React.CSSProperties;
}

export function EditableSliderValue({
  value,
  onChange,
  min,
  max,
  step,
  format,
  parse = parseFloat,
  style,
}: EditableSliderValueProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const startEditing = useCallback(() => {
    setEditValue(String(value));
    setEditing(true);
    // Focus + select after React renders the input
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
  }, [value]);

  const commitEdit = useCallback(() => {
    const parsed = parse(editValue);
    if (!isNaN(parsed)) {
      // Clamp to range and snap to step
      const clamped = Math.min(max, Math.max(min, parsed));
      const snapped = Math.round(clamped / step) * step;
      // Fix floating point: round to step's decimal places
      const decimals = step < 1 ? String(step).split(".")[1]?.length ?? 0 : 0;
      onChange(Number(snapped.toFixed(decimals)));
    }
    setEditing(false);
  }, [editValue, parse, min, max, step, onChange]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        commitEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelEdit();
      }
    },
    [commitEdit, cancelEdit]
  );

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="text"
        inputMode="decimal"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={commitEdit}
        onKeyDown={handleKeyDown}
        style={{
          ...style,
          width: 50,
          fontSize: 12,
          fontWeight: 600,
          padding: "1px 4px",
          border: "1px solid var(--color-border-focus)",
          borderRadius: 4,
          background: "var(--color-surface)",
          color: "var(--color-text-primary)",
          outline: "none",
          textAlign: "center",
          boxSizing: "border-box",
        }}
      />
    );
  }

  return (
    <span
      onClick={startEditing}
      title="Click to edit"
      style={{
        ...style,
        cursor: "pointer",
        borderBottom: "1px dashed var(--color-text-muted)",
        userSelect: "none",
      }}
    >
      {format(value)}
    </span>
  );
}
