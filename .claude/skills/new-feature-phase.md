# Plan New Feature Phase

Design and plan a new phase of development for Habla Hermano.

## When to Use
- Planning a new feature (Phase 15+)
- Designing a major enhancement that spans multiple files
- Creating a design document for a new capability

## Steps

1. **Review current architecture**
   - Read `docs/architecture.md` for the full system overview
   - Check `docs/phases/` for existing phase design documents
   - Read the latest ADR in `docs/adr/` for recent architectural decisions

2. **Assess impact across layers**
   - **Agent layer**: New nodes, state fields, prompts, routing changes?
   - **API layer**: New routes, auth requirements, rate limiting?
   - **Service layer**: New business logic, algorithm implementations?
   - **Database layer**: New tables, columns, RLS policies?
   - **Frontend layer**: New templates, HTMX interactions, mobile support?
   - **Test layer**: New test files, fixtures, mocking patterns?

3. **Create a design document** at `docs/phases/phase-{N}-{name}.md`
   ```markdown
   # Phase {N}: {Feature Name}

   ## Overview
   {What this phase adds and why}

   ## User Stories
   - As a learner, I want to {action} so that {benefit}

   ## Technical Design

   ### Agent Changes
   - New node: {name} - {purpose}
   - State fields: {new fields}
   - Routing: {how it connects to existing graph}

   ### API Changes
   - `{METHOD} /path` - {description}

   ### Database Changes
   - Table: {name} - {columns}
   - RLS: {policy description}

   ### Frontend Changes
   - Template: {name} - {description}

   ## Implementation Plan
   1. {Step 1}
   2. {Step 2}
   ...

   ## Testing Strategy
   - Unit tests for {components}
   - Integration tests for {flows}

   ## Migration Notes
   {Any database migrations or breaking changes}
   ```

4. **Create an ADR** if making architectural decisions at `docs/adr/{NNN}-{decision}.md`
   ```markdown
   # ADR-{NNN}: {Decision Title}

   ## Status
   Proposed

   ## Context
   {Why we need to make this decision}

   ## Decision
   {What we decided}

   ## Consequences
   {Positive and negative implications}
   ```

5. **Plan the implementation order**
   - Database/models first (foundation)
   - Repository layer (data access)
   - Service layer (business logic)
   - Agent nodes (if applicable)
   - API routes
   - Templates/frontend
   - Tests throughout each step

6. **Estimate scope**
   - Files to create/modify
   - New tests needed
   - Dependencies to add (check pyproject.toml)
   - CI/CD impact

## Completed Phases Reference
| Phase | Feature | Key Components |
|-------|---------|----------------|
| 1-3 | Core chat | LangGraph pipeline, FastAPI, basic UI |
| 4 | Persistence | Supabase, checkpointing, session management |
| 5 | Authentication | JWT, RLS, user profiles |
| 6 | Vocabulary | Tracking, word banks, learning stats |
| 7-8 | Scaffolding | A0/A1 scaffolding, conditional routing |
| 9 | Analysis | Grammar feedback, vocabulary extraction |
| 10 | Lessons | 60 YAML lessons, catalog, player |
| 11 | Progress | Stats aggregation, learning sessions |
| 12 | Review | SM-2 algorithm, chat weaving |
| 13 | Mobile | Responsive design, themes, safe areas |
| 14 | Learning paths | Adaptive recommendations, daily plans |
