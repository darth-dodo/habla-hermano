# Phase 13: Mobile Responsive Design

## Overview

Make Habla Hermano fully mobile-responsive so the app delivers a native-like experience on phones and tablets. The app already has a solid foundation (viewport meta tag, touch-friendly button sizing, one mobile media query), but most pages were designed desktop-first with minimal responsive breakpoint usage. This phase systematically addresses every page, partial, and interaction pattern to ensure a polished mobile experience across all screen sizes.

**Business Value**: Language learning is fundamentally a mobile activity. Users practice during commutes, breaks, and downtime. A friction-free mobile experience directly increases session frequency and retention.

## Requirements

### Functional Requirements

- F1: Chat page must use full viewport height on mobile with no content hidden behind browser chrome or virtual keyboards
- F2: All dropdown menus (language, level, hamburger menu) must work correctly on touch devices with proper tap targets and dismiss behavior
- F3: Lesson player must have a fixed footer that doesn't shift on scroll, with adequate touch targets for navigation
- F4: Progress dashboard charts must resize gracefully on small screens without overlapping labels
- F5: Scaffolding word bank must wrap naturally and remain easily tappable on narrow screens
- F6: Review mode cards must be fully usable on 320px-wide screens
- F7: Auth pages (login/signup) must be centered and usable on all screen sizes
- F8: Navigation between pages must be accessible via the existing mobile-friendly hamburger menu

### Non-Functional Requirements

- NFR1: No horizontal scrolling on any page at any viewport width >= 320px
- NFR2: All interactive elements must have minimum 44x44px touch targets (WCAG 2.1 AA)
- NFR3: Page load performance must not degrade - no additional JS viewport detection libraries
- NFR4: All existing accessibility features (reduced motion, high contrast) must continue working
- NFR5: All three themes (light/dark/ocean) must look correct at every breakpoint
- NFR6: Text must remain readable (>= 16px body, >= 14px secondary) without pinch-to-zoom

## Architecture

### Current State Analysis

**What already works**:
- Viewport meta tag in `base.html`: `width=device-width, initial-scale=1.0`
- `overscroll-behavior: none` on mobile (prevents iOS bounce)
- 48px min-height for buttons on mobile via `@media (max-width: 640px)`
- Chat bubbles widen to 90% on mobile
- `prefers-reduced-motion` and `prefers-contrast: high` support
- Basic responsive grids: `grid-cols-2 md:grid-cols-4` for stats, `sm:grid-cols-2` for lessons
- Max-width containers (`max-w-3xl`, `max-w-4xl`, `max-w-2xl`) prevent over-wide layouts

**What needs work**:

| Page | Issue | Severity |
|------|-------|----------|
| **Chat** | Input footer doesn't account for iOS safe areas or virtual keyboards | High |
| **Chat** | Header controls (3 dropdowns) feel cramped below 375px | Medium |
| **Chat** | No safe-area-inset padding for notched phones | High |
| **Lesson Player** | Footer nav buttons lack adequate mobile touch targets | Medium |
| **Lesson Player** | Step content can overflow horizontally if code/tables present | Medium |
| **Progress** | Charts render at fixed `h-48` - labels overlap on small screens | Medium |
| **Progress** | Stats cards 2-col grid works but spacing is tight on small screens | Low |
| **Lessons** | Card descriptions truncate aggressively on narrow screens | Low |
| **Scaffold** | `max-w-[85%]` clips content on mobile | Medium |
| **Review** | Review cards/questions don't adapt spacing for mobile | Medium |
| **Auth** | Already responsive (`sm:max-w-md`) - minor polish needed | Low |
| **Global** | No `env(safe-area-inset-*)` for notched devices | High |
| **Global** | Scrollbar styling wastes 8px on mobile where overlay scrollbars are native | Low |
| **Global** | No touch-action optimizations for scroll containers | Low |

### Design Approach

**Strategy: CSS-only, mobile-first enhancement using Tailwind responsive prefixes**

No JavaScript viewport detection. No new dependencies. Pure Tailwind classes + targeted CSS media queries in `input.css`. This aligns with the existing architecture (HTMX + Alpine.js + Tailwind CDN).

The only JS addition is a small `visualViewport` listener for virtual keyboard handling on the chat page.

### Breakpoint Strategy

Use Tailwind's default breakpoints (already configured):

| Token | Width | Target Devices |
|-------|-------|----------------|
| (base) | 0-639px | Phones (portrait) |
| `sm:` | >= 640px | Phones (landscape), small tablets |
| `md:` | >= 768px | Tablets (portrait) |
| `lg:` | >= 1024px | Tablets (landscape), laptops |

No custom breakpoints needed. The app's max-width containers (`max-w-3xl` = 768px, `max-w-4xl` = 896px) already prevent the layout from stretching beyond reasonable widths.

### Files to Modify

```
Templates (7 files):
  src/templates/base.html              # Safe area insets, viewport fixes, scrollbar
  src/templates/chat.html              # Header spacing, keyboard-aware footer
  src/templates/lesson_player.html     # Responsive footer, overflow handling
  src/templates/lessons.html           # Card description overflow
  src/templates/progress.html          # Chart container, stats grid
  src/templates/auth/login.html        # Input font-size for iOS
  src/templates/auth/signup.html       # Input font-size for iOS

Partials (11 files):
  src/templates/partials/scaffold.html           # Remove max-w clip on mobile
  src/templates/partials/pronunciation_tips.html # Remove max-w clip on mobile
  src/templates/partials/grammar_feedback.html   # Remove max-w clip on mobile
  src/templates/partials/review_start.html       # Mobile spacing + button sizing
  src/templates/partials/review_question.html    # Mobile card layout
  src/templates/partials/review_feedback.html    # Mobile card layout
  src/templates/partials/review_complete.html    # Mobile spacing
  src/templates/partials/stats_summary.html      # Tighter mobile padding
  src/templates/partials/vocab_sidebar.html      # Mobile collapse behavior
  src/templates/partials/lesson_step.html        # Overflow handling
  src/templates/partials/lesson_step_enhanced.html # Overflow handling

CSS (1 file):
  src/static/css/input.css             # Safe areas, touch utilities, scrollbar

JavaScript (1 file):
  src/static/js/app.js                 # Virtual keyboard scroll fix
```

## Detailed Changes

### 1. Safe Area & Viewport Fixes (base.html + input.css)

**Problem**: iPhones with notches/Dynamic Island clip content behind system UI. The virtual keyboard pushes content off-screen on iOS Safari. `h-full` (100vh) includes the browser chrome height on mobile Safari, causing content to extend behind the URL bar.

**Changes to base.html**:
```html
<!-- Update viewport meta (line 5) -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">

<!-- Update #app container (line 487) -->
<!-- Change: class="h-full flex flex-col" -->
<!-- To:     class="h-dvh flex flex-col"   -->
```

**Changes to input.css** - add at end of file:
```css
/* ============================================
   MOBILE RESPONSIVE - Phase 13
   ============================================ */

/* Dynamic viewport height - accounts for mobile browser chrome */
.h-dvh {
    height: 100vh; /* fallback */
    height: 100dvh;
}

/* Safe area utilities for notched devices */
.safe-top    { padding-top: env(safe-area-inset-top); }
.safe-bottom { padding-bottom: env(safe-area-inset-bottom); }
.safe-x      {
    padding-left: env(safe-area-inset-left);
    padding-right: env(safe-area-inset-right);
}

/* Prevent text size adjustment on orientation change */
html { -webkit-text-size-adjust: 100%; }

/* Prevent 300ms tap delay */
html { touch-action: manipulation; }

/* Prevent iOS input zoom (inputs < 16px trigger zoom) */
@media (max-width: 640px) {
    input, select, textarea {
        font-size: 16px !important;
    }

    /* Hide scrollbar on mobile (overlay scrollbars are native) */
    ::-webkit-scrollbar { width: 0; height: 0; }
    * { scrollbar-width: none; }
}
```

### 2. Chat Page (chat.html)

**Header** (line 8):
- Add `safe-top safe-x` classes to header
- Tighten selector gap on mobile: change `gap-2` to `gap-1.5 sm:gap-2` on the right-side controls div (line 136)

**Chat container** (line 236):
- Reduce vertical padding on mobile: change `py-8` to `py-4 sm:py-8`

**Input footer** (line 300):
- Add `safe-bottom safe-x` classes to footer
- Reduce padding on mobile: change `px-4 py-4 sm:px-6` to `px-3 py-3 sm:px-6 sm:py-4`

### 3. Virtual Keyboard Handling (app.js)

Add to end of file:
```javascript
// Virtual keyboard: scroll chat to bottom when keyboard opens/closes
if ('visualViewport' in window) {
    window.visualViewport.addEventListener('resize', function() {
        var chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });
}
```

### 4. Lesson Player (lesson_player.html)

**Header** (line 8):
- Add `safe-top safe-x` classes
- Add `truncate` to title span (line 18) to prevent overflow on narrow screens

**Content area** (line 37-38):
- Add `overflow-x-hidden` to the scrollable div
- Reduce padding: change `px-4 py-8` to `px-3 py-4 sm:px-4 sm:py-8`

**Footer** (line 46):
- Add `safe-bottom safe-x` classes
- Increase button padding for touch: prev button `px-4 py-2` to `px-4 py-3 sm:py-2`, next/complete button `px-5 py-2` to `px-5 py-3 sm:py-2`

### 5. Progress Dashboard (progress.html)

**Section spacing** (line 28):
- Change `space-y-6` to `space-y-4 sm:space-y-6`

**Chart containers** (lines 60, 67):
- Change `p-5` to `p-4 sm:p-5`
- Change `h-48` to `h-40 sm:h-48`

**Chart.js options** (in script block):
- Add `maxTicksLimit: 5` to x-axis ticks for mobile readability (line 113)

### 6. Scaffold & Feedback Partials

**scaffold.html** (line 14):
- Change `max-w-[85%]` to `max-w-full sm:max-w-[85%]`

**pronunciation_tips.html** and **grammar_feedback.html**:
- Same treatment: any `max-w-[85%]` becomes `max-w-full sm:max-w-[85%]`

### 7. Review Partials

**review_start.html, review_question.html, review_feedback.html, review_complete.html**:
- Reduce padding: any `p-6` becomes `p-4 sm:p-6`
- Action buttons: add `w-full sm:w-auto` for full-width buttons on mobile
- Increase spacing between answer options for touch accuracy

### 8. Lessons Page (lessons.html)

Already well-structured. One improvement:
- Lesson card descriptions (lines 35-36, 69-70): change `truncate` to `line-clamp-2 sm:truncate` for better mobile readability

### 9. Auth Pages (login.html, signup.html)

Already responsive. Minor fixes:
- Add `safe-top` class to the outer container
- Input `font-size: 16px` fix is handled globally by the CSS rule in Task 1

## Dependencies

- No new libraries or packages
- No backend changes required
- No database migrations
- No API contract changes

All modifications are frontend-only: templates, CSS, and a small JS addition.

## Implementation Plan

### Task 1: Global Foundation (base.html + input.css) - 45 min

- [ ] Update viewport meta to `viewport-fit=cover`
- [ ] Add safe area CSS utilities to `input.css`
- [ ] Add `h-dvh` utility class
- [ ] Replace `h-full` with `h-dvh` on `#app` container
- [ ] Add touch optimization CSS (manipulation, input font-size fix)
- [ ] Add mobile scrollbar hiding
- [ ] Add `-webkit-text-size-adjust: 100%`

### Task 2: Chat Page Responsive (chat.html + app.js) - 45 min

- [ ] Add `safe-top safe-x` to header
- [ ] Add `safe-bottom safe-x` to footer
- [ ] Tighten header control spacing for mobile (`gap-1.5 sm:gap-2`)
- [ ] Reduce chat container padding on mobile (`py-4 sm:py-8`)
- [ ] Reduce footer padding on mobile (`px-3 py-3 sm:px-6 sm:py-4`)
- [ ] Add virtual keyboard handling in `app.js`

### Task 3: Lesson Player Responsive (lesson_player.html) - 30 min

- [ ] Add safe area classes to header and footer
- [ ] Add `truncate` to lesson title
- [ ] Add `overflow-x-hidden` to content area
- [ ] Reduce content padding on mobile
- [ ] Increase footer button touch targets (`py-3 sm:py-2`)

### Task 4: Progress Dashboard Responsive (progress.html) - 30 min

- [ ] Reduce chart height on mobile (`h-40 sm:h-48`)
- [ ] Tighten section spacing (`space-y-4 sm:space-y-6`)
- [ ] Reduce card padding (`p-4 sm:p-5`)
- [ ] Add `maxTicksLimit: 5` to chart x-axis

### Task 5: Partial Components - 45 min

- [ ] Fix scaffold `max-w-[85%]` → `max-w-full sm:max-w-[85%]`
- [ ] Fix pronunciation_tips and grammar_feedback `max-w` on mobile
- [ ] Update review partials with responsive padding (`p-4 sm:p-6`)
- [ ] Make review buttons full-width on mobile (`w-full sm:w-auto`)
- [ ] Verify word bank chips meet 44px touch target

### Task 6: Lessons + Auth Pages - 20 min

- [ ] Add `line-clamp-2 sm:truncate` to lesson card descriptions
- [ ] Add safe area padding to auth pages
- [ ] Verify form inputs are 16px on mobile (handled by global CSS)

### Task 7: Testing & Polish - 30 min

- [ ] Visual testing at 320px, 375px, 393px, 768px, 1024px viewports
- [ ] Test all three themes at each breakpoint
- [ ] Test virtual keyboard behavior on chat page
- [ ] Test dropdown menus on touch devices
- [ ] Verify no horizontal scrolling on any page
- [ ] Verify accessibility (reduced motion, high contrast) still works
- [ ] Test lesson player step navigation on mobile
- [ ] Test review mode full flow on mobile

**Total estimated effort: ~4 hours**

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `100dvh` not supported in old browsers | Low | Slight gap on older Safari | Fallback: `height: 100vh; height: 100dvh;` (stacked declarations) |
| `env(safe-area-inset-*)` not supported | Low | Extra padding doesn't apply | Feature is purely additive; no breakage on unsupported browsers |
| iOS zoom on input focus | Medium | Disorienting zoom when tapping chat input | Force `font-size: 16px` on mobile inputs via CSS |
| Virtual keyboard pushes layout | Medium | Chat input hidden behind keyboard | `visualViewport` API listener + scroll fix in app.js |
| Chart.js labels overlap on small screens | Medium | Unreadable chart axis labels | Set `maxTicksLimit: 5` on x-axis for mobile |
| `scrollbar-width: none` hides scrollbar everywhere on mobile | Low | Users lose scroll position indicator | Acceptable trade-off; content is vertically scrollable and users expect this on mobile |

## Testing Strategy

### Existing Tests
- No new unit tests needed (CSS-only changes don't affect Python logic)
- Existing 1445+ tests remain unaffected
- Run full suite to confirm: `make test`

### Visual Testing (Playwright)
Screenshot comparisons at 5 viewport widths:
- 320px (iPhone SE / smallest supported)
- 375px (iPhone SE 3rd gen)
- 393px (iPhone 15 Pro)
- 768px (iPad Mini portrait)
- 1024px (iPad landscape / small laptop)

All 3 themes at each width. Pages: chat, lessons, lesson player, progress, login.

### Manual Testing Checklist

- [ ] iPhone SE (375x667) - smallest common iPhone
- [ ] iPhone 15 Pro (393x852) - modern iPhone with Dynamic Island
- [ ] iPad Mini (768x1024) - tablet portrait
- [ ] Galaxy S21 (360x800) - common Android phone
- [ ] Virtual keyboard open/close on chat page
- [ ] Dropdown menus dismiss on outside tap
- [ ] Landscape orientation on phones (no horizontal overflow)
- [ ] All three themes at every viewport
- [ ] Scaffold word bank tappability
- [ ] Lesson player step navigation
- [ ] Review mode full flow on mobile

### Acceptance Criteria

- [ ] No horizontal scrollbar on any page at >= 320px width
- [ ] All interactive elements >= 44x44px touch target
- [ ] Chat input remains visible when virtual keyboard opens
- [ ] Safe area insets applied on notched devices
- [ ] Charts readable at 375px width
- [ ] All three themes render correctly at all breakpoints
- [ ] Existing accessibility features unaffected
- [ ] No new JavaScript dependencies added
- [ ] All existing tests pass unchanged
