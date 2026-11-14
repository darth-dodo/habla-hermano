# Habla Hermano

> Your AI conversation partner for Spanish, German, French and Hinglish.

[![CI](https://github.com/darth-dodo/habla-hermano/actions/workflows/ci.yml/badge.svg)](https://github.com/darth-dodo/habla-hermano/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/darth-dodo/habla-hermano/graph/badge.svg)](https://codecov.io/gh/darth-dodo/habla-hermano)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

### 🗣️ [Try it live: habla-hermano.onrender.com](https://habla-hermano.onrender.com)

Language apps teach flashcards; people freeze in real conversations. Hermano gets you **talking from message one**, even as a complete beginner, and shifts from mostly English (A0) to almost all target language (B1) as you improve.

<p align="center">
  <img src="docs/screenshots/demo-a0.gif" alt="A0 learner asks how to say I like coffee; Hermano replies with a word bank, hint, sentence starter and pronunciation tips" width="250"/>
  &nbsp;
  <img src="docs/screenshots/mobile-scaffolding-beach.png" alt="Word bank and scaffolding" width="250"/>
  &nbsp;
  <img src="docs/screenshots/mobile-pronunciation-beach.png" alt="Pronunciation tips" width="250"/>
</p>

## What you get

```mermaid
graph LR
    C(("Chat with<br/>Hermano"))
    C --> S["Scaffolding<br/>word bank, hints, starters"]
    C --> F["Gentle corrections<br/>grammar + pronunciation"]
    C --> V["Voice<br/>speak and listen"]
    C --> L["60 lessons<br/>inside the chat"]
    C --> R["Spaced repetition<br/>woven into chat"]
    C --> T["Threads, progress,<br/>learning paths"]
```

| Level | Hermano speaks | Help you get |
|---|---|---|
| **A0** complete beginner | 80% English, one new word at a time | word bank and hints open by default, 0.75x voice |
| **A1** beginner | 50 / 50 | word bank and hints, 0.85x voice |
| **A2** elementary | 80% target language | grammar tips on demand |
| **B1** intermediate | 95%+ target language | peer-level corrections |

- **Lessons**: 20 topics x Spanish, German, French, 4 CEFR levels. They run as a guided chat, with multiple choice, fill-in and translation exercises.
- **Voice**: tap the mic to talk (code-switching between English and the target language is fine). Tap play to hear any reply, from 0.75x to 1.5x speed with the pitch kept natural.
- **Review**: SM-2 tracks every word you learn and brings due words back into conversation. No flashcard decks.
- **Guest or account**: chat, feedback and voice work without signing up. An account adds vocabulary tracking, progress charts, multiple threads, password reset and account deletion.
- **Privacy**: conversations and personal fields are encrypted at rest, and row-level security keeps each user's data separate.
- **Five themes**: Azulejo, Terracotta, Flamenco, Sangria, Jardín (all WCAG AA).

<p align="center">
  <img src="docs/screenshots/lessons-svg-icons.png" alt="Lesson catalog" width="420"/>
  &nbsp;
  <img src="docs/screenshots/threads-mobile-sidebar-open.png" alt="Thread sidebar" width="200"/>
</p>

## How it works

```mermaid
graph LR
    B["Browser<br/>HTMX + ES modules"] -- "SSE" --> F["FastAPI"]
    F --> LG["LangGraph<br/>respond, scaffold, analyze"]
    LG --> OR["OpenRouter"]
    OR --> H["Claude Haiku 5.5"]
    B -- "WS /ws/speak" --> F -- "TTS" --> OR --> G["Gemini TTS"]
    B -- "WS /ws/transcribe" --> F -- "STT" --> DG["Deepgram Nova-3"]
    F <--> DB[("Supabase<br/>Postgres + Auth")]
```

FastAPI renders HTML with Jinja2 and HTMX. Each chat turn runs a LangGraph graph, and the reply streams token by token over SSE. Voice is proxied through FastAPI, so API keys never reach the browser. Details: [docs/architecture.md](docs/architecture.md).

## Decisions and trade-offs

| Decision | Why | Cost, or when to revisit |
|---|---|---|
| Server-rendered HTML with HTMX, no SPA ([ADR-003](docs/adr/ADR-003-htmx-alpine-frontend.md)) | The server owns all state; one codebase, no client routing or duplicated API layer | Rich client interactivity is harder; voice and streaming still need hand-written ES modules |
| LangGraph with Postgres checkpoints, encrypted by an `EncryptedSerializer` (Fernet) ([ADR-002](docs/adr/ADR-002-langgraph-conversation-engine.md)) | Conversation state survives restarts, and stored chats are unreadable without `SECRET_KEY` | Checkpoints cannot be queried in SQL; there is no key rotation, so changing `SECRET_KEY` makes old checkpoints unreadable |
| OpenRouter for both chat and TTS ([ADR-011](docs/adr/ADR-011-openrouter-for-llm-and-tts.md)) | One key and one bill; models are settings, and provider routing comes for free | One more hop, and a single point of failure for chat and voice |
| Slowed TTS buffered into `<audio>` with `preservesPitch` | Web Audio `playbackRate` drops the pitch, which misleads beginners at 0.75x and 0.85x | Speeds other than 1x wait for the whole clip before playing |
| Per-client-IP rate limits in process memory | No Redis to run or pay for; correct with `--workers 1` on Render | Move to Redis before running a second worker or instance |
| Guests as signed session cookies, served by the admin client scoped to that session | Guests have no Supabase JWT, so RLS cannot identify them | Guest isolation relies on app code filtering by session ID, not on the database |

## Run it locally

```bash
git clone https://github.com/darth-dodo/habla-hermano.git && cd habla-hermano
make install
cp .env.example .env   # set OPENROUTER_API_KEY and SECRET_KEY
make dev               # http://localhost:8000
```

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/) and Node 18+. Without Supabase it runs in memory with guest sessions. Add `DEEPGRAM_API_KEY` for the mic. Full setup, migrations and Render deploy: [docs/setup.md](docs/setup.md).

| Command | Does |
|---|---|
| `make dev` | dev server with reload |
| `make test` | pytest (about 2,400 tests, parallel) + Vitest (about 260) |
| `make check` | ruff lint, format check, mypy strict |

## Docs

| Doc | For |
|---|---|
| [Codebase summary](docs/codebase-summary.md) | onboarding: read order, one request end to end, where to change things, gotchas |
| [Architecture](docs/architecture.md) | how every part works, with diagrams |
| [API](docs/api.md) | routes, SSE events, WebSocket protocols |
| [Product](docs/product.md) | pedagogy, the Hermano persona, the A0 to B1 journey |
| [Setup](docs/setup.md) | local setup, Supabase, Render |
| [Testing](docs/testing.md) | running tests, layout, mocking patterns |
| [E2E checklist](docs/playwright-e2e.md) | manual browser flows to verify |
| [Design system](docs/design/design-system.md) | tokens, type, themes |
| [ADRs](docs/adr/) · [phase notes](docs/design/) · [changelog](CHANGELOG.md) | history and decisions |
