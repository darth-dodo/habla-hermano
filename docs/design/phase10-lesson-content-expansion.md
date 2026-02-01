# Phase 10: Lesson Content Expansion Design Document

> Expand lesson content from 5 Spanish A0 lessons to 60 lessons across 3 languages and 4 CEFR levels

---

## Overview

Phase 10 expands the micro-lessons system to support the full learning journey from absolute beginner (A0) to intermediate (B1) across all three target languages: Spanish, German, and French.

**Current State**: 5 Spanish A0 lessons (greetings, introductions, numbers, colors, family)

**Target State**: 60 lessons (5 categories × 4 levels × 3 languages)

**Business Value**: A complete curriculum enables users to progress from zero to conversational fluency entirely within the app. The structured content provides scaffolding that makes the conversational AI experience accessible to true beginners across multiple languages.

**Learning Goal**: Demonstrate multi-agent coordination patterns for content creation at scale using the `.agentic-framework`.

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Spanish A1-B1 lessons | P0 | 15 new lessons across 3 levels |
| German A0-B1 lessons | P0 | 20 lessons covering all levels |
| French A0-B1 lessons | P0 | 20 lessons covering all levels |
| Level-appropriate exercises | P0 | Multiple exercise types per level |
| Language-specific grammar tips | P1 | Grammar notes adapted to each language |
| Consistent category coverage | P0 | All 5 categories at each level |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| YAML validation | All lessons parse without errors |
| Content quality | Pedagogically sound vocabulary and examples |
| Cultural accuracy | Language-specific cultural tips |
| Exercise variety | Progressive difficulty with exercise type mix |

---

## Content Architecture

### Category Matrix

Each category builds vocabulary progressively across levels:

| Category | A0 Focus | A1 Focus | A2 Focus | B1 Focus |
|----------|----------|----------|----------|----------|
| **greetings** | Basic hello/goodbye | Formal/informal greetings | Social situations | Idiomatic expressions |
| **introductions** | Name, nice to meet you | Where from, occupation | Describe yourself in detail | Interview-style conversation |
| **numbers** | 1-10 | 11-100, ordinals | Prices, dates, time | Statistics, percentages |
| **colors** | Basic colors (6-8) | Shades, materials | Descriptive adjectives | Abstract usage, metaphors |
| **family** | Immediate family | Extended family | Relationships, ages | Family stories, traditions |

### Level Progression

| Level | Vocab/Lesson | Exercises | Exercise Types | Grammar Focus |
|-------|--------------|-----------|----------------|---------------|
| **A0** | 6 words | 3 | 100% multiple_choice | Single words, basic phrases |
| **A1** | 8 words | 4 | 50% MC, 50% fill_blank | Present tense, simple sentences |
| **A2** | 10 words | 4 | 25% MC, 25% fill, 50% translate | Past tense, compound sentences |
| **B1** | 12 words | 5 | 20% MC, 20% fill, 60% translate | Subjunctive, conditionals |

### Language-Specific Considerations

#### Spanish (es)
- **A0**: Basic greetings, present tense "ser" and "estar"
- **A1**: Present tense regular verbs, gender agreement
- **A2**: Preterite and imperfect tense introduction
- **B1**: Subjunctive mood, conditional sentences

#### German (de)
- **A0**: Noun genders (der/die/das), basic cases (Nominative)
- **A1**: Artikel (ein/eine/einen), Accusative case
- **A2**: Perfekt tense (haben/sein + Partizip II), modal verbs
- **B1**: Konjunktiv II, passive voice, Dative case

#### French (fr)
- **A0**: Pronunciation notes (silent letters, liaisons)
- **A1**: Gender agreement (masculine/feminine adjectives)
- **A2**: Passé composé vs imparfait, reflexive verbs
- **B1**: Subjonctif, conditional, literary tenses introduction

---

## YAML Content Format

### Lesson File Template

```yaml
id: {category}-001
title: {Title in English}
description: {Brief description}
language: {es|de|fr}
level: {A0|A1|A2|B1}
estimated_minutes: {2-5}
category: {greetings|introductions|numbers|colors|family}
tags:
  - {tag1}
  - {tag2}
vocabulary_count: {6-12}
icon: "{emoji}"

steps:
  - type: instruction
    content: "{Welcome and context setting}"
    order: 1

  - type: vocabulary
    content: "Key vocabulary for this lesson:"
    vocabulary:
      - word: {target_word}
        translation: {english_translation}
      # ... 6-12 words based on level
    order: 2

  - type: example
    content: "{Example sentence in target language}"
    translation: "{English translation}"
    order: 3

  - type: example
    content: "{Second example sentence}"
    translation: "{English translation}"
    order: 4

  - type: tip
    content: "{Grammar or cultural tip}"
    order: 5

  - type: tip
    content: "{Second tip - language-specific note}"
    order: 6

  - type: practice
    content: "{Encouragement to practice}"
    exercise_id: "ex-{type}-{cat}-001"
    order: 7

exercises:
  # Multiple Choice (all levels)
  - id: ex-mc-{cat}-001
    type: multiple_choice
    question: "{Question text}"
    options:
      - {Option 1}
      - {Option 2}
      - {Option 3}
      - {Option 4}
    correct_index: {0-3}
    explanation: "{Why this is correct}"

  # Fill Blank (A1+)
  - id: ex-fb-{cat}-001
    type: fill_blank
    sentence_template: "{Sentence with _____ blank}"
    correct_answer: "{correct_word}"
    alternatives:
      - {alternative_spelling}
    hint: "{Optional hint}"

  # Translate (A2+)
  - id: ex-tr-{cat}-001
    type: translate
    source_text: "{English sentence}"
    target_language: "{es|de|fr}"
    correct_translation: "{Target language sentence}"
    alternatives:
      - {alternative_translation}
```

### File Naming Convention

```
data/lessons/{language}/{level}/{category}-001.yaml

Examples:
- data/lessons/es/A1/greetings-001.yaml
- data/lessons/de/A0/numbers-001.yaml
- data/lessons/fr/B1/family-001.yaml
```

---

## Multi-Agent Architecture

### Parallel Coordination Pattern

Using the `.agentic-framework/workflows/multi-agent-coordination.md` pattern:

```
Orchestrator (Main Claude)
    │
    ├── Agent ES (Spanish) ─┐
    │   └── 15 lessons (A1, A2, B1)
    │                        │
    ├── Agent DE (German)  ─┼─→ Merge & Validate
    │   └── 20 lessons (A0-B1)
    │                        │
    └── Agent FR (French)  ─┘
        └── 20 lessons (A0-B1)
```

### Agent Task Breakdown

| Agent | Language | Levels | Files | Exercise Focus |
|-------|----------|--------|-------|----------------|
| **ES** | Spanish | A1, A2, B1 | 15 | fill_blank, translate |
| **DE** | German | A0, A1, A2, B1 | 20 | all types + gender notes |
| **FR** | French | A0, A1, A2, B1 | 20 | all types + pronunciation |

### Execution Flow

1. **Setup Phase** (Orchestrator):
   - Create directory structure for de/, fr/ folders
   - Validate reference content exists (es/A0/)

2. **Parallel Content Creation** (3 Agents simultaneously):
   - Each agent creates lessons for their language
   - Each agent has full context of YAML format
   - Agents work independently without file conflicts

3. **Validation Phase** (Orchestrator):
   - Run `make test` to verify YAML parsing
   - Count files to ensure completeness
   - Spot-check content quality

4. **Finalization** (Orchestrator):
   - Update tasks.md with Phase 10 completion
   - Commit all changes

### Efficiency Gains

| Metric | Sequential | Parallel |
|--------|------------|----------|
| Estimated time | 4-6 hours | 1.5-2 hours |
| Agent utilization | 1 agent × 100% | 3 agents × 100% |
| Efficiency gain | Baseline | ~65% faster |

---

## Content Guidelines

### Vocabulary Selection

**A0 Vocabulary**:
- High-frequency words learners encounter immediately
- Concrete nouns and basic action verbs
- Words that appear in everyday greetings/introductions

**A1 Vocabulary**:
- Building on A0 with related words
- Simple verb conjugations
- Common adjectives and adverbs

**A2 Vocabulary**:
- More nuanced expressions
- Past tense markers
- Transition words and connectors

**B1 Vocabulary**:
- Abstract concepts
- Idiomatic expressions
- Professional/academic vocabulary

### Exercise Design

**Multiple Choice**:
- 4 options with plausible distractors
- Clear, unambiguous question
- Explanation of why correct answer is right

**Fill Blank**:
- Sentence provides context for the blank
- Only one correct answer (with alternatives for spelling variants)
- Hint available for A1/A2 learners

**Translate**:
- Source sentence appropriate to level
- Accept multiple valid translations
- Alternatives include common variations

### Cultural Tips

Each lesson should include culturally relevant tips:

- **Spanish**: Regional variations (Spain vs Latin America), formal "usted"
- **German**: Formal "Sie", compound word formation, Umlauts
- **French**: Liaison rules, formal "vous", silent letters

---

## File Structure

### Final Directory Layout

```
data/lessons/
├── es/
│   ├── A0/                      # 5 existing lessons
│   │   ├── greetings-001.yaml
│   │   ├── introductions-001.yaml
│   │   ├── numbers-001.yaml
│   │   ├── colors-001.yaml
│   │   └── family-001.yaml
│   ├── A1/                      # 5 new lessons (Agent ES)
│   │   ├── greetings-001.yaml
│   │   ├── introductions-001.yaml
│   │   ├── numbers-001.yaml
│   │   ├── colors-001.yaml
│   │   └── family-001.yaml
│   ├── A2/                      # 5 new lessons (Agent ES)
│   │   └── ... (5 files)
│   └── B1/                      # 5 new lessons (Agent ES)
│       └── ... (5 files)
├── de/
│   ├── A0/                      # 5 new lessons (Agent DE)
│   │   └── ... (5 files)
│   ├── A1/                      # 5 new lessons (Agent DE)
│   │   └── ... (5 files)
│   ├── A2/                      # 5 new lessons (Agent DE)
│   │   └── ... (5 files)
│   └── B1/                      # 5 new lessons (Agent DE)
│       └── ... (5 files)
└── fr/
    ├── A0/                      # 5 new lessons (Agent FR)
    │   └── ... (5 files)
    ├── A1/                      # 5 new lessons (Agent FR)
    │   └── ... (5 files)
    ├── A2/                      # 5 new lessons (Agent FR)
    │   └── ... (5 files)
    └── B1/                      # 5 new lessons (Agent FR)
        └── ... (5 files)
```

**Total**: 60 lessons (5 existing + 55 new)

---

## Validation Strategy

### Automated Validation

1. **YAML Parsing**: `make test` runs LessonService tests that load all YAML files
2. **File Count**: `find data/lessons -name "*.yaml" | wc -l` should equal 60
3. **Structure Check**: LessonService filters should work for all language/level combinations

### Manual Spot Checks

1. **Content Quality**: Review 2-3 lessons per language for pedagogical soundness
2. **Grammar Accuracy**: Native speaker review for B1 content (optional)
3. **Cultural Appropriateness**: Verify tips are accurate and helpful

### E2E Testing (Playwright)

```
1. Navigate to /lessons
2. Filter by each language (es, de, fr)
3. Filter by each level (A0, A1, A2, B1)
4. Play through at least one lesson per language
5. Submit exercises of each type
6. Verify completion flow
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Translation inaccuracies | Medium | Medium | Use well-established vocabulary, spot-check output |
| YAML formatting errors | Low | Low | Tests catch parsing failures immediately |
| Inconsistent difficulty | Medium | Low | Clear level guidelines, template-based structure |
| Missing files | Low | Medium | Verify file count before committing |
| Agent coordination issues | Low | Low | Independent files, no merge conflicts |

---

## Success Criteria

### Functional

- [x] 60 total lessons available (5 existing + 55 new)
- [x] All 3 languages represented (es, de, fr)
- [x] All 4 levels represented per language (A0, A1, A2, B1)
- [x] All 5 categories represented per level
- [x] Exercise types match level guidelines

### Technical

- [x] All YAML files parse without errors
- [x] LessonService filters return correct results
- [x] No test regressions

### Quality

- [x] Vocabulary appropriate to level
- [x] Grammar tips language-specific
- [x] Cultural notes accurate
- [x] Exercise difficulty progresses appropriately

---

## Appendix: Agent Prompts

### Agent ES (Spanish) Prompt

```
You are a content writer creating Spanish language lessons for the Habla Hermano app.

Task: Create 15 Spanish lesson YAML files for levels A1, A2, B1.

Reference file for exact YAML format: data/lessons/es/A0/greetings-001.yaml

Categories to create (5 per level):
- greetings-001.yaml
- introductions-001.yaml
- numbers-001.yaml
- colors-001.yaml
- family-001.yaml

Level Guidelines:
- A1: 8 vocabulary words, 4 exercises (50% multiple_choice, 50% fill_blank), present tense focus
- A2: 10 vocabulary words, 4 exercises (25% MC, 25% fill_blank, 50% translate), past tense introduction
- B1: 12 vocabulary words, 5 exercises (20% MC, 20% fill_blank, 60% translate), subjunctive mood

Spanish-specific notes:
- Include "ser vs estar" tips where relevant
- Note formal (usted) vs informal (tú) usage
- Regional variations (Spain vs Latin America) where significant

Output: Create all 15 files in data/lessons/es/{level}/{category}-001.yaml
```

### Agent DE (German) Prompt

```
You are a content writer creating German language lessons for the Habla Hermano app.

Task: Create 20 German lesson YAML files for levels A0, A1, A2, B1.

Reference file for exact YAML format: data/lessons/es/A0/greetings-001.yaml

Categories to create (5 per level):
- greetings-001.yaml
- introductions-001.yaml
- numbers-001.yaml
- colors-001.yaml
- family-001.yaml

Level Guidelines:
- A0: 6 vocabulary words, 3 exercises (100% multiple_choice)
- A1: 8 vocabulary words, 4 exercises (50% MC, 50% fill_blank)
- A2: 10 vocabulary words, 4 exercises (25% MC, 25% fill_blank, 50% translate)
- B1: 12 vocabulary words, 5 exercises (20% MC, 20% fill_blank, 60% translate)

German-specific notes:
- Include noun genders (der/die/das) with all vocabulary
- A0/A1: Focus on Nominative case
- A2: Introduce Perfekt tense (haben/sein + Partizip II)
- B1: Konjunktiv II for polite requests, Dative case

Output: Create all 20 files in data/lessons/de/{level}/{category}-001.yaml
```

### Agent FR (French) Prompt

```
You are a content writer creating French language lessons for the Habla Hermano app.

Task: Create 20 French lesson YAML files for levels A0, A1, A2, B1.

Reference file for exact YAML format: data/lessons/es/A0/greetings-001.yaml

Categories to create (5 per level):
- greetings-001.yaml
- introductions-001.yaml
- numbers-001.yaml
- colors-001.yaml
- family-001.yaml

Level Guidelines:
- A0: 6 vocabulary words, 3 exercises (100% multiple_choice)
- A1: 8 vocabulary words, 4 exercises (50% MC, 50% fill_blank)
- A2: 10 vocabulary words, 4 exercises (25% MC, 25% fill_blank, 50% translate)
- B1: 12 vocabulary words, 5 exercises (20% MC, 20% fill_blank, 60% translate)

French-specific notes:
- Include pronunciation notes for silent letters, liaisons
- A0/A1: Gender agreement (masculine/feminine adjectives)
- A2: Passé composé vs imparfait distinction
- B1: Subjonctif introduction, conditional sentences

Output: Create all 20 files in data/lessons/fr/{level}/{category}-001.yaml
```

---

## Related Documents

- [Phase 6: Micro-Lessons](phase6-micro-lessons.md) - Original lessons implementation
- [Multi-Agent Coordination](.agentic-framework/workflows/multi-agent-coordination.md) - Parallel agent pattern
- [Content Creation Workflow](.agentic-framework/workflows/content-creation.md) - Writer workflow
