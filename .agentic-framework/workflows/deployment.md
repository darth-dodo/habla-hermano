# Deployment Workflow

**Purpose**: Deploy habla-hermano to Render with verification and rollback procedures.

**Agents**: Developer (Pre-deploy) --> DevOps (Deploy) --> QA (Post-deploy)

---

## Pre-Deploy (Developer)

All must pass before merging to `main`:

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest --tb=short
grep -rn "breakpoint()\|import pdb\|print(" src/ --include="*.py" || echo "Clean"
```

### Required Environment Variables (set in Render dashboard)

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | LLM API access | Yes |
| `SUPABASE_URL` | Database connection | Yes |
| `SUPABASE_KEY` | Database auth | Yes |
| `LLM_MODEL` | Model (default: `claude-sonnet-4-20250514`) | No |
| `LLM_TEMPERATURE` | Creativity (default: `0.7`) | No |

### Pre-Deploy Checklist

- [ ] All quality gates pass
- [ ] Feature branch merged to `main` via PR
- [ ] Environment variables confirmed in Render dashboard
- [ ] `render.yaml` up-to-date if config changed

---

## Deploy (DevOps)

Render auto-deploys on push to `main` (configured in `render.yaml`):

```yaml
services:
  - type: web
    name: habla-hermano
    branch: main
    autoDeploy: true
    buildCommand: pip install uv && uv sync --frozen --no-dev --no-install-project
    startCommand: uv run uvicorn src.api.main:app --host 0.0.0.0 --port $PORT --workers 1
    healthCheckPath: /health
```

Render polls `/health` to verify service is up. Deploy completes when health check passes.

---

## Post-Deploy Verification (QA)

```bash
# Health check
curl -s https://habla-hermano.onrender.com/health | python -m json.tool

# Smoke test conversation
curl -X POST https://habla-hermano.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola", "level": "A1", "language": "es"}'
```

### Verification Checklist

- [ ] Health endpoint returns 200
- [ ] Chat endpoint responds with tutor message
- [ ] Supabase connection active
- [ ] No errors in response body

---

## Rollback

**When**: Health check fails, chat errors, LLM responses broken, DB connection errors.

**How**: Render Dashboard --> Service --> Deploys --> "Rollback" on previous successful deploy.

**Post-Rollback**:
- [ ] Verify service is healthy
- [ ] Create bug fix branch, follow [bug-fix.md](bug-fix.md)
- [ ] Re-deploy once fix validated

---

## Related Documents

- [feature-development.md](feature-development.md) -- Feature workflow (deploy after merge)
- [bug-fix.md](bug-fix.md) -- Bug fix process (post-rollback)
- [agent-development.md](agent-development.md) -- LangGraph node development
- [task-management.md](task-management.md) -- Task tracking and session lifecycle
