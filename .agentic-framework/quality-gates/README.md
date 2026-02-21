# Quality Gates - habla-hermano

7-gate quality system for the habla-hermano Python backend API (FastAPI + LangGraph + Supabase).

## Quick Start

```bash
# Install dev dependencies
uv sync --dev

# Run all checks (the final gate)
make lint && make typecheck && make test

# Run individually
uv run ruff check src/ tests/          # Gate 3: Lint
uv run ruff format --check src/ tests/ # Gate 3: Format check
uv run mypy src/                       # Gate 2: Type check
uv run pytest                          # Gate 5: Tests
uv run pytest --cov=src --cov-report=term-missing  # Gate 5: Tests + coverage
```

## The 7 Gates

| Gate | Name | Command | Threshold |
|------|------|---------|-----------|
| 1 | Syntax | `python -m compileall src/ tests/ -q` | Zero errors |
| 2 | Type Safety | `uv run mypy src/` | Zero errors (strict mode) |
| 3 | Lint + Format | `uv run ruff check src/ tests/` | Zero errors |
| 4 | Security | Manual review checklist | JWT, auth, input validation |
| 5 | Tests | `uv run pytest --cov=src --cov-report=term-missing` | 70% coverage |
| 6 | Performance | Manual review checklist | API response times, query patterns |
| 7 | Integration | `make lint && make typecheck && make test` | All pass |

Gate 7 (Accessibility) from the generic system is removed -- this is a backend API, not a UI.

## File Reference

- **[generic-gates.md](generic-gates.md)** -- Full gate definitions with commands and checklists
- **[examples/python.md](examples/python.md)** -- habla-hermano-specific examples and workflows

## Configuration

All tool configuration lives in `pyproject.toml` at the project root:

- `[tool.ruff]` / `[tool.ruff.lint]` -- Linter and formatter rules
- `[tool.mypy]` -- Type checker with strict mode and per-module overrides
- `[tool.pytest.ini_options]` -- Test runner and markers
- `[tool.coverage.run]` / `[tool.coverage.report]` -- Coverage with `fail_under = 70`

## CI/CD Quick Reference

```yaml
# .github/workflows/quality-gates.yml
steps:
  - name: Install dependencies
    run: uv sync --dev

  - name: Gate 1-3 - Syntax, Types, Lint
    run: |
      python -m compileall src/ tests/ -q
      uv run mypy src/
      uv run ruff check src/ tests/
      uv run ruff format --check src/ tests/

  - name: Gate 5 - Tests
    run: uv run pytest --cov=src --cov-report=term-missing
```
