/**
 * Text editor component — textarea with character count.
 *
 * Per design spec §3.7 (Textarea).
 * Ref: T18 Plan §7 — Text Editor
 */

interface TextEditorProps {
  text: string;
  onTextChange: (text: string) => void;
  placeholder?: string;
  t: (key: string) => string;
}

export function TextEditor({ text, onTextChange, placeholder, t }: TextEditorProps) {
  return (
    <div className="relative flex flex-col flex-1">
      <textarea
        id="tts-text-input"
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder={placeholder || t("text_placeholder")}
        style={{
          width: "100%",
          minHeight: 200,
          flex: 1,
          resize: "vertical",
          background: "var(--color-surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-4)",
          fontSize: 14,
          fontWeight: 400,
          lineHeight: 1.6,
          color: "var(--color-text-primary)",
          outline: "none",
          fontFamily: "inherit",
          transition: `border-color var(--duration-fast) var(--ease-default),
                       box-shadow var(--duration-fast) var(--ease-default)`,
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "var(--color-border-focus)";
          e.currentTarget.style.boxShadow = "var(--shadow-focus)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.boxShadow = "none";
        }}
      />

      {/* Character count badge */}
      <span
        style={{
          position: "absolute",
          bottom: 12,
          right: 12,
          fontSize: 11,
          fontWeight: 400,
          lineHeight: 1.4,
          letterSpacing: "0.1px",
          color: "var(--color-text-muted)",
          pointerEvents: "none",
        }}
      >
        {text.length}
      </span>
    </div>
  );
}
