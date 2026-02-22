# Add Lesson Content

Create new YAML lesson files for the Habla Hermano lesson catalog.

## When to Use
- Adding lessons for a new category (beyond greetings, numbers, colors, family, introductions)
- Adding a new language's lesson set
- Creating lessons for a new CEFR level

## Steps

1. **Review existing lesson structure**
   - Read a reference lesson: `data/lessons/es/A0/greetings-001.yaml`
   - Check `src/lessons/models.py` for the `Lesson`, `LessonStep`, and `LessonExercise` Pydantic models
   - Read `src/lessons/service.py` for how lessons are loaded and validated

2. **Plan the lesson content**
   - Identify language (`es`, `de`, `fr`), level (`A0`, `A1`, `A2`, `B1`), and category
   - Plan 4-6 vocabulary items appropriate for the level
   - Design 2-3 exercises (multiple_choice, fill_blank, translate)
   - Write step-by-step instructions, examples, and tips

3. **Create the YAML file** at `data/lessons/{lang}/{level}/{category}-001.yaml`
   ```yaml
   id: {category}-001
   title: {Descriptive Title}
   description: {One-line description}
   language: {es|de|fr}
   level: {A0|A1|A2|B1}
   estimated_minutes: {3-10}
   category: {category}
   tags:
     - {tag1}
     - {tag2}
   vocabulary_count: {number}
   icon: "{emoji}"

   steps:
     - type: instruction
       content: "Welcome text..."
       order: 1
     - type: vocabulary
       content: "Key vocabulary:"
       vocabulary:
         - word: {target_word}
           translation: {english_translation}
       order: 2
     - type: example
       content: "{Example sentence in target language}"
       translation: "{English translation}"
       order: 3
     - type: tip
       content: "{Cultural or grammar tip}"
       order: 4
     - type: practice
       exercise_id: ex-mc-{category}-001
       order: 5

   exercises:
     - id: ex-mc-{category}-001
       type: multiple_choice
       question: "{Question text}"
       options: [{option1}, {option2}, {option3}, {option4}]
       correct_index: {0-3}
       explanation: "{Why this is correct}"
     - id: ex-fb-{category}-001
       type: fill_blank
       question: "{Sentence with ___ blank}"
       correct_answer: "{answer}"
       explanation: "{Explanation}"
   ```

4. **Validate the lesson loads correctly**
   ```bash
   uv run python -c "from src.lessons.service import LessonService; ls = LessonService(); print(ls.get_lesson('{lang}', '{level}', '{category}-001'))"
   ```

5. **Run lesson tests**
   ```bash
   uv run pytest tests/lessons/ -v
   ```

## Level Guidelines

| Level | Vocabulary | Sentence Complexity | Grammar Focus |
|-------|-----------|-------------------|---------------|
| A0 | Single words, basic phrases | Simple present tense | Articles, basic verbs |
| A1 | Common phrases, basic sentences | Present + near future | Conjugation basics, question forms |
| A2 | Expanded vocabulary, compound sentences | Past + future tenses | Irregular verbs, pronouns |
| B1 | Abstract concepts, idiomatic expressions | Complex sentences | Subjunctive, conditionals |

## File Organization
- `data/lessons/{lang}/{level}/{category}-001.yaml`
- Categories: greetings, numbers, colors, family, introductions (and custom ones)
- 60 existing lessons: 3 languages x 4 levels x 5 categories
