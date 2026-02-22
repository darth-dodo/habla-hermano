# Quality Gates - habla-hermano

7-gate system for the habla-hermano FastAPI backend. Every command below is copy-pasteable.

---

## Gate 1: Syntax Validation

Verify all Python files parse without syntax errors.

**Command:**

```bash
python -m compileall src/ tests/ -q
```

**Pass criteria:** Zero output (no errors). A non-zero exit code means a file failed to compile.

**When it fails:**

```bash
# Check a single file
python -m py_compile src/api/main.py

# Get AST-level detail
python -c "import ast; ast.parse(open('src/api/main.py').read())"
```

---

## Gate 2: Type Safety

Catch type errors before runtime. mypy runs in strict mode (configured in `pyproject.toml`).

**Command:**

```bash
uv run mypy src/
```

**Pass criteria:** Zero errors. Warnings are acceptable during development.

**Key configuration notes** (see `pyproject.toml` for full config):

- `strict = true` -- all strict flags enabled
- Third-party modules (langgraph, langchain, supabase, psycopg, jwt, etc.) have `ignore_missing_imports = true`
- `src.db.*` and `src.services.*` have `ignore_errors = true` for stub files not yet implemented

**When it fails:**

```bash
# Check a specific module
uv run mypy src/api/

# Show error codes for targeted suppression
uv run mypy src/ --show-error-codes

# Suppress a specific line (use sparingly)
x = some_call()  # type: ignore[no-untyped-call]
```

---

## Gate 3: Code Quality (Lint + Format)

Enforce coding standards and consistent formatting with ruff.

**Commands:**

```bash
# Lint
uv run ruff check src/ tests/

# Format check (CI mode, no changes)
uv run ruff format --check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/

# Auto-format
uv run ruff format src/ tests/
```

**Pass criteria:** Zero lint errors. Zero format differences.

**What ruff checks** (see `pyproject.toml [tool.ruff.lint]` for full list):

- `E/W` pycodestyle, `F` pyflakes, `I` isort, `B` flake8-bugbear
- `C4` comprehensions, `UP` pyupgrade, `ARG` unused arguments
- `SIM` simplify, `TCH` type-checking imports, `PTH` pathlib
- `ERA` commented-out code, `PL` pylint subset, `RUF` ruff-specific

**When it fails:**

```bash
# See what ruff would fix
uv run ruff check --diff src/ tests/

# Fix everything auto-fixable
uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/
```

---

## Gate 4: Security

No automated security scanner is currently in the project dependencies. This gate is a manual review checklist.

**Review checklist:**

- [ ] JWT tokens verified server-side via Supabase (see `src/api/` auth middleware)
- [ ] All user input validated with Pydantic models before processing
- [ ] No hardcoded secrets -- all credentials loaded from environment variables
- [ ] `.env` files are in `.gitignore`
- [ ] Rate limiting applied to public endpoints (see `ratelimit` dependency)
- [ ] No raw SQL with string interpolation -- all queries use parameterized statements
- [ ] LLM prompt injection mitigations in place for user-provided text
- [ ] CORS configuration is restrictive (not `allow_origins=["*"]` in production)

**Optional automated tooling** (not currently installed):

```bash
# If you add bandit to dev dependencies:
uv run bandit -r src/ -ll

# If you add pip-audit:
uv run pip-audit
```

---

## Gate 5: Tests

Verify functionality with pytest. Coverage threshold is 70% (configured in `pyproject.toml`).

**Commands:**

```bash
# Run all tests
uv run pytest

# Run with coverage (enforces 70% threshold)
uv run pytest --cov=src --cov-report=term-missing

# Run with HTML coverage report
uv run pytest --cov=src --cov-report=html --cov-report=term-missing

# Run fast tests only (skip slow/integration)
uv run pytest -m "not slow"

# Run a specific test file
uv run pytest tests/api/test_chat.py

# Stop on first failure
uv run pytest -x
```

**Pass criteria:**

- All tests pass
- Coverage >= 70% on `src/` (enforced by `fail_under = 70` in `pyproject.toml`)

**Test markers** (defined in `pyproject.toml`):

- `slow` -- tests that take significant time
- `integration` -- tests requiring external services (Supabase, LLM APIs)

**When coverage is too low:**

```bash
# See exactly which lines are uncovered
uv run pytest --cov=src --cov-report=term-missing

# Generate browsable HTML report
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## Gate 6: Performance

No automated performance gate exists for this project. This gate is a manual review checklist.

**Review checklist:**

- [ ] API endpoint response times are acceptable (target: < 500ms for non-LLM calls)
- [ ] LLM calls use streaming where appropriate to reduce perceived latency
- [ ] Database queries use indexes on frequently-queried columns
- [ ] No N+1 query patterns in data access layers
- [ ] Rate limiting prevents abuse without blocking legitimate traffic
- [ ] Async handlers used for I/O-bound operations (FastAPI async endpoints)
- [ ] LangGraph checkpointing does not create excessive database writes

**Manual verification:**

```bash
# Start the dev server
uv run uvicorn src.api.main:app --reload --port 8000

# Smoke-test response time
curl -w "\n%{time_total}s\n" http://localhost:8000/api/health
```

---

## Gate 7: Integration (Final Gate)

Run all automated gates together. This is the "does everything pass" check.

**Command:**

```bash
make lint && make typecheck && make test
```

Which expands to:

```bash
uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest
```

**Pass criteria:** All three commands exit with code 0.

**Full validation including format check:**

```bash
make check && make test
```

Which runs: lint + format-check + typecheck + tests.

**Health check after deployment:**

```bash
curl -f http://localhost:8000/api/health
```

---

## Skipping Gates

Use sparingly and document why.

```bash
# Skip pre-commit hooks for emergency commit
git commit --no-verify -m "hotfix: ..."

# Suppress a specific mypy error on one line
result = untyped_call()  # type: ignore[no-untyped-call]

# Suppress a specific ruff rule on one line
x = eval(expr)  # noqa: S307
```

---

## Gate Execution Order

Run the cheapest gates first for fast feedback:

1. **Syntax** (< 1s) -- catches broken files immediately
2. **Type Safety** (5-15s) -- catches type errors before running tests
3. **Lint + Format** (< 5s) -- catches style and logic issues
4. **Security** (manual) -- review before merging to main
5. **Tests** (30-120s) -- most expensive automated gate
6. **Performance** (manual) -- review for significant changes
7. **Integration** (combined) -- final automated check
