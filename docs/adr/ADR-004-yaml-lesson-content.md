# ADR-004: YAML-Based Lesson Content with Pydantic Validation

**Date**: 2025-01-14
**Status**: Accepted
**Context**: Phase 6 - Micro-Lessons, expanded in Phase 10 (Content Expansion)
**Decider(s)**: Project Owner

---

## Summary

Define all lesson content in YAML files organized by language and CEFR level directories, validated at load time with Pydantic models, and cached via a LessonService singleton. The system supports 60 lessons across 3 languages (Spanish, German, French) x 4 CEFR levels (A0-B1) x 5 categories, with level-appropriate vocabulary counts and exercise mixes.

---

## Problem Statement

### The Challenge

Habla Hermano needs a structured content system for its micro-lesson curriculum with several interacting requirements:

1. **Structured content at scale**: 60 lessons with vocabulary steps, instructional content, and graded exercises
2. **Multi-language, multi-level organization**: 3 languages (Spanish, German, French) x 4 CEFR levels (A0, A1, A2, B1) x 5 categories per level
3. **Authoring ergonomics**: Content must be easy to write, review in pull requests, and diff in version control
4. **Early error detection**: Content structure errors should be caught at load time, not when a user hits a broken lesson
5. **AI compatibility**: Content format must support future AI-generated lesson enhancement (Phase 9)

### Why This Matters

For Habla Hermano to deliver a reliable language learning experience:
- Lessons are the core product; their format determines authoring velocity and quality
- Bad content structure (missing translations, wrong exercise types) must be caught before users see it
- The curriculum will grow with new languages and levels; the format must scale cleanly
- AI-generated content (Phase 9) needs a machine-readable, schema-validated target format

### Success Criteria

- [x] All 60 lessons loadable from YAML with zero runtime parsing errors
- [x] Pydantic validation catches missing fields, wrong types, and invalid enums at load time
- [x] Content is human-readable and git-diffable for PR review
- [x] LessonService provides fast lookups by language, level, and lesson ID
- [x] Exercise difficulty scales appropriately across CEFR levels

---

## Context

### Current State

**Existing Architecture**:
```
No lesson content system exists.
Conversations are free-form chat with the Hermano AI agent.
         │
         ▼
    No structured curriculum
    No vocabulary progression
    No graded exercises
```

**Pain Points**:

- Users have no guided learning path through the language
- No way to introduce vocabulary systematically before conversation practice
- No exercises to reinforce what users learn in chat
- Difficulty scaling is uncontrolled (entirely dependent on AI behavior)

**Technical Constraints**:

- Must integrate with existing FastAPI backend architecture
- Must work alongside the LangGraph chat agent (lessons complement, not replace, chat)
- Content must be statically analyzable (no runtime-only content generation)
- Development workflow must remain simple (no CMS, no admin panel)

### Requirements

**Functional Requirements**:

- Structured lessons with vocabulary, instructions, and exercises
- Multiple exercise types: multiple choice, fill-in-the-blank, translation
- Level-appropriate difficulty scaling across A0 through B1
- Lesson metadata for UI display (title, icon, category, language, level)
- Vocabulary extraction for integration with the vocabulary tracking system

**Non-Functional Requirements**:

- **Performance**: Lessons cached after first load; lookups in O(1) via composite key
- **Reliability**: Pydantic validation guarantees structural correctness at startup
- **Maintainability**: YAML files editable by anyone with a text editor
- **Extensibility**: New languages and levels added by creating new directories and files
- **Testability**: Content structure testable without running the full application

**Stakeholder Concerns**:

- Content authoring should not require programming knowledge
- Lessons should be reviewable in GitHub pull requests like any other code change
- Adding a new language should be a directory and file operation, not a schema migration

---

## Options Considered

### Option A: YAML Files + Pydantic Models (Chosen)

**Description**:
Store all lesson content in YAML files organized under `data/lessons/{lang}/{level}/`, loaded by a LessonService singleton, and validated against Pydantic models (Lesson, Step, Exercise) at load time. Composite key `lang/level/id` for fast lookups.

**Implementation**:
- YAML files in `data/lessons/{es,de,fr}/{A0,A1,A2,B1}/{category}-001.yaml`
- Pydantic models define exact schema: Lesson, LessonMetadata, Step, Exercise
- Enum types enforce valid values: LessonLevel, LessonStepType, ExerciseType
- LessonService loads all YAML on first call, validates with Pydantic, caches via `@lru_cache`
- API routes expose lessons through standard REST endpoints

**Pros**:

- Human-readable: YAML is approachable for non-developers authoring content
- Git-diffable: Every curriculum change appears clearly in pull request diffs
- Schema validation: Pydantic catches errors at load time with descriptive messages
- AI-authorable: LLMs can generate valid YAML given the Pydantic schema as a prompt
- Static analysis: Content can be linted, counted, and audited with simple scripts
- No infrastructure: No database tables, migrations, or admin panel required

**Cons**:

- No database queries: Cannot filter or search lessons with SQL
- Manual file organization: Directory structure must be maintained by convention
- No dynamic creation: Users cannot create or modify lessons at runtime
- File count growth: Each new language x level combination adds 5 files

**Risks**:

- **YAML syntax errors**: Medium probability; mitigate with Pydantic validation and CI checks
- **File naming conflicts**: Low probability; mitigate with naming convention `{category}-001.yaml`

**Estimated Effort**: 2-3 days

---

### Option B: Database-Stored Lessons (Supabase Tables)

**Description**:
Store lesson content in Supabase Postgres tables with columns for metadata, JSON columns for steps and exercises, and standard SQL for querying.

**Implementation**:
- `lessons` table with metadata columns and JSONB for steps/exercises
- `lesson_vocabulary` join table for vocabulary items
- `lesson_exercises` table for individual exercises
- Admin API routes for lesson CRUD operations
- RLS policies for read-only public access

**Pros**:

- Queryable: SQL filtering by language, level, category, difficulty
- Dynamic updates: Lessons can be modified without redeployment
- Relational integrity: Foreign keys and constraints enforce consistency
- Supabase tooling: Dashboard for content management

**Cons**:

- Harder to author: Writing JSON/SQL is less ergonomic than YAML
- No git history: Content changes are database mutations, not versioned commits
- Migration required: Schema changes need Supabase migrations
- Harder to review: Content changes invisible in pull requests
- Overhead: Requires database queries for every lesson load

**Risks**:

- **Schema migration pain**: High probability as lesson structure evolves
- **Content review gaps**: Medium impact; changes bypass code review process

**Estimated Effort**: 4-5 days

---

### Option C: Markdown with YAML Frontmatter

**Description**:
Store lessons as Markdown files with YAML frontmatter for metadata and custom syntax for exercises and vocabulary sections.

**Implementation**:
- `.md` files with YAML frontmatter for lesson metadata
- Custom Markdown extensions for vocabulary tables and exercises
- Python-Markdown parser with custom extensions
- Frontmatter extracted with `python-frontmatter` library

**Pros**:

- Familiar format: Markdown is widely understood
- Rich text support: Instructions can use full Markdown formatting
- Git-friendly: Text files with clear diffs

**Cons**:

- Structured data is awkward: Exercises with options, correct answers, and types are hard to express in Markdown
- No nested data: Vocabulary lists with word/translation/example triples need custom syntax
- Weaker validation: No native schema enforcement for the Markdown body
- Custom parser: Must build and maintain Markdown extensions for exercises
- Ambiguous parsing: Custom syntax can conflict with standard Markdown

**Risks**:

- **Parser complexity**: High probability; custom Markdown extensions are fragile
- **Content ambiguity**: Medium impact; authors may use conflicting Markdown syntax

**Estimated Effort**: 3-4 days

---

## Comparison Matrix

| Criteria                   | Weight | Option A (YAML+Pydantic) | Option B (Database) | Option C (Markdown) |
| -------------------------- | ------ | ------------------------ | ------------------- | ------------------- |
| **Authoring Ergonomics**   | High   | 5                        | 2                   | 4                   |
| **Version Control**        | High   | 5                        | 1                   | 5                   |
| **Schema Validation**      | High   | 5                        | 3                   | 2                   |
| **AI Compatibility**       | High   | 5                        | 3                   | 3                   |
| **Implementation Effort**  | Medium | 5                        | 3                   | 3                   |
| **Queryability**           | Medium | 2                        | 5                   | 2                   |
| **Nested Data Support**    | Medium | 5                        | 4                   | 2                   |
| **Dynamic Updates**        | Low    | 2                        | 5                   | 2                   |
| **PR Reviewability**       | Medium | 5                        | 1                   | 5                   |
| **Total Score**            | -      | **39**                   | 27                  | 28                  |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent
**Note**: For negative criteria (Effort), higher score = lower effort

---

## Decision

### Chosen Option

**Selected**: Option A: YAML Files + Pydantic Models

**Rationale**:
Lessons are static curriculum content, not user-generated data. They benefit most from version control, human-readable authoring, and pull request review -- all strengths of file-based storage. The Pydantic validation layer turns YAML files into a schema-enforced content system, catching authoring errors at load time rather than letting broken lessons reach users. The format is also naturally compatible with AI content generation (Phase 9), since LLMs can produce valid YAML from a schema definition.

**Key Factors**:

- Curriculum content is authored, reviewed, and versioned like code
- Pydantic models provide the schema enforcement that YAML alone lacks
- YAML's nested structure maps cleanly to lesson/step/exercise hierarchy
- `@lru_cache` singleton eliminates repeated file I/O after first load
- AI can generate YAML content given Pydantic schema constraints

**Trade-offs Accepted**:

- No SQL queries for lesson filtering (acceptable; filter in Python over cached data)
- Manual directory convention (acceptable; small number of well-defined paths)
- No runtime lesson creation (acceptable; curriculum is curated, not crowdsourced)

---

## Content Structure

### YAML Lesson Format

```yaml
# data/lessons/es/A0/greetings-001.yaml
id: greetings-001
title: "Basic Greetings"
language: es
level: A0
category: greetings
icon: "wave"
steps:
  - type: vocabulary
    vocabulary:
      - word: "hola"
        translation: "hello"
        example: "Hola, amigo!"
      - word: "buenos dias"
        translation: "good morning"
        example: "Buenos dias, senora."
      - word: "adios"
        translation: "goodbye"
        example: "Adios, hasta luego!"
  - type: instruction
    content: "Let's learn basic Spanish greetings. These are the words you'll use every day."
  - type: tip
    content: "In Spanish, greetings change based on time of day."
  - type: practice
    content: "Try using these greetings in the chat with Hermano!"
exercises:
  - type: multiple_choice
    question: "How do you say 'hello' in Spanish?"
    options: ["Hola", "Adios", "Gracias"]
    correct_index: 0
  - type: multiple_choice
    question: "What does 'buenos dias' mean?"
    options: ["Good night", "Good morning", "Good afternoon"]
    correct_index: 1
  - type: multiple_choice
    question: "How do you say 'goodbye'?"
    options: ["Hola", "Gracias", "Adios"]
    correct_index: 2
```

### Directory Layout

```
data/lessons/
  es/                        # Spanish
    A0/
      greetings-001.yaml
      numbers-001.yaml
      phrases-001.yaml
      food-001.yaml
      travel-001.yaml
    A1/
      greetings-001.yaml
      ...
    A2/
      ...
    B1/
      ...
  de/                        # German
    A0/
      ...
    A1/
      ...
    A2/
      ...
    B1/
      ...
  fr/                        # French
    A0/
      ...
    ...
```

**Total**: 3 languages x 4 levels x 5 categories = 60 YAML files

### Level-Appropriate Difficulty

| CEFR Level | Vocabulary Items | Exercises | Exercise Mix                              |
| ---------- | ---------------- | --------- | ----------------------------------------- |
| **A0**     | 6                | 3         | 100% multiple choice                      |
| **A1**     | 8                | 4         | 50% multiple choice, 50% fill-in-blank    |
| **A2**     | 10               | 4         | 25% MC, 25% fill-in-blank, 50% translate  |
| **B1**     | 12               | 5         | 20% MC, 20% fill-in-blank, 60% translate  |

---

## Pydantic Models

### Model Hierarchy

```
Lesson
  ├── id: str
  ├── title: str
  ├── language: str (es | de | fr)
  ├── level: LessonLevel (A0 | A1 | A2 | B1)
  ├── category: str
  ├── icon: str
  ├── steps: list[Step]
  │     ├── type: LessonStepType (instruction | vocabulary | example | tip | practice)
  │     ├── content: str | None
  │     └── vocabulary: list[VocabularyItem] | None
  │           ├── word: str
  │           ├── translation: str
  │           └── example: str
  └── exercises: list[Exercise]
        ├── type: ExerciseType (multiple_choice | fill_blank | translate)
        ├── question: str
        ├── options: list[str] | None      (multiple_choice only)
        ├── correct_index: int | None      (multiple_choice only)
        ├── correct_answer: str | None     (fill_blank, translate)
        └── hint: str | None
```

### Enums

- **LessonLevel**: `A0`, `A1`, `A2`, `B1`
- **LessonStepType**: `instruction`, `vocabulary`, `example`, `tip`, `practice`
- **ExerciseType**: `multiple_choice`, `fill_blank`, `translate`

### Validation Rules

- Lesson `id` must be non-empty and match filename stem
- Every lesson must have at least one step and one exercise
- Vocabulary steps must have a non-empty vocabulary list
- Multiple choice exercises must have `options` and a valid `correct_index`
- Fill-blank and translate exercises must have `correct_answer`
- Level and language must be valid enum values

---

## LessonService

### Design

```python
@lru_cache(maxsize=1)
def get_lesson_service() -> LessonService:
    """Singleton LessonService, loaded and cached on first call."""
    service = LessonService()
    service.load_all()
    return service
```

### Composite Key Strategy

Lessons are indexed by `{language}/{level}/{id}` for O(1) lookups:

```
"es/A0/greetings-001" → Lesson(...)
"de/A1/numbers-001"   → Lesson(...)
"fr/B1/travel-001"    → Lesson(...)
```

### API Methods

| Method                  | Returns              | Description                                    |
| ----------------------- | -------------------- | ---------------------------------------------- |
| `get_lesson(lang, level, id)` | `Lesson`       | Single lesson by composite key                 |
| `get_lessons(lang, level)`    | `list[Lesson]` | All lessons for a language/level               |
| `get_categories(lang, level)` | `list[str]`    | Distinct categories for a language/level       |
| `get_lesson_vocabulary(lang, level, id)` | `list[VocabularyItem]` | Vocabulary items from a lesson |

### Loading Behavior

1. On first call to `get_lesson_service()`, scan `data/lessons/` recursively
2. Parse each `.yaml` file with PyYAML
3. Validate each parsed dict against the `Lesson` Pydantic model
4. If validation fails, raise with descriptive error (file path + field + issue)
5. Index all valid lessons by composite key
6. Cache the entire service instance via `@lru_cache`
7. Subsequent calls return the cached instance with zero I/O

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:

- Easy to author new lessons with any text editor
- Every curriculum change is a versioned, reviewable git commit
- Pydantic catches structural errors before deployment
- Composite key lookups are O(1) after initial load
- Content format is self-documenting (YAML is readable without tooling)

**Long-term Benefits**:

- AI can generate valid YAML lessons given the Pydantic schema (Phase 9)
- Static analysis scripts can audit content coverage, vocabulary overlap, difficulty curves
- New languages added by creating a directory tree with 20 YAML files
- Content can be externalized to a separate repo if curriculum team grows

### Negative Outcomes

**Immediate Costs**:

- 60 YAML files to author for initial curriculum
- Directory convention must be documented and followed manually
- No database-backed search or filtering

**Technical Debt Created**:

- Composite key management is manual (not enforced by database constraints)
- File-to-model mapping relies on directory naming convention

**Trade-offs**:

- Users cannot create lessons dynamically (acceptable; curriculum is curated)
- File count grows linearly with languages and levels (acceptable; well-organized)
- No partial loading; all lessons cached in memory (acceptable; 60 lessons is small)

### Risks and Mitigation

**Risk 1**: YAML authoring errors (syntax, indentation)

- **Probability**: Medium (especially for non-developer authors)
- **Impact**: Lesson fails to load, service startup error
- **Mitigation**: Pydantic validation with clear error messages; CI check that loads all lessons

**Risk 2**: Directory/filename convention drift

- **Probability**: Low
- **Impact**: Lessons not discovered by LessonService scanner
- **Mitigation**: Documentation, CI validation script, naming convention enforced by example

**Risk 3**: Memory usage with large content sets

- **Probability**: Low (60 lessons is small; even 600 lessons would be manageable)
- **Impact**: Increased memory footprint at startup
- **Mitigation**: Monitor; implement lazy loading per language/level if needed

---

## Implementation Plan

### Phases

**Phase 1**: Pydantic Models + Enums

- **Tasks**:
  - [ ] Define LessonLevel, LessonStepType, ExerciseType enums
  - [ ] Define VocabularyItem, Step, Exercise Pydantic models
  - [ ] Define Lesson model with validators
  - [ ] Write unit tests for model validation (valid and invalid inputs)
- **Deliverable**: `src/lessons/models.py` with full test coverage

**Phase 2**: LessonService

- **Tasks**:
  - [ ] Implement YAML scanning and loading logic
  - [ ] Implement composite key indexing
  - [ ] Implement `@lru_cache` singleton pattern
  - [ ] Implement `get_lesson()`, `get_lessons()`, `get_categories()`, `get_lesson_vocabulary()`
  - [ ] Write unit tests with fixture YAML files
- **Deliverable**: `src/lessons/service.py` with full test coverage

**Phase 3**: Content Authoring (A0 Lessons)

- **Tasks**:
  - [ ] Create directory structure `data/lessons/{es,de,fr}/{A0,A1,A2,B1}/`
  - [ ] Author 5 Spanish A0 lessons (greetings, numbers, phrases, food, travel)
  - [ ] Author 5 German A0 lessons
  - [ ] Author 5 French A0 lessons
  - [ ] Validate all lessons load correctly
- **Deliverable**: 15 A0 lessons across 3 languages

**Phase 4**: Content Authoring (A1-B1 Lessons)

- **Tasks**:
  - [ ] Author A1 lessons (3 languages x 5 categories = 15 files)
  - [ ] Author A2 lessons (15 files)
  - [ ] Author B1 lessons (15 files)
  - [ ] Verify difficulty scaling across levels
- **Deliverable**: All 60 lessons authored and validated

**Phase 5**: API Routes

- **Tasks**:
  - [ ] Create `/api/lessons/{lang}/{level}` endpoint (list lessons)
  - [ ] Create `/api/lessons/{lang}/{level}/{id}` endpoint (single lesson)
  - [ ] Create `/api/lessons/{lang}/{level}/categories` endpoint
  - [ ] Wire routes into FastAPI app
  - [ ] Write integration tests for all endpoints
- **Deliverable**: `src/api/routes/lessons.py` with full test coverage

**Phase 6**: CI Validation

- **Tasks**:
  - [ ] Add CI step that loads all lessons and checks for validation errors
  - [ ] Add content coverage report (languages x levels x categories)
  - [ ] Verify all 60 lessons pass Pydantic validation in CI
- **Deliverable**: Green CI pipeline with content validation

### Dependencies

**Prerequisites**:

- PyYAML and Pydantic already in project dependencies
- FastAPI route patterns established in existing codebase

**Parallel Work**:

- Pydantic models and LessonService can be built in parallel with content authoring
- API routes can be built once LessonService interface is defined

**Blocked By**:

- None (can start immediately)

### Rollback Plan

**Trigger Conditions**:
- YAML format proves too rigid for lesson content needs
- Memory usage from cached lessons exceeds acceptable limits
- Content authoring velocity is too slow with YAML

**Rollback Steps**:

1. Keep Pydantic models as the canonical schema
2. Implement database loader as alternative to YAML loader
3. Migrate YAML content into Supabase tables via script
4. Swap LessonService data source from files to database

**Fallback Option**:
Migrate to database-stored lessons (Option B) while preserving the Pydantic validation layer as a shared schema between both storage backends.

---

## Key Files

| File | Purpose |
| ---- | ------- |
| `data/lessons/` | Root directory for all YAML lesson content |
| `data/lessons/{lang}/{level}/*.yaml` | Individual lesson files |
| `src/lessons/models.py` | Pydantic models, enums, and validators |
| `src/lessons/service.py` | LessonService singleton with caching and lookups |
| `src/api/routes/lessons.py` | FastAPI routes for lesson API endpoints |

---

## Validation

### Pre-Implementation Checklist

- [x] Decision addresses the original problem
- [x] Success criteria are achievable
- [x] Risks are identified and mitigated
- [x] Implementation plan is realistic
- [x] Dependencies are understood
- [x] Rollback plan exists

### Architect Quality Standards

- [x] **Scalability**: New languages/levels are directory additions, not schema changes
- [x] **Maintainability**: YAML is human-readable; Pydantic models are self-documenting
- [x] **Best Practices**: Schema validation, singleton caching, composite key indexing
- [x] **Simplicity**: No database, no CMS, no admin panel -- just files and models
- [x] **Trade-offs**: No dynamic content accepted for version control benefits

### Post-Implementation Validation

**Success Metrics**:

- Lesson load time: Target <500ms for all 60 lessons on first call
- Pydantic validation: 100% of lessons pass at startup
- Content coverage: 60/60 lessons authored (3 languages x 4 levels x 5 categories)
- Test coverage: Target 95%+ for models and service

**Validation Tests**:

- [ ] All 60 YAML files parse and validate without errors
- [ ] Composite key lookup returns correct lesson for every valid key
- [ ] Invalid YAML produces descriptive Pydantic validation error
- [ ] API endpoints return correct lessons filtered by language and level
- [ ] Exercise difficulty scales correctly across A0 to B1

**Review Date**: 2025-02-14 (1 month post-implementation)

---

## Related Decisions

**Supersedes**:

- None (first structured content system)

**Related To**:

- ADR-001: Supabase Integration - Supabase stores user progress on lessons, not the lessons themselves

**Depends On**:

- None

**Informs**:

- Phase 9: AI-enhanced lessons can generate YAML content validated by the same Pydantic models
- Phase 10: Content Expansion adds more languages/levels using the same directory structure
- Phase 14: Learning Paths reference lessons by their composite key

---

## References

### Documentation

- [Phase 6 Design](../design/phase6-micro-lessons.md) - Micro-lessons implementation details (if exists)
- [Phase 10 Design](../design/phase10-content-expansion.md) - Content expansion plan (if exists)

### External Resources

- [Pydantic Documentation](https://docs.pydantic.dev/) - Model validation reference
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) - YAML parsing library
- [CEFR Levels](https://www.coe.int/en/web/common-european-framework-reference-languages/level-descriptions) - Common European Framework language levels

### Code References

- `src/lessons/models.py` - Pydantic models and enums for lesson content
- `src/lessons/service.py` - LessonService singleton with YAML loading and caching
- `src/api/routes/lessons.py` - FastAPI routes for lesson endpoints
- `data/lessons/` - YAML lesson content directory tree

---

## Discussion and Updates

### Decision History

**2025-01-14**: Proposed

- Initial proposal for YAML-based lesson content system for Phase 6 micro-lessons
- Evaluated database and Markdown alternatives; YAML chosen for authoring ergonomics and version control

**2025-01-14**: Accepted

- Decision approved for implementation
- 60-lesson curriculum plan confirmed across 3 languages, 4 CEFR levels, 5 categories

### Questions Raised

**Q1**: Why not store lessons in Supabase alongside user data?

- **A**: Lessons are static curriculum content, not user-generated. They benefit from version control, PR review, and git history. User progress on lessons is stored in Supabase; the lessons themselves are files.

**Q2**: How does this support AI-generated content in Phase 9?

- **A**: LLMs can generate valid YAML given the Pydantic schema as a prompt constraint. Generated content is validated by the same models before being committed to the repository.

**Q3**: What happens when we add a new language?

- **A**: Create a new directory under `data/lessons/{lang_code}/` with subdirectories for each CEFR level and 5 YAML files per level. The LessonService discovers new content automatically on next load.

**Q4**: Will 60 cached lessons cause memory issues?

- **A**: No. Each lesson is a small Pydantic model (roughly 2-5KB in memory). 60 lessons total under 300KB, which is negligible.

### Feedback Incorporated

- Level-appropriate difficulty scaling (A0 simpler exercises, B1 more translation) was added based on CEFR pedagogical guidelines
- Composite key strategy chosen over auto-increment IDs for human-readable lesson references

---

## Metadata

**ADR Number**: 004
**Created**: 2025-01-14
**Last Updated**: 2025-01-14
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: content, yaml, pydantic, lessons, curriculum, validation, cefr

**Project Phase**: Development

---

## Notes

This ADR establishes the content foundation for Habla Hermano's structured learning experience. The choice of YAML over database storage reflects a key insight: curriculum content has more in common with source code (authored, reviewed, versioned) than with user data (dynamic, queried, transactional). The Pydantic validation layer bridges the gap, giving YAML files the schema enforcement typically associated with database schemas.

The 60-lesson initial curriculum (3 languages x 4 levels x 5 categories) provides meaningful coverage for early users while the directory structure scales cleanly for future expansion. The LessonService singleton with `@lru_cache` ensures that the file-based approach incurs no ongoing I/O cost after startup.

---

**Status**: ACCEPTED
**Next Review**: 2025-02-14
