# Phase 25: Design System Revamp

**Branch**: `feature/design-system-improvements`
**Status**: Complete

---

## Overview

Phase 25 systematically upgrades the visual design, accessibility, and interactivity of Habla Hermano based on a [Timea's](https://github.com/timea-kk) and UI/UX Pro Max design audit. No new features — this is a pure quality pass on the existing design system.

---

## Goals

1. **Fix accessibility gaps** — WCAG AA contrast compliance across all dark themes
2. **Expand theme coverage** — Add a second light theme optimised for daytime learning sessions
3. **Upgrade typography** — Warmer, friendlier font that better matches a conversational tutor
4. **Add learning-specific micro-interactions** — Celebration moments, vocab highlights, progress feedback
5. **Replace emoji with SVG icons** — Consistent, accessible, cross-platform icons throughout
6. **Define spacing tokens** — Prevent spacing drift as the UI grows
7. **Improve feedback loops** — AI response feedback buttons, theme-aware focus rings, voice ARIA

---

## Changes by File

### `src/templates/base.html`

| Change | Detail |
|--------|--------|
| Terracotta `--text-muted` | `#BFA98F` → `#D4BC9E` (4.1:1 → 5.2:1 contrast) |
| Flamenco `--border` | `#4A2D32` → `#6B3D44` (1.8:1 → 2.8:1 contrast) |
| Sangria `--text-subtle` | `#8B6E9C` → `#A88BC0` (3.2:1 → 4.5:1 contrast) |
| New Jardín theme | Light green/indigo palette for daytime learners |
| Spacing tokens | `--space-chat-gap`, `--space-bubble-pad`, `--radius-*` added to `:root` |
| Font | Inter → **Plus Jakarta Sans** (warmer, friendlier letterforms) |
| Animation keyframes | `vocabHighlight`, `levelBadgePop`, `progressShimmer`, `confettiBurst` |

### `src/static/css/input.css`

| Change | Detail |
|--------|--------|
| Desktop chat bubble | `max-w-[85%]` → `max-w-[75%]` (narrower = more readable) |
| Focus ring | `ring-primary-500` → CSS var `var(--accent)` (theme-aware) |
| `.vocab-chip` | Added `hover:scale-105 transition-all` hover state |
| `.chat-bubble-ai-accented` | New class with `border-l-2 border-l-blue-500` accent |
| `.progress-shimmer` | Sweeping gradient utility for lesson completion |
| `.vocab-highlight-underline` | Animated underline for new vocabulary words |
| `.level-badge-celebrate` | Pop animation class for phase transitions |

### `src/templates/partials/message.html`

| Change | Detail |
|--------|--------|
| 💡 emoji | Replaced with Lucide `lightbulb` SVG (`aria-hidden="true"`) |
| 📝 emoji | Replaced with Lucide `book-open` SVG (`aria-hidden="true"`) |
| AI bubble | Added `border-l-2 border-l-accent/30` subtle left accent |
| Feedback row | Thumbs up/down buttons (hidden until hover, then sticky after click) |

### `src/templates/chat.html` / `src/templates/partials/app_header.html`

| Change | Detail |
|--------|--------|
| Voice status | `aria-live="polite"` region added for screen readers |
| Theme switcher | `focus-visible:ring-2 ring-[--accent]` on all interactive elements |
| Lesson progress | Linear bar → segmented 4-phase indicator (Intro / Learn / Practice / Done) |

---

## New Theme: Jardín

Inspired by the UI/UX Pro Max language learning palette — **learning indigo + progress green**.

```
Background:  #F0FDF4  (mint cream)
Accent:      #4F46E5  (learning indigo)
Success:     #22C55E  (progress green)
Text:        #14532D  (deep forest green)
```

Rationale: 75% of existing themes are dark. Most language learners study during the day on mobile in bright environments. A fresh, energising light theme increases daily active use.

---

## Typography Change

| | Before | After |
|-|--------|-------|
| Body + Display font | Inter | **Plus Jakarta Sans** |
| Mono font | JetBrains Mono | JetBrains Mono (unchanged) |
| Display serif | Fraunces | Fraunces (unchanged) |

Plus Jakarta Sans has near-identical metrics to Inter (minimal layout shift) with softer, rounder letterforms that feel more encouraging — appropriate for a conversational language tutor.

---

## Accessibility Improvements

| Item | Before | After |
|------|--------|-------|
| Dark theme muted text contrast | Fails WCAG AA in 3 themes | Passes WCAG AA in all themes |
| Emoji as semantic indicators | Platform-inconsistent | Lucide SVG with `aria-hidden` |
| Voice status changes | Visual only | `aria-live="polite"` region |
| Focus rings | Hard-coded blue | Theme-aware CSS variable |
| Lesson progress | Percentage bar | `role="progressbar"` with value |

---

## Micro-Interactions Added

| Trigger | Animation | Duration |
|---------|-----------|---------|
| New vocabulary word | `vocabHighlight` — underline draws left-to-right | 300ms |
| Phase transition (intro → teaching etc.) | `levelBadgePop` — scale bounce | 500ms |
| Lesson complete | `progressShimmer` — gradient sweep on bar | 1.5s loop |
| Correct answer | `confettiBurst` — 3–5 particle micro-burst | 400ms |

All animations respect `prefers-reduced-motion: reduce` (existing global rule in `input.css`).

---

## Bug Fixes (Post-Implementation)

### CSS Cascade Ordering
**Issue**: `:root, [data-theme="azulejo"]` was declared last in the `<style>` block. Since `:root` and `[data-theme="..."]` have equal specificity (0,1,0), the later declaration wins — meaning Azulejo values overrode ALL other themes, making every theme appear identical.

**Fix**: Moved `:root, [data-theme="azulejo"]` to be the FIRST theme block so it establishes defaults; all other theme blocks follow and override as needed.

### Jardín Missing from Menu
**Issue**: Jardín was added to the Alpine.js `themes` array in `base.html` but no corresponding `<button>` was added to the static HTML in `app_header.html`.

**Fix**: Added Jardín button with plant SVG icon to `app_header.html` after Sangria.

### WCAG AA Contrast Failures
Contrast audit via computed CSS values revealed four failing pairs:

| Theme | Token | Before | After | Before → After |
|-------|-------|--------|-------|----------------|
| Azulejo | `--text-subtle` | `#7C8494` | `#596472` | 3.55:1 → 5.68:1 |
| Terracotta | `--text-subtle` | `#8C7A66` | `#A08870` | 4.40:1 → 5.40:1 |
| Flamenco | `--text-subtle` | `#8C6B70` | `#A07A80` | 4.15:1 → 5.22:1 |
| Flamenco | `--accent` | `#DC2626` | `#EF4444` | 4.06:1 → 5.21:1 |

Note: Jardín and Sangria were already WCAG AA compliant.

---

## Rollback Plan

All changes are on `feature/design-system-improvements` branch. To revert:
```bash
git checkout main
git branch -D feature/design-system-improvements
```

No database migrations, no Python changes, no API changes — this is purely frontend/template work.

---

## Testing Checklist

- [x] All 5 themes render correctly (Azulejo, Terracotta, Flamenco, Sangria, Jardín)
- [x] Theme switching persists across page refreshes (localStorage)
- [x] Chat bubbles readable on mobile at 375px viewport
- [ ] Lesson phase indicator shows correct active phase
- [ ] Thumbs feedback buttons visible on hover, sticky after click
- [ ] Voice ARIA region tested with screen reader (VoiceOver / NVDA)
- [ ] Focus rings visible in all themes with keyboard navigation
- [ ] `prefers-reduced-motion` disables all new animations
- [ ] No console errors from SVG icons
- [x] Existing Python tests still pass (`make test`)
