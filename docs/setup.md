# Setup Guide

Step-by-step instructions for setting up Habla Hermano locally and deploying to production.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for Tailwind CSS and Vitest)
- A [Supabase](https://supabase.com) account (free tier works)
- An [Anthropic API key](https://console.anthropic.com/)

## 1. Supabase Project Setup

1. Create a new project at [supabase.com/dashboard](https://supabase.com/dashboard).
2. Go to **Settings > API** and note:
   - **Project URL** (e.g., `https://abcdefg.supabase.co`)
   - **Anon/public key** (starts with `eyJ...`)
3. Go to **Settings > Database > Connection string > URI** and note the connection string.
4. Go to **Authentication > Providers > Email** and enable the Email provider.

## 2. Database Migrations

Run the following SQL files in order via the Supabase SQL Editor (**SQL Editor** in the dashboard sidebar). Each file is in the `migrations/` directory:

| Order | File | Purpose |
|-------|------|---------|
| 1 | `phase12_spaced_repetition.sql` | Vocabulary and review tables |
| 2 | `fix_vocabulary_columns.sql` | Column fixes for vocabulary table |
| 3 | `003_atomic_counter_operations.sql` | Atomic counter operations |
| 4 | `004_checkpoint_rls.sql` | Row-level security on checkpoint tables |
| 5 | `005_conversation_threads.sql` | Conversation thread support |

To run each migration: open the file, copy its contents, paste into the Supabase SQL Editor, and click **Run**.

## 3. Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values. See `.env.example` for descriptions of each variable.

**Required variables:**

| Variable | Source |
|----------|--------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| `SUPABASE_URL` | Supabase dashboard > Settings > API |
| `SUPABASE_ANON_KEY` | Supabase dashboard > Settings > API |
| `SUPABASE_DB_URL` | Supabase dashboard > Settings > Database > Connection string |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

**Optional variables:**

| Variable | Purpose |
|----------|---------|
| `DEEPGRAM_API_KEY` | Enables voice input/output (STT/TTS) |
| `SENTRY_DSN` | Enables Sentry error monitoring (backend + frontend) |
| `ANTHROPIC_ZERO_RETENTION` | Request Anthropic not to log API data |
| `DEBUG` | Enable debug mode (local dev only) |

## 4. Install and Run

```bash
make install   # Install Python + JS dependencies
make dev       # Start dev server at http://localhost:8000
```

## 5. Deployment (Render)

The project includes a `render.yaml` blueprint for one-click deployment to [Render](https://render.com):

1. Push your repo to GitHub.
2. In Render, click **New > Blueprint** and connect your repository.
3. Render will detect `render.yaml` and configure the service.
4. Set the environment variables listed above in the Render dashboard.

The start command is:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

### Deploy hook from CI

Render's Git auto-deploy has not always fired on merges to `main`, so CI can trigger the deploy instead. The `deploy` job in `.github/workflows/ci.yml` runs only on `push` to `main`, waits for every check (`lint`, `typecheck`, `test`, `test-js`, `security`, `build`) to pass, then POSTs to a Render deploy hook. The hook URL is read from the `RENDER_DEPLOY_HOOK_URL` repository secret and is never printed. If the secret is not set, the job skips the deploy step and stays green.

One-time setup:

1. In the Render dashboard, open the `habla-hermano` service, go to **Settings > Deploy Hook**, and copy the URL. Treat it as a secret: anyone holding it can trigger deploys.
2. Store it as a repository secret (paste the URL when prompted, so it does not land in shell history):
   ```bash
   gh secret set RENDER_DEPLOY_HOOK_URL -R darth-dodo/habla-hermano
   ```
3. In Render, go to **Settings > Build & Deploy > Auto-Deploy** and set it to **Off**, so each merge deploys once (from CI) instead of twice. `render.yaml` keeps `autoDeploy: true` until the hook is confirmed working; once it is, change it to `autoDeploy: false` so a Blueprint sync does not switch Auto-Deploy back on.
4. After the next merge to `main`, confirm the live commit with `curl -s https://habla-hermano.onrender.com/version` (once `/version` is available) and compare it to `git rev-parse origin/main`.

Trade-off: CI is path-filtered, so a push that only touches unfiltered paths (for example `docs/`, `README.md`, `migrations/`) does not run CI and does not deploy. Those paths do not change the running app (SQL migrations are applied to Supabase separately). `data/` is read at runtime (lessons, stopwords), so it is part of the CI path filter. If a deploy is ever needed for an unfiltered change, use **Manual Deploy > Deploy latest commit** in Render.
