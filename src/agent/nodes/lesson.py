"""
Lesson nodes for the AI-enhanced lesson delivery subgraph.

Phase 9: These nodes work together to:
1. Load step data from YAML lessons
2. Enhance content with Hermano's personalized teaching
3. Validate exercise answers with AI-generated feedback
"""

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.lesson_state import LessonState
from src.agent.llm import get_llm
from src.agent.prompts import get_exercise_feedback_prompt, get_lesson_enhance_prompt
from src.lessons.models import (
    FillBlankExercise,
    MultipleChoiceExercise,
    TranslateExercise,
)
from src.lessons.service import get_lesson_service


def _extract_intro(content: str) -> str:
    """Extract the intro portion from enhanced content.

    Looks for labeled sections in the LLM response:
    - INTRO: for most step types
    - PEP_TALK: for practice steps

    Falls back to first paragraph if no label found.

    Args:
        content: Full enhanced content from the LLM.

    Returns:
        The intro portion, limited to 2-3 sentences.
    """
    text = content.strip()

    # Try to find INTRO: section
    if "INTRO:" in text:
        parts = text.split("INTRO:", 1)
        if len(parts) > 1:
            intro_section = parts[1]
            # Find where intro ends (at next label or double newline)
            for label in [
                "EXTRA:",
                "EXAMPLES:",
                "ALTERNATIVE:",
                "STORY:",
                "USAGE NOTE:",
                "WHY IT MATTERS:",
            ]:
                if label in intro_section:
                    intro_section = intro_section.split(label, 1)[0]
            # Also split at double newline
            if "\n\n" in intro_section:
                intro_section = intro_section.split("\n\n", 1)[0]
            return intro_section.strip()

    # Try to find PEP_TALK: section (for practice steps)
    if "PEP_TALK:" in text:
        parts = text.split("PEP_TALK:", 1)
        if len(parts) > 1:
            return parts[1].strip()

    # Fallback: return first paragraph, limited to 2-3 sentences
    paragraphs = text.split("\n\n")
    if paragraphs:
        intro = paragraphs[0].strip()
        # Limit to 3 sentences max
        sentences = re.split(r"(?<=[.!?])\s+", intro)
        if len(sentences) > 3:
            return " ".join(sentences[:3])
        return intro

    return text[:200] if len(text) > 200 else text


async def load_step_node(state: LessonState) -> dict[str, Any]:
    """Load step data from lesson service.

    Reads the current step from the YAML-based lesson and populates
    state fields for downstream processing.

    Args:
        state: Current lesson state with lesson_id and step_index.

    Returns:
        Dictionary with step data to update state.

    Raises:
        ValueError: If lesson or step not found.
    """
    service = get_lesson_service()
    lesson = service.get_lesson(state["lesson_id"])

    if not lesson:
        raise ValueError(f"Lesson not found: {state['lesson_id']}")

    steps = lesson.content.get_ordered_steps()
    step_index = state["step_index"]

    if step_index < 0 or step_index >= len(steps):
        raise ValueError(f"Step {step_index} not found. Lesson has {len(steps)} steps.")

    step = steps[step_index]

    return {
        "step_type": step.type.value,
        "step_content": step.content,
        "step_vocabulary": step.vocabulary or [],
        "step_target_text": step.target_text,
        "step_translation": step.translation,
        "exercise_id": step.exercise_id,
    }


async def enhance_step_node(state: LessonState) -> dict[str, Any]:
    """Hermano enhances the step with dynamic, personalized content.

    Based on step type, generates:
    - instruction: Warm intro + additional context
    - vocabulary: Example sentences using the words
    - example: Alternative phrasings + usage notes
    - tip: Cultural anecdotes
    - practice: Encouragement before exercise

    Args:
        state: Current lesson state with step data.

    Returns:
        Dictionary with enhanced_content and hermano_intro.
    """
    llm = get_llm("enhancement")

    # Build the enhancement prompt
    prompt = get_lesson_enhance_prompt(
        language=state["language"],
        level=state["level"],
        step_type=state.get("step_type", "instruction"),
        step_content=state.get("step_content", ""),
        vocabulary=state.get("step_vocabulary"),
        target_text=state.get("step_target_text"),
        translation=state.get("step_translation"),
    )

    # Call Claude for enhancement
    # The chat completions API requires at least one HumanMessage
    response = await llm.ainvoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(content="Please enhance this lesson step."),
        ]
    )
    content = str(response.content)

    # Extract the intro portion
    hermano_intro = _extract_intro(content)

    return {
        "enhanced_content": content,
        "hermano_intro": hermano_intro,
    }


async def validate_exercise_node(state: LessonState) -> dict[str, Any]:
    """Validate exercise answer with personalized feedback from Hermano.

    Goes beyond correct/incorrect to provide:
    - Encouragement on correct answers
    - Helpful hints on incorrect answers
    - Cultural context when relevant

    Args:
        state: Current lesson state with exercise submission.

    Returns:
        Dictionary with is_correct and exercise_feedback.
    """
    user_answer = state.get("user_answer")
    exercise_id = state.get("exercise_id")

    if not user_answer or not exercise_id:
        return {
            "is_correct": None,
            "exercise_feedback": None,
        }

    # Get the exercise from the lesson
    service = get_lesson_service()
    lesson = service.get_lesson(state["lesson_id"])

    if not lesson:
        return {
            "is_correct": False,
            "exercise_feedback": "Unable to validate - lesson not found.",
        }

    exercise = lesson.content.get_exercise_by_id(exercise_id)
    if not exercise:
        return {
            "is_correct": False,
            "exercise_feedback": "Unable to validate - exercise not found.",
        }

    # Check correctness based on exercise type
    is_correct = False
    correct_answer = ""

    if isinstance(exercise, MultipleChoiceExercise):
        try:
            selected_index = int(user_answer)
            is_correct = selected_index == exercise.correct_index
            correct_answer = exercise.options[exercise.correct_index]
        except (ValueError, IndexError):
            is_correct = False
            correct_answer = exercise.options[exercise.correct_index]

    elif isinstance(exercise, FillBlankExercise):
        is_correct = exercise.check_answer(user_answer)
        correct_answer = exercise.correct_answer

    elif isinstance(exercise, TranslateExercise):
        is_correct = exercise.check_answer(user_answer)
        correct_answer = exercise.correct_translation

    # Build exercise description based on type
    exercise_description = ""
    if isinstance(exercise, MultipleChoiceExercise):
        exercise_description = f"Question: {exercise.question}"
    elif isinstance(exercise, FillBlankExercise):
        exercise_description = f"Fill in the blank: {exercise.sentence_template}"
    elif isinstance(exercise, TranslateExercise):
        exercise_description = f"Translate '{exercise.source_text}' to {exercise.target_language}"

    # Generate personalized feedback with AI
    llm = get_llm("enhancement")
    feedback_prompt = get_exercise_feedback_prompt(
        language=state["language"],
        level=state["level"],
        exercise_description=exercise_description,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
    )

    # The chat completions API requires at least one HumanMessage
    response = await llm.ainvoke(
        [
            SystemMessage(content=feedback_prompt),
            HumanMessage(content="Please provide feedback on this answer."),
        ]
    )

    return {
        "is_correct": is_correct,
        "exercise_feedback": str(response.content),
    }
