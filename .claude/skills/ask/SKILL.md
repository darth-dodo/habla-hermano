---
name: ask
description: Answer a question about how Habla Hermano works (code, design, data flow, decisions, why something is the way it is) from the repo's walkthroughs, docs and the current code, with file:line links. Use for /ask, "how does X work", "where is X", "why do we X", "what happens when", or interview-style questions about this project. Read-only.
---

# Ask: answer questions about Habla Hermano

Answer like a senior engineer on this codebase: a direct answer first, then the evidence. Read only; change nothing unless the user asks.

## 1. Find the source

Start from the doc that covers the topic, then confirm in code. Docs drift; code is the truth.

| Topic | Start here | Then check |
|---|---|---|
| One chat message, SSE, the LangGraph graph | `docs/walkthroughs/chat-message.md` | `src/api/routes/chat_stream.py`, `src/api/streaming.py`, `src/agent/graph.py` |
| FastAPI or LangGraph basics, dependency injection | `docs/fastapi-langgraph-in-5-minutes.md` | `src/api/auth.py`, `src/api/dependencies.py` |
| Voice (STT, TTS, playback) | `docs/walkthroughs/voice-pipeline.md` | `src/api/routes/voice.py`, `src/services/tts.py`, `src/static/js/modules/voice*.js` |
| Security, cookies, CSRF, CSP, rate limits, encryption | `docs/walkthroughs/security-model.md` | `src/api/middleware.py`, `src/api/cookies.py`, `src/api/rate_limit.py`, `src/db/encryption.py` |
| Lessons, SM-2 review, vocabulary | `docs/walkthroughs/lessons-and-review.md` | `src/agent/lesson_chat_graph.py`, `src/services/review.py`, `src/services/lesson_completion.py` |
| Evals, testing | `docs/walkthroughs/llm-evals.md`, `docs/testing.md` | `evals/`, `tests/conftest.py` |
| CI, deploy, how changes ship | `docs/walkthroughs/software-factory.md` | `.github/workflows/ci.yml`, `render.yaml`, `Makefile` |
| Why a choice was made | README "Decisions and trade-offs", `docs/adr/` | the code the ADR names |
| Routes and event formats | `docs/api.md` | `src/api/routes/` |
| Everything else | `docs/architecture.md`, `docs/codebase-summary.md` | grep the symbol |

`docs/history/` is a frozen record: use it for "when" or "why it used to", never for how things work now.

## 2. Verify

- Grep the symbols the doc names and read the lines you will cite. Walkthrough line numbers can drift.
- When a doc and the code disagree, trust the code, and say which doc is stale.
- A claim you could not check (runtime behaviour, prod settings, dashboards) is labelled "not verified".

## 3. Answer

- First line: the answer, in one or two plain sentences.
- Then the path through the code as a short list of `path:line` links, in the order a request travels.
- Add a small mermaid diagram only when the answer is a flow with three or more steps.
- For a "why" question, give the trade-off and what was given up, citing the ADR or decisions table.
- End with one line naming any stale doc you found, and offer to fix it.

Keep it short: most answers fit in 10 to 20 lines.

## Rules

- Never read, print or quote `.env` files or secrets. Use `.env.example` for setting names.
- Don't run the app, `make eval` or anything that calls an LLM or a paid API to answer a question.
- No em dashes or en dashes.
