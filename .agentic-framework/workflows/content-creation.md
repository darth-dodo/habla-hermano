# Content Creation Workflow

**Purpose**: Structured workflow for creating documentation, lesson content, and prompt templates for habla-hermano.

**Agents**: Scribe (Outline) --> Scribe (Write) --> QA (Review)

---

## Phase 1: Outline (Scribe)

**Objective**: Create content outline with structure and key points.

### Tasks

- [ ] Define content type: README, API docs, lesson content, or prompt template
- [ ] Identify target audience (developers, learners, contributors)
- [ ] Research existing docs and identify gaps
- [ ] Create hierarchical outline with sections
- [ ] Plan code examples and conversation samples
- [ ] Estimate scope

### Content Types for Habla Hermano

| Type | Location | Purpose |
|------|----------|---------|
| Lesson content | `src/lessons/` | CEFR-aligned curriculum (A0-B1) |
| Prompt templates | `src/templates/` | Jinja2 templates for LLM prompts |
| API documentation | `docs/` | Endpoint reference, auth flows |
| Architecture docs | `docs/design/` | System design, graph structure |
| README | project root | Setup, usage, contributing |

### Quality Gate: Outline Review

- [ ] Target audience clearly defined
- [ ] Content objectives measurable
- [ ] Logical section hierarchy
- [ ] CEFR level alignment (if lesson content)
- [ ] Examples planned

---

## Phase 2: Write (Scribe)

**Objective**: Expand outline into complete, high-quality content.

### Tasks

- [ ] Write each section with clear, concise language
- [ ] Create code examples and conversation samples
- [ ] For lesson content: ensure CEFR level-appropriate vocabulary and grammar
- [ ] For prompt templates: test with actual LLM calls
- [ ] Apply consistent formatting and terminology
- [ ] Self-review against outline objectives

### Writing Guidelines

- Use simple, direct language (one concept per paragraph)
- Active voice preferred
- Define technical terms on first use
- For lesson content: include Spanish/target language examples with translations
- For prompt templates: include expected input/output format
- All code examples must be tested and working

### Quality Gate: Writing Review

- [ ] All outline sections completed
- [ ] Code examples tested: `uv run pytest` (if applicable)
- [ ] Consistent formatting and terminology
- [ ] CEFR level-appropriate (if lesson content)
- [ ] No placeholder text remaining

---

## Phase 3: Review (QA)

**Objective**: Validate content accuracy, completeness, and quality.

### Tasks

- [ ] Verify technical accuracy (code examples, API contracts)
- [ ] Test any code samples or prompt templates
- [ ] Check for CEFR level accuracy (if lesson content)
- [ ] Validate links and cross-references
- [ ] Review grammar, spelling, and clarity
- [ ] For prompt templates: run through agent graph and verify output quality
- [ ] Approve or request changes

### Quality Gate: Final Review

- [ ] Technical accuracy verified
- [ ] All code/prompt examples tested
- [ ] No broken links or references
- [ ] Content meets outline objectives
- [ ] Ready for publication/merge

---

## Merge Checklist

- [ ] All three phases completed
- [ ] All quality gates passed
- [ ] Commit messages: `docs: description` or `content: description`
- [ ] Branch: `docs/descriptive-name` or `content/descriptive-name`
