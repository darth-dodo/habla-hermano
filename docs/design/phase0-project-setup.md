# Feature: Phase 0 - Project Setup and Infrastructure

## Overview

Phase 0 establishes the foundation for HablaAI: a modern Python web application stack optimized for rapid development and maintainability. This phase focuses on project scaffolding, development tooling, and infrastructure configuration before any application logic is implemented.

**Business Value**: A well-configured project foundation reduces friction for future development, ensures code quality from day one, and establishes patterns that scale as the application grows.

**Learning Goal**: Master modern Python project setup with FastAPI, HTMX, and Tailwind CSS as a lightweight alternative to heavy JavaScript frameworks.

---

## Requirements

### Functional Requirements

1. **Python Environment**: Modern Python 3.11+ with type hints throughout
2. **Web Framework**: FastAPI with async support for the backend
3. **Template Rendering**: Jinja2 templates with HTMX for interactivity
4. **Styling**: Tailwind CSS for utility-first styling
5. **Development Server**: Hot reload for rapid iteration

### Non-Functional Requirements

- Project setup should take less than 5 minutes for new contributors
- All tooling commands available through Makefile
- Pre-commit hooks enforce code quality before commits
- Type checking catches errors at development time

---

## Architecture

### Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Jinja2    │  │    HTMX     │  │  Tailwind   │         │
│  │  Templates  │  │  (No React) │  │     CSS     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      Backend Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   FastAPI   │  │   Pydantic  │  │   SQLite    │         │
│  │   (async)   │  │  Settings   │  │  (aiosqlite)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Development Tooling                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  │   uv    │ │  Ruff   │ │  MyPy   │ │ Pytest  │ │Pre-   │ │
│  │ (pkgs)  │ │ (lint)  │ │ (types) │ │ (test)  │ │commit │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure

```
habla-ai/
├── src/
│   ├── __init__.py
│   ├── api/                    # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py            # App entry point, lifespan management
│   │   ├── config.py          # Pydantic Settings configuration
│   │   └── routes/            # Route modules
│   │       ├── __init__.py
│   │       └── chat.py        # Chat endpoints
│   ├── agent/                  # LangGraph agent (Phase 1+)
│   │   ├── __init__.py
│   │   ├── graph.py           # LangGraph workflow
│   │   ├── state.py           # Conversation state
│   │   ├── prompts.py         # LLM prompt templates
│   │   ├── routing.py         # Conditional routing logic
│   │   └── nodes/             # Graph nodes
│   │       ├── __init__.py
│   │       ├── respond.py     # AI response generation
│   │       ├── analyze.py     # Grammar/vocab analysis
│   │       ├── feedback.py    # Feedback formatting
│   │       └── scaffold.py    # Beginner scaffolding
│   ├── db/                     # Database layer (Phase 4+)
│   │   └── ...
│   ├── services/               # Business logic services
│   │   └── ...
│   ├── static/                 # Static assets
│   │   ├── css/
│   │   │   ├── input.css      # Tailwind source
│   │   │   ├── output.css     # Compiled CSS (gitignored)
│   │   │   └── styles.css     # Additional custom styles
│   │   └── js/                # JavaScript files
│   └── templates/              # Jinja2 templates
│       ├── base.html          # Base template with head/scripts
│       ├── chat.html          # Main chat interface
│       ├── lessons.html       # Lessons page
│       └── partials/          # HTMX partial templates
│           └── ...
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures
│   ├── test_api_config.py
│   ├── test_api_routes.py
│   └── ...
├── docs/                       # Documentation
│   ├── api.md                 # API reference
│   ├── architecture.md        # Technical architecture
│   ├── product.md             # Product requirements
│   ├── testing.md             # Testing guide
│   └── design/                # Design documents
│       └── ...
├── data/                       # SQLite database (gitignored)
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI pipeline
├── pyproject.toml             # Project config and dependencies
├── uv.lock                    # Locked dependencies
├── Makefile                   # Development commands
├── .pre-commit-config.yaml    # Pre-commit hook configuration
├── .env.example               # Environment template
├── .gitignore                 # Git ignore patterns
├── .secrets.baseline          # detect-secrets allowlist
├── Dockerfile                 # Container build
├── render.yaml                # Render deployment config
└── README.md                  # Project documentation
```

---

## Technical Decisions

### Why FastAPI

FastAPI was chosen over Django or Flask for several reasons:

| Factor | FastAPI | Django | Flask |
|--------|---------|--------|-------|
| **Async Support** | Native async/await | Partial (ASGI) | Requires extensions |
| **Type Hints** | First-class | Optional | Optional |
| **Auto Documentation** | OpenAPI built-in | External tools | External tools |
| **Performance** | High (Starlette) | Moderate | Moderate |
| **Learning Curve** | Modern Python patterns | Django ORM/conventions | Minimal |
| **Validation** | Pydantic integration | Forms-based | Manual |

**Decision**: FastAPI's native async support aligns with LangGraph's async nodes, and Pydantic integration ensures type-safe configuration and request validation.

### Why HTMX over React/Vue

| Factor | HTMX + Jinja2 | React/Vue SPA |
|--------|---------------|---------------|
| **Bundle Size** | ~14KB (HTMX) | 100KB+ (React) |
| **Build Step** | None | Webpack/Vite required |
| **JavaScript Required** | Minimal | Extensive |
| **Server-Side Rendering** | Native | Requires SSR setup |
| **Learning Curve** | HTML attributes | Component lifecycle |
| **SEO** | Excellent | Requires hydration |
| **Real-time Updates** | WebSocket or polling | Built-in state |

**Decision**: HTMX provides sufficient interactivity for a chat interface without the complexity of a JavaScript framework. Server-rendered HTML with HTMX partial updates keeps the stack simple and the bundle small.

### Why Tailwind CSS

| Factor | Tailwind CSS | Traditional CSS | CSS-in-JS |
|--------|--------------|-----------------|-----------|
| **Rapid Prototyping** | Excellent | Slow | Moderate |
| **Design Consistency** | Built-in constraints | Manual | Variable |
| **Bundle Size** | Small (purged) | Variable | Runtime overhead |
| **Learning Curve** | Utility classes | CSS fundamentals | Framework-specific |
| **Dark Mode** | Built-in variants | Manual | Framework-specific |
| **Responsive Design** | Mobile-first classes | Media queries | Manual |

**Decision**: Tailwind's utility-first approach enables rapid UI iteration. The input.css file uses `@layer` directives for custom component classes that maintain consistency across the chat interface.

### Why uv Package Manager

| Factor | uv | pip + venv | Poetry |
|--------|-----|-----------|--------|
| **Speed** | 10-100x faster | Baseline | 2-3x slower |
| **Lock File** | Native | pip-tools | Native |
| **Python Version** | Manages versions | System only | pyenv integration |
| **Dependency Resolution** | Fast, correct | Basic | Correct but slow |
| **Disk Space** | Efficient | Duplicates | Duplicates |

**Decision**: uv provides dramatically faster dependency installation (important for CI) and modern Python version management. The `uv sync --dev` command installs all dependencies from the lock file in seconds.

---

## Configuration Files

### pyproject.toml

The central configuration file containing:

```toml
[project]
name = "habla-ai"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Web framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.12",

    # Database
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.20.0",

    # LangGraph + LangChain
    "langchain>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langgraph>=0.2.0",

    # Configuration
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "pre-commit>=4.0.0",
]
```

**Key Configuration Sections**:

- `[tool.ruff]` - Linter rules (E, W, F, I, B, C4, UP, etc.) with Python 3.11 target
- `[tool.ruff.lint]` - 100-character line length, first-party imports configuration
- `[tool.mypy]` - Strict mode with LangChain import exceptions
- `[tool.pytest.ini_options]` - Async mode auto-detection, coverage thresholds
- `[tool.coverage.report]` - 70% minimum coverage requirement

### .pre-commit-config.yaml

Pre-commit hooks enforce quality before code reaches the repository:

```yaml
repos:
  # General hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: detect-private-key

  # Python: Ruff (linting + formatting)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
        args: [--config-file=pyproject.toml, src]

  # Security
  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  # Commit message format
  - repo: https://github.com/commitizen-tools/commitizen
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

### Makefile

Developer-friendly commands for common operations:

```makefile
# Installation
install:         # Install dependencies with uv
install-hooks:   # Install pre-commit hooks

# Development
dev:             # Run development server (uvicorn --reload)
dev-css:         # Watch and compile Tailwind CSS

# Testing
test:            # Run all tests
test-cov:        # Run tests with coverage report
test-fast:       # Run tests without slow markers

# Code Quality
lint:            # Run Ruff linter
lint-fix:        # Run Ruff with auto-fix
format:          # Format code with Ruff
typecheck:       # Run MyPy type checker
check:           # Run all checks (lint, format, typecheck)

# Pre-commit
pre-commit:      # Run pre-commit on all files

# Database
db-init:         # Initialize database
db-seed:         # Seed database with initial data
db-reset:        # Reset database (drop and recreate)

# Cleanup
clean:           # Remove build artifacts and caches
clean-all:       # Remove all generated files including db
```

### .env.example

Environment configuration template:

```bash
# LLM Configuration
ANTHROPIC_API_KEY=your_api_key_here
LLM_MODEL=claude-sonnet-4-20250514
LLM_TEMPERATURE=0.7

# Database
DATABASE_URL=sqlite:///data/habla.db

# Application
DEBUG=true
HOST=127.0.0.1
PORT=8000

# Feature Flags
ENABLE_VOICE_INPUT=false
ENABLE_SPACED_REPETITION=false
```

---

## Development Workflow

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/darth-dodo/habla-ai.git
cd habla-ai

# 2. Install dependencies (uses uv)
make install

# 3. Install pre-commit hooks
make install-hooks

# 4. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. Start development server
make dev
```

### Daily Development

```bash
# Terminal 1: Run the server
make dev

# Terminal 2: Watch Tailwind CSS (if making style changes)
make dev-css

# Before committing
make check      # Run lint, format check, and typecheck
make test       # Run test suite
```

### Code Quality Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `make lint` | Check for linting errors | Before committing |
| `make lint-fix` | Auto-fix linting errors | Fix style issues |
| `make format` | Format code | Ensure consistent style |
| `make typecheck` | Run MyPy type checker | Catch type errors |
| `make check` | All quality checks | Pre-commit validation |
| `make test` | Run pytest | Verify functionality |
| `make test-cov` | Test with coverage | Check coverage metrics |

### Pre-commit Flow

When you run `git commit`, pre-commit hooks automatically:

1. Remove trailing whitespace and fix EOF
2. Validate YAML, JSON, and TOML files
3. Check for merge conflicts and private keys
4. Run Ruff linter with auto-fix
5. Run Ruff formatter
6. Run MyPy type checker on `src/`
7. Scan for secrets with detect-secrets
8. Validate commit message format (commitizen)

---

## CI/CD Pipeline

### GitHub Actions (`.github/workflows/ci.yml`)

The CI pipeline runs on every push to `main` and all pull requests:

```yaml
jobs:
  lint:
    # Ruff linter and formatter check

  typecheck:
    # MyPy strict type checking

  test:
    # Pytest with coverage reporting
    # Uploads coverage to Codecov

  docker:
    # Validates Dockerfile builds successfully
    # Ensures Render deployment will work
```

### Deployment (Render)

The `render.yaml` file configures automatic deployment:

- Docker-based deployment from the repository
- Health check endpoint at `/health`
- Environment variables managed through Render dashboard

---

## Dependencies

### Production Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `fastapi` | Web framework | >=0.115.0 |
| `uvicorn[standard]` | ASGI server | >=0.32.0 |
| `jinja2` | Template engine | >=3.1.0 |
| `python-multipart` | Form data parsing | >=0.0.12 |
| `sqlalchemy` | ORM and database toolkit | >=2.0.0 |
| `aiosqlite` | Async SQLite driver | >=0.20.0 |
| `langchain` | LLM orchestration | >=0.3.0 |
| `langchain-anthropic` | Claude API integration | >=0.3.0 |
| `langgraph` | Stateful agent workflows | >=0.2.0 |
| `pydantic-settings` | Configuration management | >=2.0.0 |
| `python-dotenv` | Environment file loading | >=1.0.0 |

### Development Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `pytest` | Testing framework | >=8.0.0 |
| `pytest-asyncio` | Async test support | >=0.24.0 |
| `pytest-cov` | Coverage reporting | >=6.0.0 |
| `httpx` | Async HTTP client (testing) | >=0.28.0 |
| `ruff` | Linter and formatter | >=0.8.0 |
| `mypy` | Static type checker | >=1.13.0 |
| `pre-commit` | Git hook management | >=4.0.0 |

---

## Success Criteria

### Infrastructure

- [x] Python 3.11+ project with uv package manager
- [x] FastAPI application with async lifespan management
- [x] Jinja2 templates with HTMX integration
- [x] Tailwind CSS with custom component classes
- [x] SQLite database with async support

### Tooling

- [x] Makefile with all common commands
- [x] Pre-commit hooks for quality enforcement
- [x] Ruff linting with comprehensive rule set
- [x] MyPy strict type checking
- [x] Pytest with async support and coverage

### CI/CD

- [x] GitHub Actions pipeline for lint/test/typecheck
- [x] Docker build validation in CI
- [x] Render deployment configuration

### Documentation

- [x] README with quick start guide
- [x] Environment configuration template (.env.example)
- [x] Comprehensive .gitignore

---

## Appendix: Key File Examples

### FastAPI Application Entry Point

```python
# src/api/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting %s...", settings.APP_NAME)
    yield
    logger.info("Shutting down %s...", settings.APP_NAME)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-powered language tutor",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    app.include_router(chat.router)
    return app

app = create_app()
```

### Pydantic Settings Configuration

```python
# src/api/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    ANTHROPIC_API_KEY: str
    APP_NAME: str = "HablaAI"
    DEBUG: bool = False
    LLM_MODEL: str = "claude-sonnet-4-20250514"

    @property
    def templates_dir(self) -> Path:
        return self.project_root / "src" / "templates"
```

### Tailwind CSS Structure

```css
/* src/static/css/input.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
    .chat-bubble {
        @apply px-4 py-3 rounded-2xl max-w-[85%];
    }
    .chat-bubble-user {
        @apply chat-bubble bg-primary-600 text-white rounded-tr-sm;
    }
    .btn-primary {
        @apply px-4 py-3 bg-primary-600 hover:bg-primary-500
               text-white font-medium rounded-xl transition-colors;
    }
}
```

This Phase 0 setup provides a solid foundation for all subsequent phases of HablaAI development.
