# Habla Hermano

**Learn Spanish, German, or French through conversation, not flashcards.**

An AI conversation partner that takes absolute beginners to confident speakers. Start talking from day one with intelligent scaffolding that fades as you improve.

<p align="center">
  <img src="docs/screenshots/desktop-ocean-home.png" alt="Habla Hermano Desktop" width="700"/>
</p>

---

## The Problem with Language Apps

Most language apps drill vocabulary in isolation. You memorize words, ace flashcards, but freeze when someone actually speaks to you. **Conversation confidence comes from conversation practice.**

Habla Hermano is different:

- **Talk from day one** — Even complete beginners have real conversations
- **Scaffolding that fades** — Word banks and hints for beginners, natural flow for intermediates
- **Gentle corrections** — Grammar feedback that doesn't interrupt your flow
- **No gamification guilt** — No streaks, XP, or leaderboards. Just learning.

---

## How It Works

### Real Conversations at Every Level

<p align="center">
  <img src="docs/screenshots/mobile-ocean-conversation.png" alt="Habla Hermano Mobile Conversation" width="300"/>
</p>

The AI adapts its language mix based on your level:

| Level | What You Experience |
|-------|---------------------|
| **A0** Complete Beginner | 80% English with Spanish words introduced one at a time. Pronunciation guides, celebration of every attempt. |
| **A1** Beginner | 50/50 mix. Short sentences, translations when needed, natural back-and-forth. |
| **A2** Elementary | 80% Spanish. Past tense, longer exchanges, less hand-holding. |
| **B1** Intermediate | 95%+ Spanish. Idioms, subjunctive, real discussions like talking to a native friend. |

### Scaffolding That Helps You Respond

<p align="center">
  <img src="docs/screenshots/desktop-ocean-scaffold-a0.png" alt="Word Bank and Hints" width="700"/>
</p>

Stuck on what to say? Beginners get contextual help:

- **Word Bank** — Clickable vocabulary relevant to the conversation (click to insert)
- **Hints** — Simple guidance in English on how to respond
- **Sentence Starters** — Partial sentences to get you going

For A0 learners, scaffolding appears automatically. A1 learners can expand it when needed. By A2, you won't need it anymore.

### Grammar Feedback Without Interruption

<p align="center">
  <img src="docs/screenshots/desktop-ocean-grammar.png" alt="Grammar Feedback" width="700"/>
</p>

Made a mistake? The AI models the correct form naturally in its response (like a native speaker would), then offers an expandable grammar tip for deeper learning:

```
You:  "Yo soy cansado"
AI:   "¿Estás cansado? Yo también después del trabajo."

      💡 Grammar tip: Use "estar" for temporary feelings like tired.
```

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/darth-dodo/habla-hermano.git
cd habla-hermano
make install

# Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Run
make dev
```

Open [http://localhost:8000](http://localhost:8000) and start your first conversation.

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/) or pip, Anthropic API key

---

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **4 Proficiency Levels** | A0 → B1 with adaptive AI behavior |
| **Intelligent Scaffolding** | Word banks, hints, sentence starters for beginners |
| **Grammar Feedback** | Gentle corrections with expandable explanations |
| **3 Languages** | Spanish, German, and French — full support A0-B1 |
| **Beautiful Themes** | Ocean (shown), Dark, and Light modes |
| **Mobile-First** | Works great on phone, tablet, or desktop |

---

## Documentation

- [Product Vision](docs/product.md) — Pedagogy and feature philosophy
- [Architecture](docs/architecture.md) — Technical design and LangGraph implementation
- [API Reference](docs/api.md) — Endpoints and data structures
- [Changelog](CHANGELOG.md) — Release history

---

## Built With

FastAPI • HTMX • Tailwind CSS • LangGraph • Claude API

---

<p align="center">
  <strong>Start speaking today, not someday.</strong>
</p>
