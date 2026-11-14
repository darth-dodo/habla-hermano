# Testing

How the Habla Hermano test suites are laid out, how to run them, and how they avoid real network calls.

As of 2026-11-14 there are about 2,378 Python tests (pytest) and 257 JS tests (Vitest). Counts drift, so treat them as rough.

## Run the tests

```bash
uv sync --extra dev        # or: make install
make test                  # pytest, then vitest
make test-js               # Vitest only
make test-cov              # pytest with HTML + terminal coverage
make test-fast             # pytest -m "not slow"
make check                 # ruff lint + format check + mypy
```

Notes:

- `pyproject.toml` sets `addopts = -v --tb=short --strict-markers -n auto`. Every pytest run is parallel through pytest-xdist. Add `-n 0` to debug one test serially.
- Markers are strict. Only `slow` and `integration` exist.
- Settings need `OPENROUTER_API_KEY` and `SECRET_KEY`. Any dummy value works. CI sets `test-api-key-for-ci` and `test-secret-key-for-ci`.

```bash
OPENROUTER_API_KEY=x SECRET_KEY=x uv run pytest tests/agent -n 0 -k scaffold
```

## Test pyramid

```mermaid
flowchart TB
    M["Manual Playwright MCP flows<br/>(docs/playwright-e2e.md)"]
    R["Route tests: FastAPI TestClient<br/>tests/api"]
    U["Unit tests: agent, services, lessons, db<br/>Vitest for JS modules"]
    M --> R --> U
```

There is no automated browser suite. Browser checks are the manual flows in [playwright-e2e.md](playwright-e2e.md).

## Layout

| Path | Covers |
|---|---|
| `tests/conftest.py` | Shared fixtures: `CSRF_HEADERS`, `mock_settings`, `mock_supabase`, mocked graph and checkpointer, an app client with the graph mocked. Autouse fixture clears settings, template, rate limit, LLM and graph caches after each test. |
| `tests/agent/` | LangGraph build and routing, state, prompts, review graph, checkpointer and checkpoint purge, LLM zero retention settings |
| `tests/agent/nodes/` | Node logic: respond, scaffold, analyze, review, lesson chat phase machine |
| `tests/api/` | App level concerns: auth, CSRF, security headers, sanitizing, session, SSE streaming, threads API, privacy, persistence, Supabase client |
| `tests/api/routes/` | Per route modules: chat, lessons, learn, progress, review, auth (incl. password reset), validation, voice (STT WebSocket, TTS), plus `test_e2e.py` (multi route coverage tests, not browser tests) |
| `tests/services/` | Business logic: SM-2 review, learning paths, adaptive, levels, progress, vocabulary, threads, thread messages, thread titling, data retention, TTS client, Langfuse tracing mask |
| `tests/lessons/` | Lesson YAML models and lesson service |
| `tests/db/` | Fernet field encryption, `FernetCipher`, models, repositories with and without encryption |
| `tests/test_rate_limiting.py` | REST and WebSocket rate limits |
| `tests/evals/` | LLM eval scorer (pure functions) and the eval runner end to end with a fake chat model |
| `tests/js/` | Vitest specs for `src/static/js/modules`: dom, fsm, htmx-handlers, scaffold, shortcuts, stream, voice |

## Mocking strategy

No test calls OpenRouter, Gemini, Deepgram or Supabase.

| What | How |
|---|---|
| LLM | Patch `get_llm` in the module that uses it, e.g. `src.agent.nodes.respond.get_llm`, `src.agent.nodes.lesson_chat.get_llm`, `src.services.thread_titling.get_llm`. The client is `ChatOpenAI` pointed at OpenRouter (`src.agent.llm`). |
| Whole graph | `mock_compiled_graph` in `conftest.py` fakes `ainvoke` and `astream` for route and streaming tests. |
| TTS HTTP | `tests/services/test_tts.py` builds an `httpx.AsyncClient` on `httpx.MockTransport`, so it checks the exact request sent. |
| TTS in routes | `FakeSynthesizer` in `tests/api/routes/tts_fakes.py` stands in for `src.services.tts.synthesize_pcm` and records each call. |
| Supabase | `mock_supabase_client` returns a `MagicMock` whose chained PostgREST methods (`table().select().eq()...`) all return the same mock table. `.not_` needs a `PropertyMock` on the type. |
| Auth | Override `get_current_user` / `get_current_user_optional` through FastAPI dependency overrides. |
| CSRF | POST, PUT, PATCH and DELETE need `HX-Request: true`. Use `CSRF_HEADERS` from `tests/conftest.py`. |

Patch where the name is looked up, not where it is defined. Inner layers import from canonical modules, so patch `src.config.get_settings`, not the `src.api.config` shim. The same rule applies to `src.validation` and `src.db.client`.

## JS tests

- Vitest with the `jsdom` environment (`vitest.config.js`).
- Specs live in `tests/js/**/*.test.js` and import the ES modules in `src/static/js/modules/` directly.
- `make test-js` runs once. `make test-js-watch` watches.

## LLM evals

Unit tests mock the model. `evals/` checks that Hermano behaves as designed with the real model (whatever `LLM_MODEL` is set to, through OpenRouter).

`evals/cases.yaml` holds 20 single-turn cases across es, de, fr and Hinglish and all four levels: A0 beginners writing English, learners making a known grammar error, B1 idiom questions. `evals/run.py` builds the real chat graph (respond, scaffold, analyze) with an in-memory `MemorySaver`, sends each case on a fresh thread, and scores the result with deterministic checks from `evals/scoring.py`:

| Check | Passes when |
|---|---|
| `language_mix` | Share of target language stopwords vs English stopwords (lists in `data/stopwords.json`) is inside the level band: A0 5-50%, A1 20-80%, A2 55-100%, B1 80-100%. Skipped under 5 recognised words. |
| `scaffolding` | A0/A1 get scaffolding with a non-empty word bank; A2/B1 get none |
| `json_parses` | Every scaffold and analyze output parses as a JSON object |
| `length` | Reply is 5-150 words (A0/A1) or 5-220 words (A2/B1) |
| `grammar_feedback` | Error cases: analyze returns at least one correction |
| `no_lecture` | Error cases: reply avoids "wrong", "incorrect", "mistake", "error", "grammar rule" |
| `recast_in_reply` | Error cases: reply models a corrected form (for example "eres" for "Yo es") |
| `contains_any` | Case specific words, such as "danke" for "how do I say thank you" |
| `judge_recast` | Only with `--judge`: an LLM judge (the `analysis` profile) rates the correction a gentle recast, not a lecture |

Run it:

```bash
OPENROUTER_API_KEY=sk-or-... make eval            # all cases
make eval ARGS="--judge"                         # add the LLM judge on error cases
make eval ARGS="--only es-b1"                    # cases whose id contains "es-b1"
```

It refuses to start (exit 2) when `OPENROUTER_API_KEY` is not exported. It prints a table with checks passed, latency and tokens per case plus the pass rate, writes a JSON report to `evals/results/` (gitignored), and exits 1 if any case failed.

Cost: one run is about 50 LLM calls (respond and analyze per case, scaffold for A0/A1). Measured on 2026-11-14: about 32k input and 16k output tokens, roughly 1 US cent at Claude Haiku 5.5 list prices ($0.10 / $0.50 per million tokens).

### Results

| Date | Model | Pass rate | Time | Tokens in / out | Note |
|---|---|---|---|---|---|
| 2026-11-14 | `anthropic/claude-haiku-5.5` | 9/20 | 191s | 31.6k / 31.7k | Hidden reasoning used up `max_tokens` and cut the analyze JSON short, so grammar feedback was silently empty |
| 2026-11-14 | `anthropic/claude-haiku-5.5` | 20/20 | 117s | 31.6k / 15.9k | With reasoning disabled in `get_llm()` (#122) |

Add a row when the model, prompts or thresholds change.

The real eval never runs in CI or `make test`. CI covers the scorer and the runner through `tests/evals/`, which drive the real graph with a fake chat model.

## CI

`.github/workflows/ci.yml` runs on pushes to `main` and on PRs, only when `src/`, `tests/`, `data/`, dependency files, the Dockerfile, `render.yaml` or the workflow change.

```mermaid
flowchart LR
    lint[lint: ruff check + format] --> build
    type[typecheck: mypy src/] --> build
    test[test: pytest + coverage] --> build
    js[test-js: vitest] --> build
    build[build: Docker image] --> gate[ci-success]
    sec[security: bandit -ll] --> gate
    build -.push to main.-> deploy[deploy: Render hook]
    sec -.push to main.-> deploy
```

`ci-success` and `deploy` both wait on all six jobs (the diagram shortens this). `test-js` also runs `npm run build:css` and fails if the committed `src/static/css/styles.css` is stale.

- `test` uploads `coverage.xml` to Codecov (does not fail the build).
- `deploy` only runs on push to `main` and skips if `RENDER_DEPLOY_HOOK_URL` is not set.

## Writing a new test

1. Put it next to its peers in the table above. Python files are `test_*.py`, JS files are `*.test.js`.
2. Reuse `conftest.py` fixtures before adding new ones.
3. Mock the LLM and any HTTP client. A test that needs a real key is a bug.
4. Run the file serially first (`-n 0`), then the full suite.
