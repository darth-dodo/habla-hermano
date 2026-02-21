# Bug Fix Workflow

**Purpose**: Systematic workflow for investigating, fixing, and verifying bugs in habla-hermano.

**Agents**: Developer (Investigate) --> Developer (Fix) --> QA (Verify)

---

## Phase 1: Investigate (Developer)

**Objective**: Root cause analysis and fix strategy.

### Tasks

- [ ] Reproduce the bug consistently
- [ ] Document reproduction steps and environment
- [ ] Analyze error messages, stack traces, and logs
- [ ] Check recent commits: `git log --oneline -20`
- [ ] Identify affected components:
  - Agent nodes (`src/agent/nodes/`)? Graph routing (`src/agent/routing.py`)?
  - API layer (`src/api/`)? Database (`src/db/`)?
  - Prompt templates (`src/templates/`)? Services (`src/services/`)?
- [ ] Determine root cause (not just symptoms)
- [ ] Develop fix strategy with alternatives

### Root Cause Categories

- **Agent Logic**: Incorrect node behavior, routing errors, state corruption
- **Prompt Issues**: Template producing wrong output, missing context
- **API Layer**: Endpoint validation, request handling, SSE streaming
- **State Management**: `ConversationState` fields missing or mistyped
- **External Services**: Anthropic API errors, Supabase connection issues
- **Configuration**: Environment variables, model settings

### Quality Gate: Investigation Review

- [ ] Bug reliably reproducible
- [ ] Root cause identified (not symptoms)
- [ ] Impact assessed (which user flows break)
- [ ] Fix strategy defined with alternatives
- [ ] Testing requirements specified

---

## Phase 2: Fix (Developer)

**Objective**: Implement fix with regression tests using TDD.

### Tasks

- [ ] Create fix branch: `git checkout -b fix/descriptive-name`
- [ ] Write failing regression test (RED): `uv run pytest tests/path -k test_name`
- [ ] Implement minimal fix (GREEN)
- [ ] Refactor for quality (REFACTOR)
- [ ] Verify fix resolves original issue
- [ ] Run full validation:
  ```bash
  uv run ruff check src/ tests/
  uv run mypy src/
  uv run pytest
  ```

### Fix Checklist

- [ ] Minimal change to fix root cause (no unrelated modifications)
- [ ] Regression test created that fails before fix, passes after
- [ ] Edge cases covered
- [ ] Error handling improved where relevant
- [ ] No debug code left behind (no `print()`, `breakpoint()`)

### Quality Gate: Fix Review

- [ ] Root cause addressed (not symptoms)
- [ ] Regression test passes: `uv run pytest tests/ -k regression_test_name`
- [ ] Full suite passing: `uv run pytest`
- [ ] No lint/type errors: `uv run ruff check && uv run mypy src/`
- [ ] No unrelated changes in diff

---

## Phase 3: Verify (QA)

**Objective**: Validate bug is fixed without regressions.

### Tasks

- [ ] Review fix implementation and approach
- [ ] Follow original reproduction steps -- bug should not occur
- [ ] Test edge cases and variations
- [ ] Run full test suite: `uv run pytest --tb=short`
- [ ] Test related conversation flows manually (if agent/prompt changes)
- [ ] Approve or request changes

### Quality Gate: Final Verification

- [ ] Original bug completely resolved
- [ ] No regressions in related features
- [ ] Regression test is comprehensive
- [ ] All test suites passing
- [ ] Ready for merge to main

---

## Merge Checklist

- [ ] All three phases completed
- [ ] All quality gates passed
- [ ] Branch up-to-date with main
- [ ] Commit messages: `fix: description`
- [ ] `uv run ruff check && uv run mypy src/ && uv run pytest` all pass
