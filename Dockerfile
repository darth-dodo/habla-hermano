# Habla Hermano Production Dockerfile
#
# A simple, single-stage Dockerfile for the Habla Hermano FastAPI application.
# Uses Python 3.12-slim base with uv for fast dependency management.
#
# Build:   docker build -t habla-ai .
# Run:     docker run -p 8000:8000 --env-file .env habla-ai
#
# Required environment variables:
#   - ANTHROPIC_API_KEY: API key for Claude LLM access
#
# Optional environment variables (see .env.example for full list):
#   - DEBUG: true|false (default: false)
#   - LLM_MODEL: Model to use (default: claude-sonnet-4-20250514)
#   - DATABASE_URL: SQLite database path (default: sqlite:///data/habla.db)

FROM python:3.12-slim

# Copy uv from the official image for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy all necessary files for installation
COPY pyproject.toml .
COPY uv.lock* .
COPY README.md .
COPY src/ src/

# Create data directory for SQLite database
RUN mkdir -p data

# Create venv and install the package (production dependencies only)
# Using --system to install into the container's Python environment
RUN uv pip install --system .

# Expose the application port
EXPOSE 8000

# Run the FastAPI application with uvicorn
# --host 0.0.0.0 allows connections from outside the container
# PORT environment variable support for Render compatibility (defaults to 8000)
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
