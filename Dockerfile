# Habla Hermano Production Dockerfile
#
# A simple, single-stage Dockerfile for the Habla Hermano FastAPI application.
# Uses Python 3.12-slim base with uv for fast dependency management.
#
# Build:   docker build -t habla-ai .
# Run:     docker run -p 8000:8000 --env-file .env habla-ai
#
# Required environment variables:
#   - OPENROUTER_API_KEY: API key for OpenRouter LLM access
#
# Optional environment variables (see .env.example for full list):
#   - DEBUG: true|false (default: false)
#   - LLM_MODEL: Model to use (default: anthropic/claude-haiku-4.5)
#   - SUPABASE_URL: Supabase project URL
#   - SUPABASE_ANON_KEY: Supabase anonymous/public key
#   - SUPABASE_SERVICE_KEY: Supabase service role key
#   - SUPABASE_DB_URL: Supabase PostgreSQL connection string

FROM python:3.12-slim

# Copy uv from the official image for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy all necessary files for installation
COPY pyproject.toml .
COPY uv.lock* .
COPY README.md .
COPY src/ src/
COPY data/ data/

# Create venv and install the package (production dependencies only)
# Using --system to install into the container's Python environment
RUN uv pip install --system .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Expose the application port
EXPOSE 8000

# Health check to monitor application availability
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Run the FastAPI application with uvicorn
# --host 0.0.0.0 allows connections from outside the container
# PORT environment variable support for Render compatibility (defaults to 8000)
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
