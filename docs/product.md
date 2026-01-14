# HablaAI Product Specification

> Take someone from zero to conversational in Spanish or German

---

## Vision

HablaAI is an AI conversation partner that takes absolute beginners (A0) to confident intermediate speakers (B1). Unlike apps that drill vocabulary or grammar in isolation, HablaAI gets you talking from day one—with enough scaffolding that you're never lost.

**Core Belief**: Conversation confidence comes from conversation practice. Grammar and vocabulary stick better when learned in context, not from flashcards.

---

## Target Users

- **Primary**: Complete beginners who want to actually speak, not just study
- **Secondary**: Lapsed learners who studied before but never got comfortable talking
- **Tertiary**: Anyone preparing for travel/work who needs practical conversation skills

**Sweet spot**: Someone who's intimidated by conversation but motivated to learn

---

## The A0 → B1 Journey

### Level Progression

| Level | You Can... | AI Behavior | Scaffolding |
|-------|-----------|-------------|-------------|
| **A0** | Say nothing yet | Bilingual mode, heavy hand-holding | Word banks, sentence templates, translations |
| **A1** | Handle basic phrases | Simple questions, slow pace | Hints available, translations on request |
| **A2** | Have simple exchanges | Everyday topics, past tense | Occasional hints, grammar tips contextual |
| **B1** | Hold real conversations | Opinions, narratives, abstract topics | Minimal scaffolding, corrections only |

### What Makes Each Level Feel Different

**A0 - First Steps** (0-2 weeks)
- AI speaks 80% English, 20% target language
- Every prompt has a "How do I say...?" helper
- Sentence starters provided: "Yo soy..." / "Ich bin..."
- Celebrate tiny wins: "You just said your first Spanish sentence!"

**A1 - Building Blocks** (2-8 weeks)
- AI speaks 50/50, always offers translation toggle
- Topics: introductions, family, food, daily routine
- Grammar learned by doing: "You used 'soy' perfectly! That's the verb 'to be'"
- Word bank for new vocabulary, but user types full sentences

**A2 - Finding Your Voice** (2-4 months)
- AI speaks 80% target language, 20% English for complex explanations
- Topics: travel, shopping, describing experiences, making plans
- Past tense introduced naturally through storytelling
- Hints available but not automatic

**B1 - Confident Conversations** (4-6 months)
- AI speaks 95%+ target language
- Topics: opinions, news, hypotheticals, professional contexts
- Corrections are gentle nudges, not interruptions
- User drives the conversation

---

## Core Features (MVP)

### 1. Scaffolded Conversation

The main experience. Chat with an AI that meets you at your level.

**For Beginners (A0-A1):**
```
┌─────────────────────────────────────────────────────────┐
│  🤖 ¡Hola! What's your name?                            │
│     (En español: ¿Cómo te llamas?)                      │
│                                                         │
│  💡 Try saying: "Me llamo [your name]"                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Me llamo...                              [Send] │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Word Bank: me llamo, soy, hola, mucho gusto]         │
└─────────────────────────────────────────────────────────┘
```

**For Intermediate (A2-B1):**
```
┌─────────────────────────────────────────────────────────┐
│  🤖 ¿Qué hiciste el fin de semana?                      │
│                                                         │
│  👤 Fui al cine con mis amigos. Vimos una película     │
│     de terror pero no me gustó mucho.                   │
│                                                         │
│  🤖 ¡Qué interesante! ¿Por qué no te gustó?            │
│     Yo tampoco soy muy fan del terror...               │
│                                                         │
│     💡 Nice use of preterite! [tap to learn more]      │
└─────────────────────────────────────────────────────────┘
```

### 2. Micro-Lessons

2-3 minute focused lessons that unlock conversation abilities.

**Lesson Structure:**
1. **Context**: Why this matters for conversation (30 sec)
2. **Pattern**: The grammar/vocab pattern with examples (60 sec)
3. **Practice**: 3-5 quick exercises (60 sec)
4. **Use It**: Guided mini-conversation using the pattern (30 sec)

**Example Lessons:**
- "Introducing Yourself" (A0)
- "Ordering Food" (A1)
- "Talking About Your Weekend" (A2)
- "Giving Your Opinion" (B1)

### 3. Progress That Feels Real

No arbitrary XP or streaks. Progress = "I can do things I couldn't before."

**Progress Indicators:**
- Topics unlocked: "You can now talk about: Family, Food, Daily Routine"
- Vocabulary size: "142 words learned" (with breakdown by category)
- Grammar patterns: "Patterns you've used: present tense, ser vs estar, gustar"
- Conversation milestones: "First 5-minute conversation without English!"

### 4. Adaptive Difficulty

AI continuously adjusts based on your performance:

- **Struggling?** → More scaffolding, simpler vocabulary, bilingual mode
- **Cruising?** → Less hand-holding, new grammar introduced, longer responses
- **Specific weakness?** → Extra practice on that pattern

User always has override: "This is too easy" / "I need more help"

---

## Conversation Design

### Scaffolding Levels

| Level | Scaffolding | Example |
|-------|-------------|---------|
| **Full** | Template + word bank + translation | "Say: Me llamo ___ [word bank: me llamo, soy]" |
| **Guided** | Hint available on tap | "💡 Tap for hint" → "Try using 'me gusta'" |
| **Light** | Translation toggle only | "[🇬🇧 Show English]" |
| **None** | Corrections only after response | Grammar feedback collapsed by default |

### Grammar Through Context

Instead of teaching rules, then practicing:

```
User: "Yo soy cansado"

AI Response: "Ah, ¿estás cansado? Yo también después del trabajo."

[Collapsed feedback]
💡 Quick tip: For feelings like tired, hungry, or happy,
   Spanish uses "estar" not "ser".

   estar = how you feel right now
   ser = what you are (permanent)

   [More examples →]
```

### Conversation Starters by Level

**A0**: AI initiates everything with heavy scaffolding
**A1**: AI provides topics, user chooses
**A2**: Mix of AI-led and user-initiated
**B1**: User can start any topic, AI follows

---

## Technical Simplifications

### What's Different from Original Spec

| Original | Now | Why |
|----------|-----|-----|
| LangGraph with 8 nodes | Simpler state machine | MVP doesn't need complex routing |
| Conversation checkpointing | Session-based only | Cross-session memory is V2 |
| Spaced repetition system | Simple "words learned" list | SRS is V2 |
| Scenarios with goals | Free conversation + lessons | Scenarios are V2 |
| Voice input | Text only | Voice is V2 |

### MVP Technical Scope

- Single conversation thread per session
- SQLite for persistence (vocabulary, progress, settings)
- Claude API for all language generation
- Simple prompt engineering (no complex agent routing)
- HTMX for reactive UI without JS complexity

---

## User Experience Principles

1. **Never Lost**: Beginners always have a lifeline (translation, hint, word bank)

2. **Always Progressing**: Every conversation teaches something, even mistakes

3. **Conversation First**: Lessons exist to unlock conversations, not the reverse

4. **Gentle Corrections**: Errors are learning moments, not failures

5. **Real Progress**: "I can order food in Spanish" beats "500 XP streak"

---

## Success Metrics

### Learning Effectiveness
- Time to first unassisted sentence (target: <5 min)
- Scaffolding usage over time (should decrease)
- Level progression velocity
- Vocabulary retention (revisit learned words in context)

### Engagement
- Sessions per week
- Average session length
- Return rate after first session
- Completion rate of micro-lessons

### Satisfaction
- "I feel more confident speaking" (self-report)
- Scaffolding level chosen vs needed
- Would recommend to friend

---

## What We're NOT Building

- **Grammar course**: We teach through practice, not lectures
- **Flashcard app**: Vocabulary learned in conversation context
- **Gamified experience**: No streaks, XP, leaderboards, or guilt
- **Translation tool**: Goal is to think in the language, not translate
- **Perfect pronunciation trainer**: Text-based for MVP, voice is future

---

## MVP Scope (Phase 1)

### Must Have
- [ ] Scaffolded conversation with 4 difficulty levels
- [ ] Micro-lessons (5-10 covering A0-A1 basics)
- [ ] Vocabulary tracking (words encountered, can review list)
- [ ] Grammar feedback (contextual, collapsed by default)
- [ ] Level selection (A0/A1/A2/B1) with appropriate AI behavior
- [ ] Spanish language support
- [ ] Basic progress view (words learned, lessons completed)

### Nice to Have
- [ ] German language support
- [ ] Conversation history
- [ ] Settings (feedback verbosity, translation preferences)

### Explicitly Deferred
- Voice input/output
- Spaced repetition
- Scenario roleplay
- Cross-session conversation memory
- Multiple personas
- Offline mode

---

## Launch Plan

### Week 1: Core Loop
- Scaffolded conversation working at all 4 levels
- A0 experience with word banks and templates
- Basic Claude prompts for level-appropriate responses

### Week 2: Learning Features
- 5 micro-lessons for A0-A1
- Vocabulary tracking and display
- Grammar feedback system

### Week 3: Polish
- Progress visualization
- Settings panel
- German support (if time)
- UI polish and mobile responsiveness

### Week 4+: Iterate
- User testing with actual beginners
- Adjust scaffolding based on feedback
- Add more lessons as needed
