# HablaAI Product Specification

> An AI-powered language learning companion for Spanish and German conversation practice

---

## Vision

HablaAI is a conversational language tutor that adapts to your level, corrects mistakes gently, and tracks your vocabulary growth over time. Unlike traditional apps that focus on drills and flashcards, HablaAI prioritizes natural conversation with intelligent feedback.

**Core Belief**: The best way to learn a language is through practice, not memorization. But practice needs to be guided, tracked, and adapted to the learner.

---

## Target Users

- **Primary**: Self-learners who want conversation practice beyond what Duolingo offers
- **Secondary**: Anyone preparing for travel, work, or exams who needs practical speaking skills
- **Tertiary**: Language hobbyists who enjoy the process of learning

**Not for**: Complete beginners (A0) who need foundational grammar instruction first

---

## Core Features

### V1 — Minimum Lovable Product

| Feature | Description | Why It Matters |
|---------|-------------|----------------|
| **Adaptive Conversation** | AI responds in target language at your CEFR level (A1-C2) | Conversations that challenge without overwhelming |
| **Gentle Grammar Feedback** | Catches mistakes, explains the rule briefly, suggests corrections | Learn from errors without interrupting flow |
| **Vocabulary Tracking** | Automatically extracts and saves new words you encounter | See your vocabulary grow organically |
| **Multi-Language Support** | Spanish and German with extensible architecture | Two popular languages, room to grow |
| **Progress Visibility** | Words learned, sessions completed, level progression | Motivation through visible growth |
| **Customizable Feedback** | Choose gentle, detailed, or minimal correction style | Match your learning preferences |

### V2 — Enhanced Learning

| Feature | Description |
|---------|-------------|
| **Scenario Roleplay** | Practice specific situations (ordering food, job interviews, doctor visits) |
| **Spaced Repetition** | Review vocabulary at optimal intervals for retention |
| **Grammar Pattern Library** | Track which grammar rules you struggle with most |
| **Voice Input** | Practice pronunciation with Whisper speech-to-text |
| **Conversation History** | Review past conversations and corrections |

### Future Considerations

- Regional language variants (Mexican Spanish, Austrian German)
- Additional languages
- Mobile-optimized PWA
- Export vocabulary to Anki

---

## User Experience Design

### Design Principles

1. **Focus on Conversation**: The chat is center stage. Everything else supports it.

2. **Non-Interrupting Feedback**: Corrections appear after the AI's natural response, collapsed by default. Expand if you want to learn more.

3. **Progress Without Pressure**: No timers, no streak anxiety, no gamification guilt. Just track what you've learned.

4. **Predictable Patterns**: Same layout every session. Consistent interaction patterns. Reduce cognitive overhead.

5. **Visual Learning Aids**: Color-coded parts of speech, highlighted grammar patterns, clear visual hierarchy.

6. **Flexible Pacing**: Take as long as you need. Pause anytime. Resume with full context.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [🇪🇸 Spanish ▾]    HablaAI    [Level: B1]    [⚙️]             │
├─────────────────────────────────────────────────────────────────┤
│                                               │                  │
│   ┌────────────────────────────────────┐     │  📚 New Words    │
│   │                                    │     │  ──────────────  │
│   │  🤖 ¡Hola! ¿Cómo estás hoy?       │     │  • mercado (n)   │
│   │                                    │     │  • comprar (v)   │
│   │  👤 Estoy bien. Ayer fui al       │     │  • fresco (adj)  │
│   │     mercado con mi madre.          │     │                  │
│   │                                    │     │  [View all →]    │
│   │  🤖 ¡Qué bien! ¿Qué compraron?    │     │                  │
│   │                                    │     ├──────────────────┤
│   │     💡 Great use of preterite!    │     │  📊 Session      │
│   │        [Expand for details]        │     │  ──────────────  │
│   │                                    │     │  Words: +5       │
│   └────────────────────────────────────┘     │  Time: 12 min    │
│                                               │                  │
│   ┌────────────────────────────────────┐     │                  │
│   │  Type your response...       [📤] │     │                  │
│   └────────────────────────────────────┘     │                  │
└─────────────────────────────────────────────────────────────────┘
```

### Feedback Display

Corrections appear inline but collapsed:

```
🤖 ¡Muy bien! Entiendo que fuiste de compras.

💡 Small note
   ├─ You wrote: "Yo soy ir al mercado"
   ├─ Better: "Yo fui al mercado"
   └─ Rule: Use preterite (fui) for completed past actions
      [Learn more about preterite →]
```

### Visual Vocabulary

Words are color-coded by part of speech for visual pattern recognition:

- 🔵 Verbs: comprar, hablar, entender
- 🟢 Nouns: mercado, madre, comida
- 🟠 Adjectives: fresco, grande, nuevo
- 🟣 German Gender: der (m), die (f), das (n)

---

## CEFR Level Behavior

| Level | AI Behavior | Vocabulary | Grammar Focus |
|-------|-------------|------------|---------------|
| **A1** | Simple sentences, common topics, slow pacing | Basic (500 words) | Present tense, basic questions |
| **A2** | Short conversations, everyday situations | Elementary (1000 words) | Past tense basics, pronouns |
| **B1** | Extended discussions, opinions, narratives | Intermediate (2000 words) | Complex past, subjunctive intro |
| **B2** | Abstract topics, nuanced expression | Upper-intermediate (4000 words) | Subjunctive, conditionals |
| **C1** | Professional/academic discourse | Advanced (8000 words) | Nuanced usage, idioms |
| **C2** | Native-like complexity | Near-native | All structures, style |

### Level Adjustment Logic

- **Upgrade trigger**: 10+ correct sentences in a row with level-appropriate structures
- **Downgrade trigger**: 5+ fundamental errors suggesting level is too high
- **User override**: Always allow manual level selection

---

## Scenarios (V2)

Pre-built conversation contexts with specific goals:

| Scenario | Level | You Play | Goal |
|----------|-------|----------|------|
| Lost in the City | A1 | Tourist | Ask for directions, understand basic instructions |
| At the Restaurant | A1-A2 | Customer | Order food, ask about menu, request bill |
| Hotel Check-in | A2 | Guest | Check in, ask about amenities, report issues |
| Doctor Visit | B1 | Patient | Describe symptoms, understand instructions |
| Job Interview | B2 | Candidate | Answer questions about experience, ask about role |
| Apartment Hunting | B1 | Renter | Negotiate terms, ask about utilities |
| Business Meeting | B2-C1 | Colleague | Present ideas, discuss strategy |

Each scenario has:
- Clear setup and context
- Specific vocabulary focus
- Success criteria
- Option to continue as free conversation

---

## Success Metrics

### Engagement (Do people use it?)

- Sessions per week per user
- Average session duration
- Return rate after first session

### Learning (Does it work?)

- Vocabulary growth over time
- Error rate decrease for specific patterns
- Level progression velocity

### Satisfaction (Do people like it?)

- Would recommend to friend
- Qualitative feedback on conversation quality
- Feature usage patterns

---

## Open Questions

1. **Pronunciation feedback**: Should we add voice input in V1 or wait? (Leaning: V2)

2. **Community features**: Vocabulary sharing? Conversation sharing? (Leaning: Not in V1-V2)

3. **Offline mode**: Important for travel use case but adds complexity (Leaning: Future)

4. **Multiple personas**: Different AI personalities (formal teacher, casual friend)? (Leaning: V2)

---

## Non-Goals

- **Not a grammar course**: We correct mistakes, but don't teach grammar from scratch
- **Not a certification prep tool**: Focus is practical conversation, not test-taking
- **Not a social platform**: No leaderboards, no comparing with others
- **Not a replacement for human interaction**: Supplement, not substitute

---

## Technical Constraints

- **Single user initially**: No authentication complexity for MVP
- **SQLite persistence**: Simple, no server setup required
- **API costs**: Claude API usage scales with conversation length
- **Browser-based**: No native app, HTMX for minimal JS

---

## Launch Plan

### Phase 1: Personal Use (Weekend 1-2)
- Core chat working
- Basic feedback
- Single language (Spanish)

### Phase 2: Polish (Weekend 3)
- German support
- Vocabulary sidebar
- Settings panel

### Phase 3: Share (Week 4+)
- Deploy publicly
- Get feedback from friends
- Iterate based on usage

### Phase 4: Expand (If it works)
- Scenarios
- Spaced repetition
- Voice input
