# HablaAI

**AI Language Tutor: A0 to B1**

An AI conversation partner that takes absolute beginners to confident intermediate speakers in Spanish or German. Unlike apps that drill vocabulary in isolation, HablaAI gets you talking from day one with level-appropriate scaffolding.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)
![Tests](https://img.shields.io/badge/Tests-229-brightgreen.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Current Status: Phase 1 Complete

- LangGraph StateGraph with `respond` node
- FastAPI + HTMX + Jinja2 server-driven UI
- Level-specific prompts (A0, A1, A2, B1) for Spanish and German
- Dark theme chat interface with level selector
- 229 pytest tests passing
- E2E testing infrastructure via Playwright

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI | Async API, SSE streaming, Pydantic validation |
| **Frontend** | HTMX + Jinja2 | Server-driven UI, minimal JavaScript |
| **Agent** | LangGraph | Stateful conversation graphs, routing, checkpointing |
| **LLM** | Claude API | Language understanding, structured outputs |
| **Database** | SQLite + SQLAlchemy | Simple persistence, vocabulary tracking |
| **Styling** | Tailwind CSS | Utility-first, dark theme |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/habla-ai.git
cd habla-ai

# Install dependencies
make install
```

### Environment Setup

Create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY=your_api_key_here
```

### Run Development Server

```bash
make dev
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
habla-ai/
├── src/
│   ├── api/              # FastAPI app, routes, dependencies
│   ├── agent/            # LangGraph definition, nodes, prompts
│   ├── db/               # SQLAlchemy models, repository
│   ├── services/         # Business logic (vocabulary, levels)
│   ├── templates/        # Jinja2 HTML templates
│   └── static/           # CSS, JavaScript assets
├── tests/                # Pytest test suite
├── docs/                 # Product and architecture documentation
└── data/                 # SQLite database, lesson content
```

---

## Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies with uv |
| `make dev` | Run development server on port 8000 |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage report |
| `make lint` | Run Ruff linter |
| `make format` | Format code with Ruff |
| `make typecheck` | Run MyPy type checker |
| `make check` | Run all checks (lint, format, typecheck) |
| `make db-init` | Initialize database |
| `make clean` | Remove build artifacts and caches |

---

## Development Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Minimal Graph - Basic StateGraph with respond node | Complete |
| **Phase 2** | Multi-node - Add analyze node for grammar/vocab | Planned |
| **Phase 3** | Conditional Routing - Scaffolding based on level | Planned |
| **Phase 4** | Checkpointing - Conversation persistence | Planned |
| **Phase 5** | Complex State - Rich nested state structures | Planned |
| **Phase 6** | Subgraphs - Lesson subgraphs, graph composition | Planned |

---

## Documentation

- [Product Specification](docs/product.md) - Vision, user journey, features
- [Technical Architecture](docs/architecture.md) - LangGraph design, API endpoints, database schema

---

## License

MIT
