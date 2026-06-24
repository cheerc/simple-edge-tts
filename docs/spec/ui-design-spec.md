# Simple Edge TTS — UI Design Specification

> **Status**: Draft v2 — addressing reviewer REJECTED findings (contrast, popover, radius-full)
> **Decision**: d-11 (Light Cream + Coral + Wide, operator confirmed)
> **Framework**: PyWebView + React (Vite + Tailwind CSS + shadcn/ui)
> **Target**: Desktop app (macOS / Windows), fixed landscape window ~1200×750

---

## 1. Design Tokens

### 1.1 Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-background` | `#fafafa` | App background (cream) |
| `--color-surface` | `#ffffff` | Card / panel surfaces |
| `--color-surface-hover` | `#f5f5f5` | Surface hover state |
| `--color-surface-active` | `#eeeeee` | Surface pressed/active state |
| `--color-accent` | `#cc4a35` | Primary CTA, active indicators (WCAG AA 4.57:1 with white) |
| `--color-accent-hover` | `#b8422f` | Accent hover state (5.44:1) |
| `--color-accent-active` | `#a53b2a` | Accent pressed state (6.44:1) |
| `--color-accent-subtle` | `#fff0ec` | Accent background tint (badges, highlights) |
| `--color-text-primary` | `#333333` | Primary body text |
| `--color-text-secondary` | `#666666` | Secondary / helper text |
| `--color-text-muted` | `#737373` | Placeholder, disabled text (WCAG AA 4.54:1 on cream) |
| `--color-text-on-accent` | `#ffffff` | Text on accent-colored backgrounds |
| `--color-border` | `#e5e5e5` | Default borders, dividers |
| `--color-border-focus` | `#cc4a35` | Focus ring color (= accent) |
| `--color-overlay` | `rgba(0, 0, 0, 0.4)` | Modal overlay backdrop |
| `--color-destructive` | `#dc2626` | Error / destructive actions |
| `--color-destructive-text` | `#ffffff` | Text on destructive |
| `--color-success` | `#16a34a` | Success indicators |
| `--color-warning` | `#f59e0b` | Warning indicators |
| `--color-shadow` | `rgba(0, 0, 0, 0.08)` | Card shadow |
| `--color-shadow-elevated` | `rgba(0, 0, 0, 0.12)` | Modal / dropdown shadow |

**Contrast verification (WCAG AA 4.5:1, computed via relative luminance)**:
- `#333333` on `#fafafa` → 12.10:1 ✅
- `#333333` on `#ffffff` → 12.63:1 ✅
- `#666666` on `#ffffff` → 5.74:1 ✅
- `#737373` on `#ffffff` → 4.74:1 ✅
- `#737373` on `#fafafa` → 4.54:1 ✅
- `#ffffff` on `#cc4a35` → 4.57:1 ✅ (accent buttons, normal text)
- `#ffffff` on `#b8422f` → 5.44:1 ✅ (accent hover)
- `#ffffff` on `#a53b2a` → 6.44:1 ✅ (accent active)

### 1.2 Typography

**Font stack**: `Inter, -apple-system, BlinkMacSystemFont, 'SF Pro', 'Segoe UI', system-ui, sans-serif`

| Role | Size | Weight | Line Height | Letter Spacing | Token |
|------|------|--------|-------------|----------------|-------|
| Display | 28px | 700 | 1.2 | -0.5px | `--text-display` |
| Heading | 20px | 600 | 1.3 | -0.3px | `--text-heading` |
| Subheading | 16px | 600 | 1.4 | -0.1px | `--text-subheading` |
| Body | 14px | 400 | 1.5 | 0 | `--text-body` |
| Body Small | 13px | 400 | 1.5 | 0 | `--text-body-sm` |
| Label | 12px | 500 | 1.4 | 0.2px | `--text-label` |
| Caption | 11px | 400 | 1.4 | 0.1px | `--text-caption` |

**Google Fonts import** (for PyWebView context):
```
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
```

### 1.3 Spacing Scale (4px base grid)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | — |
| `--space-1` | 4px | Tight inline spacing |
| `--space-2` | 8px | Icon-to-text gap, small insets |
| `--space-3` | 12px | Default input padding, list item gap |
| `--space-4` | 16px | Card inner padding, section gap |
| `--space-5` | 20px | Panel padding |
| `--space-6` | 24px | Section separator |
| `--space-8` | 32px | Major section gap |
| `--space-10` | 40px | Top-level panel gap |
| `--space-12` | 48px | Window padding |

### 1.4 Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Small chips, tags |
| `--radius-md` | 8px | Buttons, inputs, dropdown |
| `--radius-lg` | 12px | Cards, modals |
| `--radius-xl` | 16px | Top-level panels |
| `--radius-full` | 9999px | Pill buttons, avatar |

### 1.5 Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.05)` | Subtle elevation |
| `--shadow-card` | `0 2px 12px rgba(0,0,0,0.08)` | Cards, panels |
| `--shadow-elevated` | `0 8px 24px rgba(0,0,0,0.12)` | Modals, dropdowns |
| `--shadow-focus` | `0 0 0 3px rgba(204,74,53,0.3)` | Focus ring |

### 1.6 Animation Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-fast` | 150ms | Hover, toggle |
| `--duration-normal` | 250ms | Transitions, expand/collapse |
| `--duration-slow` | 350ms | Modal enter/exit |
| `--ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General transitions |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Bouncy/playful enter |
| `--ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Enter animations |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exit animations |

### 1.7 Z-Index Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--z-base` | 0 | Default content |
| `--z-dropdown` | 10 | Dropdown menus |
| `--z-sticky` | 20 | Sticky headers |
| `--z-overlay` | 30 | Overlay backdrops |
| `--z-modal` | 40 | Modals, dialogs |
| `--z-toast` | 50 | Toast notifications |

---

## 2. Layout Structure

### 2.1 Window Frame

```
┌──────────────────────────────────────────────────────────────┐
│  Window: ~1200 × 750 (default), min 900 × 550               │
│  Background: #fafafa                                         │
│  Content padding: 32px all sides                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              HEADER BAR (h: 48px)                       │  │
│  │  Logo/App Name (left)     Settings ⚙ (right)          │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                                                        │  │
│  │  ┌─── LEFT PANEL (40%) ───┐  ┌── RIGHT PANEL (60%) ──┐│  │
│  │  │                        │  │                        ││  │
│  │  │  Voice Selection       │  │  Text Input Area       ││  │
│  │  │  ├─ Language dropdown  │  │  (textarea, 100% h)    ││  │
│  │  │  ├─ Voice dropdown     │  │                        ││  │
│  │  │  └─ Preview button     │  │                        ││  │
│  │  │                        │  │                        ││  │
│  │  │  ────────────────────  │  │                        ││  │
│  │  │                        │  │                        ││  │
│  │  │  Voice Details         │  │                        ││  │
│  │  │  (name, gender, locale)│  │                        ││  │
│  │  │                        │  │                        ││  │
│  │  └────────────────────────┘  └────────────────────────┘│  │
│  │                                                        │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │              ACTION BAR (h: 60px)                       │  │
│  │  Speed slider │ Format select │ [Speak] [Save] buttons │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Responsive Behavior

This is a **desktop-only** app (PyWebView). No mobile breakpoints needed.
- **Default**: 1200×750 — 2-column layout (40/60 split)
- **Narrow** (< 1000px): Stack to single column (voice above text)
- **Min size**: 900×550 enforced by PyWebView config

---

## 3. Component Specifications

### 3.1 Header Bar

| Property | Value |
|----------|-------|
| Height | 48px |
| Background | transparent (inherits `--color-background`) |
| Padding | `0 --space-4` |
| Border bottom | 1px solid `--color-border` |
| App name | `--text-heading` weight 700, color `--color-text-primary` |
| Settings icon | 20×20px, `--color-text-secondary`, hover → `--color-accent` |

### 3.2 Card / Panel

| Property | Value |
|----------|-------|
| Background | `--color-surface` |
| Border | 1px solid `--color-border` |
| Border radius | `--radius-xl` (16px) |
| Shadow | `--shadow-card` |
| Padding | `--space-5` (20px) |
| Hover (if interactive) | shadow → `--shadow-elevated`, duration `--duration-fast` |

### 3.3 Button — Primary (Accent)

| Property | Value |
|----------|-------|
| Background | `--color-accent` |
| Text | `--color-text-on-accent`, `--text-body` weight 600 |
| Border radius | `--radius-md` (8px) |
| Padding | `12px 24px` |
| Min height | 40px |
| Min width | 100px |
| Hover | background → `--color-accent-hover` |
| Active | background → `--color-accent-active`, scale 0.98 |
| Disabled | opacity 0.5, cursor not-allowed |
| Focus | `--shadow-focus` ring |
| Transition | `all --duration-fast --ease-default` |
| Icon gap | `--space-2` |

### 3.4 Button — Secondary (Outline)

| Property | Value |
|----------|-------|
| Background | transparent |
| Border | 1px solid `--color-border` |
| Text | `--color-text-primary`, `--text-body` weight 500 |
| Border radius | `--radius-md` (8px) |
| Hover | background → `--color-surface-hover` |
| Active | background → `--color-surface-active` |

### 3.5 Button — Ghost

| Property | Value |
|----------|-------|
| Background | transparent |
| Border | none |
| Text | `--color-text-secondary` |
| Hover | background → `--color-surface-hover`, text → `--color-text-primary` |

### 3.6 Select / Dropdown

| Property | Value |
|----------|-------|
| Height | 40px |
| Background | `--color-surface` |
| Border | 1px solid `--color-border` |
| Border radius | `--radius-md` |
| Padding | `--space-2 --space-3` |
| Font | `--text-body` |
| Focus border | `--color-border-focus` |
| Dropdown panel | `--color-surface`, `--shadow-elevated`, `--radius-lg`, max-height 280px, overflow-y auto |
| Option height | 36px, padding `--space-2 --space-3` |
| Option hover | background `--color-surface-hover` |
| Option selected | background `--color-accent-subtle`, text `--color-accent` |

### 3.7 Textarea (Text Input Area)

| Property | Value |
|----------|-------|
| Background | `--color-surface` |
| Border | 1px solid `--color-border` |
| Border radius | `--radius-lg` |
| Padding | `--space-4` |
| Font | `--text-body`, line-height 1.6 |
| Placeholder color | `--color-text-muted` |
| Focus | border → `--color-border-focus`, `--shadow-focus` |
| Resize | vertical only |
| Min height | 200px |
| Character count | bottom-right, `--text-caption`, `--color-text-muted` |

### 3.8 Slider (Speed Control)

| Property | Value |
|----------|-------|
| Track height | 4px |
| Track color | `--color-border` |
| Track fill | `--color-accent` |
| Thumb size | 16px |
| Thumb color | `--color-accent` |
| Thumb border | 2px solid white |
| Thumb shadow | `--shadow-sm` |
| Thumb hover | scale 1.15 |
| Label | `--text-label`, displayed above thumb |
| Range | 0.5× – 2.0× |
| Step | 0.1 |

### 3.9 Action Bar

| Property | Value |
|----------|-------|
| Height | 60px |
| Background | `--color-surface` |
| Border top | 1px solid `--color-border` |
| Border radius | bottom `--radius-xl` |
| Padding | `--space-3 --space-5` |
| Layout | `flex, align-items: center, justify-content: space-between` |
| Left group | Speed slider (w: 200px) + Format select (w: 120px) |
| Right group | [Speak] primary button + [Save As...] secondary button |
| Gap | `--space-4` between elements |

### 3.10 Settings Modal

| Property | Value |
|----------|-------|
| Overlay | `--color-overlay`, backdrop-filter: blur(4px) |
| Modal width | 480px |
| Modal background | `--color-surface` |
| Border radius | `--radius-xl` |
| Shadow | `--shadow-elevated` |
| Padding | `--space-6` |
| Header | `--text-heading`, bottom border |
| Close button | top-right, ghost button, `×` icon |
| Sections | Language, Theme (future), About |
| Enter animation | scale 0.95 → 1.0 + fade in, `--duration-normal --ease-spring` |
| Exit animation | scale 1.0 → 0.95 + fade out, `--duration-fast --ease-in` |

### 3.11 Toast Notifications

| Property | Value |
|----------|-------|
| Position | bottom-center, 24px from bottom |
| Background | `--color-text-primary` |
| Text | white, `--text-body-sm` weight 500 |
| Border radius | `--radius-md` |
| Padding | `--space-3 --space-4` |
| Shadow | `--shadow-elevated` |
| Duration | auto-dismiss 4s |
| Enter | slide-up 16px + fade in |
| Exit | fade out |
| Success variant | left border 3px `--color-success` |
| Error variant | left border 3px `--color-destructive` |

---

## 4. Interaction States

### 4.1 Voice Selection Flow

1. User selects language → voice dropdown filters to matching voices
2. Voice dropdown shows: name, gender tag, locale tag
3. Selecting voice → voice details card updates with subtle fade transition
4. Preview button → plays short sample, button shows spinner during loading

### 4.2 TTS Action Flow

1. User types/pastes text in textarea (character count updates live)
2. Clicks [Speak] → button shows spinner, text "Speaking..."
3. Audio plays via HTML5 `<audio>` element
4. On completion → button returns to idle state
5. [Save As...] → native file dialog (PyWebView), then toast "Saved to ~/Downloads/..."

### 4.3 Loading States

| State | Indicator |
|-------|-----------|
| Voice list loading | Skeleton placeholders (3 lines, shimmer) |
| TTS generating | Button spinner + "Generating..." text |
| Audio playing | Accent-colored progress bar in action bar |
| File saving | Button spinner + "Saving..." |

---

## 5. Accessibility Checklist

- [ ] All text meets WCAG AA contrast (4.5:1 body, 3:1 large text)
- [ ] All interactive elements have visible focus rings (`--shadow-focus`)
- [ ] Keyboard tab order: Header → Voice panel (top-to-bottom) → Text area → Action bar
- [ ] Dropdowns keyboard navigable (arrow keys, enter, escape)
- [ ] Button loading states disable pointer events + show aria-busy
- [ ] `prefers-reduced-motion`: disable slide/scale animations, keep opacity transitions
- [ ] All icons have `aria-label` or adjacent text label
- [ ] Modal traps focus, Escape closes
- [ ] Toast uses `aria-live="polite"`
- [ ] Form labels linked to inputs with `for`/`id`

---

## 6. Tailwind CSS Token Mapping

```js
// tailwind.config.ts — extend theme
{
  colors: {
    background: '#fafafa',
    surface: {
      DEFAULT: '#ffffff',
      hover: '#f5f5f5',
      active: '#eeeeee',
    },
    accent: {
      DEFAULT: '#cc4a35',
      hover: '#b8422f',
      active: '#a53b2a',
      subtle: '#fff0ec',
    },
    text: {
      primary: '#333333',
      secondary: '#666666',
      muted: '#737373',
      'on-accent': '#ffffff',
    },
    border: {
      DEFAULT: '#e5e5e5',
      focus: '#cc4a35',
    },
    destructive: {
      DEFAULT: '#dc2626',
      text: '#ffffff',
    },
    success: '#16a34a',
    warning: '#f59e0b',
  },
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
  boxShadow: {
    sm: '0 1px 3px rgba(0,0,0,0.05)',
    card: '0 2px 12px rgba(0,0,0,0.08)',
    elevated: '0 8px 24px rgba(0,0,0,0.12)',
    focus: '0 0 0 3px rgba(204,74,53,0.3)',
  },
  fontFamily: {
    sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'SF Pro', 'Segoe UI', 'system-ui', 'sans-serif'],
  },
  fontSize: {
    display: ['28px', { lineHeight: '1.2', fontWeight: '700', letterSpacing: '-0.5px' }],
    heading: ['20px', { lineHeight: '1.3', fontWeight: '600', letterSpacing: '-0.3px' }],
    subheading: ['16px', { lineHeight: '1.4', fontWeight: '600', letterSpacing: '-0.1px' }],
    body: ['14px', { lineHeight: '1.5', fontWeight: '400' }],
    'body-sm': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
    label: ['12px', { lineHeight: '1.4', fontWeight: '500', letterSpacing: '0.2px' }],
    caption: ['11px', { lineHeight: '1.4', fontWeight: '400', letterSpacing: '0.1px' }],
  },
  transitionDuration: {
    fast: '150ms',
    normal: '250ms',
    slow: '350ms',
  },
  transitionTimingFunction: {
    default: 'cubic-bezier(0.4, 0, 0.2, 1)',
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  },
  zIndex: {
    dropdown: '10',
    sticky: '20',
    overlay: '30',
    modal: '40',
    toast: '50',
  },
}
```

---

## 7. Implementation Notes

### 7.1 CSS Custom Properties (bridge to Tailwind)

Define all tokens as CSS custom properties in `frontend/src/index.css` for runtime access from both Tailwind utility classes and JS:

```css
:root {
  --color-background: #fafafa;
  --color-surface: #ffffff;
  --color-accent: #cc4a35;
  /* ... all tokens from §1 ... */
}
```

Tailwind `theme.extend.colors` references these via `var(--color-...)` for future theme switching (dark mode).

### 7.2 shadcn/ui Integration

Map design tokens to shadcn/ui's CSS variable convention (`--background`, `--foreground`, `--primary`, etc.) in `frontend/src/index.css`:

| shadcn variable | Our token |
|-----------------|-----------|
| `--background` | `--color-background` |
| `--foreground` | `--color-text-primary` |
| `--card` | `--color-surface` |
| `--card-foreground` | `--color-text-primary` |
| `--primary` | `--color-accent` |
| `--primary-foreground` | `--color-text-on-accent` |
| `--secondary` | `--color-surface-hover` |
| `--secondary-foreground` | `--color-text-primary` |
| `--muted` | `--color-surface-hover` |
| `--muted-foreground` | `--color-text-secondary` |
| `--accent` | `--color-accent-subtle` |
| `--accent-foreground` | `--color-accent` |
| `--destructive` | `--color-destructive` |
| `--destructive-foreground` | `--color-destructive-text` |
| `--border` | `--color-border` |
| `--input` | `--color-border` |
| `--ring` | `--color-accent` |
| `--radius` | `--radius-lg` |
| `--popover` | `--color-surface` |
| `--popover-foreground` | `--color-text-primary` |

### 7.3 Component-to-Task Mapping

| Component | Task | Dependencies |
|-----------|------|-------------|
| Header Bar | T18 | — |
| Voice Selector (Language + Voice dropdowns) | T18 | T16 (IPC for voice list) |
| Text Editor (textarea + char count) | T18 | — |
| Action Bar (slider + format + buttons) | T18 | T16 (IPC for TTS) |
| Settings Modal | T19 | T16 (IPC for config) |
| Toast System | T18 | — |
| System Tray | T20 | pystray |
