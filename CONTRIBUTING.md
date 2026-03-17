# Contributing to Habla Hermano

Thanks for your interest in contributing. This document covers the basics for getting started.

## Setup

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/your-username/habla-hermano.git
   cd habla-hermano
   ```

2. **Install dependencies** (requires [uv](https://docs.astral.sh/uv/)):

   ```bash
   make install
   ```

3. **Configure environment**:

   ```bash
   cp .env.example .env
   ```

   Fill in at minimum:
   - `ANTHROPIC_API_KEY` -- from [console.anthropic.com](https://console.anthropic.com/)
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL` -- from your [Supabase](https://supabase.com) project
   - `SECRET_KEY` -- generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

4. **Run the dev server**:

   ```bash
   make dev   # Starts at http://localhost:8000
   ```

## Running Tests

```bash
make test       # All tests (Python + JavaScript)
make test-fast  # Skip slow tests
make test-cov   # With coverage report
make test-js    # JavaScript tests only (Vitest)
```

The project has 2,400+ Python tests and 241 JavaScript tests.

## Code Quality

Before submitting a PR, ensure all checks pass:

```bash
make check   # Runs: ruff lint + ruff format --check + mypy
```

The project uses:
- **Ruff** for linting and formatting
- **MyPy** in strict mode for type checking
- **Pre-commit hooks** (install with `make install-hooks`)

## Pull Request Guidelines

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests** for new functionality. Follow the patterns in `tests/`.

3. **Ensure `make check` passes** with no errors.

4. **Keep commits focused**. One logical change per commit with a descriptive message.

5. **Open a PR** with a clear description of what changed and why.

## Project Structure

```
src/           Core application code
  api/         FastAPI routes, middleware, auth
  agent/       LangGraph pipeline, nodes, prompts
  db/          Database client, models, repositories
  services/    Business logic (review, paths, adaptive)
  lessons/     Lesson models and service
  templates/   Jinja2 HTML templates
  static/      CSS + JavaScript modules
tests/         Python tests (pytest)
tests/js/      JavaScript tests (Vitest)
data/lessons/  60 YAML lesson files
docs/          Architecture docs and design documents
migrations/    SQL migration files for Supabase
```

## Code Style

- Follow existing patterns in the codebase
- Python: type hints on all functions, no `Any` without justification
- JavaScript: ES modules, no global state
- Templates: HTMX for interactivity, minimal inline JS
- CSS: Tailwind utility classes, CSS custom properties for theming
