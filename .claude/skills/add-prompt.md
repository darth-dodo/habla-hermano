# Add or Modify LLM Prompt

Create or update prompts used by the LangGraph agent nodes.

## When to Use
- Adding a new prompt for a new node or subgraph
- Modifying the Hermano personality or conversation behavior
- Adding language-specific adaptations
- Tuning scaffolding, analysis, or review prompts

## Steps

1. **Review existing prompts**
   - Read `src/agent/prompts.py` for all prompt templates and the `LANGUAGE_ADAPTER`
   - Understand the `.format()` pattern used for language/level adaptation

2. **Understand the LANGUAGE_ADAPTER pattern**
   ```python
   LANGUAGE_ADAPTER = {
       "es": {"language_name": "Spanish", "hello": "Hola", "friend": "amigo", ...},
       "de": {"language_name": "German", "hello": "Hallo", "friend": "Freund", ...},
       "fr": {"language_name": "French", "hello": "Bonjour", "friend": "ami", ...},
   }
   ```
   Prompts use `{language_name}`, `{hello}`, etc. as format placeholders.

3. **Create the prompt template**
   ```python
   NEW_PROMPT = """You are Hermano, a friendly {language_name} language tutor.

   Current student level: {level}

   {specific_instructions}

   Remember to:
   - Use {language_name} appropriate to {level} level
   - Be encouraging and patient
   - Provide corrections gently
   """
   ```

4. **Key prompt design patterns**
   - **Level-aware**: A0/A1 get simpler language, more scaffolding; A2/B1 get richer interactions
   - **Language-adapted**: Use `LANGUAGE_ADAPTER[language]` to get language-specific values
   - **Personality consistent**: Hermano is friendly, encouraging, patient, uses target language naturally
   - **Review word injection**: For respond_node, review words are injected into the system prompt

5. **Format the prompt in the node**
   ```python
   from src.agent.prompts import NEW_PROMPT, LANGUAGE_ADAPTER

   adapter = LANGUAGE_ADAPTER.get(language, LANGUAGE_ADAPTER["es"])
   formatted_prompt = NEW_PROMPT.format(
       language_name=adapter["language_name"],
       level=level,
       **adapter,
   )
   ```

6. **If adding new LANGUAGE_ADAPTER keys**, update ALL three language entries (es, de, fr)

7. **Test the prompt**
   - Write unit tests that verify prompt formatting doesn't raise KeyError
   - Test with all language/level combinations
   - Mock the LLM call and verify the formatted prompt is passed correctly

8. **Run quality checks**
   ```bash
   uv run pytest tests/agent/ -v
   uv run ruff check src/agent/
   ```

## Prompt Categories
| Prompt | Used By | Purpose |
|--------|---------|---------|
| SYSTEM_PROMPT | respond_node | Main conversation personality |
| SCAFFOLD_PROMPT | scaffold_node | Word bank/hint generation (A0-A1) |
| ANALYZE_PROMPT | analyze_node | Grammar/vocabulary extraction |
| REVIEW_QUESTION_PROMPT | review subgraph | Generate review questions |
| REVIEW_EVALUATE_PROMPT | review subgraph | Evaluate user answers |
| LESSON_ENHANCE_PROMPT | lesson subgraph | Enhance lesson content |

## Tips
- Keep prompts under 2000 tokens for efficiency
- Include examples in prompts for more consistent LLM output
- Use structured output instructions (JSON, bullet points) for parsing reliability
- Test edge cases: very short messages, non-target-language input, mixed language input
