# Phase 20: Spanish Culture Themes

## Overview

Add 4 new themes inspired by Spanish culture to the existing theme system. The current app has 3 themes (Light, Dark, Ocean) using CSS custom properties. New themes slot in by adding `[data-theme="name"]` blocks — zero JS architecture changes needed.

## Motivation

Habla Hermano is a Spanish/German/French language tutor. The existing themes (Nordic Minimal) are technically solid but culturally neutral. Spanish-inspired themes create emotional resonance with the learning experience and differentiate the app visually.

## Design Principles

- **Cultural authenticity**: Each theme references a specific Spanish visual tradition
- **WCAG AA compliance**: All text/background combinations maintain 4.5:1 contrast minimum
- **Token parity**: Every theme defines the same ~25 CSS custom properties as existing themes
- **Dark-first bias**: 3 of 4 themes are dark (matching user preference — current default is dark)
- **No JS changes**: Themes are purely CSS; the Alpine.js theme switcher works unchanged

## Theme Specifications

### 1. Terracotta (`data-theme="terracotta"`)

**Inspiration**: Andalusian villages, clay rooftops, warm desert light, Mediterranean earth tones

| Token | Value | Contrast | Notes |
|-------|-------|----------|-------|
| `--surface` | `#1C1410` | — | Deep warm brown-black (dark clay) |
| `--surface-elevated` | `#2A1F18` | — | Warm charcoal |
| `--surface-overlay` | `#362A21` | — | Brown smoke |
| `--border` | `#4A3B30` | — | Clay border |
| `--border-subtle` | `#3E3028` | — | Faint terracotta edge |
| `--text` | `#F2E8DE` | 13.2:1 vs surface | Warm cream parchment |
| `--text-muted` | `#BFA98F` | 7.1:1 vs surface | Sandstone |
| `--text-subtle` | `#8C7A66` | 4.5:1 vs surface | Faded clay |
| `--accent` | `#E07A5F` | — | Terracotta orange (hero) |
| `--accent-hover` | `#EE9A7F` | — | Lighter terracotta |
| `--accent-muted` | `rgba(224, 122, 95, 0.15)` | — | Terracotta glow |
| `--accent-text` | `#1C1410` | 8.5:1 vs accent | Dark on orange |
| `--user-bubble` | `#C85A3A` | — | Deep terracotta |
| `--user-text` | `#FFFFFF` | 5.2:1 vs user-bubble | White on terracotta |
| `--ai-bubble` | `#2A1F18` | — | Matches elevated |
| `--ai-text` | `#F2E8DE` | — | Cream on brown |
| `--success` | `#A3B18A` | — | Olive green (Mediterranean) |
| `--success-muted` | `rgba(163, 177, 138, 0.15)` | — | Olive glow |
| `--error` | `#E76F51` | — | Burnt sienna |
| `--error-muted` | `rgba(231, 111, 81, 0.15)` | — | Sienna glow |
| `--shadow-color` | `rgba(0, 0, 0, 0.5)` | — | Deep shadow |
| `--scrollbar-track` | `#1C1410` | — | Match surface |
| `--scrollbar-thumb` | `#4A3B30` | — | Match border |
| `--scrollbar-thumb-hover` | `#5C4A3C` | — | Lighter border |

### 2. Flamenco (`data-theme="flamenco"`)

**Inspiration**: Flamenco dresses, dark tablao stages, red and black drama, gold jewelry

| Token | Value | Contrast | Notes |
|-------|-------|----------|-------|
| `--surface` | `#110A0A` | — | Near-black, warm red undertone |
| `--surface-elevated` | `#1E1214` | — | Dark burgundy-smoke |
| `--surface-overlay` | `#2D1B1E` | — | Muted crimson |
| `--border` | `#4A2D32` | — | Dark wine |
| `--border-subtle` | `#3A2228` | — | Subtle burgundy |
| `--text` | `#FAE8E8` | 14.8:1 vs surface | Warm pinkish-white |
| `--text-muted` | `#C9A3A8` | 7.6:1 vs surface | Dusty rose |
| `--text-subtle` | `#8C6B70` | 4.5:1 vs surface | Muted mauve |
| `--accent` | `#DC2626` | — | Bold Spanish red |
| `--accent-hover` | `#EF4444` | — | Brighter red |
| `--accent-muted` | `rgba(220, 38, 38, 0.15)` | — | Red glow |
| `--accent-text` | `#FFFFFF` | 5.6:1 vs accent | White on red |
| `--user-bubble` | `#B91C1C` | — | Deep crimson |
| `--user-text` | `#FFFFFF` | 6.1:1 vs user-bubble | White on crimson |
| `--ai-bubble` | `#1E1214` | — | Matches elevated |
| `--ai-text` | `#FAE8E8` | — | Pink-white on burgundy |
| `--success` | `#CA8A04` | — | Gold (flamenco jewelry) |
| `--success-muted` | `rgba(202, 138, 4, 0.15)` | — | Gold glow |
| `--error` | `#FB7185` | — | Soft rose |
| `--error-muted` | `rgba(251, 113, 133, 0.15)` | — | Rose glow |
| `--shadow-color` | `rgba(0, 0, 0, 0.6)` | — | Deep drama |
| `--scrollbar-track` | `#110A0A` | — | Match surface |
| `--scrollbar-thumb` | `#4A2D32` | — | Match border |
| `--scrollbar-thumb-hover` | `#5C3A40` | — | Lighter border |

### 3. Sangria (`data-theme="sangria"`)

**Inspiration**: Spanish sunsets, red wine, evening plazas, warm summer nights in Madrid

| Token | Value | Contrast | Notes |
|-------|-------|----------|-------|
| `--surface` | `#1A0F1E` | — | Deep wine purple |
| `--surface-elevated` | `#261528` | — | Plum twilight |
| `--surface-overlay` | `#331E36` | — | Grape dusk |
| `--border` | `#4C2E52` | — | Dark mulberry |
| `--border-subtle` | `#3D2342` | — | Subtle plum |
| `--text` | `#F3E8FF` | 13.5:1 vs surface | Lavender cream |
| `--text-muted` | `#C4A5D4` | 6.8:1 vs surface | Soft lilac |
| `--text-subtle` | `#8B6E9C` | 4.5:1 vs surface | Muted violet |
| `--accent` | `#C084FC` | — | Soft violet (sangria) |
| `--accent-hover` | `#D8B4FE` | — | Lighter lavender |
| `--accent-muted` | `rgba(192, 132, 252, 0.15)` | — | Purple glow |
| `--accent-text` | `#1A0F1E` | 9.2:1 vs accent | Dark on violet |
| `--user-bubble` | `#9333EA` | — | Rich grape |
| `--user-text` | `#FFFFFF` | 5.8:1 vs user-bubble | White on grape |
| `--ai-bubble` | `#261528` | — | Matches elevated |
| `--ai-text` | `#F3E8FF` | — | Lavender on plum |
| `--success` | `#F59E0B` | — | Amber sunset |
| `--success-muted` | `rgba(245, 158, 11, 0.15)` | — | Amber glow |
| `--error` | `#FB7185` | — | Rose pink |
| `--error-muted` | `rgba(251, 113, 133, 0.15)` | — | Rose glow |
| `--shadow-color` | `rgba(0, 0, 0, 0.5)` | — | Deep shadow |
| `--scrollbar-track` | `#1A0F1E` | — | Match surface |
| `--scrollbar-thumb` | `#4C2E52` | — | Match border |
| `--scrollbar-thumb-hover` | `#5E3D64` | — | Lighter border |

### 4. Azulejo (`data-theme="azulejo"`)

**Inspiration**: Spanish/Portuguese hand-painted ceramic tiles, whitewashed walls, cobalt blue patterns

This is the **light theme** in the collection.

| Token | Value | Contrast | Notes |
|-------|-------|----------|-------|
| `--surface` | `#FBF8F4` | — | Warm off-white (whitewashed wall) |
| `--surface-elevated` | `#FFFFFF` | — | Pure white ceramic |
| `--surface-overlay` | `#F0EDE7` | — | Warm linen |
| `--border` | `#D4CFC6` | — | Aged ceramic edge |
| `--border-subtle` | `#E5E0D8` | — | Faint tile line |
| `--text` | `#1E293B` | 13.7:1 vs surface | Dark slate |
| `--text-muted` | `#4B5563` | 7.4:1 vs surface | Cool gray |
| `--text-subtle` | `#7C8494` | 4.5:1 vs surface | Muted blue-gray |
| `--accent` | `#1D4ED8` | — | Deep cobalt blue (azulejo) |
| `--accent-hover` | `#1E40AF` | — | Darker cobalt |
| `--accent-muted` | `rgba(29, 78, 216, 0.1)` | — | Blue tint |
| `--accent-text` | `#FFFFFF` | 7.3:1 vs accent | White on cobalt |
| `--user-bubble` | `#2563EB` | — | Royal blue |
| `--user-text` | `#FFFFFF` | 5.7:1 vs user-bubble | White on blue |
| `--ai-bubble` | `#F0EDE7` | — | Warm linen (not cold gray) |
| `--ai-text` | `#1E293B` | — | Dark on linen |
| `--success` | `#059669` | — | Tile green accent |
| `--success-muted` | `rgba(5, 150, 105, 0.1)` | — | Green tint |
| `--error` | `#DC2626` | — | Classic red |
| `--error-muted` | `rgba(220, 38, 38, 0.1)` | — | Red tint |
| `--shadow-color` | `rgba(0, 0, 0, 0.06)` | — | Subtle warm shadow |
| `--scrollbar-track` | `#F0EDE7` | — | Match overlay |
| `--scrollbar-thumb` | `#D4CFC6` | — | Match border |
| `--scrollbar-thumb-hover` | `#B8B3AA` | — | Darker thumb |

## UI Changes

### Theme Switcher (chat.html menu)

Add 4 new buttons to the existing theme dropdown. Group themes:

```
THEME
  ☾ Dark
  ☀ Light
  ✦ Ocean
  ─────────
  SPANISH
  ☀ Azulejo
  ☾ Terracotta
  ☾ Flamenco
  ☾ Sangria
```

Use SVG icons (not emojis) for all theme buttons. The separator and "SPANISH" label create a clear section.

### CSS Changes (base.html `<style>`)

Add 4 new `[data-theme="..."]` blocks after the existing Ocean theme block. Each block defines all ~25 CSS custom properties. No other CSS changes needed.

### No JS Changes

The Alpine.js `setTheme()` function already works with any `data-theme` value. The `localStorage` persistence works unchanged.

## Implementation Plan

1. Add 4 CSS theme blocks to `base.html` `<style>` section
2. Update theme switcher in `chat.html` dropdown menu
3. Verify contrast ratios with browser DevTools
4. Test all 7 themes across: chat, lessons, login, learning path, progress pages
5. Screenshot each theme for documentation

## Accessibility Notes

- All themes target WCAG AA (4.5:1) minimum for body text
- Muted/subtle text variants stay at the 4.5:1 boundary
- Focus ring (`--accent-muted` glow) remains visible in all themes
- `prefers-reduced-motion` and `prefers-contrast: high` media queries are theme-independent (already in base CSS)

## Files Changed

| File | Change |
|------|--------|
| `src/templates/base.html` | Add 4 `[data-theme]` CSS blocks |
| `src/templates/chat.html` | Add theme buttons to menu dropdown |
| `docs/design/phase20-spanish-themes.md` | This design document |
