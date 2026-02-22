# Run Quality Checks

Run the full quality check pipeline: lint, format, typecheck, and tests.

## When to Use
- Before committing changes
- After implementing a feature or fix
- Before creating a pull request
- When CI fails and you need to reproduce locally

## Steps

1. **Run all checks in sequence** (mirrors CI pipeline)
   ```bash
   # Lint
   uv run ruff check src/ tests/

   # Format check
   uv run ruff format --check src/ tests/

   # Type check
   uv run mypy src/

   # Tests
   uv run pytest -v
   ```

   Or use the Makefile shortcut:
   ```bash
   make check   # lint + format-check + typecheck
   make test    # all tests
   ```

2. **Auto-fix lint and format issues**
   ```bash
   uv run ruff check --fix src/ tests/
   uv run ruff format src/ tests/
   ```

3. **Run tests with coverage**
   ```bash
   uv run pytest --cov=src --cov-report=term-missing
   ```
   Target: 97% coverage (current), minimum 70% (configured).

4. **Run specific test modules**
   ```bash
   # Agent tests only
   uv run pytest tests/agent/ -v

   # API route tests
   uv run pytest tests/api/ -v

   # Service tests
   uv run pytest tests/services/ -v

   # Database tests
   uv run pytest tests/db/ -v

   # Lesson tests
   uv run pytest tests/lessons/ -v

   # Single test file
   uv run pytest tests/agent/nodes/test_analyze.py -v

   # Single test function
   uv run pytest tests/agent/nodes/test_analyze.py::test_function_name -v
   ```

5. **Full CI reproduction**
   ```bash
   # Matches .github/workflows/ci.yml exactly
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run mypy src/
   uv run pytest --cov=src --cov-report=term-missing
   ```

## Common Issues

| Issue | Fix |
|-------|-----|
| Import order | `uv run ruff check --fix` (isort rules) |
| Line too long | Formatter handles it: `uv run ruff format` |
| Unused import | `uv run ruff check --fix` (F401) |
| Type error in src/db | MyPy has `ignore_errors = true` for `src.db.*` |
| Type error in src/services | MyPy has `ignore_errors = true` for `src.services.*` |
| Late import warning (PLC0415) | Allowed in `src/agent/nodes/*.py` for circular dep avoidance |
| Async test issues | Tests use `asyncio_mode = "auto"` - no `@pytest.mark.asyncio` needed |

## Ruff Rules Reference
- **E/W**: pycodestyle (style errors/warnings)
- **F**: Pyflakes (unused imports, undefined names)
- **I**: isort (import ordering)
- **B**: flake8-bugbear (common bugs)
- **UP**: pyupgrade (modern Python patterns)
- **SIM**: flake8-simplify (simplification suggestions)
- **RUF**: Ruff-specific rules
