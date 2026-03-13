# Habla Hermano Design System

> Living reference for the visual language, tokens, and component patterns of the Habla Hermano language tutor.

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Warm & Approachable** | A tutor, not a textbook. Typography, color, and motion should feel encouraging. |
| **Mobile-First** | Most learners study on phones. Every layout starts at 375px and scales up. |
| **Theme-Aware** | All color is expressed through CSS custom properties — never hard-coded hex values. |
| **Accessible by Default** | WCAG AA minimum. High-contrast mode support. Reduced-motion respected. |
| **Celebrate Progress** | Micro-interactions at learning milestones reinforce habit formation. |

---

## 2. Color System

### 2.1 Token Architecture

Every theme defines the same set of CSS custom properties on `[data-theme="..."]`. Components reference tokens, never raw colors.

```
Surface Layer        Text Layer           Interactive Layer
─────────────        ──────────           ─────────────────
--surface            --text               --accent
--surface-elevated   --text-muted         --accent-hover
--surface-overlay    --text-subtle        --accent-muted
                                          --accent-text

Chat Layer           Feedback Layer       Chrome Layer
──────────           ──────────────       ────────────
--user-bubble        --success            --border
--user-text          --success-muted      --border-subtle
--ai-bubble          --error              --shadow-color
--ai-text            --error-muted        --scrollbar-*
```

### 2.2 Themes

#### Azulejo (Light — Default)
Inspiration: Portuguese ceramic tiles, cobalt blue, whitewashed walls.

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#FBF8F4` | Page background |
| `--surface-elevated` | `#FFFFFF` | Cards, header |
| `--surface-overlay` | `#F0EDE7` | Hover states, overlays |
| `--border` | `#D4CFC6` | Dividers, input borders |
| `--text` | `#1E293B` | Primary text |
| `--text-muted` | `#4B5563` | Secondary text |
| `--text-subtle` | `#7C8494` | Tertiary / placeholder |
| `--accent` | `#1D4ED8` | Links, CTA, interactive |
| `--accent-hover` | `#1E40AF` | Hover state |
| `--user-bubble` | `#2563EB` | User message bg |
| `--ai-bubble` | `#F0EDE7` | AI message bg |
| `--success` | `#059669` | Correct answers |
| `--error` | `#DC2626` | Errors, wrong answers |

#### Terracotta (Dark — Warm)
Inspiration: Andalusian earth, warm clay, parchment cream.

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#1C1410` | Page background |
| `--surface-elevated` | `#2A1F18` | Cards, header |
| `--surface-overlay` | `#362A21` | Hover states |
| `--border` | `#4A3B30` | Dividers |
| `--text` | `#F2E8DE` | Primary text |
| `--text-muted` | `#BFA98F` | Secondary text |
| `--accent` | `#E07A5F` | Burnt orange interactive |
| `--accent-hover` | `#EE9A7F` | Hover state |
| `--user-bubble` | `#C85A3A` | User message bg |
| `--ai-bubble` | `#2A1F18` | AI message bg |
| `--success` | `#A3B18A` | Sage green |
| `--error` | `#E76F51` | Burnt sienna |

#### Flamenco (Dark — Dramatic)
Inspiration: Passionate night, red drama, black stage, gold accents.

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#110A0A` | Page background |
| `--surface-elevated` | `#1E1214` | Cards, header |
| `--surface-overlay` | `#2D1B1E` | Hover states |
| `--border` | `#4A2D32` | Dividers |
| `--text` | `#FAE8E8` | Primary text |
| `--text-muted` | `#C9A3A8` | Secondary text |
| `--accent` | `#DC2626` | Vibrant red interactive |
| `--accent-hover` | `#EF4444` | Hover state |
| `--user-bubble` | `#B91C1C` | User message bg |
| `--ai-bubble` | `#1E1214` | AI message bg |
| `--success` | `#CA8A04` | Amber / gold |
| `--error` | `#FB7185` | Pink |

#### Sangria (Dark — Cool)
Inspiration: Mediterranean dusk, wine purple, sunset amber.

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#1A0F1E` | Page background |
| `--surface-elevated` | `#261528` | Cards, header |
| `--surface-overlay` | `#331E36` | Hover states |
| `--border` | `#4C2E52` | Dividers |
| `--text` | `#F3E8FF` | Primary text |
| `--text-muted` | `#C4A5D4` | Secondary text |
| `--accent` | `#C084FC` | Vivid purple interactive |
| `--accent-hover` | `#D8B4FE` | Hover state |
| `--user-bubble` | `#9333EA` | User message bg |
| `--ai-bubble` | `#261528` | AI message bg |
| `--success` | `#F59E0B` | Amber |
| `--error` | `#FB7185` | Pink |

### 2.3 Contrast Audit (Known Issues)

| Theme | Token | Current | Ratio | WCAG AA Target | Suggested Fix |
|-------|-------|---------|-------|----------------|---------------|
| Terracotta | `--text-muted` | `#BFA98F` on `#1C1410` | ~4.1:1 | 4.5:1 | `#D4BC9E` (~5.2:1) |
| Flamenco | `--border` | `#4A2D32` on `#110A0A` | ~1.8:1 | 3:1 (UI) | `#6B3D44` (~2.8:1) |
| Sangria | `--text-subtle` | `#8B6FA0` on `#1A0F1E` | ~3.2:1 | 4.5:1 | `#A88BC0` (~4.5:1) |

---

## 3. Typography

### 3.1 Font Stack

| Role | Font | Fallback | Weight Range |
|------|------|----------|-------------|
| **Display** | Fraunces | Georgia, serif | 600–700 |
| **Body** | Inter | system-ui, -apple-system, sans-serif | 400–600 |
| **Mono** | JetBrains Mono | monospace | 400 |

### 3.2 Tailwind Config

```js
fontFamily: {
  display: ['Fraunces', 'Georgia', 'serif'],
  sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
  mono: ['JetBrains Mono', 'monospace'],
}
```

### 3.3 Type Scale

| Element | Size (mobile) | Size (desktop) | Weight | Font |
|---------|--------------|----------------|--------|------|
| Page title | 1.5rem (24px) | 1.875rem (30px) | 600 | Display |
| Section heading | 1.25rem (20px) | 1.5rem (24px) | 600 | Display |
| Body text | 1rem (16px) | 1rem (16px) | 400 | Sans |
| Chat message | 0.9375rem (15px) | 1rem (16px) | 400 | Sans |
| Label / caption | 0.75rem (12px) | 0.8125rem (13px) | 500 | Sans |
| Code / vocab | 0.875rem (14px) | 0.875rem (14px) | 400 | Mono |

### 3.4 Typography Rules

- Headings and `.font-display`: `letter-spacing: -0.01em`
- Target words, `em`, `i` in AI responses: Fraunces italic, colored with `--accent`
- Body line-height: `1.5`–`1.75`
- Max line length: 65–75 characters (`max-w-prose`)
- Minimum mobile font size: 16px (prevents iOS auto-zoom)

### 3.5 Recommended Upgrade Path

**Candidate**: Swap Inter → **Plus Jakarta Sans** for warmer letterforms with near-identical metrics. Minimal layout disruption, friendlier personality.

---

## 4. Spacing & Layout

### 4.1 Spacing Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--space-chat-gap` | `0.75rem` (12px) | Gap between chat messages |
| `--space-bubble-pad` | `1rem` (16px) | Padding inside chat bubbles |
| `--space-section-gap` | `2rem` (32px) | Between major UI sections |
| `--space-input-height` | `3rem` (48px) | Input / button min-height (touch target) |

### 4.2 Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-bubble` | `1rem` (16px) | Chat bubbles |
| `--radius-button` | `0.75rem` (12px) | Buttons |
| `--radius-card` | `1rem` (16px) | Lesson cards |
| `--radius-input` | `0.75rem` (12px) | Inputs, textareas |

### 4.3 Container Widths

| Context | Max-Width | Tailwind Class |
|---------|-----------|---------------|
| Chat messages | 48rem (768px) | `max-w-3xl` |
| Lesson list | 56rem (896px) | `max-w-4xl` |
| Chat bubbles (desktop) | 85% of container | — |
| Chat bubbles (mobile) | 90% of container | — |

### 4.4 Breakpoints

| Name | Width | Usage |
|------|-------|-------|
| Default | 0–639px | Mobile (primary) |
| `sm` | 640px+ | Tablet and above |

### 4.5 Safe Areas

```css
.safe-top    { padding-top: env(safe-area-inset-top); }
.safe-bottom { padding-bottom: env(safe-area-inset-bottom); }
.safe-x      { padding-left: env(safe-area-inset-left);
               padding-right: env(safe-area-inset-right); }
```

---

## 5. Components

### 5.1 Chat Bubbles

```
┌──────────────────────────────┐
│  User Bubble                 │  Right-aligned
│  bg: --user-bubble           │  text: --user-text
│  rounded-2xl rounded-br-md   │  max-w: 85% / 90% mobile
│  shadow-sm                   │
└──────────────────────────────┘

┌──────────────────────────────┐
│  AI Bubble                   │  Left-aligned
│  bg: --ai-bubble             │  text: --ai-text
│  rounded-2xl rounded-bl-md   │  max-w: 85% / 90% mobile
│  shadow-sm                   │  Supports markdown content
└──────────────────────────────┘
```

### 5.2 Buttons

| Variant | Background | Text | Border | Min Height |
|---------|-----------|------|--------|-----------|
| Primary | `--accent` | `--accent-text` | none | 48px (mobile) |
| Secondary | `--surface-overlay` | `--text-muted` | `--border` | 48px (mobile) |
| Ghost | transparent | `--accent` | none | 48px (mobile) |

All buttons: `rounded-xl`, `transition-colors duration-200`, `cursor-pointer`, `active:scale-95`.

### 5.3 Badges & Chips

| Type | Background | Text | Example |
|------|-----------|------|---------|
| Level badge | `--accent-muted` | `--accent` | `A1`, `B1` |
| Vocabulary chip | `--surface-overlay` | `--text` | New words |
| Success badge | `--success-muted` | `--success` | Correct |
| Error badge | `--error-muted` | `--error` | Incorrect |

### 5.4 Input Area

- Textarea with auto-grow (1 → multiple rows)
- Min height: 48px (touch target)
- Border: `--border`, focus: `--accent` with ring
- Rounded: `xl` (0.75rem)
- Font size: 16px minimum (prevents iOS zoom)
- Placeholder: language-dependent hint text

### 5.5 Lesson Cards

```
┌─────────────────────────────────┐
│  🇪🇸  Lesson Title              │  Icon + title row
│  Brief description of lesson    │  Description
│  ┌──────┐                       │
│  │  A1  │  Topic tag            │  Level badge + metadata
│  └──────┘                       │
└─────────────────────────────────┘
```

Rounded: `--radius-card`. Hover: `hover-lift` (translateY -2px + shadow). Clickable: `cursor-pointer`.

### 5.6 Voice UI

| Component | Style | Size |
|-----------|-------|------|
| TTS play button | Circle, `--accent` bg | 28px |
| TTS speed pill | Pill shape, `--surface-overlay` bg | Auto |
| Mic button | Circle, toggles red on recording | 44px min |
| Error tooltip | Positioned above button, `--error` border | Auto |
| Processing indicator | Pill above mic, pulse animation | Auto |

---

## 6. Animation & Motion

### 6.1 Timing Defaults

| Category | Duration | Easing |
|----------|----------|--------|
| Micro-interaction | 150–200ms | `ease-out` |
| State transition | 200–300ms | `ease-in-out` |
| Entry animation | 300–400ms | `ease-out` |
| Celebration | 400–600ms | `cubic-bezier(0.34, 1.56, 0.64, 1)` |

### 6.2 Defined Keyframes

| Animation | Description | Duration | Usage |
|-----------|-------------|----------|-------|
| `fadeIn` | Opacity 0→1 | 400ms | General entrance |
| `slideUp` | Opacity + translateY 12px→0 | 400ms | Message entrance |
| `pulseSubtle` | Opacity pulse | 2s | Waiting states |
| `warmGlow` | Box-shadow bloom | 600ms | Success feedback |
| `checkDraw` | SVG stroke draw | 400ms | Checkmark animation |
| `gentleBounce` | Scale 0.95→1.02→1 | 500ms | Button press |
| `float` | TranslateY oscillation | 3s | Decorative |
| `loadingDot` | Scale pulse (staggered) | 1.6s | Typing indicator |
| `voicePulse` | Red ring pulse | 1.5s | Recording state |
| `voiceSpin` | 360deg rotation | 600ms | Processing spinner |

### 6.3 Animation Classes

| Class | Animation | Trigger |
|-------|-----------|---------|
| `.message-enter` | slideUp | New message appears |
| `.loading-dots` | loadingDot (×3, staggered) | AI thinking |
| `.streaming-cursor` | Blinking caret | Token-by-token display |
| `.success-glow` | warmGlow | Correct answer |
| `.check-draw` | checkDraw | Exercise pass |
| `.hover-lift` | translateY + shadow | Card hover |
| `.btn-press` | scale(0.95) | Button active |
| `.theme-transition` | Color transition | Theme switch |

### 6.4 Reduced Motion

All animations collapse to `0.01ms` when `prefers-reduced-motion: reduce` is active. This is enforced globally in `input.css`.

### 6.5 Recommended Additions

| Moment | Animation | Description |
|--------|-----------|-------------|
| Correct answer | `confetti-burst` | 3–5 small particles, 400ms |
| New vocabulary | `vocab-highlight` | Accent underline draws left-to-right, 300ms |
| Level/phase change | `level-badge-pop` | Scale 0→1.1→1, bounce, 500ms |
| Lesson complete | `progress-shimmer` | Gradient sweep on progress bar |
| Streak increment | `progress-fill` | Width ease-out animation |

---

## 7. Accessibility

### 7.1 Standards

- **Target**: WCAG 2.1 AA
- **Text contrast**: 4.5:1 minimum (body), 3:1 (large text / UI)
- **Touch targets**: 44×44px minimum on mobile (enforced via `min-h-[44px]`)
- **Focus rings**: `focus-visible:ring-2 ring-[--accent] ring-offset-2`
- **High-contrast mode**: Thicker borders, higher color saturation
- **Reduced-motion**: All animations disabled

### 7.2 ARIA Patterns

| Component | ARIA |
|-----------|------|
| Chat messages | `role="log"`, `aria-live="polite"` on container |
| Send button | `aria-label="Send message"` |
| Mic button | `aria-label="Start voice input"`, `aria-pressed` |
| Theme switcher | `aria-label="Change theme"` |
| Lesson progress | `role="progressbar"`, `aria-valuenow`, `aria-valuemax` |
| Voice status | `aria-live="polite"` region for STT state changes |

### 7.3 Keyboard Navigation

- Tab order matches visual order (left-to-right, top-to-bottom)
- `Escape` closes modals / menus
- `Enter` sends message (textarea uses `Shift+Enter` for newline)
- All interactive elements reachable via keyboard

---

## 8. Icons

### 8.1 Current State

The app uses emoji characters as semantic indicators (💡 for corrections, 📝 for vocabulary). These render inconsistently across platforms and are not screen-reader friendly.

### 8.2 Recommended Approach

Use **Lucide** SVG icons (or Heroicons) for all semantic UI elements:

| Current Emoji | Replacement Icon | Lucide Name |
|--------------|-----------------|-------------|
| 💡 | Lightbulb SVG | `lightbulb` |
| 📝 | Notebook SVG | `book-open` |
| ✅ | Checkmark circle SVG | `check-circle` |
| ❌ | X circle SVG | `x-circle` |
| 🎯 | Target SVG | `target` |

Flag emojis (🇪🇸, 🇩🇪, 🇫🇷) are acceptable — they carry cultural meaning and render well on all platforms.

---

## 9. Libraries & Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| Tailwind CSS | CDN (dev) | Utility-first CSS |
| HTMX | 1.9.10 | Hypermedia interactions |
| Alpine.js | 3.13.3 | Lightweight reactivity |
| Animate.css | 4.1.1 | Utility animations |
| Google Fonts | — | Inter, JetBrains Mono, Fraunces |

### 9.1 Font Loading

Fonts loaded via Google Fonts API with `display=swap` for fast initial render. Critical weights (400, 600) preloaded; decorative weights (300, 700) lazy-loaded.

---

## 10. Improvement Roadmap

Prioritized changes to evolve the design system.

### Tier 1 — Do First (Low effort, High impact)

- [ ] Fix dark theme contrast issues (Terracotta, Flamenco, Sangria muted text)
- [ ] Replace emoji semantic indicators with SVG icons (Lucide)
- [ ] Add `focus-visible` ring to theme switcher and all interactive chrome
- [ ] Add `aria-live="polite"` to voice status region

### Tier 2 — Do Second (Medium effort, High impact)

- [ ] Add a second light theme ("Jardín" — green/indigo learning palette)
- [ ] Evaluate Plus Jakarta Sans as Inter replacement (A/B if possible)
- [ ] Define and apply spacing tokens as CSS custom properties
- [ ] Add AI response feedback buttons (thumbs up/down)

### Tier 3 — Plan Next (Medium effort, Medium impact)

- [ ] Implement learning celebration micro-interactions (confetti, vocab highlight)
- [ ] Add segmented step indicator for lesson phases
- [ ] Add `progress-shimmer` animation on lesson completion
- [ ] Narrow desktop chat bubbles from 85% to 75% max-width

### Tier 4 — Nice to Have

- [ ] Add subtle left-border accent on AI bubbles for visual distinction
- [ ] Hover-to-expand definitions on vocabulary chips
- [ ] Phase transition label animations ("Practice Time!")
- [ ] Haptic feedback hints for mobile (via `navigator.vibrate`)
