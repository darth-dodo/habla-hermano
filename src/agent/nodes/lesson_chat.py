"""
Lesson respond node for Phase 19 conversational lesson delivery.

Implements the lesson phase machine inside a single LangGraph node:
    intro -> teaching -> exercise_ask -> exercise_eval -> complete

Each phase is handled by a private helper function. The node is registered
as "respond" in the graph so existing SSE streaming works unchanged.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.lesson_chat_state import STEP_BATCH_SIZE, LessonChatState
from src.agent.llm import get_llm
from src.agent.prompts import get_prompt_for_level
from src.agent.prompts_lesson_chat import (
    LESSON_COMPLETE_PROMPT,
    LESSON_EXERCISE_ASK_PROMPT,
    LESSON_EXERCISE_EVAL_PROMPT,
    LESSON_INTRO_PROMPT,
    LESSON_TEACHING_PROMPT,
    format_exercise_for_prompt,
    format_steps_for_prompt,
    get_teaching_adjustments,
)
from src.lessons.models import FillBlankExercise, TranslateExercise
from src.validation import LANGUAGE_NAMES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MC answer parser
# ---------------------------------------------------------------------------


def _parse_mc_answer(user_text: str, options: list[str]) -> int | None:
    """Parse a multiple-choice answer from free-text chat input.

    Accepts:
      - Single letter A-D (case-insensitive)
      - Single digit 1-4
      - Full text match against option strings (normalized)

    Returns the 0-based option index, or None if ambiguous.
    """
    text = user_text.strip().lower()

    # Single letter A-D
    if len(text) == 1 and text in "abcd":
        idx = ord(text) - ord("a")
        return idx if idx < len(options) else None

    # Single digit 1-4
    if len(text) == 1 and text in "1234":
        idx = int(text) - 1
        return idx if idx < len(options) else None

    # Full text match
    for i, opt in enumerate(options):
        if text == opt.lower().strip():
            return i

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ordered_steps(lesson_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Get lesson steps sorted by order field."""
    steps = lesson_data.get("content", {}).get("steps", [])
    return sorted(steps, key=lambda s: s.get("order", 0))


def _get_exercises(lesson_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Get lesson exercises list."""
    exercises: list[dict[str, Any]] = lesson_data.get("content", {}).get("exercises", [])
    return exercises


def _get_language_name(language: str) -> str:
    """Resolve language code to display name."""
    return LANGUAGE_NAMES.get(language, language)


def _build_lesson_ui(
    state: LessonChatState,
    phase: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build lesson_ui dict for SSE events."""
    lesson_data = state["lesson_data"]
    ordered_steps = _get_ordered_steps(lesson_data)
    ui: dict[str, Any] = {
        "step": state.get("step_index", 0),
        "total_steps": len(ordered_steps),
        "phase": phase,
        "title": lesson_data.get("metadata", {}).get("title", ""),
    }
    ui.update(extra)
    return ui


async def _call_llm(system_prompt: str, state: LessonChatState) -> Any:
    """Invoke the conversational LLM with system prompt + message history."""
    messages = [SystemMessage(content=system_prompt), *state["messages"]]
    llm = get_llm("conversational")
    return await llm.ainvoke(messages)


# ---------------------------------------------------------------------------
# Phase handlers
# ---------------------------------------------------------------------------


async def _handle_intro(state: LessonChatState) -> dict[str, Any]:
    """Handle the intro phase: welcome the learner to the lesson."""
    lesson_data = state["lesson_data"]
    metadata = lesson_data.get("metadata", {})
    language = state["language"]
    level = state["level"]

    ordered_steps = _get_ordered_steps(lesson_data)
    exercises = _get_exercises(lesson_data)

    system_prompt = LESSON_INTRO_PROMPT.format(
        language_name=_get_language_name(language),
        level=level,
        lesson_title=metadata.get("title", ""),
        lesson_description=metadata.get("description", ""),
        step_count=len(ordered_steps),
        exercise_count=len(exercises),
        teaching_adjustments=get_teaching_adjustments(level),
    )

    # Prepend the base level prompt for Hermano personality
    base_prompt = get_prompt_for_level(language, level)
    full_prompt = base_prompt + "\n\n" + system_prompt

    response = await _call_llm(full_prompt, state)
    logger.info("Lesson %s: intro -> teaching", state.get("lesson_id", "?"))

    return {
        "messages": [response],
        "lesson_phase": "teaching",
        "step_index": 0,
        "lesson_ui": _build_lesson_ui(state, "intro"),
    }


async def _handle_teaching(state: LessonChatState) -> dict[str, Any]:
    """Handle the teaching phase: present a batch of lesson steps."""
    lesson_data = state["lesson_data"]
    language = state["language"]
    level = state["level"]
    step_index = state.get("step_index", 0)

    ordered_steps = _get_ordered_steps(lesson_data)
    exercises = _get_exercises(lesson_data)

    # Batch steps: up to STEP_BATCH_SIZE, break on practice type
    batch_end = step_index
    batch_count = 0
    while batch_end < len(ordered_steps) and batch_count < STEP_BATCH_SIZE:
        step = ordered_steps[batch_end]
        if step.get("type") == "practice":
            break
        batch_end += 1
        batch_count += 1

    # Format step content for the prompt
    steps_content = format_steps_for_prompt(ordered_steps, step_index, batch_end)
    total_steps = len(ordered_steps)
    step_numbers = f"{step_index + 1}-{batch_end} of {total_steps}"

    system_prompt = LESSON_TEACHING_PROMPT.format(
        language_name=_get_language_name(language),
        level=level,
        lesson_title=lesson_data.get("metadata", {}).get("title", ""),
        steps_content=steps_content,
        step_numbers=step_numbers,
        teaching_adjustments=get_teaching_adjustments(level),
    )

    base_prompt = get_prompt_for_level(language, level)
    full_prompt = base_prompt + "\n\n" + system_prompt

    response = await _call_llm(full_prompt, state)

    # Determine next phase
    new_step_index = batch_end
    # Check if next step is a practice step (skip it, transition to exercises)
    if (
        new_step_index < len(ordered_steps)
        and ordered_steps[new_step_index].get("type") == "practice"
    ):
        new_step_index += 1  # Skip the practice step marker

    # If more non-practice steps remain, keep teaching
    remaining_content = [s for s in ordered_steps[new_step_index:] if s.get("type") != "practice"]

    if remaining_content:
        next_phase = "teaching"
    elif exercises:
        next_phase = "exercise_ask"
    else:
        next_phase = "complete"

    logger.info(
        "Lesson %s: teaching steps %d-%d -> %s",
        state.get("lesson_id", "?"),
        step_index,
        batch_end - 1,
        next_phase,
    )

    return {
        "messages": [response],
        "lesson_phase": next_phase,
        "step_index": new_step_index,
        "lesson_ui": _build_lesson_ui(state, "teaching"),
    }


async def _handle_exercise_ask(state: LessonChatState) -> dict[str, Any]:
    """Handle exercise_ask phase: present the current exercise."""
    lesson_data = state["lesson_data"]
    language = state["language"]
    level = state["level"]
    exercise_index = state.get("exercise_index", 0)

    exercises = _get_exercises(lesson_data)
    if exercise_index >= len(exercises):
        # No more exercises — go to complete
        return await _handle_complete(state)

    exercise_data = exercises[exercise_index]
    exercise_content = format_exercise_for_prompt(exercise_data)

    system_prompt = LESSON_EXERCISE_ASK_PROMPT.format(
        language_name=_get_language_name(language),
        level=level,
        exercise_type=exercise_data.get("type", "unknown"),
        exercise_content=exercise_content,
        exercise_number=f"{exercise_index + 1} of {len(exercises)}",
        teaching_adjustments=get_teaching_adjustments(level),
    )

    base_prompt = get_prompt_for_level(language, level)
    full_prompt = base_prompt + "\n\n" + system_prompt

    response = await _call_llm(full_prompt, state)
    logger.info(
        "Lesson %s: exercise_ask %d/%d",
        state.get("lesson_id", "?"),
        exercise_index + 1,
        len(exercises),
    )

    return {
        "messages": [response],
        "lesson_phase": "exercise_eval",
        "lesson_ui": _build_lesson_ui(state, "exercise_ask"),
    }


async def _handle_exercise_eval(state: LessonChatState) -> dict[str, Any]:
    """Handle exercise_eval phase: evaluate the user's answer."""
    lesson_data = state["lesson_data"]
    language = state["language"]
    level = state["level"]
    exercise_index = state.get("exercise_index", 0)
    exercise_results = list(state.get("exercise_results", []))

    exercises = _get_exercises(lesson_data)
    exercise_data = exercises[exercise_index]
    exercise_type = exercise_data.get("type", "")

    # Get user's answer from latest message
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    raw_content = user_messages[-1].content if user_messages else ""
    user_answer = str(raw_content).strip()

    # Determine correctness
    is_correct: bool | None = None

    if exercise_type == "multiple_choice":
        options = exercise_data.get("options", [])
        parsed_idx = _parse_mc_answer(user_answer, options)
        if parsed_idx is None:
            # Ambiguous — ask for clarification
            return {
                "messages": [HumanMessage(content=user_answer)],
                "lesson_phase": "exercise_eval",  # Stay in eval
                "lesson_ui": _build_lesson_ui(state, "exercise_eval"),
            }
        is_correct = parsed_idx == exercise_data.get("correct_index")
        correct_answer = options[exercise_data.get("correct_index", 0)]

    elif exercise_type == "fill_blank":
        fill_blank = FillBlankExercise(**exercise_data)
        is_correct = fill_blank.check_answer(user_answer)
        correct_answer = exercise_data.get("correct_answer", "")

    elif exercise_type == "translate":
        translate = TranslateExercise(**exercise_data)
        is_correct = translate.check_answer(user_answer)
        correct_answer = exercise_data.get("correct_translation", "")

    else:
        # Unknown exercise type — mark as correct to avoid blocking
        is_correct = True
        correct_answer = ""

    # Build exercise description for feedback prompt
    exercise_description = (
        exercise_data.get("question", "")
        or exercise_data.get("sentence_template", "")
        or exercise_data.get("source_text", "")
    )

    # Determine feedback context
    is_last_exercise = exercise_index >= len(exercises) - 1
    feedback_context = (
        "This was the last exercise — the lesson is wrapping up."
        if is_last_exercise
        else f"There are {len(exercises) - exercise_index - 1} more exercise(s) after this."
    )

    # Build evaluation prompt
    language_name = _get_language_name(language)
    system_prompt = LESSON_EXERCISE_EVAL_PROMPT.format(
        language_name=language_name,
        level=level,
        is_correct="Yes" if is_correct else "No",
        user_answer=user_answer,
        correct_answer=correct_answer,
        exercise_description=exercise_description,
        feedback_context=feedback_context,
        teaching_adjustments=get_teaching_adjustments(level),
    )

    base_prompt = get_prompt_for_level(language, level)
    full_prompt = base_prompt + "\n\n" + system_prompt

    response = await _call_llm(full_prompt, state)

    # Record result
    exercise_results.append(
        {
            "exercise_id": exercise_data.get("id", f"ex-{exercise_index}"),
            "is_correct": is_correct,
            "user_answer": user_answer,
        }
    )

    # Determine next phase
    new_exercise_index = exercise_index + 1
    next_phase = "complete" if is_last_exercise else "exercise_ask"

    logger.info(
        "Lesson %s: exercise_eval %d/%d correct=%s -> %s",
        state.get("lesson_id", "?"),
        exercise_index + 1,
        len(exercises),
        is_correct,
        next_phase,
    )

    # Build UI with exercise result
    ui = _build_lesson_ui(
        state,
        "exercise_eval",
        exercise_result={
            "is_correct": is_correct,
            "exercise_id": exercise_data.get("id", f"ex-{exercise_index}"),
        },
    )

    return {
        "messages": [response],
        "lesson_phase": next_phase,
        "exercise_index": new_exercise_index,
        "exercise_results": exercise_results,
        "lesson_ui": ui,
    }


async def _handle_complete(state: LessonChatState) -> dict[str, Any]:
    """Handle the complete phase: celebrate and calculate final score."""
    lesson_data = state["lesson_data"]
    language = state["language"]
    level = state["level"]
    exercise_results = state.get("exercise_results", [])

    exercises = _get_exercises(lesson_data)
    total_exercises = len(exercises)
    correct_count = sum(1 for r in exercise_results if r.get("is_correct"))
    score = round(correct_count / total_exercises * 100) if total_exercises > 0 else 100

    # Count vocabulary words in lesson
    ordered_steps = _get_ordered_steps(lesson_data)
    vocab_count = 0
    for step in ordered_steps:
        if step.get("type") == "vocabulary":
            vocab_items = step.get("vocabulary", [])
            if isinstance(vocab_items, list):
                vocab_count += len(vocab_items)

    system_prompt = LESSON_COMPLETE_PROMPT.format(
        language_name=_get_language_name(language),
        level=level,
        lesson_title=lesson_data.get("metadata", {}).get("title", ""),
        score=score,
        total_exercises=total_exercises,
        correct_count=correct_count,
        vocab_count=vocab_count,
        has_next_lesson="true",  # Placeholder — route layer resolves this
    )

    base_prompt = get_prompt_for_level(language, level)
    full_prompt = base_prompt + "\n\n" + system_prompt

    response = await _call_llm(full_prompt, state)
    logger.info(
        "Lesson %s: complete, score=%d%% (%d/%d)",
        state.get("lesson_id", "?"),
        score,
        correct_count,
        total_exercises,
    )

    ui = _build_lesson_ui(
        state,
        "complete",
        score=score,
        vocab_count=vocab_count,
        correct_count=correct_count,
        total_exercises=total_exercises,
    )

    return {
        "messages": [response],
        "lesson_phase": "complete",
        "lesson_score": score,
        "lesson_completed": True,
        "lesson_ui": ui,
    }


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------


async def lesson_respond_node(state: LessonChatState) -> dict[str, Any]:
    """Generate a lesson-aware response based on current phase.

    This is the core node for the conversational lesson delivery graph.
    It dispatches to phase-specific handlers based on the current
    ``lesson_phase`` in state.

    Args:
        state: Current lesson chat state with lesson data and phase tracking.

    Returns:
        Dictionary with updated messages, lesson_phase, and other state fields.
        The add_messages reducer will append messages to existing list.
    """
    phase = state.get("lesson_phase", "intro")

    if phase == "intro":
        return await _handle_intro(state)
    elif phase == "teaching":
        return await _handle_teaching(state)
    elif phase == "exercise_ask":
        return await _handle_exercise_ask(state)
    elif phase == "exercise_eval":
        return await _handle_exercise_eval(state)
    elif phase == "complete":
        return await _handle_complete(state)
    else:
        # Fallback to intro for unknown phases
        logger.warning("Unknown lesson phase '%s', falling back to intro", phase)
        return await _handle_intro(state)
