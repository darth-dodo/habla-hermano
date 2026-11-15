# Changelog

What changed, in plain words, newest first. Each line says what a learner (or a maintainer) notices, with the PR number.
The full technical log, with every file and fix, is in [docs/history/changelog-detailed.md](docs/history/changelog-detailed.md).

## Unreleased

**New**
- Demo accounts now come with 10 ready-made conversations across Spanish, German, French and Hinglish, from A0 to B1, each with a typical mistake corrected.

**Fixed**
- Conversations idle for 30 days are now really deleted, daily. The old purge looked for a column LangGraph does not have and silently deleted nothing; it is now tested against a real Postgres in CI. An unused setting that would have deleted progress data is gone.
- "Delete all conversations" works again once guests have chatted. A guest row made the database ownership check error out, so nothing was deleted. Needs migration 007 applied in Supabase.

**New**
- A `/demo` page creates, reseeds, re-passwords and deletes ready-made demo accounts, so a demo needs no server shell. Only emails in `DEMO_ADMIN_EMAILS` can open it (#136, `make seed-demo` still works).

**Safer and leaner**
- Rate-limited requests are refused before the login check, so they no longer cost a call to Supabase (#131).
- Deploys only happen from CI after every check passes, and `main` requires a green CI run to merge (#131).
- About 3,000 lines of unused code removed: a review subgraph the app never called, and a guest path in lesson completion that could not run (#131).
- The old lesson subgraph and its prompts are gone too: lessons have run through the chat phase machine since Phase 23, and nothing called it.

**For maintainers**
- Two more code walkthroughs: threads and the data lifecycle, and the frontend without React.

## 1.0.0 (2026-11-15): first tagged release

**Hermano got more reliable**
- Grammar tips now appear on every turn. They were often missing because the model ran out of room mid-answer; replies are also about 39% faster (#122).
- A set of 20 real conversations (`make eval`) checks Hermano's behaviour before prompt or model changes. It found the bug above (#120).

**New**
- Hinglish as a fourth language, taught in English (#97, #99).
- A new voice for Hermano (Gemini), the same in every language. Sped-up speech keeps its normal pitch (#108, #110, #111).
- Spanish now shows the Argentina flag (#119).

**Safer and more private**
- Guest sessions can't be faked, and the voice endpoint needs a session (#113).
- One busy visitor can no longer use up the rate limit for everyone (#113).
- All AI calls go through OpenRouter with zero data retention (#107).
- No scripts load from outside sites any more (#121).
- Optional tracing (Langfuse) records timings and costs, never what learners write (#123).

**For maintainers**
- Deploys run from CI after every check passes; `/version` shows the live commit, and `/health` reports real failures (#105, #106, #115, #124).
- New docs: a 5-minute FastAPI and LangGraph intro, six code walkthroughs, a decisions table, and a README banner (#112, #118, #124 to #127).
- Repo cleanup, and an 88% test coverage floor (#117, #118).
- `make seed-demo` fills a demo account with four weeks of history, and the changelog is now plain words (#128, #129).

## April 2026: monitoring and live voice

- Errors in the app and the browser are reported to Sentry (#91).
- Hermano's voice streams as it speaks instead of after the whole reply (#74, #92).
- Fixed: review sessions no longer log you out midway; garbled audio fixed (#92, #93).
- Small mobile fixes: the sidebar close button, a doubled review input (#88).

## March 2026: threads, lessons in chat, privacy

- **Conversation threads.** Keep several chats, each with its own language and level. Threads are named automatically, and can be renamed or deleted (Phase 26).
- **Lessons inside the chat.** A lesson is now a conversation: intro, teaching, exercises, done, with a progress bar. Translations are graded by the AI, so close-enough answers count (Phases 19, 23).
- **Encryption at rest.** Names, translations and chat history are encrypted in the database, and each user can only read their own rows (Phase 24).
- **New look.** Five Spanish-inspired themes, a new font, and WCAG AA contrast (Phases 20, 25).
- **Better voice.** A redesigned mic and playback bar, speed per message, and many iPhone audio fixes (Phases 21, 22).
- **Progress page redesign** with charts and a streak, a language filter, and password reset by email (#78 to #87).
- **Release audit.** Security, accessibility and code-quality fixes across the app; open-source licence and setup guide added.

## February 2026: voice, streaming, learning paths

- **Talk to Hermano.** Speech to text and text to speech, with voices matched to each language (Phase 17).
- **Streaming replies.** Answers appear word by word (Phase 15).
- **Learning paths.** Suggested next lessons based on your progress and weak spots (Phase 14).
- **Spaced repetition.** Words you learn come back for review at the right time (SM-2), and due words are woven into chat (Phase 12).
- **60 lessons** across Spanish, German and French, A0 to B1 (Phase 10).
- **Works on phones** (Phase 13), and a security pass: CSRF protection, authenticated voice, rate limits, content security policy.

## January 2026: the first version

- Chat with Hermano at your level, from A0 to B1 (Phase 1).
- Grammar feedback on what you write, and a word bank and hints for beginners (Phases 2, 3).
- Short lessons with exercises (Phase 6).
- Accounts, a progress dashboard, and guest sessions without signing up (Phases 7, 8).
