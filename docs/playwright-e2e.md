# Manual E2E checks with Playwright MCP

There is no automated browser suite. Before a release, or after a UI change, an agent (or a person) walks the critical flows below in a real browser using the Playwright MCP server. Unit and route tests are covered in [testing.md](testing.md).

## Setup

1. Fill `.env` from `.env.example`. Chat needs `OPENROUTER_API_KEY`. Auth, threads and saved progress need the Supabase keys. Speech to text needs `DEEPGRAM_API_KEY`. Text to speech goes through OpenRouter (Gemini TTS).
2. Start the app with `make dev` (uvicorn on `http://localhost:8000`, auto reload).
3. Use a test Supabase account for the signed in flows. Never a real user.

## Driving the browser

The Playwright MCP tools used most:

| Tool | Use |
|---|---|
| `browser_navigate` | Open a URL, e.g. `http://localhost:8000/?lesson=<id>` |
| `browser_snapshot` | Read the accessibility tree and get element refs (prefer this over screenshots) |
| `browser_click`, `browser_type`, `browser_select_option` | Interact by ref |
| `browser_wait_for` | Wait for streamed text to appear |
| `browser_console_messages`, `browser_network_requests` | Catch JS errors, failed requests, CSP blocks |
| `browser_resize` | Check mobile width (e.g. 390x844) |
| `browser_take_screenshot` | Visual evidence for a PR |

After every flow, check:

- The console has no errors (CSP violations show up here).
- No request returned an unexpected 4xx or 5xx.

## Critical flows

| Flow | Steps | Verify |
|---|---|---|
| Guest chat A0 | `/`, pick a language, level A0, send "hola" | Reply streams in token by token (SSE). Mostly English. Scaffold is expanded with a word bank. Clicking a word inserts it into the input. |
| Guest chat A1 | Switch to A1, send a short sentence | Roughly half target language. Scaffold is collapsed and expands on click. |
| Chat A2 / B1 | Switch level, send a sentence with a grammar mistake | Mostly target language. No scaffold. Grammar feedback appears after the stream ends. |
| Language switch | Change the language dropdown as a guest | Flag and welcome text update. Next reply uses the new language. |
| Lessons | `/lessons`, open a lesson card | Opens in the main chat at `/?lesson=<id>`. Lesson header and progress bar show. Phases move intro, teaching, exercise, complete. Exercises accept and grade answers. Completion shows a score. |
| Learning paths | `/learn` | Path cards render with progress. Continue goes to the next lesson. |
| Review | `/?mode=review` with words due | Review start UI shows. Answers are graded and the next card loads. |
| Progress | `/progress` | Stats, vocabulary list and chart render. `/progress/chart-data` returns JSON. A fresh guest sees the empty state. |
| Guest persistence | Finish a lesson as a guest, then open `/progress` | Session cookie is set. The completed lesson shows on progress. |
| Auth | `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/forgot-password` | Bad password and mismatch show errors. Valid login lands on chat with read only language/level badges. Logout returns to the login page and guest dropdowns work again. |
| Threads (signed in) | Sidebar: New Chat, pick language and level | Thread is created and opens. Switching threads loads the right language, level and history. Rename submits on Enter, Escape cancels. Delete asks first. Deleting the active thread goes to `/`. |
| Threads on mobile | Resize to phone width, use the hamburger | Sidebar opens and closes (button, Escape, backdrop). It closes after picking a thread. |
| Voice | Allow the mic, use the mic button, speak | Transcript appears via `/ws/transcribe`. Reply can be played back (TTS). Changing speed keeps the voice pitch. Errors show a message instead of hanging. |
| Privacy | `/privacy` as guest, then signed in | Guest sees info cards only. Signed in user sees delete history and delete account controls. |

## Recording a run

Put the result in the PR description: date, commit, which flows passed, and screenshots for anything that failed. Do not add run logs to this file.
