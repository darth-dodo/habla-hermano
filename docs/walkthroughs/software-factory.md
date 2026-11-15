# Walkthrough: the software factory

How a change travels from an idea to production. Most changes start as a request to a coding agent (Claude Code), which works in its own git worktree and opens a PR. Checks then catch bad changes: local hooks, six CI jobs, a CI success gate, and a health check after deploy.

## Design

```mermaid
graph LR
    I([Request]) --> W[Agent in a worktree<br/>branch from origin/main]
    W --> L[Local gates<br/>pre-commit + make check]
    L --> P[Pull request]
    P --> C[CI: 6 jobs]
    C --> G{all jobs passed?}
    G -. "no: fix" .-> W
    G -- yes --> M[Person merges]
    M -- "push to main, CI again" --> D[Render deploy hook]
    D --> H([/health + /version])
```

| Stage | What runs | Code |
|---|---|---|
| Agent recipes | 12 repo skills (`.claude/skills/<name>/SKILL.md`): add a route, node, lesson, test; run checks; `ask` answers questions about the code with file:line evidence | [.claude/skills/](../../.claude/skills/) |
| Local gates | pre-commit (ruff, mypy, secret and large-file checks), `make check` | [.pre-commit-config.yaml](../../.pre-commit-config.yaml), [Makefile](../../Makefile) |
| CI | lint, typecheck, test with 88% coverage floor and a Postgres service for SQL tests, JS tests + stale CSS check, Bandit, Docker build | [ci.yml](../../.github/workflows/ci.yml) |
| Gate | `ci-success` fails if any job did not succeed | [ci-success](../../.github/workflows/ci.yml#L227-L245) |
| Deploy | Render deploy hook, push to main only, after every job | [deploy](../../.github/workflows/ci.yml#L255-L283) |
| Verify | Render polls `/health`; `/version` names the deployed commit | [main.py](../../src/api/main.py) |
| Manual | `make eval` against the real model before prompt or model changes | [Makefile](../../Makefile) |

**Key decisions**

- **Agents write, people merge.** Agent output gets the same checks as human code, and a person merges each PR.
- **One worktree per task.** Parallel agents never touch the same checkout or someone's uncommitted work.
- **Repo skills as recipes.** They keep agent changes in the house style.
- **The CI hook deploys only after every job passes.**

## Implementation

The checks that turn CI red:

```yaml
# .github/workflows/ci.yml: Tailwind is compiled and committed; stale CSS fails CI (#121)
- name: Check built Tailwind CSS is up to date
  run: |
    npm run build:css
    git diff --exit-code src/static/css/styles.css || { ...; exit 1; }
```

```toml
# pyproject.toml: coverage floor (#118)
fail_under = 88
```

```yaml
# .github/workflows/ci.yml: deploy only after all six jobs, on push to main
deploy:
  needs: [lint, typecheck, test, test-js, security, build]
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  concurrency: { group: render-deploy, cancel-in-progress: false }
```

## Gates and gaps (checked 2026-11-15)

- **main requires `CI Success`** (branch protection, set 2026-11-15). Admins can still bypass it in an emergency, and force pushes and deletion are blocked.
- **Render deploys only from CI** ([render.yaml](../../render.yaml#L28-L31) sets `autoDeploy: false`). The Render dashboard's Auto-Deploy toggle must also be Off.
- **Every PR runs CI**, so the required check always reports. Pushes to main keep the path filter, so docs-only merges do not redeploy.
- **Evals are manual.** No CI job runs `make eval`.
