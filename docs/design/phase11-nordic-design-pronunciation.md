# Phase 11: Nordic Minimal Design + Pronunciation Tips

> Clean, modern design system with integrated pronunciation guidance

---

## Overview

Phase 11 introduces two major enhancements:
1. **Nordic Minimal Design System** - A clean, modern aesthetic with cool grays, ice blue accents, and Inter typography
2. **Pronunciation Tips** - Natural pronunciation guidance integrated into Hermano's conversational style

---

## Design System: Nordic Minimal

### Design Philosophy

The Nordic Minimal design follows Scandinavian design principles:
- **Clean lines** and generous whitespace
- **Subtle color palette** with purposeful accents
- **Modern typography** with Inter font family
- **Functional minimalism** - every element serves a purpose

### Color Palette

#### Light Theme (Nordic Day)
```css
--surface: #FAFBFC;           /* Clean off-white background */
--surface-elevated: #FFFFFF;   /* Pure white for cards */
--surface-overlay: #F1F5F9;    /* Subtle gray for overlays */
--text: #0F172A;               /* Near-black for readability */
--text-muted: #475569;         /* Subdued text */
--accent: #3B82F6;             /* Ice blue primary */
--accent-hover: #2563EB;       /* Deeper blue on hover */
--success: #10B981;            /* Emerald green */
--error: #EF4444;              /* Clear red */
--border: #E2E8F0;             /* Light gray borders */
```

#### Dark Theme (Nordic Night)
```css
--surface: #0F1115;            /* Deep charcoal */
--surface-elevated: #1A1D23;   /* Elevated dark surface */
--text: #F8FAFC;               /* Off-white text */
--accent: #60A5FA;             /* Lighter ice blue */
```

#### Ocean Theme
```css
--surface: #0C1222;            /* Deep ocean blue */
--accent: #38BDF8;             /* Sky blue accent */
```

### Typography

- **Primary Font**: Inter - Clean, modern sans-serif optimized for screens
- **Monospace**: JetBrains Mono - For code snippets and technical content
- **Font Weights**: 400 (regular), 500 (medium), 600 (semibold)

### Component Styling

#### Chat Interface
- Simplified header with icon-based branding
- Clean message bubbles with subtle shadows
- Minimal input area with focus states

#### Lessons List
- Badge-style level indicators (Beginner/Intermediate)
- Compact cards with chevron navigation indicators
- Clean grid layout

#### Lesson Player
- Thin progress bar (4px)
- Minimal navigation footer
- Content-focused step display

---

## Pronunciation Tips Feature

### Implementation Approach

Pronunciation guidance is woven naturally into Hermano's conversational style through the prompt system. Each CEFR level receives appropriate pronunciation coaching.

### LANGUAGE_ADAPTER Additions

Each language now includes pronunciation-specific data:

```python
LANGUAGE_ADAPTER = {
    "es": {
        # ... existing fields ...
        "tricky_sounds": "the rolled 'rr', the 'ñ' (like 'ny' in canyon), and 'j' (like English 'h')",
        "stress_rule": "the second-to-last syllable unless there's an accent mark",
        "sound_tip": "'ll' sounds like 'y' in most places, 'z' sounds like 'th' in Spain but 's' in Latin America",
    },
    "de": {
        "tricky_sounds": "the 'ch' (like clearing your throat lightly), umlauts (ä, ö, ü), and the 'r' sound",
        "stress_rule": "usually the first syllable in German words",
        "sound_tip": "'w' sounds like English 'v', 'v' sounds like English 'f', and 'ie' is 'ee' while 'ei' is 'eye'",
    },
    "fr": {
        "tricky_sounds": "the French 'r' (back of throat), nasal vowels (on, an, in), and silent final consonants",
        "stress_rule": "always the last syllable of a word or phrase",
        "sound_tip": "most final consonants are silent, 'u' is like saying 'ee' with rounded lips",
    },
}
```

### Pronunciation by Level

#### A0 (Complete Beginner)
```
PRONUNCIATION TIPS: When introducing new words, casually mention how to pronounce them:
- Tricky sounds in {language_name}: {tricky_sounds}
- Stress pattern: {stress_rule}
- Quick tip: {sound_tip}
- Keep it light and fun - don't overwhelm with phonetics
- Only mention pronunciation for 1-2 words per exchange
```

#### A1 (Beginner)
```
PRONUNCIATION TIPS: Sprinkle in pronunciation guidance naturally:
- Point out sounds that don't exist in English
- Stress patterns: "In {language_name}, stress usually falls on..."
- Common mistakes: "Lots of people say X, but it's actually more like Y"
- Use phonetic comparisons to English words they know
- Max 1-2 pronunciation notes per conversation turn
```

#### A2 (Elementary)
```
PRONUNCIATION TIPS: Help them sound more natural:
- Linking sounds: "Native speakers connect these words..."
- Rhythm and flow: "{language_name} has a different rhythm than English"
- Regional variations: "In Spain they say X, but in Latin America it's Y"
- Intonation patterns for questions vs statements
- Model correct pronunciation casually in responses
```

#### B1 (Intermediate)
```
PRONUNCIATION TIPS: Polish their accent naturally:
- Subtle sound distinctions that mark fluency
- Emotional intonation: "When you're surprised, your voice goes up like..."
- Speed and reduction: "Native speakers often blend these sounds..."
- Regional accents and when to use them
- Compliment good pronunciation when you hear it
```

### Example Interactions

**A0 Level:**
```
Hermano: "Let's try 'gracias' - that's GRAH-see-ahs.
          The stress is on the first part: GRA-cias.
          Pretty simple, right? Give it a shot!"
```

**A1 Level:**
```
Hermano: "Nice use of 'años'! Quick tip - that 'ñ' sound
          is like the 'ny' in 'canyon'. So it's AHN-yos, not AN-os."
```

**A2 Level:**
```
Hermano: "Notice how I said 'para el' almost as one word?
          Native speakers link sounds together like that.
          Try saying 'pa-ra-el' smoothly!"
```

**B1 Level:**
```
Hermano: "Tu pronunciación de 'desarrollo' fue perfecta -
          the double 'rr' sounded great! Most English speakers
          struggle with that one."
```

---

## Files Changed

### Templates
- `src/templates/base.html` - Nordic theme CSS variables, Inter font
- `src/templates/chat.html` - Minimal header, clean input styling
- `src/templates/lessons.html` - Badge indicators, compact cards
- `src/templates/lesson_player.html` - Thin progress bar, minimal nav
- `src/templates/partials/feedback.html` - Nordic-styled feedback states
- `src/templates/partials/lesson_exercise.html` - Clean form styling
- `src/templates/partials/lesson_step.html` - Minimal step components
- `src/templates/partials/message.html` - Clean message bubbles

### Agent
- `src/agent/prompts.py` - PRONUNCIATION TIPS sections, language-specific data

---

## Testing

### Visual Testing
Screenshots captured via Playwright MCP:
- Chat interface (light/dark themes)
- Lessons list page
- Lesson player with vocabulary
- Pronunciation tip in conversation

### Functional Testing
- Prompts load correctly with pronunciation data
- All three languages have pronunciation guidance
- Format strings resolve without errors

---

## Migration Notes

This is a non-breaking change:
- Design changes are purely visual
- Pronunciation tips are additive to existing prompts
- No database changes required
- No API changes required

---

## Future Enhancements

Potential Phase 12+ ideas:
- Audio pronunciation examples (text-to-speech)
- Interactive pronunciation exercises
- Accent comparison (user vs native speaker)
- IPA phonetic notation for advanced learners
