# HablaAI Makefile
# Usage: make [target]

.PHONY: install dev test lint format typecheck clean help
.DEFAULT_GOAL := help

# =============================================================================
# Installation
# =============================================================================

install: ## Install dependencies with uv
	uv sync --dev

install-hooks: ## Install pre-commit hooks
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# =============================================================================
# Development
# =============================================================================

dev: ## Run development server
	uv run uvicorn src.api.main:app --reload --port 8000

dev-css: ## Watch and compile Tailwind CSS
	npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css --watch

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	uv run pytest

test-cov: ## Run tests with coverage report
	uv run pytest --cov=src --cov-report=html --cov-report=term-missing

test-fast: ## Run tests without slow markers
	uv run pytest -m "not slow"

test-watch: ## Run tests in watch mode
	uv run pytest-watch

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run Ruff linter
	uv run ruff check src/ tests/

lint-fix: ## Run Ruff linter with auto-fix
	uv run ruff check --fix src/ tests/

format: ## Format code with Ruff
	uv run ruff format src/ tests/

format-check: ## Check code formatting
	uv run ruff format --check src/ tests/

typecheck: ## Run MyPy type checker
	uv run mypy src/

check: lint format-check typecheck ## Run all checks (lint, format, typecheck)

# =============================================================================
# Pre-commit
# =============================================================================

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	uv run pre-commit autoupdate

# =============================================================================
# Database
# =============================================================================

db-init: ## Initialize database
	uv run python -c "from src.db.models import init_db; init_db()"

db-seed: ## Seed database with initial data
	uv run python src/db/seed.py

db-reset: ## Reset database (drop and recreate)
	rm -f data/habla.db
	$(MAKE) db-init
	$(MAKE) db-seed

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	rm -rf dist/ build/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Remove all generated files including db
	rm -f data/habla.db
	rm -rf node_modules/
	rm -f src/static/css/output.css

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
