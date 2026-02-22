# Feature Development Workflow

**Purpose**: Structured workflow for new features in the habla-hermano AI language tutor.

**Agents**: Architect --> Developer --> QA

---

## Phase 1: Design (Architect)

**Objective**: Technical design and implementation plan.

### Tasks

- [ ] Analyze feature requirements and define acceptance criteria
- [ ] Design component structure (which modules in `src/` are affected)
- [ ] Define data models, API contracts, and state schema changes
- [ ] Identify dependencies (LangGraph nodes, Supabase tables, prompt templates)
- [ ] Create implementation task breakdown (<4h chunks)
- [ ] Assess risks and plan testing strategy

### Key Design Questions

- Does this touch `ConversationState`? If so, use `NotRequired` for new fields
- Does this need a new LangGraph node in `src/agent/nodes/`?
- Does this need new prompt templates in `src/templates/`?
- Does this need new API routes in `src/api/`?
- Does this affect Supabase schema in `src/db/`?

### Quality Gate: Design Review

- [ ] Requirements have clear acceptance criteria
- [ ] Architecture fits existing LangGraph graph structure
- [ ] Data models and interfaces documented
- [ ] Tasks broken into <4h chunks
- [ ] Testing strategy defined (unit + integration)

---

## Phase 2: Implementation (Developer)

**Objective**: Implement feature following TDD approach.

### Tasks

- [ ] Create feature branch: `git checkout -b feature/descriptive-name`
- [ ] Write failing tests in `tests/` (RED)
- [ ] Implement minimal code to pass tests (GREEN)
- [ ] Refactor for quality (REFACTOR)
- [ ] Add integration tests for component interactions
- [ ] Implement error handling and edge cases
- [ ] Run full validation:
  ```bash
  uv run ruff check src/ tests/
  uv run mypy src/
  uv run pytest
  ```

### Implementation Checklist

- [ ] No hardcoded values (use `src/services/` or env config)
- [ ] Error handling for all failure scenarios
- [ ] Input validation on any new API endpoints
- [ ] Consistent naming conventions (snake_case throughout)
- [ ] Type hints on all function signatures

### Quality Gate: Implementation Review

- [ ] All planned functionality implemented
- [ ] Unit test coverage >= 80% for new code
- [ ] Integration tests for critical paths
- [ ] All tests passing: `uv run pytest`
- [ ] No lint errors: `uv run ruff check src/ tests/`
- [ ] No type errors: `uv run mypy src/`
- [ ] Self-review completed

---

## Phase 3: Validation (QA)

**Objective**: Verify feature works correctly and passes all quality gates.

### Tasks

- [ ] Review implementation against design document
- [ ] Verify all acceptance criteria met
- [ ] Run full test suite: `uv run pytest --tb=short`
- [ ] Test edge cases and error scenarios manually
- [ ] Test conversation flow end-to-end (if agent changes)
- [ ] Check for regressions in related features
- [ ] Approve or request changes

### Quality Gate: Final Validation

- [ ] All acceptance criteria verified
- [ ] Test suite passing (100%)
- [ ] No critical or high-severity issues
- [ ] No regressions in existing conversation flows
- [ ] Ready for merge to main

---

## Merge Checklist

- [ ] All three phases completed
- [ ] All quality gates passed
- [ ] Branch up-to-date with main
- [ ] Commit messages follow conventional format (`feat:`, `fix:`, etc.)
- [ ] PR created with description
- [ ] `uv run ruff check && uv run mypy src/ && uv run pytest` all pass
