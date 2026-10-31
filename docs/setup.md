# Setup Guide

Step-by-step instructions for setting up Habla Hermano locally and deploying to production.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for Tailwind CSS and Vitest)
- A [Supabase](https://supabase.com) account (free tier works)
- An [OpenRouter API key](https://openrouter.ai/keys)

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
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `SUPABASE_URL` | Supabase dashboard > Settings > API |
| `SUPABASE_ANON_KEY` | Supabase dashboard > Settings > API |
| `SUPABASE_DB_URL` | Supabase dashboard > Settings > Database > Connection string |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

**Optional variables:**

| Variable | Purpose |
|----------|---------|
| `DEEPGRAM_API_KEY` | Enables voice input/output (STT/TTS) |
| `SENTRY_DSN` | Enables Sentry error monitoring (backend + frontend) |
| `OPENROUTER_ZERO_RETENTION` | Restrict routing to providers that don't retain/train on data |
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
